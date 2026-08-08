"""Recover Gate — 교정이 재검증할 준비가 되었는지의 판정.

Recover의 ``CLEAR``는 완료가 아니다 — "Recover 관점에서 막을 것이 없고,
남은 판정은 Verify의 것"이라는 뜻이며 목적지는 항상 Verify다. MISSION
COMPLETE는 여전히 Verify Gate만 선언한다 (ADR-0031 §6).

계약: ``docs/09_RECOVER.md`` §11
결정: ``docs/adr/0031-recover-v1-failure-and-retry-contract.md``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mission_control.domain.brief.gate import GateOutcome
from mission_control.domain.recover.packet import (
    FailureClassification,
    FailurePacket,
    FailureSource,
    RecoverPolicy,
)
from mission_control.domain.stage import Stage


class RecoverGateBlockingCondition(StrEnum):
    """Verify 재검증으로의 진행을 막은 조건."""

    CORRECTION_PENDING = "correction_pending"
    RETRY_BUDGET_EXHAUSTED = "retry_budget_exhausted"
    BLOCKED_ON_PRECONDITION = "blocked_on_precondition"
    STALLED = "stalled"
    USER_DECISION_REQUIRED = "user_decision_required"


@dataclass(frozen=True, slots=True)
class RecoverGateBlocker:
    condition: RecoverGateBlockingCondition
    detail: str


@dataclass(frozen=True, slots=True)
class RecoverGateDecision:
    """실패 packet들에 대한 Recover Gate 판정과 그 근거."""

    outcome: GateOutcome
    blueprint_revision: int
    gate_blockers: tuple[RecoverGateBlocker, ...]
    next_destination: Stage | None

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        """사람이 읽을 수 있는 이유 목록. 표시용이며 판정 근거는 원본 blocker다."""
        return tuple(blocker.detail for blocker in self.gate_blockers)


def _blocker_for(packet: FailurePacket, policy: RecoverPolicy) -> RecoverGateBlocker:
    """packet의 상태에서 막는 조건을 결정적으로 파생한다.

    분류(BLOCKED·STALL)와 escalation 대기가 예산보다 먼저다 — 그런 실패는
    예산이 남아 있어도 재시도가 답이 아니기 때문이다.
    """
    if packet.classification is FailureClassification.BLOCKED:
        return RecoverGateBlocker(
            condition=RecoverGateBlockingCondition.BLOCKED_ON_PRECONDITION,
            detail=(
                f"criterion {packet.ac_key}: hard precondition — needs a user "
                f"decision, not a retry: {packet.error_excerpt}"
            ),
        )
    if packet.classification is FailureClassification.STALL:
        return RecoverGateBlocker(
            condition=RecoverGateBlockingCondition.STALLED,
            detail=(
                f"criterion {packet.ac_key}: the same error repeated "
                f"{policy.stall_threshold} times; retrying is pointless"
            ),
        )
    if packet.source is FailureSource.ESCALATION_PENDING:
        return RecoverGateBlocker(
            condition=RecoverGateBlockingCondition.USER_DECISION_REQUIRED,
            detail=(
                f"criterion {packet.ac_key}: verdict uncertainty needs escalation; "
                "v1 has no consensus — a user decision is required"
            ),
        )
    if packet.budget_exhausted(policy):
        return RecoverGateBlocker(
            condition=RecoverGateBlockingCondition.RETRY_BUDGET_EXHAUSTED,
            detail=(
                f"criterion {packet.ac_key}: {packet.retries_used} corrective retries "
                f"used of {policy.retry_budget}; a user decision is required"
            ),
        )
    return RecoverGateBlocker(
        condition=RecoverGateBlockingCondition.CORRECTION_PENDING,
        detail=(
            f"criterion {packet.ac_key}: {packet.source} awaits a corrective retry "
            f"({packet.retries_used}/{policy.retry_budget} used)"
        ),
    )


def evaluate_recover_gate(
    *,
    packets: tuple[FailurePacket, ...],
    blueprint_revision: int,
    policy: RecoverPolicy,
) -> RecoverGateDecision:
    """남은 실패가 없으면 ``CLEAR — Clear for Verify``다.

    packet이 없다는 것은 둘 중 하나다 — 교정이 재실행되어 재검증만 남았거나,
    애초에 Recover가 다룰 실패가 아니었다(판정 미완 등 Verify의 일). 어느
    쪽이든 다음은 Verify다.
    """
    gate_blockers = tuple(_blocker_for(packet, policy) for packet in packets)
    cleared = not gate_blockers
    return RecoverGateDecision(
        outcome="CLEAR" if cleared else "HOLD",
        blueprint_revision=blueprint_revision,
        gate_blockers=gate_blockers,
        next_destination=Stage.VERIFY if cleared else None,
    )
