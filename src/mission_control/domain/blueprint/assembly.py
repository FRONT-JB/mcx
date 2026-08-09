"""Blueprint 조립 — 초안을 승인 대상 명세로 확정한다.

생성은 두 층으로 나뉜다.

**위임되는 것** — 성공 조건 문장을 확인 가능한 계약으로 구체화하는 일. "목록에
새 댓글이 보인다"에서 "무엇을 실행하고 무엇을 확인할 것인가"를 뽑는 데는 판단이
필요하다.

**결정적인 것** — 그 초안이 handoff의 범위를 벗어나지 않았는지 확인하고 lineage를
붙이는 일. 이 모듈이 그 부분이다.

범위 검사가 이 모듈의 존재 이유다. 생성기가 handoff에 없던 제약을 추가할 수
있으면 handoff 계약이 장식이 된다. 사용자가 승인한 것은 Brief의 내용이고,
Blueprint는 그것을 **구체화**할 수 있을 뿐 **확장**할 수 없다.

계약: ``docs/06_BLUEPRINT.md``
결정: ``docs/adr/0018-blueprint-generation-contract.md``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.brief.handoff import BriefHandoff
from mission_control.domain.errors import MissionControlError


class ScopeViolation(StrEnum):
    """초안이 handoff의 범위를 벗어난 방식."""

    CONSTRAINT_NOT_IN_HANDOFF = "constraint_not_in_handoff"
    NON_GOAL_NOT_IN_HANDOFF = "non_goal_not_in_handoff"
    NON_GOAL_DROPPED = "non_goal_dropped"
    NO_ACCEPTANCE_CRITERIA = "no_acceptance_criteria"
    EMPTY_GOAL = "empty_goal"


@dataclass(frozen=True, slots=True)
class ScopeFinding:
    violation: ScopeViolation
    detail: str


class BlueprintScopeError(MissionControlError):
    """초안이 승인된 Brief의 범위를 벗어났다.

    Blueprint는 Brief를 구체화하는 것이지 확장하는 것이 아니다. 범위 밖 내용이
    실리면 사용자가 승인한 적 없는 요구사항이 실행 명세가 된다
    (Constitution Appendix A, "Scope는 hard boundary").
    """

    def __init__(self, *, mission_id: str, findings: tuple[ScopeFinding, ...]) -> None:
        joined = "; ".join(f"{item.violation.value}: {item.detail}" for item in findings)
        super().__init__(
            f"Blueprint 초안이 mission {mission_id}의 승인된 범위를 벗어난다: {joined}"
        )
        self.mission_id = mission_id
        self.findings = findings


@dataclass(frozen=True, slots=True)
class BlueprintDraft:
    """생성기가 반환하는 초안. 아직 승인 대상이 아니다.

    lineage(mission, revision)를 담지 않는다. 그것은 생성기가 정할 것이 아니라
    조립 단계가 handoff에서 가져온다. 생성기가 revision을 정할 수 있으면 승인
    대상이 어느 Brief에서 나왔는지를 모델이 주장하게 된다.
    """

    goal: str
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]


def check_scope(*, draft: BlueprintDraft, handoff: BriefHandoff) -> tuple[ScopeFinding, ...]:
    """초안이 handoff의 범위 안에 있는지 확인한다.

    제약과 Non-goal은 **그대로 옮겨져야 한다.** 이 둘은 사용자가 결정한 경계이며
    구체화의 대상이 아니다. 새로 추가하면 승인받지 않은 경계가 생기고, 빠뜨리면
    승인된 경계가 사라진다.

    수용 기준은 다르다. 성공 조건 문장을 확인 가능한 계약으로 바꾸는 것이
    생성기의 일이므로, 문장이 쪼개지거나 다시 쓰일 수 있다. 따라서 내용 일치를
    요구하지 않고 **존재만** 요구한다. 이 느슨함의 대가는 알려진 한계로 남는다.
    """
    findings: list[ScopeFinding] = []

    if not draft.goal.strip():
        findings.append(
            ScopeFinding(violation=ScopeViolation.EMPTY_GOAL, detail="초안의 goal이 비어 있다")
        )

    allowed_constraints = set(handoff.constraints)
    for constraint in draft.constraints:
        if constraint not in allowed_constraints:
            findings.append(
                ScopeFinding(
                    violation=ScopeViolation.CONSTRAINT_NOT_IN_HANDOFF,
                    detail=constraint,
                )
            )

    allowed_non_goals = set(handoff.non_goals)
    for non_goal in draft.non_goals:
        if non_goal not in allowed_non_goals:
            findings.append(
                ScopeFinding(violation=ScopeViolation.NON_GOAL_NOT_IN_HANDOFF, detail=non_goal)
            )

    for missing in allowed_non_goals - set(draft.non_goals):
        findings.append(ScopeFinding(violation=ScopeViolation.NON_GOAL_DROPPED, detail=missing))

    if not draft.acceptance_criteria:
        findings.append(
            ScopeFinding(
                violation=ScopeViolation.NO_ACCEPTANCE_CRITERIA,
                detail="수용 기준이 없는 Blueprint는 검증할 수 없다",
            )
        )

    return tuple(findings)


def assemble_blueprint(
    *, draft: BlueprintDraft, handoff: BriefHandoff, revision: int = 1
) -> Blueprint:
    """범위를 확인하고 lineage를 붙여 Blueprint를 확정한다.

    범위를 벗어났으면 거부한다. 경고로 남기고 진행하지 않는 이유는, 승인 화면에
    올라간 순간 사용자가 그것을 Brief에서 합의한 내용으로 읽기 때문이다.
    """
    findings = check_scope(draft=draft, handoff=handoff)
    if findings:
        raise BlueprintScopeError(mission_id=handoff.mission_id, findings=findings)

    return Blueprint(
        mission_id=handoff.mission_id,
        revision=revision,
        brief_revision=handoff.revision,
        goal=draft.goal,
        constraints=draft.constraints,
        non_goals=draft.non_goals,
        acceptance_criteria=draft.acceptance_criteria,
    )
