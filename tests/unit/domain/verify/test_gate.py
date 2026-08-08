"""Verify Gate — CLEAR가 곧 MISSION COMPLETE이며 v1은 도달할 수 없다.

계약: docs/08_VERIFY.md §9 / docs/adr/0028-verify-v1-mechanical-contract.md
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

COMMANDED = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")
PROSE = AcceptanceCriterion(description="코드가 읽기 좋다")

BLUEPRINT = Blueprint(
    mission_id="m-1",
    revision=1,
    brief_revision=3,
    goal="댓글 기능",
    acceptance_criteria=(COMMANDED, PROSE),
)


def _evidence(run: VerificationRun, revision: int = 1) -> VerificationEvidence:
    return VerificationEvidence(
        mission_id="m-1",
        blueprint_revision=revision,
        execution_attempt_numbers=(1,),
        runs=(run,),
    )


def _conditions(evidence: VerificationEvidence | None, blueprint: Blueprint = BLUEPRINT):
    decision = evaluate_verify_gate(evidence=evidence, blueprint=blueprint)
    return decision, tuple(item.condition for item in decision.gate_blockers)


class TestHold:
    def test_no_evidence_holds_per_criterion(self) -> None:
        decision, conditions = _conditions(None)

        assert decision.outcome == "HOLD"
        assert VerifyGateBlockingCondition.CRITERION_UNVERIFIED in conditions
        assert VerifyGateBlockingCondition.NOT_MECHANICALLY_VERIFIABLE in conditions

    def test_mechanical_success_still_needs_semantic_verdicts(self) -> None:
        """v1의 CLEAR 불가는 침묵이 아니라 blocker로 드러난다 (ADR-0028)."""
        blueprint = BLUEPRINT.model_copy(update={"acceptance_criteria": (COMMANDED,)})
        passed = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=0, passed=True
        )
        decision, conditions = _conditions(_evidence(passed), blueprint)

        assert decision.outcome == "HOLD"
        assert conditions == (VerifyGateBlockingCondition.SEMANTIC_VERDICT_MISSING,)

    def test_a_failed_run_holds_with_a_derived_reason(self) -> None:
        failed = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=3, passed=False
        )
        decision, conditions = _conditions(_evidence(failed))

        assert VerifyGateBlockingCondition.VERIFICATION_FAILED in conditions
        assert any("status 3" in reason for reason in decision.blocking_reasons)

    def test_an_assertion_miss_is_derived_from_the_fields(self) -> None:
        """exit 0인데 실패면 남은 가능성은 assertion 불일치뿐이다."""
        missed = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=0, passed=False
        )
        decision, _ = _conditions(_evidence(missed))
        assert any("assertion" in reason for reason in decision.blocking_reasons)

    def test_missing_artifacts_and_timeout_reasons(self) -> None:
        missing = VerificationRun(
            ac_key=COMMANDED.key, passed=False, missing_artifacts=("report.md",)
        )
        decision, _ = _conditions(_evidence(missing))
        assert any("report.md" in reason for reason in decision.blocking_reasons)

        timed = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", passed=False, timed_out=True
        )
        decision, _ = _conditions(_evidence(timed))
        assert any("timed out" in reason for reason in decision.blocking_reasons)

    def test_stale_revision_evidence_does_not_count(self) -> None:
        """이전 revision의 검증 결과는 현재 revision을 지지하지 않는다."""
        passed = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=0, passed=True
        )
        current = BLUEPRINT.model_copy(update={"revision": 2})
        _, conditions = _conditions(_evidence(passed, revision=1), current)

        assert VerifyGateBlockingCondition.CRITERION_UNVERIFIED in conditions
