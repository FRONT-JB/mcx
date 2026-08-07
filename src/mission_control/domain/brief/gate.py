"""Brief Gate — 다음 Stage로 진행할 수 있는지에 대한 정책 판정.

Gate는 boolean 성공 플래그보다 풍부한 결정이다. ``HOLD``는 실패 선언이 아니라
“현재 조건으로는 진행 불가”라는 판정이며, 무엇이 부족한지와 다음에 무엇을 해야
하는지를 함께 제시해야 한다.

이 모듈이 강제하는 두 방향의 불충분성이 있다.

**점수만으로는 부족하다.** clarity 조건을 모두 만족해도 사용자 승인이 없거나
승격할 수 없는 요구사항 후보가 남아 있으면 ``HOLD``다. 점수는 "얼마나 명확해
보이는가"를 측정할 뿐 아직 아무도 답하지 않은 질문이 있다는 사실을 대신하지
못한다. 후보 판정은 모델을 부르지 않는 결정적 정책이므로 점수와 독립적으로
성립한다 (:func:`~mission_control.domain.brief.requirement.evaluate_promotion`).

**승인만으로도 부족하다.** 사용자가 승인해도 검증할 수 없는 성공 조건이 남아
있으면 ``HOLD``다. 승인은 필요조건이지 만능 override가 아니다. 이것이 없으면
"일단 진행해 주세요"가 모든 gap을 통과시키는 열쇠가 된다.

판정 이유는 요약하지 않고 원래 조건 그대로 전달한다. 사용자가 무엇을 해결해야
하는지 알 수 있어야 하고, 나중에 이 결정이 왜 내려졌는지 재구성할 수 있어야
한다.

계약: ``docs/05_BRIEF.md`` §11.5, §13
결정: ``docs/adr/0009-brief-completion-gate-policy.md``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from mission_control.domain.brief.clarity import ClarityPolicy, CompletionBlocker
from mission_control.domain.brief.state import BriefState
from mission_control.domain.errors import StaleGateDecisionError
from mission_control.domain.stage import Stage

#: Gate 판정 결과. ``NO-GO``는 사용하지 않는다 (``docs/00_MISSION_CONTROL.md`` §5).
GateOutcome = Literal["CLEAR", "HOLD"]


class GateBlockingCondition(StrEnum):
    """clarity 점수 외의 이유로 진행을 막은 조건."""

    APPROVAL_MISSING = "approval_missing"
    APPROVAL_STALE = "approval_stale"
    UNPROMOTABLE_REQUIREMENT = "unpromotable_requirement"


@dataclass(frozen=True, slots=True)
class GateBlocker:
    condition: GateBlockingCondition
    detail: str


@dataclass(frozen=True, slots=True)
class BriefGateDecision:
    """한 revision에 대한 Gate 판정과 그 근거.

    ``clarity_blockers``와 ``gate_blockers``를 분리해 담는다. 전자는 "더 물어봐야
    한다"를, 후자는 "사람이 무언가를 해야 한다"를 뜻하므로 다음 행동이 다르다.
    """

    outcome: GateOutcome
    revision: int
    policy_version: str
    clarity_blockers: tuple[CompletionBlocker, ...]
    gate_blockers: tuple[GateBlocker, ...]
    next_destination: Stage | None

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        """사람이 읽을 수 있는 이유 목록. 표시용이며 판정 근거는 원본 blocker다."""
        return (
            *(blocker.detail for blocker in self.clarity_blockers),
            *(blocker.detail for blocker in self.gate_blockers),
        )


def evaluate_brief_gate(*, state: BriefState, policy: ClarityPolicy) -> BriefGateDecision:
    """Brief가 Blueprint로 진행할 수 있는지 판정한다.

    Gate는 질문 루프의 종료 판정(:meth:`ClarityPolicy.assess_completion`)을
    입력으로 사용하되 그것과 동일하지 않다. 종료 후보 도달은 사용자에게 승인을
    물어볼 자격이고, ``CLEAR``는 승인을 받은 뒤에야 가능하다.

    평가 결과와 stability signal을 인자로 받지 않고 상태에서 읽는다. 따로 받으면
    호출자가 지난 revision의 평가를 현재 상태에 붙여 판정할 수 있고, 그것이
    §8.1 규칙 7이 막으려는 상황이다. 상태에 함께 저장되어 있으므로 material
    변경이 둘을 동시에 무효화한다.

    이 함수는 순수 함수다. 상태를 바꾸지 않으며 저장도 하지 않는다. persistence
    성공 여부는 호출하는 application 계층이 판단한다 — 저장에 실패했다면
    ``CLEAR``를 기록해서는 안 된다 (``docs/05_BRIEF.md`` §9.2).
    """
    candidacy = policy.assess_completion(
        assessment=state.assessment,
        answered_rounds=len(state.answered_rounds),
        stability_signal=state.stability_signal,
    )

    gate_blockers: list[GateBlocker] = []

    if state.approval is None:
        gate_blockers.append(
            GateBlocker(
                condition=GateBlockingCondition.APPROVAL_MISSING,
                detail="user approval for the current Brief revision is missing",
            )
        )
    elif not state.has_current_approval:
        gate_blockers.append(
            GateBlocker(
                condition=GateBlockingCondition.APPROVAL_STALE,
                detail=(
                    f"approval targets revision {state.approval.revision} "
                    f"but the current revision is {state.revision}"
                ),
            )
        )

    for decision in state.promotion.blockers:
        gate_blockers.append(
            GateBlocker(
                condition=GateBlockingCondition.UNPROMOTABLE_REQUIREMENT,
                detail=(
                    f"{decision.reason.value} — "
                    f"[{decision.candidate.section.value}] {decision.candidate.text}"
                ),
            )
        )

    cleared = candidacy.is_candidate and not gate_blockers
    return BriefGateDecision(
        outcome="CLEAR" if cleared else "HOLD",
        revision=state.revision,
        policy_version=policy.version,
        clarity_blockers=candidacy.blockers,
        gate_blockers=tuple(gate_blockers),
        next_destination=Stage.BLUEPRINT if cleared else None,
    )


def next_stage_after_brief(*, state: BriefState, decision: BriefGateDecision) -> Stage:
    """Gate decision을 실제 Stage 전이로 옮긴다.

    Brief에서 나가는 정상 경로는 ``CLEAR`` 하나뿐이고 목적지는 Blueprint뿐이다.
    ``HOLD``는 Stage exit가 아니라 Brief에 머무르는 판정이다
    (``docs/05_BRIEF.md`` §9.2, ``docs/02_MISSION_LIFECYCLE.md`` §9).

    Brief → Execute와 Brief → Verify는 금지 전이다 (Lifecycle §9.1). 이 함수는
    그 두 값을 반환할 수 없으므로 금지가 검사 항목이 아니라 타입으로 성립한다.

    판정과 전이 사이에 내용이 바뀌었으면 거부한다. Gate가 본 적 없는 revision을
    승인된 것으로 넘기지 않기 위해서다.
    """
    if decision.revision != state.revision:
        raise StaleGateDecisionError(
            mission_id=state.mission_id,
            decision_revision=decision.revision,
            current_revision=state.revision,
        )
    return Stage.BLUEPRINT if decision.outcome == "CLEAR" else Stage.BRIEF
