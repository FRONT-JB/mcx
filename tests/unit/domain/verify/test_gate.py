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
    proven_criteria,
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


class TestProvenCriteria:
    """checkpoint가 커밋하는 것과 Gate가 인정하는 것은 같아야 한다 (ADR-0046 §2)."""

    def _proven(self, evidence, verdicts, blueprint: Blueprint = BLUEPRINT):
        return proven_criteria(
            evidence=evidence, verdicts=verdicts, blueprint=blueprint, policy=POLICY
        )

    def test_clear_means_every_criterion_is_proven(self) -> None:
        evidence = _evidence()
        verdicts = _verdicts(_verdict(COMMANDED.key), _verdict(PROSE.key))
        decision, _ = _conditions(evidence, verdicts)

        assert decision.outcome == "CLEAR"
        assert self._proven(evidence, verdicts) == (COMMANDED.key, PROSE.key)

    def test_nothing_recorded_proves_nothing(self) -> None:
        assert self._proven(None, None) == ()

    def test_a_failed_mechanical_run_is_not_proven_but_its_peer_is(self) -> None:
        """한 AC의 실패가 다른 AC의 입증을 지우지 않는다 — 그래서 부분 고정이 된다."""
        failed = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=1, passed=False
        )
        verdicts = _verdicts(_verdict(COMMANDED.key), _verdict(PROSE.key))

        assert self._proven(_evidence(failed), verdicts) == (PROSE.key,)

    def test_a_missing_verdict_is_not_proven(self) -> None:
        assert self._proven(_evidence(), _verdicts(_verdict(COMMANDED.key))) == (COMMANDED.key,)

    def test_an_escalating_verdict_is_not_proven(self) -> None:
        """불확실성이 임계를 넘으면 Gate가 막는다 — 커밋도 하지 않는다."""
        verdicts = _verdicts(
            _verdict(COMMANDED.key), _verdict(PROSE.key, uncertainty=0.99)
        )

        assert self._proven(_evidence(), verdicts) == (COMMANDED.key,)

    def test_another_revisions_results_prove_nothing(self) -> None:
        stale = _verdicts(_verdict(COMMANDED.key), _verdict(PROSE.key), revision=9)

        assert self._proven(_evidence(revision=9), stale) == ()

    def test_it_agrees_with_the_gate_on_every_shape(self) -> None:
        """두 판정이 갈리면 커밋된 것과 Gate가 인정한 것이 어긋난다."""
        shapes = [
            (None, None),
            (_evidence(), None),
            (None, _verdicts(_verdict(COMMANDED.key), _verdict(PROSE.key))),
            (_evidence(), _verdicts(_verdict(COMMANDED.key), _verdict(PROSE.key))),
            (
                _evidence(),
                _verdicts(_verdict(COMMANDED.key), _verdict(PROSE.key, satisfied=False)),
            ),
        ]
        for evidence, verdicts in shapes:
            decision, _ = _conditions(evidence, verdicts)
            proven = self._proven(evidence, verdicts)
            everything = tuple(item.key for item in BLUEPRINT.acceptance_criteria)
            assert (decision.outcome == "CLEAR") == (proven == everything)
