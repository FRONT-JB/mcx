"""실행 순서 — 선언 순서에서 아직 실행되지 않은 첫 AC의 결정적 선택.

계약: docs/07_EXECUTE.md §6.3, §6.4 / docs/adr/0024-execute-v1-execution-model.md §3
"""

from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.execute.plan import next_criterion
from mission_control.domain.execute.state import CapabilityEnvelope, ExecuteState

ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission")

FIRST = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")
SECOND = AcceptanceCriterion(description="빈 댓글이 거부된다", verify_command="pytest -k empty")


def _blueprint(*, revision: int = 1) -> Blueprint:
    return Blueprint(
        mission_id="m-1",
        revision=revision,
        brief_revision=3,
        goal="댓글 기능",
        acceptance_criteria=(FIRST, SECOND),
    )


def _executed(state: ExecuteState, *, ac_key: str, blueprint_revision: int = 1) -> ExecuteState:
    dispatched = state.dispatch(
        execution_id=f"exec-m-1-{len(state.attempts) + 1:04d}",
        runtime_backend="fake",
        blueprint_revision=blueprint_revision,
        ac_key=ac_key,
        envelope=ENVELOPE,
    )
    return dispatched.record_result(succeeded=True)


class TestNextCriterion:
    def test_declaration_order_starts_at_the_first(self) -> None:
        state = ExecuteState.start(mission_id="m-1")
        assert next_criterion(blueprint=_blueprint(), state=state) == FIRST

    def test_an_executed_criterion_is_skipped(self) -> None:
        state = _executed(ExecuteState.start(mission_id="m-1"), ac_key=FIRST.key)
        assert next_criterion(blueprint=_blueprint(), state=state) == SECOND

    def test_everything_executed_yields_none(self) -> None:
        state = _executed(ExecuteState.start(mission_id="m-1"), ac_key=FIRST.key)
        state = _executed(state, ac_key=SECOND.key)
        assert next_criterion(blueprint=_blueprint(), state=state) is None

    def test_a_failed_criterion_is_selected_again(self) -> None:
        """실패한 AC가 다시 첫 순위가 된다 — 재시도가 자연스러운 다음 행동이다."""
        state = ExecuteState.start(mission_id="m-1").dispatch(
            execution_id="exec-m-1-0001",
            runtime_backend="fake",
            blueprint_revision=1,
            ac_key=FIRST.key,
            envelope=ENVELOPE,
        )
        state = state.record_result(succeeded=False, error="tests exploded")

        assert next_criterion(blueprint=_blueprint(), state=state) == FIRST

    def test_old_revision_results_do_not_count(self) -> None:
        """새 revision이 승인되면 이전 실행 결과를 자동 재사용하지 않는다."""
        state = _executed(ExecuteState.start(mission_id="m-1"), ac_key=FIRST.key)

        assert next_criterion(blueprint=_blueprint(revision=2), state=state) == FIRST
