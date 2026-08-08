"""Execute use case — 진입 확인, dispatch, 결과 기록, Gate 판정의 조율.

:class:`~mission_control.application.brief_service.BriefService`와 같은 규칙을
따른다 — 도메인 규칙은 여기 두지 않고, 저장이 성공한 뒤에만 전이가 일어났다고
보고한다.

이 계층이 추가로 지키는 순서가 둘 있다.

**진입 확인이 모든 일보다 먼저다.** 작업을 만들 수 있는 것은 이 use case
하나이고, 그 진입은 Blueprint Gate의 ``CLEAR``다 (ADR-0023 §1). Gate가
``HOLD``면 dispatch도 Gate 판정도 시작하지 않는다.

**지속이 dispatch보다 먼저다.** attempt를 저장한 뒤에 Runtime에 위임한다
(ADR-0024 §4). 반대로 하면 결과를 받기 전에 죽었을 때 시도했다는 사실 자체가
사라지고, upstream 관측(§12.3)의 "아무도 모르는 작업"이 우리 쪽에서 재현된다.

계약: ``docs/07_EXECUTE.md`` §8
결정: ``docs/adr/0023-execute-entry-and-provenance.md``,
``docs/adr/0024-execute-v1-execution-model.md``
"""

from __future__ import annotations

from dataclasses import dataclass

from mission_control.application.blueprint_service import BlueprintNotFoundError
from mission_control.application.brief_service import BriefNotFoundError
from mission_control.application.ports import (
    BlueprintRepository,
    BriefRepository,
    ExecuteRepository,
    ExecutionRequest,
    ExecutionRuntime,
)
from mission_control.domain.blueprint.gate import evaluate_blueprint_gate
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.errors import MissionControlError
from mission_control.domain.execute.gate import ExecuteGateDecision, evaluate_execute_gate
from mission_control.domain.execute.plan import next_criterion
from mission_control.domain.execute.state import CapabilityEnvelope, ExecuteState


class BlueprintNotClearedError(MissionControlError):
    """Execute 진입 Gate가 ``CLEAR``가 아닌데 실행하려 했다.

    승인된 Blueprint 없이 Execute하지 않는다 (ADR-0002, ADR-0023 §1). 승인이
    없거나, 승인 뒤 내용이 바뀌었거나, Brief가 그 사이 바뀐 경우가 전부 여기서
    막힌다.
    """

    def __init__(self, *, mission_id: str, reasons: tuple[str, ...]) -> None:
        joined = "; ".join(reasons)
        super().__init__(f"blueprint for mission {mission_id} is not cleared for Execute: {joined}")
        self.mission_id = mission_id
        self.reasons = reasons


class AllCriteriaExecutedError(MissionControlError):
    """모든 AC가 이미 실행된 상태에서 dispatch를 요청했다.

    남은 일은 실행이 아니라 Gate 판정과 Verify다. 조용히 아무것도 하지 않으면
    호출자는 새 작업이 시작됐다고 믿는다.
    """

    def __init__(self, *, mission_id: str, blueprint_revision: int) -> None:
        super().__init__(
            f"every criterion of blueprint revision {blueprint_revision} for mission "
            f"{mission_id} is already executed; decide the gate instead"
        )
        self.mission_id = mission_id
        self.blueprint_revision = blueprint_revision


@dataclass(frozen=True, slots=True)
class ExecuteService:
    """Execute Stage의 application 경계."""

    briefs: BriefRepository
    blueprints: BlueprintRepository
    repository: ExecuteRepository
    runtime: ExecutionRuntime
    #: 이 Mission Control 인스턴스가 dispatch에 부여하는 실행 경계. workspace
    #: 격리 방식은 미정이므로(Execute Guide §17) v1은 구성으로 주입한다.
    envelope: CapabilityEnvelope

    async def dispatch_next(self, *, mission_id: str) -> ExecuteState:
        """다음 AC 하나를 실행하고 결과까지 기록한 상태를 반환한다.

        Runtime이 예외를 올리면 그것은 실행 실패다 — attempt는 이미 저장돼
        있으므로 ``EXECUTION_FAILED``로 기록한다. 삼키는 것이 아니라 상태로
        옮기는 것이다. 결과 저장 자체가 실패하면 attempt는 ``DISPATCHED``로
        남고, 그 상태가 곧 "결과 불명"이다 (ADR-0024 §4).
        """
        blueprint = (await self._cleared_blueprint(mission_id)).current
        state = await self._state(mission_id)

        criterion = next_criterion(blueprint=blueprint, state=state)
        if criterion is None:
            raise AllCriteriaExecutedError(
                mission_id=mission_id, blueprint_revision=blueprint.revision
            )

        dispatched = state.dispatch(
            execution_id=f"exec-{mission_id}-{len(state.attempts) + 1:04d}",
            runtime_backend=self.runtime.backend,
            blueprint_revision=blueprint.revision,
            ac_key=criterion.key,
            envelope=self.envelope,
        )
        await self.repository.save(dispatched)

        try:
            outcome = await self.runtime.execute(self._request(blueprint, criterion))
        except Exception as error:
            failed = dispatched.record_result(
                succeeded=False, error=f"runtime raised before returning an outcome: {error}"
            )
            await self.repository.save(failed)
            return failed

        resolved = dispatched.record_result(
            succeeded=outcome.succeeded,
            native_session_id=outcome.native_session_id,
            result_summary=outcome.result_summary,
            error=outcome.error,
        )
        await self.repository.save(resolved)
        return resolved

    async def decide_gate(self, *, mission_id: str) -> ExecuteGateDecision:
        """저장된 상태로 Verify 진입 Gate를 판정한다.

        진입 조건(Blueprint ``CLEAR``)을 먼저 확인한다 — Brief나 Blueprint가
        그 사이 바뀌었다면 실행 결과의 판정 이전에 진입 자체가 무효다.
        """
        blueprint = (await self._cleared_blueprint(mission_id)).current
        state = await self._state(mission_id)
        return evaluate_execute_gate(state=state, blueprint=blueprint)

    async def _state(self, mission_id: str) -> ExecuteState:
        stored = await self.repository.load(mission_id)
        return stored if stored is not None else ExecuteState.start(mission_id=mission_id)

    async def _cleared_blueprint(self, mission_id: str) -> BlueprintState:
        """Execute 진입 Gate를 확인하고 승인된 Blueprint 상태를 반환한다."""
        blueprint_state = await self.blueprints.load(mission_id)
        if blueprint_state is None:
            raise BlueprintNotFoundError(mission_id)
        brief = await self.briefs.load(mission_id)
        if brief is None:
            raise BriefNotFoundError(mission_id)

        decision = evaluate_blueprint_gate(state=blueprint_state, brief_revision=brief.revision)
        if decision.outcome != "CLEAR":
            raise BlueprintNotClearedError(mission_id=mission_id, reasons=decision.blocking_reasons)
        return blueprint_state

    def _request(self, blueprint: Blueprint, criterion: AcceptanceCriterion) -> ExecutionRequest:
        """Runtime에 전달할 bounded 입력을 구성한다.

        Blueprint의 방향 필드와 대상 AC 하나만 담는다. 다른 AC의 내용은
        전달하지 않는다 — 실행 범위는 이 AC이고, 전체를 주면 범위 밖 작업을
        유도한다.
        """
        return ExecutionRequest(
            goal=blueprint.goal,
            constraints=blueprint.constraints,
            non_goals=blueprint.non_goals,
            criterion=criterion,
            workspace=self.envelope.workspace,
            allowed_tools=self.envelope.allowed_tools,
        )
