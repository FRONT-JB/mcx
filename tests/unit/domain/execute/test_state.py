"""Execute 상태 — attempt 규칙, provenance 강제, 상태-결과 일관성.

계약: docs/07_EXECUTE.md §6, §7 / docs/adr/0024-execute-v1-execution-model.md
Test Matrix: Sequence·Attempt·Telemetry 행 (docs/07_EXECUTE.md §13)
"""

from pydantic import ValidationError
import pytest

from mission_control.domain.execute.state import (
    AttemptStatus,
    CapabilityEnvelope,
    ExecuteState,
    ExecutionAttempt,
    HaltedByFailedCriterionError,
    NoOpenAttemptError,
    OpenAttemptError,
)

ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission", allowed_tools=("edit", "bash"))


def _dispatched(
    state: ExecuteState, *, ac_key: str = "ac_a", blueprint_revision: int = 1
) -> ExecuteState:
    return state.dispatch(
        execution_id=f"exec-m-1-{len(state.attempts) + 1:04d}",
        runtime_backend="fake",
        blueprint_revision=blueprint_revision,
        ac_key=ac_key,
        envelope=ENVELOPE,
    )


class TestDispatch:
    def test_dispatch_records_provenance_and_envelope(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"))

        attempt = state.attempts[0]
        assert attempt.number == 1
        assert attempt.execution_id == "exec-m-1-0001"
        assert attempt.runtime_backend == "fake"
        assert attempt.blueprint_revision == 1
        assert attempt.ac_key == "ac_a"
        assert attempt.envelope == ENVELOPE
        assert attempt.status is AttemptStatus.DISPATCHED
        assert state.sequence == 2

    def test_a_second_dispatch_needs_the_first_result(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"))
        with pytest.raises(OpenAttemptError):
            _dispatched(state, ac_key="ac_b")

    def test_a_failed_criterion_blocks_other_criteria(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"))
        state = state.record_result(succeeded=False, error="tests exploded")

        with pytest.raises(HaltedByFailedCriterionError):
            _dispatched(state, ac_key="ac_b")

    def test_the_failed_criterion_itself_may_be_retried(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"))
        state = state.record_result(succeeded=False, error="tests exploded")

        retried = _dispatched(state, ac_key="ac_a")
        assert retried.attempts[-1].number == 2
        assert retried.attempts[-1].ac_key == "ac_a"

    def test_a_new_blueprint_revision_lifts_the_halt(self) -> None:
        """revision이 바뀌면 이전 revision의 실패가 새 작업을 막지 않는다."""
        state = _dispatched(ExecuteState.start(mission_id="m-1"))
        state = state.record_result(succeeded=False, error="tests exploded")

        moved_on = _dispatched(state, ac_key="ac_b", blueprint_revision=2)
        assert moved_on.attempts[-1].blueprint_revision == 2


class TestRecordResult:
    def test_success_becomes_executed_unverified(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"))
        resolved = state.record_result(
            succeeded=True, native_session_id="sess-9", result_summary="구현 완료"
        )

        attempt = resolved.attempts[-1]
        assert attempt.status is AttemptStatus.EXECUTED_UNVERIFIED
        assert attempt.native_session_id == "sess-9"
        assert resolved.open_attempt is None

    def test_failure_requires_an_error(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"))
        with pytest.raises(ValidationError, match="requires an error"):
            state.record_result(succeeded=False)

    def test_success_cannot_carry_an_error(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"))
        with pytest.raises(ValidationError, match="cannot carry an error"):
            state.record_result(succeeded=True, error="but it failed?")

    def test_a_result_needs_an_open_attempt(self) -> None:
        with pytest.raises(NoOpenAttemptError):
            ExecuteState.start(mission_id="m-1").record_result(succeeded=True)

    def test_recording_does_not_mutate_the_previous_state(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"))
        state.record_result(succeeded=True)
        assert state.attempts[-1].status is AttemptStatus.DISPATCHED


class TestStructuralInvariants:
    def test_attempt_numbers_must_be_contiguous(self) -> None:
        attempt = ExecutionAttempt(
            number=2,
            execution_id="exec-m-1-0002",
            runtime_backend="fake",
            blueprint_revision=1,
            ac_key="ac_a",
            envelope=ENVELOPE,
        )
        with pytest.raises(ValidationError, match="contiguous"):
            ExecuteState(mission_id="m-1", attempts=(attempt,))

    def test_only_the_last_attempt_may_be_open(self) -> None:
        open_first = ExecutionAttempt(
            number=1,
            execution_id="exec-m-1-0001",
            runtime_backend="fake",
            blueprint_revision=1,
            ac_key="ac_a",
            envelope=ENVELOPE,
        )
        resolved_second = open_first.model_copy(
            update={
                "number": 2,
                "status": AttemptStatus.EXECUTED_UNVERIFIED,
            }
        )
        with pytest.raises(ValidationError, match="last attempt"):
            ExecuteState(mission_id="m-1", attempts=(open_first, resolved_second))

    def test_a_dispatched_attempt_cannot_carry_a_result(self) -> None:
        with pytest.raises(ValidationError, match="cannot carry a result"):
            ExecutionAttempt(
                number=1,
                execution_id="exec-m-1-0001",
                runtime_backend="fake",
                blueprint_revision=1,
                ac_key="ac_a",
                envelope=ENVELOPE,
                result_summary="아직 실행 전인데 결과가 있다",
            )

    @pytest.mark.parametrize(
        "missing",
        [
            {"execution_id": ""},
            {"runtime_backend": ""},
            {"ac_key": ""},
            {"blueprint_revision": 0},
            {"number": 0},
        ],
    )
    def test_missing_provenance_is_rejected(self, missing: dict[str, object]) -> None:
        """provenance 네 항목이 없는 기록은 생성 자체가 거부된다 (ADR-0023 §3)."""
        given: dict[str, object] = {
            "number": 1,
            "execution_id": "exec-m-1-0001",
            "runtime_backend": "fake",
            "blueprint_revision": 1,
            "ac_key": "ac_a",
            "envelope": ENVELOPE,
        }
        given.update(missing)
        with pytest.raises(ValidationError):
            ExecutionAttempt(**given)  # type: ignore[arg-type]

    def test_latest_for_is_scoped_to_the_revision(self) -> None:
        state = _dispatched(ExecuteState.start(mission_id="m-1"))
        state = state.record_result(succeeded=True)

        assert state.latest_for(ac_key="ac_a", blueprint_revision=1) is not None
        assert state.latest_for(ac_key="ac_a", blueprint_revision=2) is None
