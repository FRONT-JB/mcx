"""Recover Gate — 남은 실패가 없으면 Clear for Verify.

계약: docs/09_RECOVER.md §11 / docs/adr/0031 §6
"""

from mission_control.domain.recover.gate import (
    RecoverGateBlockingCondition,
    evaluate_recover_gate,
)
from mission_control.domain.recover.packet import (
    FailureClassification,
    FailurePacket,
    FailureSource,
    RecoverPolicy,
)
from mission_control.domain.stage import Stage

POLICY = RecoverPolicy.recover_v1()


def _packet(
    *,
    source: FailureSource = FailureSource.EXECUTION_FAILED,
    classification: FailureClassification = FailureClassification.UNCLASSIFIED,
    retries_used: int = 0,
) -> FailurePacket:
    return FailurePacket(
        mission_id="m-1",
        blueprint_revision=1,
        ac_key="ac_a",
        source=source,
        classification=classification,
        error_excerpt="boom",
        retries_used=retries_used,
    )


def _conditions(*packets: FailurePacket):
    decision = evaluate_recover_gate(packets=packets, blueprint_revision=1, policy=POLICY)
    return decision, tuple(item.condition for item in decision.gate_blockers)


class TestClear:
    def test_no_packets_clear_for_verify(self) -> None:
        decision, _ = _conditions()
        assert decision.outcome == "CLEAR"
        assert decision.next_destination is Stage.VERIFY


class TestHold:
    def test_a_retryable_failure_awaits_its_correction(self) -> None:
        decision, conditions = _conditions(_packet())
        assert decision.outcome == "HOLD"
        assert conditions == (RecoverGateBlockingCondition.CORRECTION_PENDING,)

    def test_an_exhausted_budget_needs_a_user(self) -> None:
        _, conditions = _conditions(_packet(retries_used=2))
        assert conditions == (RecoverGateBlockingCondition.RETRY_BUDGET_EXHAUSTED,)

    def test_blocked_wins_over_the_budget(self) -> None:
        """권한 문제는 예산이 남아 있어도 재시도가 답이 아니다."""
        _, conditions = _conditions(
            _packet(classification=FailureClassification.BLOCKED, retries_used=2)
        )
        assert conditions == (RecoverGateBlockingCondition.BLOCKED_ON_PRECONDITION,)

    def test_a_stall_is_terminal_for_retries(self) -> None:
        _, conditions = _conditions(_packet(classification=FailureClassification.STALL))
        assert conditions == (RecoverGateBlockingCondition.STALLED,)

    def test_escalation_pending_needs_a_user_decision(self) -> None:
        _, conditions = _conditions(_packet(source=FailureSource.ESCALATION_PENDING))
        assert conditions == (RecoverGateBlockingCondition.USER_DECISION_REQUIRED,)
