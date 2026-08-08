"""semantic verdict — 정책 임계, 판정 묶음, 증거 바인딩.

계약: docs/adr/0030-verify-semantic-verdict-contract.md §1~§2, §4
"""

from pydantic import ValidationError
import pytest

from mission_control.domain.verify.evidence import (
    VerdictWithoutEvidenceError,
    VerificationEvidence,
    VerificationRun,
    VerifyState,
)
from mission_control.domain.verify.verdict import (
    CriterionVerdict,
    SemanticAssessment,
    SemanticPolicy,
)

POLICY = SemanticPolicy.verify_v1()


def _verdict(
    ac_key: str = "ac_a",
    *,
    satisfied: bool = True,
    score: float = 0.9,
    uncertainty: float = 0.1,
    risk: float = 0.0,
) -> CriterionVerdict:
    return CriterionVerdict(
        ac_key=ac_key,
        satisfied=satisfied,
        score=score,
        uncertainty=uncertainty,
        reward_hacking_risk=risk,
        reasoning="계약이 증거로 입증된다",
    )


def _evidence(revision: int = 1) -> VerificationEvidence:
    return VerificationEvidence(
        mission_id="m-1",
        blueprint_revision=revision,
        execution_attempt_numbers=(1,),
        runs=(VerificationRun(ac_key="ac_a", command="pytest", exit_code=0, passed=True),),
    )


class TestPolicy:
    def test_v1_adopts_the_upstream_thresholds(self) -> None:
        """수치 셋은 발명이 아니라 upstream 채택이다 (VERIFY_UPSTREAM_FINDINGS §6)."""
        assert POLICY.pass_score == 0.8
        assert POLICY.uncertainty_threshold == 0.3
        assert POLICY.reward_hacking_veto == 0.7

    def test_passing_needs_satisfied_and_score(self) -> None:
        assert _verdict().passes(POLICY) is True
        assert _verdict(score=0.79).passes(POLICY) is False
        assert _verdict(satisfied=False, score=0.95).passes(POLICY) is False


class TestVerdict:
    @pytest.mark.parametrize("field", ["score", "uncertainty", "reward_hacking_risk"])
    def test_out_of_range_values_are_rejected(self, field: str) -> None:
        given: dict[str, object] = {
            "ac_key": "ac_a",
            "satisfied": True,
            "score": 0.9,
            "uncertainty": 0.1,
            "reward_hacking_risk": 0.0,
            "reasoning": "t",
        }
        given[field] = 1.5
        with pytest.raises(ValidationError):
            CriterionVerdict(**given)  # type: ignore[arg-type]

    def test_a_verdict_requires_reasoning(self) -> None:
        with pytest.raises(ValidationError):
            CriterionVerdict(
                ac_key="ac_a",
                satisfied=True,
                score=0.9,
                uncertainty=0.1,
                reward_hacking_risk=0.0,
                reasoning="",
            )


class TestAssessment:
    def test_two_verdicts_for_one_criterion_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="more than one verdict"):
            SemanticAssessment(
                blueprint_revision=1,
                policy_version=POLICY.version,
                verdicts=(_verdict(), _verdict()),
            )

    def test_an_empty_assessment_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SemanticAssessment(blueprint_revision=1, policy_version=POLICY.version, verdicts=())


class TestStateBinding:
    def test_verdicts_need_matching_mechanical_evidence(self) -> None:
        """증거 없는 판정은 기록되지 않는다 (ADR-0030 §4)."""
        assessment = SemanticAssessment(
            blueprint_revision=1, policy_version=POLICY.version, verdicts=(_verdict(),)
        )
        with pytest.raises(VerdictWithoutEvidenceError):
            VerifyState.start(mission_id="m-1").record_verdicts(assessment)

    def test_a_revision_mismatch_is_rejected(self) -> None:
        state = VerifyState.start(mission_id="m-1").record(_evidence(revision=1))
        assessment = SemanticAssessment(
            blueprint_revision=2, policy_version=POLICY.version, verdicts=(_verdict(),)
        )
        with pytest.raises(VerdictWithoutEvidenceError):
            state.record_verdicts(assessment)

    def test_recording_verdicts_advances_the_sequence(self) -> None:
        state = VerifyState.start(mission_id="m-1").record(_evidence())
        assessment = SemanticAssessment(
            blueprint_revision=1, policy_version=POLICY.version, verdicts=(_verdict(),)
        )
        recorded = state.record_verdicts(assessment)
        assert recorded.sequence == state.sequence + 1
        assert recorded.verdicts == assessment

    def test_new_evidence_invalidates_old_verdicts(self) -> None:
        """재검증은 판정이 딛고 선 증거를 교체하므로 verdicts도 무효다."""
        state = VerifyState.start(mission_id="m-1").record(_evidence())
        state = state.record_verdicts(
            SemanticAssessment(
                blueprint_revision=1, policy_version=POLICY.version, verdicts=(_verdict(),)
            )
        )
        reverified = state.record(_evidence())
        assert reverified.verdicts is None
