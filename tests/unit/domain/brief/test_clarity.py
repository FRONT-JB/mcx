"""Clarity 평가와 종료 후보 판정 정책.

계약: docs/05_BRIEF.md §11 / docs/adr/0009-brief-completion-gate-policy.md
Test Matrix: B-027, B-028, B-029, B-030
upstream 회귀 근거: docs/research/INTERVIEW_UPSTREAM_FINDINGS.md §8.5
"""

import pytest

from mission_control.domain.brief.clarity import (
    BlockingCondition,
    ClarityAssessment,
    ClarityPolicy,
    DimensionScore,
)


def _assessment(
    goal: float = 0.9,
    constraint: float = 0.9,
    success: float = 0.9,
) -> ClarityAssessment:
    return ClarityAssessment(
        scores=(
            DimensionScore(dimension="goal", clarity=goal, justification="t"),
            DimensionScore(dimension="constraint", clarity=constraint, justification="t"),
            DimensionScore(dimension="success_criteria", clarity=success, justification="t"),
        ),
        policy_version=ClarityPolicy.greenfield_v1().version,
    )


def _blockers(candidacy: object) -> list[BlockingCondition]:
    return [blocker.condition for blocker in candidacy.blockers]  # type: ignore[attr-defined]


class TestDimensionScoreValidation:
    """upstream 경계 계약 — clarity는 0.0~1.0이며 경계값을 허용한다."""

    @pytest.mark.parametrize("clarity", [0.0, 1.0])
    def test_boundary_values_are_accepted(self, clarity: float) -> None:
        score = DimensionScore(dimension="goal", clarity=clarity, justification="t")

        assert score.clarity == clarity

    @pytest.mark.parametrize("clarity", [-0.1, 1.5])
    def test_out_of_range_is_rejected(self, clarity: float) -> None:
        with pytest.raises(ValueError):
            DimensionScore(dimension="goal", clarity=clarity, justification="t")


class TestAmbiguityAggregation:
    """§11.2 — ambiguity = 1 − Σ(clarity × weight). 방향이 반대임에 주의."""

    def test_perfect_clarity_is_zero_ambiguity(self) -> None:
        policy = ClarityPolicy.greenfield_v1()

        assert policy.ambiguity_of(_assessment(goal=1.0, constraint=1.0, success=1.0)) == 0.0

    def test_no_clarity_is_full_ambiguity(self) -> None:
        policy = ClarityPolicy.greenfield_v1()

        assert policy.ambiguity_of(_assessment(goal=0.0, constraint=0.0, success=0.0)) == 1.0

    def test_weighted_aggregation(self) -> None:
        """goal 0.4 + constraint 0.3 + success 0.3 가중 평균."""
        policy = ClarityPolicy.greenfield_v1()

        ambiguity = policy.ambiguity_of(_assessment(goal=1.0, constraint=0.5, success=0.5))

        assert ambiguity == pytest.approx(1.0 - (0.4 * 1.0 + 0.3 * 0.5 + 0.3 * 0.5))

    def test_weights_sum_to_one(self) -> None:
        policy = ClarityPolicy.greenfield_v1()

        assert sum(policy.weights.values()) == pytest.approx(1.0)

    def test_assessment_missing_a_weighted_dimension_is_rejected(self) -> None:
        policy = ClarityPolicy.greenfield_v1()
        partial = ClarityAssessment(
            scores=(DimensionScore(dimension="goal", clarity=0.9, justification="t"),),
            policy_version=policy.version,
        )

        with pytest.raises(ValueError, match="dimension"):
            policy.ambiguity_of(partial)


