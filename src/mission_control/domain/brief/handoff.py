"""Brief handoff — Blueprint가 읽는 Stage 경계 산출물.

Blueprint가 대화 전체를 다시 해석하지 않아도 되게 하는 것이 목적이다
(``docs/05_BRIEF.md`` §9). 대화를 요약하는 것이 아니라 **이미 승격 판정을 통과한
것만** 칸별로 모은다.

handoff는 저장되는 상태가 아니라 **파생 투영**이다. :class:`BriefState`에서
순수 함수로 만들어지며 저장소에 따로 기록되지 않는다. 저장하면 상태와 handoff가
어긋날 수 있고, 어느 쪽이 진실인지 판정할 근거가 생기지 않는다.

두 채널을 함께 제공한다 (§9.1). ``observation`` 답변의 본문은 요구사항 도출
입력에서 빠지고 관찰 사실 채널에만 남는다. 이 투영이 없으면 "현재 코드가 3회
재시도한다"는 관찰이 Blueprint에서 "3회 재시도해야 한다"로 바뀐다.

계약: ``docs/05_BRIEF.md`` §9, §9.1, §9.2
결정: ``docs/adr/0016-brief-handoff-projection.md``
"""

from __future__ import annotations

from dataclasses import dataclass

from mission_control.domain.brief.clarity import ClarityAssessment
from mission_control.domain.brief.gate import BriefGateDecision
from mission_control.domain.brief.provenance import (
    BriefRound,
    RequirementInputRound,
    observed_facts,
    project_requirement_input,
)
from mission_control.domain.brief.requirement import (
    PromotionDecision,
    PromotionDisposition,
    RequirementSection,
)
from mission_control.domain.brief.state import BriefApproval, BriefState
from mission_control.domain.errors import MissionControlError


class HandoffNotClearedError(MissionControlError):
    """``CLEAR``되지 않은 Brief에서 handoff를 만들려 했다.

    Brief에서의 정상 exit는 저장된 ``CLEAR`` 하나뿐이다 (``docs/05_BRIEF.md``
    §9.2). handoff가 그 판정 없이 만들어지면 다음 Stage는 승인되지 않은 요구사항을
    승인된 것으로 받는다.
    """

    def __init__(self, *, mission_id: str, outcome: str) -> None:
        super().__init__(
            f"cannot build a Brief handoff for mission {mission_id}: gate outcome is {outcome}"
        )
        self.mission_id = mission_id
        self.outcome = outcome


@dataclass(frozen=True, slots=True)
class BriefHandoff:
    """``CLEAR``된 Brief revision 하나에 대한 Blueprint 입력.

    칸별 목록에는 승격된 후보만 담긴다. 차단된 후보가 있으면 애초에 ``CLEAR``가
    아니므로 handoff가 만들어지지 않는다.
    """

    mission_id: str
    revision: int
    #: 사용자의 원문 의도. 요약으로 대체하지 않는다.
    initial_intent: str

    goals: tuple[str, ...]
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]
    success_criteria: tuple[str, ...]
    context: tuple[str, ...]

    #: 요구사항을 도출하는 입력. ``observation`` 답변의 본문이 빠져 있다.
    requirement_input: tuple[RequirementInputRound, ...]
    #: 관찰된 사실 원문. 제약과 현재 상태를 이해하는 데 쓴다.
    observed_facts: tuple[BriefRound, ...]

    #: 승격되지 않아 칸에 담기지 않은 후보와 그 이유. 조용히 사라지지 않는다.
    omitted: tuple[PromotionDecision, ...]

    assessment: ClarityAssessment | None
    policy_version: str
    approval: BriefApproval


def build_brief_handoff(*, state: BriefState, decision: BriefGateDecision) -> BriefHandoff:
    """``CLEAR`` 판정을 받은 상태에서 handoff를 만든다.

    ``HOLD``이거나 판정이 다른 revision을 본 것이면 거부한다. 승인과 판정과
    내용이 같은 revision을 가리켜야 handoff가 의미를 갖는다 (§8.1 규칙 7).
    """
    if decision.outcome != "CLEAR":
        raise HandoffNotClearedError(mission_id=state.mission_id, outcome=decision.outcome)
    if decision.revision != state.revision:
        raise HandoffNotClearedError(
            mission_id=state.mission_id,
            outcome=f"CLEAR for revision {decision.revision}, not {state.revision}",
        )
    if state.approval is None:
        # Gate가 CLEAR했다면 승인이 있어야 한다. 방어적으로 남기는 이유는 이
        # 불변 조건이 깨지면 다음 Stage가 승인 없이 진행하기 때문이다.
        raise HandoffNotClearedError(mission_id=state.mission_id, outcome="CLEAR without approval")

    promotion = state.promotion
    promoted = promotion.promoted

    def texts(*sections: RequirementSection) -> tuple[str, ...]:
        return tuple(item.text for item in promoted if item.section in sections)

    return BriefHandoff(
        mission_id=state.mission_id,
        revision=state.revision,
        initial_intent=state.initial_intent,
        goals=texts(RequirementSection.GOAL),
        constraints=texts(RequirementSection.CONSTRAINT, RequirementSection.EXISTING_CONSTRAINT),
        non_goals=texts(RequirementSection.NON_GOAL),
        success_criteria=texts(RequirementSection.ACCEPTANCE_CRITERION),
        context=texts(RequirementSection.CONTEXT),
        requirement_input=tuple(project_requirement_input(state.rounds)),
        observed_facts=tuple(observed_facts(state.rounds)),
        omitted=tuple(
            item for item in promotion.decisions if item.disposition is PromotionDisposition.OMIT
        ),
        assessment=state.assessment,
        policy_version=decision.policy_version,
        approval=state.approval,
    )
