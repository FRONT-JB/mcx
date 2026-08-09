"""Verify 증거 — run 판정, 필드 일관성, 상태 기록.

계약: docs/adr/0028-verify-v1-mechanical-contract.md §3~§4
Test Matrix: Mechanical 행 (docs/08_VERIFY.md §12)
"""

from pydantic import ValidationError
import pytest

from mission_control.domain.blueprint.spec import AcceptanceCriterion
from mission_control.domain.verify.evidence import (
    OUTPUT_TAIL_CHARS,
    CommandExecution,
    UnverifiableCriterionError,
    VerificationEvidence,
    VerificationRun,
    VerifyState,
    judge_run,
)

COMMANDED = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")
ASSERTED = AcceptanceCriterion(
    description="OK가 출력된다", verify_command="echo OK", output_assertion="OK"
)
ARTIFACTS_ONLY = AcceptanceCriterion(
    description="보고서가 남는다", expected_artifacts=("report.md",)
)
PROSE = AcceptanceCriterion(description="코드가 읽기 좋다")


def _passed_run(ac_key: str = "ac_a") -> VerificationRun:
    return VerificationRun(
        ac_key=ac_key, command="pytest", exit_code=0, passed=True, output_tail="ok"
    )


class TestJudgeRun:
    def test_missing_artifacts_fail_without_running_the_command(self) -> None:
        run = judge_run(
            criterion=ARTIFACTS_ONLY,
            missing_artifacts=("report.md",),
            execution=None,
            output_ref=None,
        )
        assert run.passed is False
        assert run.missing_artifacts == ("report.md",)
        assert run.command is None
        assert run.exit_code is None

    def test_artifacts_only_contract_passes_when_all_exist(self) -> None:
        run = judge_run(
            criterion=ARTIFACTS_ONLY, missing_artifacts=(), execution=None, output_ref=None
        )
        assert run.passed is True

    def test_exit_zero_passes_and_keeps_the_output(self) -> None:
        run = judge_run(
            criterion=COMMANDED,
            missing_artifacts=(),
            execution=CommandExecution(exit_code=0, output="3 passed"),
            output_ref="ref-1",
        )
        assert run.passed is True
        assert run.command == "pytest -k list"
        assert run.output_ref == "ref-1"
        assert run.output_tail == "3 passed"

    def test_a_nonzero_exit_fails(self) -> None:
        run = judge_run(
            criterion=COMMANDED,
            missing_artifacts=(),
            execution=CommandExecution(exit_code=3, output="boom"),
            output_ref="ref-1",
        )
        assert run.passed is False
        assert run.exit_code == 3

    def test_the_output_assertion_must_appear(self) -> None:
        found = judge_run(
            criterion=ASSERTED,
            missing_artifacts=(),
            execution=CommandExecution(exit_code=0, output="OK\n"),
            output_ref=None,
        )
        absent = judge_run(
            criterion=ASSERTED,
            missing_artifacts=(),
            execution=CommandExecution(exit_code=0, output="done\n"),
            output_ref=None,
        )
        assert found.passed is True
        assert absent.passed is False

    def test_a_timeout_fails_without_an_exit_code(self) -> None:
        run = judge_run(
            criterion=COMMANDED,
            missing_artifacts=(),
            execution=CommandExecution(timed_out=True),
            output_ref=None,
        )
        assert run.passed is False
        assert run.timed_out is True
        assert run.exit_code is None

    def test_the_tail_is_bounded(self) -> None:
        long_output = "x" * (OUTPUT_TAIL_CHARS * 2)
        run = judge_run(
            criterion=COMMANDED,
            missing_artifacts=(),
            execution=CommandExecution(exit_code=0, output=long_output),
            output_ref=None,
        )
        assert len(run.output_tail) == OUTPUT_TAIL_CHARS

    def test_a_contract_less_criterion_cannot_be_judged(self) -> None:
        with pytest.raises(UnverifiableCriterionError):
            judge_run(criterion=PROSE, missing_artifacts=(), execution=None, output_ref=None)

    def test_a_command_contract_requires_an_execution(self) -> None:
        with pytest.raises(ValueError, match="실행 결과가 오지 않았다"):
            judge_run(criterion=COMMANDED, missing_artifacts=(), execution=None, output_ref=None)


class TestRunConsistency:
    def test_missing_artifacts_preclude_command_execution(self) -> None:
        with pytest.raises(ValidationError, match="명령을 실행하지 않는다"):
            VerificationRun(
                ac_key="ac_a",
                command="pytest",
                exit_code=0,
                passed=False,
                missing_artifacts=("report.md",),
            )

    def test_an_unexecuted_command_cannot_carry_results(self) -> None:
        with pytest.raises(ValidationError, match="실행하지 않은 명령"):
            VerificationRun(ac_key="ac_a", passed=False, exit_code=1)

    @pytest.mark.parametrize(
        "fields",
        [
            {"command": "pytest", "passed": True, "timed_out": True},
            {"command": "pytest", "exit_code": 3, "passed": True},
            {"passed": True, "missing_artifacts": ("report.md",)},
        ],
    )
    def test_a_pass_cannot_coexist_with_a_failure_signal(self, fields: dict) -> None:
        with pytest.raises(ValidationError):
            VerificationRun(ac_key="ac_a", **fields)

    def test_a_completed_run_requires_an_exit_code(self) -> None:
        with pytest.raises(ValidationError, match="exit code가 필요하다"):
            VerificationRun(ac_key="ac_a", command="pytest", passed=False)


class TestEvidence:
    def test_two_runs_for_one_criterion_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="실행 기록이 둘 이상"):
            VerificationEvidence(
                mission_id="m-1",
                blueprint_revision=1,
                execution_attempt_numbers=(1,),
                runs=(_passed_run(), _passed_run()),
            )

    def test_evidence_requires_execution_lineage(self) -> None:
        """실행 attempt 없이 만들어지는 증거는 없다 (ADR-0026)."""
        with pytest.raises(ValidationError):
            VerificationEvidence(
                mission_id="m-1",
                blueprint_revision=1,
                execution_attempt_numbers=(),
            )


class TestVerifyState:
    def test_recording_replaces_evidence_and_advances_the_sequence(self) -> None:
        evidence = VerificationEvidence(
            mission_id="m-1",
            blueprint_revision=1,
            execution_attempt_numbers=(1,),
            runs=(_passed_run(),),
        )
        state = VerifyState.start(mission_id="m-1").record(evidence)

        assert state.sequence == 2
        assert state.evidence == evidence

    def test_evidence_for_another_mission_is_rejected(self) -> None:
        evidence = VerificationEvidence(
            mission_id="m-2",
            blueprint_revision=1,
            execution_attempt_numbers=(1,),
        )
        with pytest.raises(ValueError, match="기록할 수 없다"):
            VerifyState.start(mission_id="m-1").record(evidence)