class TestCompletionCandidacy:
    """§11.1 — 네 조건이 모두 필요하다."""

    def test_all_conditions_met_is_a_candidate(self) -> None:
        """B-030 — 종료 후보가 되어도 그것만으로 CLEAR는 아니다."""
        policy = ClarityPolicy.greenfield_v1()

        candidacy = policy.assess_completion(
            assessment=_assessment(),
            answered_rounds=3,
            stability_signal=2,
        )

        assert candidacy.is_candidate is True
        assert candidacy.blockers == ()

    def test_overall_ambiguity_above_threshold_blocks(self) -> None:
        policy = ClarityPolicy.greenfield_v1()

        candidacy = policy.assess_completion(
            assessment=_assessment(goal=0.5, constraint=0.5, success=0.5),
            answered_rounds=5,
            stability_signal=2,
        )

        assert candidacy.is_candidate is False
        assert BlockingCondition.AMBIGUITY_ABOVE_THRESHOLD in _blockers(candidacy)

    def test_threshold_boundary_is_inclusive(self) -> None:
        """upstream과 동일하게 overall == threshold는 통과한다."""
        policy = ClarityPolicy.greenfield_v1()
        assessment = _assessment(goal=0.8, constraint=0.8, success=0.8)
        assert policy.ambiguity_of(assessment) == pytest.approx(policy.max_ambiguity)

        candidacy = policy.assess_completion(
            assessment=assessment, answered_rounds=3, stability_signal=2
        )

        assert BlockingCondition.AMBIGUITY_ABOVE_THRESHOLD not in _blockers(candidacy)

    def test_dimension_floor_blocks_even_when_overall_passes(self) -> None:
        """B-027 — 한 축이 무너진 것을 다른 축의 높은 점수가 가리지 못한다."""
        policy = ClarityPolicy.greenfield_v1()
        # success_criteria가 floor(0.70) 미만이지만 가중 평균은 threshold를 통과한다.
        assessment = _assessment(goal=1.0, constraint=1.0, success=0.5)
        assert policy.ambiguity_of(assessment) <= policy.max_ambiguity

        candidacy = policy.assess_completion(
            assessment=assessment, answered_rounds=3, stability_signal=2
        )

        assert candidacy.is_candidate is False
        assert BlockingCondition.DIMENSION_FLOOR_NOT_MET in _blockers(candidacy)

    def test_floor_failure_names_the_dimension(self) -> None:
        policy = ClarityPolicy.greenfield_v1()

        candidacy = policy.assess_completion(
            assessment=_assessment(goal=1.0, constraint=1.0, success=0.5),
            answered_rounds=3,
            stability_signal=2,
        )

        floor_blockers = [
            blocker
            for blocker in candidacy.blockers
            if blocker.condition is BlockingCondition.DIMENSION_FLOOR_NOT_MET
        ]
        assert len(floor_blockers) == 1
        assert "success_criteria" in floor_blockers[0].detail

    def test_single_qualifying_evaluation_is_not_enough(self) -> None:
        """B-028 — 단발성으로 낮게 나온 평가로 종료하지 않는다."""
        policy = ClarityPolicy.greenfield_v1()

        candidacy = policy.assess_completion(
            assessment=_assessment(), answered_rounds=3, stability_signal=1
        )

        assert candidacy.is_candidate is False
        assert BlockingCondition.STABILITY_NOT_ESTABLISHED in _blockers(candidacy)

    def test_minimum_rounds_blocks(self) -> None:
        """B-029 — 근거가 쌓이기 전에는 종료 후보가 아니다."""
        policy = ClarityPolicy.greenfield_v1()

        candidacy = policy.assess_completion(
            assessment=_assessment(), answered_rounds=2, stability_signal=2
        )

        assert candidacy.is_candidate is False
        assert BlockingCondition.MINIMUM_ROUNDS_NOT_REACHED in _blockers(candidacy)

    def test_missing_assessment_blocks(self) -> None:
        """B-035 — 평가 결과 없음을 낮은 ambiguity로 해석하지 않는다."""
        policy = ClarityPolicy.greenfield_v1()

        candidacy = policy.assess_completion(assessment=None, answered_rounds=5, stability_signal=2)

        assert candidacy.is_candidate is False
        assert BlockingCondition.ASSESSMENT_MISSING in _blockers(candidacy)

    def test_all_failing_conditions_are_reported_together(self) -> None:
        """HOLD는 이유 하나가 아니라 부족한 조건 전부를 제시해야 한다."""
        policy = ClarityPolicy.greenfield_v1()

        candidacy = policy.assess_completion(
            assessment=_assessment(goal=0.3, constraint=0.3, success=0.3),
            answered_rounds=1,
            stability_signal=0,
        )

        conditions = set(_blockers(candidacy))
        assert BlockingCondition.MINIMUM_ROUNDS_NOT_REACHED in conditions
        assert BlockingCondition.AMBIGUITY_ABOVE_THRESHOLD in conditions
        assert BlockingCondition.DIMENSION_FLOOR_NOT_MET in conditions
        assert BlockingCondition.STABILITY_NOT_ESTABLISHED in conditions


class TestStabilitySignalTransition:
    """findings §8.5 — 한 평가당 정확히 한 번 갱신하고 미달 시 초기화한다."""

    def test_qualifying_evaluation_advances_by_exactly_one(self) -> None:
        policy = ClarityPolicy.greenfield_v1()

        advanced = policy.next_stability_signal(
            current=0, assessment=_assessment(), answered_rounds=3
        )

        assert advanced == 1

    def test_signal_does_not_exceed_requirement(self) -> None:
        policy = ClarityPolicy.greenfield_v1()

        advanced = policy.next_stability_signal(
            current=policy.required_stability,
            assessment=_assessment(),
            answered_rounds=3,
        )

        assert advanced == policy.required_stability

    def test_non_qualifying_evaluation_resets(self) -> None:
        policy = ClarityPolicy.greenfield_v1()

        reset = policy.next_stability_signal(
            current=1,
            assessment=_assessment(goal=0.2, constraint=0.2, success=0.2),
            answered_rounds=3,
        )

        assert reset == 0

    def test_missing_assessment_resets(self) -> None:
        policy = ClarityPolicy.greenfield_v1()

        reset = policy.next_stability_signal(current=1, assessment=None, answered_rounds=3)

        assert reset == 0

    def test_repeated_qualifying_evaluations_reach_the_requirement(self) -> None:
        """반복 신호가 진전을 만들지 못하면 사용자가 갇힌다 (upstream #405)."""
        policy = ClarityPolicy.greenfield_v1()
        signal = 0

        for _ in range(policy.required_stability):
            signal = policy.next_stability_signal(
                current=signal, assessment=_assessment(), answered_rounds=3
            )

        candidacy = policy.assess_completion(
            assessment=_assessment(), answered_rounds=3, stability_signal=signal
        )
        assert candidacy.is_candidate is True
