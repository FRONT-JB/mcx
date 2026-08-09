"""Verify use case — 진입 확인, mechanical 검증 실행, Gate 판정의 조율.

**진입 확인이 모든 일보다 먼저다.** Verify는 Blueprint Gate와 Execute Gate의
``CLEAR``를 재평가한 뒤에만 시작한다 (ADR-0026 §1). 실행 기록이 없는 작업은
여기 도달하지 못한다 — upstream evaluate가 요구하지 않아 §12.3 사고의 통로가
되었던 지점이다.

**증거는 직접 실행에서만 나온다.** Flight Controller의 ``result_summary``는
어느 경로로도 증거가 되지 않는다 (ADR-0028 §1). 이 use case가 승인된
Blueprint의 성공 계약을 읽어 runner에 넘기고, 그 결과만 기록한다.

계약: ``docs/08_VERIFY.md`` §3, §5.1, §8
결정: ``docs/adr/0026-verify-entry-requires-lineage.md``,
``docs/adr/0028-verify-v1-mechanical-contract.md``
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from mission_control.application.blueprint_service import BlueprintNotFoundError
from mission_control.application.brief_service import BriefNotFoundError
from mission_control.application.execute_service import BlueprintNotClearedError
from mission_control.application.ports import (
    BlueprintRepository,
    BriefRepository,
    CheckpointRecorder,
    ExecuteRepository,
    MechanicalRunner,
    SemanticEvaluationRequest,
    SemanticEvaluator,
    VerificationOutputStore,
    VerifyRepository,
)
from mission_control.domain.blueprint.gate import evaluate_blueprint_gate
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.checkpoint import Checkpoint
from mission_control.domain.errors import MissionControlError
from mission_control.domain.execute.gate import evaluate_execute_gate
from mission_control.domain.execute.state import AttemptStatus, ExecuteState
from mission_control.domain.verify.evidence import (
    VERIFY_COMMAND_TIMEOUT_SECONDS,
    CommandExecution,
    VerificationEvidence,
    VerificationRun,
    VerifyState,
    judge_run,
)
from mission_control.domain.verify.gate import (
    VerifyGateDecision,
    evaluate_verify_gate,
    proven_criteria,
)
from mission_control.domain.verify.verdict import (
    CriterionVerdict,
    SemanticAssessment,
    SemanticPolicy,
)


class VerdictMismatchError(MissionControlError):
    """평가자가 요청된 AC가 아닌 다른 key의 verdict를 돌려주었다.

    잘못 귀속된 판정을 받아들이면 한 AC의 판정이 다른 AC의 완료 근거가 된다.
    """

    def __init__(self, *, expected: str, received: str) -> None:
        super().__init__(f"{expected}를 판정하는데 평가자가 {received}의 verdict를 돌려주었다")
        self.expected = expected
        self.received = received


class ExecuteNotClearedError(MissionControlError):
    """Execute Gate가 ``CLEAR``가 아닌데 Verify를 시작하려 했다.

    실행되지 않았거나, 결과를 알 수 없거나, 실행이 실패한 작업 위에서는
    검증이 시작되지 않는다 (ADR-0026 §1).
    """

    def __init__(self, *, mission_id: str, reasons: tuple[str, ...]) -> None:
        joined = "; ".join(reasons)
        super().__init__(f"mission {mission_id}가 Verify 진입 CLEAR가 아니다: {joined}")
        self.mission_id = mission_id
        self.reasons = reasons


@dataclass(frozen=True, slots=True)
class VerifyService:
    """Verify Stage의 application 경계."""

    briefs: BriefRepository
    blueprints: BlueprintRepository
    executes: ExecuteRepository
    repository: VerifyRepository
    runner: MechanicalRunner
    outputs: VerificationOutputStore
    evaluator: SemanticEvaluator
    policy: SemanticPolicy
    #: 입증된 변경을 미션 브랜치에 고정한다 (ADR-0046). 주입되지 않으면
    #: checkpoint를 남기지 않는다 — 테스트와 대체 조립이 git을 요구받지 않는다.
    checkpoints: CheckpointRecorder | None = None

    async def run_mechanical(self, *, mission_id: str) -> VerifyState:
        """성공 계약이 있는 모든 AC를 검증하고 기록된 상태를 반환한다.

        검사 순서는 AC마다 artifacts → 명령이다 (ADR-0028 §3). 성공 계약이
        없는 AC는 run을 만들지 않는다 — 그 부재는 Gate가 판정 불가로
        드러낸다. 저장이 성공한 뒤에만 검증이 기록되었다고 보고한다.
        """
        blueprint, execute_state = await self._cleared_pipeline(mission_id)
        workspace = execute_state.attempts[-1].envelope.workspace
        state = await self._state(mission_id)

        runs: list[VerificationRun] = []
        for criterion in blueprint.acceptance_criteria:
            if not criterion.is_mechanically_verifiable:
                continue

            missing = await self.runner.missing_artifacts(
                workspace=workspace, artifacts=criterion.expected_artifacts
            )
            execution: CommandExecution | None = None
            output_ref: str | None = None
            if not missing and criterion.verify_command is not None:
                execution = await self.runner.run(
                    command=criterion.verify_command,
                    workspace=workspace,
                    timeout_seconds=VERIFY_COMMAND_TIMEOUT_SECONDS,
                )
                output_ref = await self.outputs.preserve(
                    mission_id=mission_id,
                    sequence=state.sequence,
                    ac_key=criterion.key,
                    content=execution.output,
                )
            runs.append(
                judge_run(
                    criterion=criterion,
                    missing_artifacts=missing,
                    execution=execution,
                    output_ref=output_ref,
                )
            )

        evidence = VerificationEvidence(
            mission_id=mission_id,
            blueprint_revision=blueprint.revision,
            execution_attempt_numbers=self._executed_attempt_numbers(
                execute_state, blueprint.revision
            ),
            runs=tuple(runs),
        )
        recorded = state.record(evidence)
        await self.repository.save(recorded)
        return recorded

    async def assess_semantics(self, *, mission_id: str) -> VerifyState:
        """모든 AC의 semantic 판정을 받아 기록된 상태를 반환한다.

        판정은 mechanical 증거 위에서만 내려진다 — 현재 revision의 evidence가
        없으면 도메인이 기록을 거부한다 (``VerdictWithoutEvidenceError``).
        평가자의 verdict는 요청한 AC에 귀속되어야 하며 불일치는 거부한다.

        AC 판정들은 서로 독립이라 **병렬**로 받는다 — upstream은 semantic
        stage를 AC별 ``asyncio.gather``로 돌리고, 하나라도 실패하면 반쪽
        평가를 집계하지 않고 전체를 중단한다
        (``mcp/tools/evaluation_handlers.py:877-955``, ADR-0030 정렬 note).
        gather의 기본 예외 전파가 그 중단 의미론이고, 저장은 전량 성공
        후에만 일어난다.
        """
        blueprint, execute_state = await self._cleared_pipeline(mission_id)
        state = await self._state(mission_id)
        workspace = execute_state.attempts[-1].envelope.workspace

        async def _assess_one(criterion: AcceptanceCriterion) -> CriterionVerdict:
            verdict = await self.evaluator.assess(
                SemanticEvaluationRequest(
                    goal=blueprint.goal,
                    constraints=blueprint.constraints,
                    non_goals=blueprint.non_goals,
                    criterion=criterion,
                    workspace=workspace,
                    mechanical_run=(
                        state.evidence.run_for(criterion.key)
                        if state.evidence is not None
                        else None
                    ),
                )
            )
            if verdict.ac_key != criterion.key:
                raise VerdictMismatchError(expected=criterion.key, received=verdict.ac_key)
            return verdict

        verdicts = list(
            await asyncio.gather(
                *(_assess_one(criterion) for criterion in blueprint.acceptance_criteria)
            )
        )

        assessment = SemanticAssessment(
            blueprint_revision=blueprint.revision,
            policy_version=self.policy.version,
            verdicts=tuple(verdicts),
        )
        recorded = state.record_verdicts(assessment)
        await self.repository.save(recorded)
        return recorded

    async def checkpoint(self, *, mission_id: str) -> Checkpoint | None:
        """이번 라운드에서 증거로 입증된 것을 되돌릴 수 있는 지점으로 고정한다.

        **검증 기록을 바꾸지 않는다** — 커밋이 실패해도 판정은 그대로 남아야
        하므로 저장 경로와 분리했다. 무엇이 통과인가의 판정은 Gate와 **같은
        함수**를 쓴다 (ADR-0046 §2).

        upstream도 checkpoint를 평가자 안이 아니라 평가 **이후**의 별도 단계로
        둔다 (findings §1).
        """
        if self.checkpoints is None:
            return None
        blueprint, execute_state = await self._cleared_pipeline(mission_id)
        state = await self._state(mission_id)
        return self.checkpoints.record(
            execute_state.attempts[-1].envelope.workspace,
            mission_id=mission_id,
            blueprint_revision=blueprint.revision,
            ac_keys=proven_criteria(
                evidence=state.evidence,
                verdicts=state.verdicts,
                blueprint=blueprint,
                policy=self.policy,
            ),
            summary=blueprint.goal,
        )

    async def decide_gate(self, *, mission_id: str) -> VerifyGateDecision:
        """저장된 두 층의 증거로 MISSION COMPLETE 여부를 판정한다.

        진입 조건을 먼저 재확인한다 — Brief·Blueprint·실행 상태가 그 사이
        바뀌었다면 증거의 판정 이전에 진입 자체가 무효다.
        """
        blueprint, _ = await self._cleared_pipeline(mission_id)
        state = await self._state(mission_id)
        return evaluate_verify_gate(
            evidence=state.evidence,
            verdicts=state.verdicts,
            blueprint=blueprint,
            policy=self.policy,
        )

    async def _state(self, mission_id: str) -> VerifyState:
        stored = await self.repository.load(mission_id)
        return stored if stored is not None else VerifyState.start(mission_id=mission_id)

    async def _cleared_pipeline(self, mission_id: str) -> tuple[Blueprint, ExecuteState]:
        """Blueprint Gate와 Execute Gate의 ``CLEAR``를 차례로 재확인한다."""
        blueprint_state = await self.blueprints.load(mission_id)
        if blueprint_state is None:
            raise BlueprintNotFoundError(mission_id)
        brief = await self.briefs.load(mission_id)
        if brief is None:
            raise BriefNotFoundError(mission_id)

        blueprint_decision = evaluate_blueprint_gate(
            state=blueprint_state, brief_revision=brief.revision
        )
        if blueprint_decision.outcome != "CLEAR":
            raise BlueprintNotClearedError(
                mission_id=mission_id, reasons=blueprint_decision.blocking_reasons
            )

        blueprint = blueprint_state.current
        stored = await self.executes.load(mission_id)
        execute_state = stored if stored is not None else ExecuteState.start(mission_id=mission_id)
        execute_decision = evaluate_execute_gate(state=execute_state, blueprint=blueprint)
        if execute_decision.outcome != "CLEAR":
            raise ExecuteNotClearedError(
                mission_id=mission_id, reasons=execute_decision.blocking_reasons
            )
        return blueprint, execute_state

    @staticmethod
    def _executed_attempt_numbers(state: ExecuteState, revision: int) -> tuple[int, ...]:
        """현재 revision에서 실행된 attempt 번호들 — evidence의 lineage."""
        return tuple(
            attempt.number
            for attempt in state.attempts
            if attempt.blueprint_revision == revision
            and attempt.status is AttemptStatus.EXECUTED_UNVERIFIED
        )
