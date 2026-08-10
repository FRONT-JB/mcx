"""Mission record — 합법 전이 그래프, 완료 규칙, 불변성 (ADR-0037·0038 §5)."""

import pytest

from mission_control.domain.mission import (
    ALLOWED_TRANSITIONS,
    CompletionNotFromVerifyError,
    InvalidStageTransitionError,
    MissionCompletedError,
    MissionRecord,
    MissionStatus,
)
from mission_control.domain.stage import Stage


def record_at(stage: Stage) -> MissionRecord:
    record = MissionRecord.create(mission_id="m", workspace="/ws")
    path = {
        Stage.BRIEF: (),
        Stage.BLUEPRINT: (Stage.BLUEPRINT,),
        Stage.EXECUTE: (Stage.BLUEPRINT, Stage.EXECUTE),
        Stage.VERIFY: (Stage.BLUEPRINT, Stage.EXECUTE, Stage.VERIFY),
        Stage.RECOVER: (Stage.BLUEPRINT, Stage.EXECUTE, Stage.VERIFY, Stage.RECOVER),
    }[stage]
    for destination in path:
        record = record.transit(destination=destination, at="t", reason="test")
    return record


def test_creation_starts_at_brief_and_active() -> None:
    record = MissionRecord.create(mission_id="m", workspace="/ws")
    assert record.current_stage is Stage.BRIEF
    assert record.status is MissionStatus.ACTIVE
    assert record.transitions == ()
    assert record.sequence == 1


def test_forward_transition_records_time_and_reason() -> None:
    record = MissionRecord.create(mission_id="m", workspace="/ws")
    moved = record.transit(destination=Stage.BLUEPRINT, at="2026-08-09T00:00:00Z", reason="r")
    assert moved.current_stage is Stage.BLUEPRINT
    assert moved.sequence == record.sequence + 1
    assert moved.transitions[-1].source is Stage.BRIEF
    assert moved.transitions[-1].at == "2026-08-09T00:00:00Z"
    assert moved.transitions[-1].reason == "r"


def test_same_stage_is_a_no_op_not_a_transition() -> None:
    record = record_at(Stage.EXECUTE)
    assert record.transit(destination=Stage.EXECUTE, at="t", reason="again") is record


@pytest.mark.parametrize(
    ("source", "destination"),
    [
        (Stage.BRIEF, Stage.EXECUTE),  # Lifecycle §9.1 금지 행
        (Stage.BRIEF, Stage.VERIFY),
        (Stage.BLUEPRINT, Stage.VERIFY),
        (Stage.BLUEPRINT, Stage.BRIEF),  # §9 표에 없는 행
    ],
)
def test_transitions_outside_lifecycle_table_are_rejected(
    source: Stage, destination: Stage
) -> None:
    with pytest.raises(InvalidStageTransitionError):
        record_at(source).transit(destination=destination, at="t", reason="x")


def test_lifecycle_table_is_mirrored_exactly() -> None:
    """§9 표에서 도출한 그래프가 코드와 문서 어느 쪽에서도 조용히 늘지 않는다."""
    assert ALLOWED_TRANSITIONS == {
        Stage.BRIEF: frozenset({Stage.BLUEPRINT}),
        Stage.BLUEPRINT: frozenset({Stage.EXECUTE}),
        Stage.EXECUTE: frozenset({Stage.VERIFY, Stage.RECOVER, Stage.BRIEF, Stage.BLUEPRINT}),
        Stage.VERIFY: frozenset({Stage.RECOVER, Stage.BRIEF, Stage.BLUEPRINT}),
        Stage.RECOVER: frozenset({Stage.VERIFY, Stage.EXECUTE, Stage.BRIEF, Stage.BLUEPRINT}),
    }


def test_complete_only_from_verify() -> None:
    done = record_at(Stage.VERIFY).complete(at="t-done")
    assert done.status is MissionStatus.COMPLETE
    assert done.completed_at == "t-done"

    for stage in (Stage.BRIEF, Stage.BLUEPRINT, Stage.EXECUTE, Stage.RECOVER):
        with pytest.raises(CompletionNotFromVerifyError):
            record_at(stage).complete(at="t")


def test_completed_record_is_closed_to_changes() -> None:
    done = record_at(Stage.VERIFY).complete(at="t")
    with pytest.raises(MissionCompletedError):
        done.transit(destination=Stage.RECOVER, at="t", reason="late")
    with pytest.raises(MissionCompletedError):
        done.complete(at="t")
