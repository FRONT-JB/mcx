"""Blueprint 조립 — 초안이 승인된 범위를 벗어나지 않는지 확인한다.

계약: docs/06_BLUEPRINT.md / docs/adr/0018-blueprint-generation-contract.md
"""

import pytest

from mission_control.domain.blueprint.assembly import (
    BlueprintDraft,
    BlueprintScopeError,
    ScopeViolation,
    assemble_blueprint,
    check_scope,
)
from mission_control.domain.blueprint.spec import (
    AcceptanceCriterion,
    OntologyField,
    OntologySchema,
)
from mission_control.domain.brief.handoff import BriefHandoff
from mission_control.domain.brief.state import BriefApproval

CONSTRAINT = "로그인 사용자만 작성"
NON_GOAL = "수정·삭제는 이번 범위가 아니다"


def _handoff(**overrides: object) -> BriefHandoff:
    defaults: dict[str, object] = {
        "mission_id": "m-1",
        "revision": 6,
        "initial_intent": "댓글 기능을 추가하고 싶다",
        "goals": ("댓글을 쓰고 볼 수 있다",),
        "constraints": (CONSTRAINT,),
        "non_goals": (NON_GOAL,),
        "success_criteria": ("목록 맨 위에 새 댓글이 보인다",),
        "context": (),
        "requirement_input": (),
        "observed_facts": (),
        "omitted": (),
        "assessment": None,
        "policy_version": "greenfield-v1",
        "approval": BriefApproval(revision=6, statement="진행"),
    }
    defaults.update(overrides)
    return BriefHandoff(**defaults)  # type: ignore[arg-type]


def _criterion(description: str = "댓글 작성 후 목록 맨 위에 보인다") -> AcceptanceCriterion:
    return AcceptanceCriterion(description=description, verify_command="pytest tests/test_x.py")


def _draft(**overrides: object) -> BlueprintDraft:
    defaults: dict[str, object] = {
        "goal": "로그인 사용자가 댓글을 쓰고 볼 수 있다",
        "constraints": (CONSTRAINT,),
        "non_goals": (NON_GOAL,),
        "acceptance_criteria": (_criterion(),),
    }
    defaults.update(overrides)
    return BlueprintDraft(**defaults)  # type: ignore[arg-type]


class TestScopeIsAHardBoundary:
    """Blueprint는 Brief를 구체화할 수 있을 뿐 확장할 수 없다."""

    def test_draft_within_scope_passes(self) -> None:
        assert check_scope(draft=_draft(), handoff=_handoff()) == ()

    def test_invented_constraint_is_rejected(self) -> None:
        """생성기가 제약을 추가할 수 있으면 승인받지 않은 경계가 생긴다."""
        draft = _draft(constraints=(CONSTRAINT, "응답은 200ms 이내"))

        findings = check_scope(draft=draft, handoff=_handoff())

        assert [item.violation for item in findings] == [ScopeViolation.CONSTRAINT_NOT_IN_HANDOFF]
        assert findings[0].detail == "응답은 200ms 이내"

    def test_invented_non_goal_is_rejected(self) -> None:
        draft = _draft(non_goals=(NON_GOAL, "성능 개선은 안 한다"))

        findings = check_scope(draft=draft, handoff=_handoff())

        assert ScopeViolation.NON_GOAL_NOT_IN_HANDOFF in [item.violation for item in findings]

    def test_dropped_non_goal_is_rejected(self) -> None:
        """빠뜨리면 승인된 경계가 사라진다. 만드는 쪽이 그 범위까지 만든다."""
        draft = _draft(non_goals=())

        findings = check_scope(draft=draft, handoff=_handoff())

        assert [item.violation for item in findings] == [ScopeViolation.NON_GOAL_DROPPED]
        assert findings[0].detail == NON_GOAL

    def test_dropped_constraint_is_allowed(self) -> None:
        """제약을 덜 싣는 것은 범위를 넓히지 않는다. Blueprint QA가 다룰 문제다."""
        draft = _draft(constraints=())

        assert check_scope(draft=draft, handoff=_handoff()) == ()

    def test_all_violations_are_reported_together(self) -> None:
        draft = _draft(
            goal="  ",
            constraints=("발명된 제약",),
            non_goals=(),
            acceptance_criteria=(),
        )

        violations = {item.violation for item in check_scope(draft=draft, handoff=_handoff())}

        assert violations == {
            ScopeViolation.EMPTY_GOAL,
            ScopeViolation.CONSTRAINT_NOT_IN_HANDOFF,
            ScopeViolation.NON_GOAL_DROPPED,
            ScopeViolation.NO_ACCEPTANCE_CRITERIA,
        }


