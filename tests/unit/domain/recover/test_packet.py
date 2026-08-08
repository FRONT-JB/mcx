"""실패 packet 파생 — 원천 구분, 결정적 분류, 예산.

계약: docs/adr/0031-recover-v1-failure-and-retry-contract.md §1~§4
"""

from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.execute.state import CapabilityEnvelope, ExecuteState
from mission_control.domain.recover.packet import (
    FailureClassification,
    FailureSource,
    RecoverPolicy,
    derive_failure_packets,
)
from mission_control.domain.verify.evidence import (
    VerificationEvidence,
    VerificationRun,
    VerifyState,
)
from mission_control.domain.verify.verdict import (
    CriterionVerdict,
    SemanticAssessment,
    SemanticPolicy,
)

POLICY = RecoverPolicy.recover_v1()
SEMANTIC = SemanticPolicy.verify_v1()
ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission")

COMMANDED = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")

BLUEPRINT = Blueprint(
    mission_id="m-1",
    revision=1,
    brief_revision=3,
    goal="댓글 기능",
    acceptance_criteria=(COMMANDED,),
)


def _failed_execution(*errors: str) -> ExecuteState:
    state = ExecuteState.start(mission_id="m-1")
    for index, error in enumerate(errors):
        state = state.dispatch(
            execution_id=f"exec-m-1-{index + 1:04d}",
            runtime_backend="fake",
            blueprint_revision=1,
            ac_key=COMMANDED.key,
            envelope=ENVELOPE,
        ).record_result(succeeded=False, error=error)
    return state


def _executed(count: int = 1) -> ExecuteState:
    state = ExecuteState.start(mission_id="m-1")
    for index in range(count):
        state = state.dispatch(
            execution_id=f"exec-m-1-{index + 1:04d}",
            runtime_backend="fake",
            blueprint_revision=1,
            ac_key=COMMANDED.key,
            envelope=ENVELOPE,
        ).record_result(succeeded=True)
    return state


def _verify_with_run(run: VerificationRun, *, attempt_numbers: tuple[int, ...]) -> VerifyState:
    return VerifyState.start(mission_id="m-1").record(
        VerificationEvidence(
            mission_id="m-1",
            blueprint_revision=1,
            execution_attempt_numbers=attempt_numbers,
            runs=(run,),
        )
    )


def _derive(execute_state: ExecuteState, verify_state: VerifyState | None = None):
    return derive_failure_packets(
        blueprint=BLUEPRINT,
        execute_state=execute_state,
        verify_state=verify_state or VerifyState.start(mission_id="m-1"),
        semantic_policy=SEMANTIC,
        policy=POLICY,
    )


class TestExecutionFailures:
    def test_a_failed_execution_becomes_a_packet(self) -> None:
        packets = _derive(_failed_execution("tests exploded"))

        assert len(packets) == 1
        packet = packets[0]
        assert packet.source is FailureSource.EXECUTION_FAILED
        assert packet.classification is FailureClassification.UNCLASSIFIED
        assert packet.error_excerpt == "tests exploded"
        assert packet.retries_used == 0
        assert packet.retryable(POLICY) is True

    def test_a_hard_precondition_is_blocked(self) -> None:
        packets = _derive(_failed_execution("bash: permission denied for /etc"))
        assert packets[0].classification is FailureClassification.BLOCKED
        assert packets[0].retryable(POLICY) is False

    def test_the_same_error_three_times_is_a_stall(self) -> None:
        packets = _derive(_failed_execution("boom", "boom", "boom"))
        assert packets[0].classification is FailureClassification.STALL
        assert packets[0].retryable(POLICY) is False

    def test_two_identical_errors_are_not_yet_a_stall(self) -> None:
        packets = _derive(_failed_execution("boom", "boom"))
        assert packets[0].classification is FailureClassification.UNCLASSIFIED

    def test_the_budget_counts_retries_not_the_first_run(self) -> None:
        packets = _derive(_failed_execution("a", "b", "c"))
        assert packets[0].retries_used == 2
        assert packets[0].budget_exhausted(POLICY) is True
        assert packets[0].retryable(POLICY) is False


class TestVerifyFailures:
    def test_a_failed_mechanical_run_becomes_a_packet(self) -> None:
        run = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=3, passed=False
        )
        packets = _derive(_executed(), _verify_with_run(run, attempt_numbers=(1,)))

        assert packets[0].source is FailureSource.MECHANICAL_FAILED
        assert "status 3" in packets[0].error_excerpt

    def test_a_corrected_attempt_awaiting_reverification_is_not_a_failure(self) -> None:
        """교정 재실행 뒤의 오래된 실패 증거는 packet이 아니다 — 재검증 대기다."""
        run = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=3, passed=False
        )
        # attempt 1을 검증했고 실패했지만, 교정으로 attempt 2가 실행됐다.
        packets = _derive(_executed(count=2), _verify_with_run(run, attempt_numbers=(1,)))
        assert packets == ()

    def test_an_unsatisfied_verdict_becomes_a_packet(self) -> None:
        run = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=0, passed=True
        )
        state = _verify_with_run(run, attempt_numbers=(1,)).record_verdicts(
            SemanticAssessment(
                blueprint_revision=1,
                policy_version=SEMANTIC.version,
                verdicts=(
                    CriterionVerdict(
                        ac_key=COMMANDED.key,
                        satisfied=False,
                        score=0.2,
                        uncertainty=0.1,
                        reward_hacking_risk=0.0,
                        reasoning="목록 갱신이 관찰되지 않는다",
                    ),
                ),
            )
        )
        packets = _derive(_executed(), state)
        assert packets[0].source is FailureSource.SEMANTIC_NOT_SATISFIED
        assert packets[0].retryable(POLICY) is True

    def test_an_uncertain_verdict_asks_for_a_user_not_a_retry(self) -> None:
        run = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=0, passed=True
        )
        state = _verify_with_run(run, attempt_numbers=(1,)).record_verdicts(
            SemanticAssessment(
                blueprint_revision=1,
                policy_version=SEMANTIC.version,
                verdicts=(
                    CriterionVerdict(
                        ac_key=COMMANDED.key,
                        satisfied=True,
                        score=0.9,
                        uncertainty=0.6,
                        reward_hacking_risk=0.0,
                        reasoning="관찰 수단이 불충분하다",
                    ),
                ),
            )
        )
        packets = _derive(_executed(), state)
        assert packets[0].source is FailureSource.ESCALATION_PENDING
        assert packets[0].retryable(POLICY) is False

    def test_a_passing_mission_yields_no_packets(self) -> None:
        run = VerificationRun(
            ac_key=COMMANDED.key, command="pytest -k list", exit_code=0, passed=True
        )
        packets = _derive(_executed(), _verify_with_run(run, attempt_numbers=(1,)))
        assert packets == ()
