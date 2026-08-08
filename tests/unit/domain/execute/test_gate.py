"""Execute Gate — Clear for Verify는 실행 완료이지 충족 판정이 아니다.

계약: docs/07_EXECUTE.md §10 / docs/adr/0024-execute-v1-execution-model.md
"""

from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.execute.gate import (
    ExecuteGateBlockingCondition,
    evaluate_execute_gate,
)
from mission_control.domain.execute.state import CapabilityEnvelope, ExecuteState
from mission_control.domain.stage import Stage

ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission")

FIRST = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")
SECOND = AcceptanceCriterion(description="빈 댓글이 거부된다", verify_command="pytest -k empty")

BLUEPRINT = Blueprint(
    mission_id="m-1",
    revision=1,
    brief_revision=3,
    goal="댓글 기능",
    acceptance_criteria=(FIRST, SECOND),
)


def _dispatched(state: ExecuteState, *, ac_key: str) -> ExecuteState:
    return state.dispatch(
        execution_id=f"exec-m-1-{len(state.attempts) + 1:04d}",
        runtime_backend="fake",
        blueprint_revision=1,
        ac_key=ac_key,
        envelope=ENVELOPE,
    )


def _conditions(state: ExecuteState):
    decision = evaluate_execute_gate(state=state, blueprint=BLUEPRINT)
    return decision, tuple(item.condition for item in decision.gate_blockers)


class TestClear:
    def test_all_criteria_executed_clears_for_verify(self) -> None:
        state = ExecuteState.start(mission_id="m-1")
        for key in (FIRST.key, SECOND.key):
            state = _dispatched(state, ac_key=key).record_result(succeeded=True)

        decision, _ = _conditions(state)
        assert decision.outcome == "CLEAR"
        assert decision.blueprint_revision == 1
        assert decision.next_destination is Stage.VERIFY


class TestHold:
    def test_nothing_executed_holds_per_criterion(self) -> None:
        decision, conditions = _conditions(ExecuteState.start(mission_id="m-1"))

        assert decision.outcome == "HOLD"
        assert conditions.count(ExecuteGateBlockingCondition.CRITERION_UNEXECUTED) == 2
        assert decision.next_destination is None

    def test_an_open_attempt_is_an_unknown_outcome(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"), ac_key=FIRST.key)
        decision, conditions = _conditions(state)

        assert decision.outcome == "HOLD"
        assert ExecuteGateBlockingCondition.ATTEMPT_OPEN in conditions

    def test_a_failed_criterion_holds_with_its_error(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"), ac_key=FIRST.key)
        state = state.record_result(succeeded=False, error="tests exploded")
        decision, conditions = _conditions(state)

        assert decision.outcome == "HOLD"
        assert ExecuteGateBlockingCondition.CRITERION_FAILED in conditions
        assert any("tests exploded" in reason for reason in decision.blocking_reasons)

    def test_old_revision_execution_does_not_clear(self) -> None:
        """이전 revision의 실행 결과로는 현재 revision이 CLEAR되지 않는다."""
        old = Blueprint(
            mission_id="m-1",
            revision=1,
            brief_revision=3,
            goal="댓글 기능",
            acceptance_criteria=(FIRST, SECOND),
        )
        state = ExecuteState.start(mission_id="m-1")
        for key in (FIRST.key, SECOND.key):
            state = _dispatched(state, ac_key=key).record_result(succeeded=True)

        current = old.model_copy(update={"revision": 2})
        decision = evaluate_execute_gate(state=state, blueprint=current)
        assert decision.outcome == "HOLD"
