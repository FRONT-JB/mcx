"""job은 원장에서 유도된다 — 새 저장소가 없다 (ADR-0041 §4·§5).

별도 job 테이블을 두면 프로세스가 죽는 순간 원장과 어긋나고, 그때 "누가
이기는가"를 또 정해야 한다. 이 파일은 그 규칙이 필요 없다는 것을 고정한다.
"""

import asyncio
from pathlib import Path

import pytest

from mission_control.cancellation import cancel_when, is_cancelled, observed
from mission_control.cli.journal import MissionJournal
from mission_control.cli.progress import ProgressTail
from mission_control.mcp.jobs import (
    JobState,
    UnknownJobError,
    job_id,
    job_view,
    parse_job_id,
    request_cancel,
)
from mission_control.progress import RuntimeActivity


def _journal(root: Path) -> MissionJournal:
    return MissionJournal(root=root, mission_id="m")


def _open(root: Path, command: str = "execute next") -> int:
    return _journal(root).open(command=command, at="2026-08-09T00:00:00+00:00")


def _close(root: Path, sequence: int, exit_code: int) -> None:
    _journal(root).close(
        sequence=sequence,
        at="2026-08-09T00:01:00+00:00",
        duration_seconds=60.0,
        exit_code=exit_code,
        calls={},
    )


class TestStateComesFromTheJournal:
    def test_an_unpaired_start_is_running(self, tmp_path: Path) -> None:
        sequence = _open(tmp_path)

        assert job_view(root=tmp_path, job=job_id(mission_id="m", sequence=sequence)).state is (
            JobState.RUNNING
        )

    def test_a_dead_process_stays_running_not_lost(self, tmp_path: Path) -> None:
        """upstream의 ``interrupted``를 따로 두지 않는 이유 — 짝 없는 start가 그 사실이다."""
        sequence = _open(tmp_path)
        # 프로세스가 죽었다고 가정: end 줄이 없다.

        view = job_view(root=tmp_path, job=job_id(mission_id="m", sequence=sequence))

        assert view.state is JobState.RUNNING
        assert view.finished_at is None

    @pytest.mark.parametrize(
        ("exit_code", "expected"),
        [(0, JobState.COMPLETED), (2, JobState.HOLD), (1, JobState.FAILED)],
    )
    def test_exit_codes_map_to_states(
        self, tmp_path: Path, exit_code: int, expected: JobState
    ) -> None:
        sequence = _open(tmp_path)
        _close(tmp_path, sequence, exit_code)

        assert job_view(root=tmp_path, job=job_id(mission_id="m", sequence=sequence)).state is (
            expected
        )

    def test_a_cancel_marker_shows_as_cancel_requested(self, tmp_path: Path) -> None:
        """요청과 실제 취소는 다른 사실이다 — 마커만으로는 아직 도는 중이다."""
        sequence = _open(tmp_path)
        request_cancel(root=tmp_path, mission_id="m", sequence=sequence)

        assert job_view(root=tmp_path, job=job_id(mission_id="m", sequence=sequence)).state is (
            JobState.CANCEL_REQUESTED
        )

    def test_a_finished_job_ignores_a_stale_marker(self, tmp_path: Path) -> None:
        sequence = _open(tmp_path)
        request_cancel(root=tmp_path, mission_id="m", sequence=sequence)
        _close(tmp_path, sequence, 0)

        assert job_view(root=tmp_path, job=job_id(mission_id="m", sequence=sequence)).state is (
            JobState.COMPLETED
        )


class TestJobIds:
    def test_round_trip(self) -> None:
        assert parse_job_id(job_id(mission_id="m-1", sequence=7)) == ("m-1", 7)

    @pytest.mark.parametrize("bad", ["m-1", "m-1#0", "#3", "m 1#3", "../x#1"])
    def test_malformed_ids_are_refused(self, bad: str) -> None:
        with pytest.raises(UnknownJobError):
            parse_job_id(bad)

    def test_an_unknown_sequence_is_refused(self, tmp_path: Path) -> None:
        _open(tmp_path)

        with pytest.raises(UnknownJobError):
            job_view(root=tmp_path, job=job_id(mission_id="m", sequence=99))


class TestCancellationIsObserved:
    def test_without_an_observer_nothing_is_cancelled(self) -> None:
        assert observed() is False
        assert is_cancelled() is False

    def test_the_observer_sees_the_marker(self, tmp_path: Path) -> None:
        marker = tmp_path / "cancel_m_1"

        with cancel_when(marker.exists):
            assert observed() is True
            assert is_cancelled() is False
            marker.write_text("cancel\n", encoding="utf-8")
            assert is_cancelled() is True

    def test_the_observer_is_scoped_to_its_block(self, tmp_path: Path) -> None:
        marker = tmp_path / "cancel_m_1"
        marker.write_text("cancel\n", encoding="utf-8")

        with cancel_when(marker.exists):
            assert is_cancelled() is True

        assert observed() is False

    async def test_concurrent_commands_do_not_share_an_observer(self, tmp_path: Path) -> None:
        """ContextVar라 한 명령의 취소가 다른 명령을 멈추지 않는다."""
        cancelled = tmp_path / "a"
        cancelled.write_text("x", encoding="utf-8")

        async def under(marker: Path) -> bool:
            with cancel_when(marker.exists):
                await asyncio.sleep(0)
                return is_cancelled()

        first, second = await asyncio.gather(under(cancelled), under(tmp_path / "b"))

        assert (first, second) == (True, False)


class TestActivityAnswersWhatTheJournalCannot:
    """원장은 명령 단위다 — 그 안에서 무엇을 하는지는 진행 꼬리가 답한다 (ADR-0049 §4)."""

    def test_a_running_job_reports_its_last_progress_line(self, tmp_path: Path) -> None:
        sequence = _open(tmp_path)
        ProgressTail(root=tmp_path, mission_id="m", sequence=sequence).record(
            RuntimeActivity(kind="tool", tool="command_execution", detail="pytest tests/"),
            at="2026-08-09T00:00:30+00:00",
        )

        view = job_view(root=tmp_path, job=job_id(mission_id="m", sequence=sequence))

        assert view.state is JobState.RUNNING
        assert view.activity == "command_execution pytest tests/"

    def test_no_progress_record_does_not_break_the_lookup(self, tmp_path: Path) -> None:
        sequence = _open(tmp_path)

        assert job_view(root=tmp_path, job=job_id(mission_id="m", sequence=sequence)).activity is (
            None
        )
