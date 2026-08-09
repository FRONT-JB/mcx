"""Verify Gate — CLEAR가 곧 MISSION COMPLETE이며 두 층 전부를 요구한다.

계약: docs/08_VERIFY.md §9 / docs/adr/0028, 0030 §4
"""

from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.verify.evidence import (
    VerificationEvidence,
    VerificationRun,
)
from mission_control.domain.verify.gate import (
    VerifyGateBlockingCondition,
    evaluate_verify_gate,
)
from mission_control.domain.verify.verdict import (
    CriterionVerdict,
    SemanticAssessment,
    SemanticPolicy,
)

POLICY = SemanticPolicy.verify_v1()

COMMANDED = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")
PROSE = AcceptanceCriterion(description="코드가 읽기 좋다")

BLUEPRINT = Blueprint(
    mission_id="m-1",
    revision=1,
    brief_revision=3,
    goal="댓글 기능",
    acceptance_criteria=(COMMANDED, PROSE),
)

PASSED_RUN = VerificationRun(
    ac_key=COMMANDED.key, command="pytest -k list", exit_code=0, passed=True
)


def _evidence(run: VerificationRun = PASSED_RUN, revision: int = 1) -> VerificationEvidence:
    return VerificationEvidence(
        mission_id="m-1",
        blueprint_revision=revision,
        execution_attempt_numbers=(1,),
        runs=(run,),
    )


def _verdict(
    ac_key: str,
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


def _verdicts(*verdicts: CriterionVerdict, revision: int = 1) -> SemanticAssessment:
    return SemanticAssessment(
        blueprint_revision=revision, policy_version=POLICY.version, verdicts=verdicts
    )


def _conditions(
    evidence: VerificationEvidence | None,
    verdicts: SemanticAssessment | None,
    blueprint: Blueprint = BLUEPRINT,
):
    decision = evaluate_verify_gate(
        evidence=evidence, verdicts=verdicts, blueprint=blueprint, policy=POLICY
    )
    return decision, tuple(item.condition for item in decision.gate_blockers)


class TestClear:
    def test_both_layers_passing_declare_mission_complete(self) -> None:
        """두 층 전부 통과 — v1이 처음으로 도달하는 CLEAR다 (ADR-0030 §4)."""
        decision, _ = _conditions(
            _evidence(), _verdicts(_verdict(COMMANDED.key), _verdict(PROSE.key))
        )
        assert decision.outcome == "CLEAR"
        assert decision.mission_complete is True
        assert decision.gate_blockers == ()


class TestHold:
    def test_nothing_recorded_holds_per_layer_and_criterion(self) -> None:
        decision, conditions = _conditions(None, None)

        assert decision.outcome == "HOLD"
        assert conditions.count(VerifyGateBlockingCondition.SEMANTIC_VERDICT_MISSING) == 2
        assert VerifyGateBlockingCondition.CRITERION_UNVERIFIED in conditions

    def test_semantic_cannot_overturn_a_mechanical_failure(self) -> None:
        """만족 verdict가 있어도 깨진 명령은 깨진 것이다 (ADR-0028 §1)."""
        failed = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=3, passed=False
        )
        decision, conditions = _conditions(
            _evidence(failed), _verdicts(_verdict(COMMANDED.key), _verdict(PROSE.key))
        )
        assert decision.outcome == "HOLD"
        assert VerifyGateBlockingCondition.VERIFICATION_FAILED in conditions

    def test_a_low_score_does_not_pass_even_when_satisfied(self) -> None:
        """통과는 satisfied AND score — upstream 관측 그대로다."""
        _, conditions = _conditions(
            _evidence(),
            _verdicts(_verdict(COMMANDED.key, score=0.79), _verdict(PROSE.key)),
        )
        assert VerifyGateBlockingCondition.CRITERION_NOT_SATISFIED in conditions

    def test_uncertainty_asks_for_escalation_not_failure(self) -> None:
        """불확실한 판정은 실패로 세지 않는다 — escalation 대기 HOLD다."""
        decision, conditions = _conditions(
            _evidence(),
            _verdicts(
                _verdict(COMMANDED.key, uncertainty=0.5, satisfied=False, score=0.2),
                _verdict(PROSE.key),
            ),
        )
        assert VerifyGateBlockingCondition.ESCALATION_REQUIRED in conditions
        assert VerifyGateBlockingCondition.CRITERION_NOT_SATISFIED not in conditions

    def test_reward_hacking_vetoes_an_otherwise_passing_verdict(self) -> None:
        _, conditions = _conditions(
            _evidence(),
            _verdicts(_verdict(COMMANDED.key, risk=0.7), _verdict(PROSE.key)),
        )
        assert VerifyGateBlockingCondition.REWARD_HACKING_SUSPECTED in conditions

    def test_stale_layers_do_not_count(self) -> None:
        """이전 revision의 evidence·verdicts는 현재 revision을 지지하지 않는다."""
        current = BLUEPRINT.model_copy(update={"revision": 2})
        decision, conditions = _conditions(
            _evidence(revision=1),
            _verdicts(_verdict(COMMANDED.key), _verdict(PROSE.key), revision=1),
            current,
        )
        assert decision.outcome == "HOLD"
        assert VerifyGateBlockingCondition.CRITERION_UNVERIFIED in conditions
        assert conditions.count(VerifyGateBlockingCondition.SEMANTIC_VERDICT_MISSING) == 2

    def test_a_failed_run_reason_is_derived_from_the_fields(self) -> None:
        missed = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=0, passed=False
        )
        decision, _ = _conditions(_evidence(missed), None)
        assert any("기대한 문구를 찾지 못했다" in reason for reason in decision.blocking_reasons)
