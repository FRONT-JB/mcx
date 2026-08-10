"""Recover use case — 실패 분석, 교정 재시도, 재검증 준비의 조율.

Recover는 실패의 **판단**을 소유하고, 교정의 **실행**은 소유하지 않는다 —
새 attempt를 만드는 것은 여전히 :class:`ExecuteService` 하나다 (ADR-0023 §1).
이 use case는 저장된 기록에서 실패 packet을 파생하고, 재시도가 의미 있는
실패에만 실패 증거를 실어 ExecuteService의 교정 진입점을 호출한다.

진입 근거는 다른 Stage와 같은 배치다 — Execute Gate 또는 Verify Gate의
``HOLD``가 있어야 Recover가 시작된다. 둘 다 ``CLEAR``면 회복할 것이 없다
(ADR-0031 §6).

계약: ``docs/09_RECOVER.md`` §5, §6, §8, §11
결정: ``docs/adr/0031-recover-v1-failure-and-retry-contract.md``
"""

from __future__ import annotations

from dataclasses import dataclass

from mission_control.application.blueprint_service import BlueprintNotFoundError
from mission_control.application.brief_service import BriefNotFoundError
from mission_control.application.execute_service import (
    BlueprintNotClearedError,
    ExecuteService,
)
from mission_control.application.ports import (
    BlueprintRepository,
    BriefRepository,
    ExecuteRepository,
    VerifyRepository,
    WorkspaceRollback,
)
from mission_control.domain.blueprint.gate import evaluate_blueprint_gate
from mission_control.domain.blueprint.spec import Blueprint
from mission_control.domain.checkpoint import Rollback
from mission_control.domain.errors import MissionControlError
from mission_control.domain.execute.gate import evaluate_execute_gate
from mission_control.domain.execute.state import ExecuteState
from mission_control.domain.recover.gate import RecoverGateDecision, evaluate_recover_gate
from mission_control.domain.recover.packet import (
    FailurePacket,
    PreviousFailure,
    RecoverPolicy,
    derive_failure_packets,
)
from mission_control.domain.verify.evidence import VerifyState
from mission_control.domain.verify.gate import evaluate_verify_gate
from mission_control.domain.verify.verdict import SemanticPolicy


class NothingToRecoverError(MissionControlError):
    """Execute와 Verify Gate가 모두 ``CLEAR``인데 Recover를 시작하려 했다.

    회복은 실패 근거 위에서만 시작된다 — 근거 없는 회복은 범위 밖 작업의
    문이 된다.
    """

    def __init__(self, *, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}에 실패한 Gate가 없다; 교정할 것이 없다")
        self.mission_id = mission_id


class NoRetryableFailureError(MissionControlError):
    """교정 재시도가 의미 있는 실패가 없는데 dispatch를 요청했다.

    남은 실패가 전부 사용자 결정(BLOCKED·STALL·예산 소진·escalation)이라면
    재시도는 낭비이거나 우회다. 조용히 아무것도 하지 않으면 호출자는 교정이
    시작됐다고 믿는다.
    """

    def __init__(self, *, mission_id: str, reasons: tuple[str, ...]) -> None:
        joined = "; ".join(reasons) if reasons else "no failure packets remain"
        super().__init__(f"mission {mission_id}에 재시도할 수 있는 실패가 없다: {joined}")
        self.mission_id = mission_id
        self.reasons = reasons


