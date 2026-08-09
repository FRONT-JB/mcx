"""Blueprint Gate — Execute로 진행할 수 있는지에 대한 판정.

Brief Gate와 달리 이 판정에 점수 조건이 없다. QA 근거 없는 승인은
:meth:`~mission_control.domain.blueprint.state.BlueprintState.approve`가 생성
자체를 거부하므로, Gate에 도달한 승인은 이미 QA 근거를 담고 있다 (ADR-0021 §6).
Gate가 확인하는 것은 **바인딩**이다 — 승인이 현재 revision을 가리키는가, 그
revision이 여전히 현재의 Brief에서 나온 것인가.

Brief 쪽 확인이 revision 비교로 충분한 이유: Blueprint는 ``CLEAR``된 Brief
revision의 handoff에서만 만들어지고, Brief revision은 내용이 달라질 때만
올라간다. revision이 같으면 내용이 같고, 같은 내용의 Gate 판정은 같다.

계약: ``docs/06_BLUEPRINT.md`` §10
결정: ``docs/adr/0021-blueprint-state-and-revisions.md`` §6
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.brief.gate import GateOutcome
from mission_control.domain.errors import StaleGateDecisionError
from mission_control.domain.stage import Stage


class BlueprintGateBlockingCondition(StrEnum):
    """Execute 진입을 막은 조건."""

    APPROVAL_MISSING = "approval_missing"
    APPROVAL_STALE = "approval_stale"
    BRIEF_REVISION_STALE = "brief_revision_stale"
    #: 확인 수단이 있는 수용 기준이 하나도 없다 (ADR-0043 §3). 이 상태로
    #: 진행하면 mechanical 층이 돌 것이 없어 공허하게 통과하고,
    #: ``MISSION COMPLETE``가 semantic 판정 하나에만 얹힌다.
    NO_VERIFIABLE_CRITERION = "no_verifiable_criterion"


@dataclass(frozen=True, slots=True)
class BlueprintGateBlocker:
    condition: BlueprintGateBlockingCondition
    detail: str


@dataclass(frozen=True, slots=True)
class BlueprintGateDecision:
    """한 Blueprint revision에 대한 Gate 판정과 그 근거.

    ``brief_revision``은 판정이 대조한 Brief revision이다. 판정 이후 Brief가
    바뀌었는지를 나중에 확인할 수 있어야 하므로 판정에 함께 남긴다.
    """

    outcome: GateOutcome
    revision: int
    brief_revision: int
    gate_blockers: tuple[BlueprintGateBlocker, ...]
    next_destination: Stage | None
    #: 확인 수단이 있는 수용 기준의 수와 전체 수 (ADR-0043 §4). 부분 커버리지는
    #: **막지 않는다** — 임계값에 근거가 없다. 대신 세어서 드러내, 사용자가
    #: 모르고 지나치지 않게 한다.
    verifiable_criteria: int = 0
    total_criteria: int = 0

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        """사람이 읽을 수 있는 이유 목록. 표시용이며 판정 근거는 원본 blocker다."""
        return tuple(blocker.detail for blocker in self.gate_blockers)


def evaluate_blueprint_gate(*, state: BlueprintState, brief_revision: int) -> BlueprintGateDecision:
    """Blueprint가 Execute로 진행할 수 있는지 판정한다.

    ``brief_revision``은 호출자가 저장소에서 읽은 **현재** Brief revision이다.
    Blueprint의 현재 revision이 다른 Brief revision에서 나왔다면 그 사이 Brief가
    바뀐 것이므로, 승인 여부와 무관하게 재평가가 필요하다 (Test Matrix
    "stale Brief revision — 재평가 요구").

    이 함수는 순수 함수다. 상태를 바꾸지 않으며 저장도 하지 않는다. 저장에
    실패했다면 ``CLEAR``를 기록해서는 안 된다는 판단은 application 계층의
    몫이다.
    """
    gate_blockers: list[BlueprintGateBlocker] = []

    if state.current.brief_revision != brief_revision:
        gate_blockers.append(
            BlueprintGateBlocker(
                condition=BlueprintGateBlockingCondition.BRIEF_REVISION_STALE,
                detail=(
                    f"Blueprint revision {state.revision}은 Brief revision "
                    f"{state.current.brief_revision}에서 나왔는데 현재 Brief revision은 "
                    f"{brief_revision}이다"
                ),
            )
        )

    if state.approval is None:
        gate_blockers.append(
            BlueprintGateBlocker(
                condition=BlueprintGateBlockingCondition.APPROVAL_MISSING,
                detail="현재 Blueprint revision에 대한 사용자 승인이 없다",
            )
        )
    elif not state.has_current_approval:
        gate_blockers.append(
            BlueprintGateBlocker(
                condition=BlueprintGateBlockingCondition.APPROVAL_STALE,
                detail=(
                    f"승인은 revision {state.approval.revision}을 대상으로 하는데 "
                    f"현재 revision은 {state.revision}이다"
                ),
            )
        )

    criteria = state.current.acceptance_criteria
    verifiable = sum(1 for item in criteria if item.is_mechanically_verifiable)
    if criteria and verifiable == 0:
        gate_blockers.append(
            BlueprintGateBlocker(
                condition=BlueprintGateBlockingCondition.NO_VERIFIABLE_CRITERION,
                detail=(
                    f"수용 기준 {len(criteria)}개 중 어느 것도 기계적 확인 수단을 갖고 있지 "
                    "않다 — 완료를 증거로 선언할 수 없다"
                ),
            )
        )

    cleared = not gate_blockers
    return BlueprintGateDecision(
        outcome="CLEAR" if cleared else "HOLD",
        revision=state.revision,
        brief_revision=brief_revision,
        gate_blockers=tuple(gate_blockers),
        next_destination=Stage.EXECUTE if cleared else None,
        verifiable_criteria=verifiable,
        total_criteria=len(criteria),
    )


def next_stage_after_blueprint(*, state: BlueprintState, decision: BlueprintGateDecision) -> Stage:
    """Gate decision을 실제 Stage 전이로 옮긴다.

    Blueprint에서 나가는 정상 경로는 ``CLEAR`` 하나뿐이고 목적지는 Execute뿐이다
    (``docs/02_MISSION_LIFECYCLE.md`` §14). Blueprint → Verify와
    Blueprint → Recover는 이 함수가 반환할 수 없으므로 금지가 검사 항목이 아니라
    타입으로 성립한다.

    판정과 전이 사이에 내용이 바뀌었으면 거부한다. Gate가 본 적 없는 revision을
    승인된 것으로 넘기지 않기 위해서다.
    """
    if decision.revision != state.revision:
        raise StaleGateDecisionError(
            mission_id=state.mission_id,
            decision_revision=decision.revision,
            current_revision=state.revision,
        )
    return Stage.EXECUTE if decision.outcome == "CLEAR" else Stage.BLUEPRINT
