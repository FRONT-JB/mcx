"""실행 순서 — 선언 순서에서 아직 실행되지 않은 첫 AC의 결정적 선택.

계약: docs/07_EXECUTE.md §6.3, §6.4 / docs/adr/0024-execute-v1-execution-model.md §3
"""

import pytest

from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.execute.plan import (
    CriterionDependency,
    DependencyPlanError,
    build_parallel_plan,
    next_criterion,
    plan_readiness,
)
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


THIRD = AcceptanceCriterion(description="댓글이 저장된다", verify_command="pytest -k stored")
FOURTH = AcceptanceCriterion(description="댓글 지표가 보인다", verify_command="pytest -k metric")


def _parallel_blueprint() -> Blueprint:
    return Blueprint(
        mission_id="m-1",
        revision=1,
        brief_revision=3,
        goal="댓글 기능",
        acceptance_criteria=(FIRST, SECOND, THIRD, FOURTH),
    )


class TestParallelPlan:
    def test_exact_dependencies_become_deterministic_stages(self) -> None:
        blueprint = _parallel_blueprint()
        plan = build_parallel_plan(
            blueprint=blueprint,
            analyzer_backend="fake_text",
            dependencies=(
                CriterionDependency(ac_key=FIRST.key),
                CriterionDependency(ac_key=SECOND.key),
                CriterionDependency(ac_key=THIRD.key, depends_on=(FIRST.key,)),
                CriterionDependency(ac_key=FOURTH.key, depends_on=(SECOND.key,)),
            ),
        )

        assert plan.stages == ((FIRST.key, SECOND.key), (THIRD.key, FOURTH.key))
        assert plan.blueprint_revision == 1

    @pytest.mark.parametrize("kind", ["missing", "unknown", "cycle"])
    def test_incomplete_unknown_and_cycle_fail_closed(self, kind: str) -> None:
        blueprint = _parallel_blueprint()
        dependencies = [
            CriterionDependency(ac_key=FIRST.key),
            CriterionDependency(ac_key=SECOND.key),
            CriterionDependency(ac_key=THIRD.key),
            CriterionDependency(ac_key=FOURTH.key),
        ]
        if kind == "missing":
            dependencies.pop()
        elif kind == "unknown":
            dependencies[0] = CriterionDependency(ac_key="ac_unknown")
        else:
            dependencies[0] = CriterionDependency(ac_key=FIRST.key, depends_on=(SECOND.key,))
            dependencies[1] = CriterionDependency(ac_key=SECOND.key, depends_on=(FIRST.key,))

        with pytest.raises(DependencyPlanError):
            build_parallel_plan(
                blueprint=blueprint,
                analyzer_backend="fake_text",
                dependencies=tuple(dependencies),
            )

    def test_failed_dependency_blocks_only_its_branch(self) -> None:
        blueprint = _parallel_blueprint()
        plan = build_parallel_plan(
            blueprint=blueprint,
            analyzer_backend="fake_text",
            dependencies=(
                CriterionDependency(ac_key=FIRST.key),
                CriterionDependency(ac_key=SECOND.key),
                CriterionDependency(ac_key=THIRD.key, depends_on=(FIRST.key,)),
                CriterionDependency(ac_key=FOURTH.key, depends_on=(SECOND.key,)),
            ),
        )
        state = ExecuteState.start(mission_id="m-1").add_plan(plan)
        state = state.dispatch_stage(
            plan=plan,
            stage_index=0,
            ac_keys=(FIRST.key, SECOND.key),
            runtime_backend="fake",
            envelope=ENVELOPE,
            requested_workers=2,
            effective_workers=2,
        )
        first_id, second_id = state.stage_runs[-1].attempt_execution_ids
        state = state.record_result_for(
            execution_id=first_id, succeeded=False, error="broken"
        )
        state = state.record_result_for(execution_id=second_id, succeeded=True)
        state = state.finalize_stage(run_id=state.stage_runs[-1].run_id)

        readiness = plan_readiness(blueprint=blueprint, plan=plan, state=state)
        assert readiness.ready_ac_keys == (FOURTH.key,)
        assert THIRD.key in readiness.blocked_ac_keys
        assert FOURTH.key not in readiness.blocked_ac_keys