@dataclass(frozen=True, slots=True)
class RecoverService:
    """Recover Stage의 application 경계."""

    briefs: BriefRepository
    blueprints: BlueprintRepository
    executes: ExecuteRepository
    verifies: VerifyRepository
    #: 교정의 실행 경로 — 작업 생성은 여전히 Execute use case 하나다.
    execute: ExecuteService
    semantic_policy: SemanticPolicy
    policy: RecoverPolicy
    #: 재투입 전에 잔해를 지우는 수단 (ADR-0047). 주입되지 않으면 되돌리지
    #: 않는다 — 테스트와 대체 조립이 git을 요구받지 않는다.
    rollback: WorkspaceRollback | None = None

    async def plan(self, *, mission_id: str) -> tuple[FailurePacket, ...]:
        """저장된 기록에서 실패 packet들을 파생한다. 읽기 전용이다."""
        blueprint, execute_state, verify_state = await self._entered(mission_id)
        return derive_failure_packets(
            blueprint=blueprint,
            execute_state=execute_state,
            verify_state=verify_state,
            semantic_policy=self.semantic_policy,
            policy=self.policy,
        )

    async def dispatch_correction(self, *, mission_id: str) -> ExecuteState:
        """재시도가 의미 있는 첫 실패에 교정을 실행한다.

        재시도 요청에는 실패 증거가 실리고, 예산의 마지막 시도에는 접근 전환
        신호가 붙는다 (ADR-0031 §5). 재시도가 답이 아닌 실패(BLOCKED·STALL·
        예산 소진·escalation)만 남았으면 거부한다.
        """
        packets = await self.plan(mission_id=mission_id)
        candidate = next((packet for packet in packets if packet.retryable(self.policy)), None)
        if candidate is None:
            decision = evaluate_recover_gate(
                packets=packets,
                blueprint_revision=packets[0].blueprint_revision if packets else 0,
                policy=self.policy,
            )
            raise NoRetryableFailureError(mission_id=mission_id, reasons=decision.blocking_reasons)

        return await self.execute.dispatch_correction(
            mission_id=mission_id,
            ac_key=candidate.ac_key,
            previous_failure=PreviousFailure(
                source=candidate.source,
                classification=candidate.classification,
                error_excerpt=candidate.error_excerpt,
                change_approach=candidate.retries_used + 1 >= self.policy.retry_budget,
            ),
        )

    def rewind(self, *, mission_id: str) -> Rollback | None:
        """실패한 시도의 잔해를 지우고 마지막 입증 지점으로 되돌린다 (ADR-0047).

        **``dispatch_correction`` 앞에 부른다.** 잔해 위에서 재시도하면 다음
        worker가 반쯤 만들어진 것을 물려받고, 그것이 실패의 원인인지 이전 시도의
        찌꺼기인지 구분할 수 없게 된다.

        순서를 강제하는 자리는 호출자(조율 계층)다 — upstream도 되돌리기를
        Core가 아니라 루프 스크립트가 부른다 (findings §2).
        """
        if self.rollback is None:
            return None
        return self.rollback.to_last_proven(self.execute.envelope.workspace, mission_id=mission_id)

    async def decide_gate(self, *, mission_id: str) -> RecoverGateDecision:
        """남은 실패들로 재검증 준비 여부를 판정한다."""
        blueprint, execute_state, verify_state = await self._entered(mission_id)
        packets = derive_failure_packets(
            blueprint=blueprint,
            execute_state=execute_state,
            verify_state=verify_state,
            semantic_policy=self.semantic_policy,
            policy=self.policy,
        )
        return evaluate_recover_gate(
            packets=packets, blueprint_revision=blueprint.revision, policy=self.policy
        )

    async def _entered(self, mission_id: str) -> tuple[Blueprint, ExecuteState, VerifyState]:
        """진입을 확인한다 — Blueprint는 유효해야 하고, 어딘가는 실패여야 한다."""
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

        stored_execute = await self.executes.load(mission_id)
        execute_state = (
            stored_execute
            if stored_execute is not None
            else ExecuteState.start(mission_id=mission_id)
        )
        stored_verify = await self.verifies.load(mission_id)
        verify_state = (
            stored_verify if stored_verify is not None else VerifyState.start(mission_id=mission_id)
        )

        execute_decision = evaluate_execute_gate(state=execute_state, blueprint=blueprint)
        verify_decision = evaluate_verify_gate(
            evidence=verify_state.evidence,
            verdicts=verify_state.verdicts,
            blueprint=blueprint,
            policy=self.semantic_policy,
        )
        if execute_decision.outcome == "CLEAR" and verify_decision.outcome == "CLEAR":
            raise NothingToRecoverError(mission_id=mission_id)
        return blueprint, execute_state, verify_state
