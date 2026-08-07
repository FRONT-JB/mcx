"""Blueprint Gate — Execute 진입은 채점·승인된 현재 revision을 요구한다.

계약: docs/06_BLUEPRINT.md §10 / docs/adr/0021-blueprint-state-and-revisions.md §6
Test Matrix: Entry stale Brief revision, Approval, Mutation 행 (docs/06_BLUEPRINT.md §14)
"""

import pytest

from mission_control.domain.blueprint.gate import (
    BlueprintGateBlockingCondition,
    evaluate_blueprint_gate,
    next_stage_after_blueprint,
)
from mission_control.domain.blueprint.qa import QaAssessment, QaPolicy
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.errors import StaleGateDecisionError
from mission_control.domain.stage import Stage

POLICY = QaPolicy.blueprint_v1()
BRIEF_REVISION = 5


def _blueprint(*, revision: int = 1, goal: str = "댓글을 쓰고 볼 수 있다") -> Blueprint:
    return Blueprint(
        mission_id="m-1",
        revision=revision,
        brief_revision=BRIEF_REVISION,
        goal=goal,
        acceptance_criteria=(
            AcceptanceCriterion(description="목록에 새 댓글이 보인다", verify_command="pytest"),
        ),
    )


def _approved() -> BlueprintState:
    state = BlueprintState.start(blueprint=_blueprint())
    state = state.record_qa(assessment=QaAssessment(score=0.92), policy=POLICY)
    return state.approve(statement="이대로 진행", policy=POLICY)


def _conditions(state: BlueprintState, *, brief_revision: int = BRIEF_REVISION):
    decision = evaluate_blueprint_gate(state=state, brief_revision=brief_revision)
    return decision, tuple(item.condition for item in decision.gate_blockers)


class TestClear:
    def test_an_approved_current_revision_clears_for_execute(self) -> None:
        decision, _ = _conditions(_approved())

        assert decision.outcome == "CLEAR"
        assert decision.revision == 1
        assert decision.brief_revision == BRIEF_REVISION
        assert decision.gate_blockers == ()
        assert decision.next_destination is Stage.EXECUTE


class TestHold:
    def test_a_missing_approval_holds(self) -> None:
        state = BlueprintState.start(blueprint=_blueprint())
        decision, conditions = _conditions(state)

        assert decision.outcome == "HOLD"
        assert BlueprintGateBlockingCondition.APPROVAL_MISSING in conditions
        assert decision.next_destination is None

    def test_an_approval_left_behind_by_a_revision_holds(self) -> None:
        state = _approved().revise(blueprint=_blueprint(revision=2, goal="다듬은 목표"))
        decision, conditions = _conditions(state)

        assert decision.outcome == "HOLD"
        assert BlueprintGateBlockingCondition.APPROVAL_STALE in conditions

    def test_a_moved_brief_holds_even_with_an_approval(self) -> None:
        decision, conditions = _conditions(_approved(), brief_revision=BRIEF_REVISION + 1)

        assert decision.outcome == "HOLD"
        assert BlueprintGateBlockingCondition.BRIEF_REVISION_STALE in conditions

    def test_blocking_reasons_are_readable(self) -> None:
        state = BlueprintState.start(blueprint=_blueprint())
        decision, _ = _conditions(state, brief_revision=BRIEF_REVISION + 1)

        assert len(decision.blocking_reasons) == 2
        assert all(isinstance(reason, str) and reason for reason in decision.blocking_reasons)


class TestTransition:
    def test_clear_moves_to_execute(self) -> None:
        state = _approved()
        decision = evaluate_blueprint_gate(state=state, brief_revision=BRIEF_REVISION)

        assert next_stage_after_blueprint(state=state, decision=decision) is Stage.EXECUTE

    def test_hold_stays_in_blueprint(self) -> None:
        state = BlueprintState.start(blueprint=_blueprint())
        decision = evaluate_blueprint_gate(state=state, brief_revision=BRIEF_REVISION)

        assert next_stage_after_blueprint(state=state, decision=decision) is Stage.BLUEPRINT

    def test_a_decision_for_another_revision_is_rejected(self) -> None:
        state = _approved()
        decision = evaluate_blueprint_gate(state=state, brief_revision=BRIEF_REVISION)
        moved = state.revise(blueprint=_blueprint(revision=2, goal="다듬은 목표"))

        with pytest.raises(StaleGateDecisionError):
            next_stage_after_blueprint(state=moved, decision=decision)