class TestAcceptanceCriteriaMayBeElaborated:
    """성공 조건을 확인 가능한 계약으로 바꾸는 것이 생성기의 일이다."""

    def test_criterion_text_need_not_match_the_handoff(self) -> None:
        draft = _draft(acceptance_criteria=(_criterion("완전히 다르게 표현된 기준"),))

        assert check_scope(draft=draft, handoff=_handoff()) == ()

    def test_one_success_criterion_may_become_several(self) -> None:
        draft = _draft(
            acceptance_criteria=(_criterion("새 댓글이 목록에 뜬다"), _criterion("새로고침 불필요"))
        )

        assert check_scope(draft=draft, handoff=_handoff()) == ()

    def test_a_blueprint_without_criteria_is_rejected(self) -> None:
        """검증할 것이 없는 명세는 완료를 증거로 선언할 수 없다."""
        findings = check_scope(draft=_draft(acceptance_criteria=()), handoff=_handoff())

        assert [item.violation for item in findings] == [ScopeViolation.NO_ACCEPTANCE_CRITERIA]


class TestAssembly:
    def test_lineage_comes_from_the_handoff_not_the_draft(self) -> None:
        """생성기가 revision을 정할 수 있으면 어느 Brief에서 나왔는지를 모델이 주장한다."""
        blueprint = assemble_blueprint(draft=_draft(), handoff=_handoff(revision=6))

        assert blueprint.mission_id == "m-1"
        assert blueprint.brief_revision == 6
        assert blueprint.revision == 1

    def test_revision_can_be_supplied_for_a_successor(self) -> None:
        blueprint = assemble_blueprint(draft=_draft(), handoff=_handoff(), revision=3)

        assert blueprint.revision == 3

    def test_out_of_scope_draft_is_refused(self) -> None:
        """경고로 남기고 진행하면 사용자가 그것을 합의된 내용으로 읽는다."""
        draft = _draft(constraints=("발명된 제약",))

        with pytest.raises(BlueprintScopeError) as error:
            assemble_blueprint(draft=draft, handoff=_handoff())

        assert error.value.mission_id == "m-1"
        assert len(error.value.findings) == 1

    def test_assembled_blueprint_carries_the_draft_content(self) -> None:
        criterion = _criterion()

        blueprint = assemble_blueprint(
            draft=_draft(acceptance_criteria=(criterion,)), handoff=_handoff()
        )

        assert blueprint.goal == "로그인 사용자가 댓글을 쓰고 볼 수 있다"
        assert blueprint.constraints == (CONSTRAINT,)
        assert blueprint.non_goals == (NON_GOAL,)
        assert blueprint.criterion_keys == (criterion.key,)

    def test_manual_draft_carries_a_complete_ontology_when_no_override_is_supplied(self) -> None:
        replacement = OntologySchema(
            name="RetryPolicy",
            description="사용자가 채택한 보완 경계",
            fields=(
                OntologyField(
                    name="retry_after",
                    field_type="str | None",
                    description="Retry-After 입력",
                    required=True,
                ),
            ),
        )

        blueprint = assemble_blueprint(
            draft=_draft(ontology=replacement),
            handoff=_handoff(),
        )

        assert blueprint.ontology == replacement
