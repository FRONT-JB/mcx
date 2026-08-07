"""Blueprint QA 루프 — 판정 경계, 최선 시도 추적, 반복 상한.

계약: docs/06_BLUEPRINT.md / docs/adr/0019-blueprint-qa-loop.md
"""

import pytest

from mission_control.domain.blueprint.qa import (
    LoopAction,
    QaAssessment,
    QaLoopState,
    QaPolicy,
    QaVerdict,
)

POLICY = QaPolicy.blueprint_v1()


def _state(*scores: float) -> QaLoopState:
    state = QaLoopState(policy=POLICY)
    for score in scores:
        state = state.record(QaAssessment(score=score))
    return state


class TestPolicyDefaults:
    def test_blueprint_bar_is_stricter_than_the_generic_one(self) -> None:
        """Blueprint는 구조적 명세라 이후 모든 Stage가 이것을 근거로 판단한다."""
        assert POLICY.pass_threshold == 0.90
        assert POLICY.max_iterations == 5

    def test_quality_bar_carries_the_granularity_rule(self) -> None:
        """수단을 수용 기준에 남기는 것을 잡는 문장이 기준에 들어 있어야 한다."""
        assert "수단" in POLICY.quality_bar
        assert "형제" in POLICY.quality_bar


class TestVerdictBands:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (1.0, QaVerdict.PASS),
            (0.90, QaVerdict.PASS),
            (0.8999, QaVerdict.REVISE),
            (0.40, QaVerdict.REVISE),
            (0.3999, QaVerdict.FAIL),
            (0.0, QaVerdict.FAIL),
        ],
    )
    def test_boundaries_are_inclusive_at_the_pass_and_fail_edges(
        self, score: float, expected: QaVerdict
    ) -> None:
        assert POLICY.verdict_for(score) is expected


class TestBestAttempt:
    def test_best_is_not_necessarily_the_latest(self) -> None:
        """고치다가 점수가 내려가는 일이 실제로 일어난다."""
        state = _state(0.81, 0.87, 0.88, 0.87)

        best = state.best
        assert best is not None
        assert best.iteration == 3
        assert best.assessment.score == 0.88

    def test_ties_keep_the_earlier_attempt(self) -> None:
        """같은 점수라면 덜 고친 쪽이 낫다."""
        state = _state(0.85, 0.85)

        best = state.best
        assert best is not None
        assert best.iteration == 1

    def test_regression_is_visible(self) -> None:
        assert _state(0.81, 0.87, 0.88, 0.87).regressed is True
        assert _state(0.81, 0.87).regressed is False
        assert _state(0.81).regressed is False

    def test_history_is_preserved_in_order(self) -> None:
        assert _state(0.81, 0.87, 0.88).score_history == (0.81, 0.87, 0.88)

    def test_recording_does_not_mutate_the_previous_state(self) -> None:
        first = _state(0.81)

        first.record(QaAssessment(score=0.9))

        assert first.score_history == (0.81,)


class TestLoopAction:
    def test_empty_loop_continues(self) -> None:
        assert QaLoopState(policy=POLICY).action is LoopAction.CONTINUE

    def test_passing_score_is_done(self) -> None:
        assert _state(0.91).action is LoopAction.DONE

    def test_failing_score_escalates_immediately(self) -> None:
        """명세 수준의 문제는 반복으로 해결하지 않는다."""
        assert _state(0.2).action is LoopAction.ESCALATE

    def test_revise_continues_while_iterations_remain(self) -> None:
        assert _state(0.85).action is LoopAction.CONTINUE
        assert _state(0.85, 0.86, 0.87).action is LoopAction.CONTINUE

    def test_reaching_the_cap_stops_the_loop(self) -> None:
        state = _state(0.81, 0.87, 0.88, 0.87, 0.88)

        assert len(state.attempts) == POLICY.max_iterations
        assert state.action is LoopAction.EXHAUSTED
        assert state.is_open is False

    def test_passing_on_the_last_allowed_iteration_still_passes(self) -> None:
        """횟수를 다 썼다는 이유로 합격을 취소하지 않는다."""
        state = _state(0.81, 0.82, 0.83, 0.84, 0.95)

        assert state.action is LoopAction.DONE

    def test_failing_on_the_last_allowed_iteration_escalates(self) -> None:
        state = _state(0.81, 0.82, 0.83, 0.84, 0.1)

        assert state.action is LoopAction.ESCALATE

    def test_exhausted_loop_still_reports_its_best(self) -> None:
        """상한에서 사용자에게 보여 줄 것은 마지막이 아니라 최선이다."""
        state = _state(0.81, 0.89, 0.72, 0.70, 0.71)

        assert state.action is LoopAction.EXHAUSTED
        best = state.best
        assert best is not None
        assert best.assessment.score == 0.89


class TestAssessmentShape:
    def test_assessment_does_not_carry_a_verdict(self) -> None:
        """채점자가 합격 여부까지 판단하면 기준을 스스로 조정할 여지가 생긴다."""
        assert not hasattr(QaAssessment(score=0.9), "verdict")

    @pytest.mark.parametrize("score", [-0.01, 1.01])
    def test_out_of_range_score_is_rejected(self, score: float) -> None:
        with pytest.raises(ValueError):
            QaAssessment(score=score)
