"""진행 꼬리 — 원장이 비워 둔 칸 (ADR-0049 §4·§5).

설치되지 않으면 아무 일도 일어나지 않는다는 것이 이 층의 핵심 성질이다.
그게 깨지면 취소 관측과 같은 실패를 반복한다 — 관측 코드가 실행 경로의
동작을 바꾸는 것.
"""

from pathlib import Path
import stat

import pytest

from mission_control.cli.progress import ProgressTail, last_activity, progress_path
from mission_control.progress import RuntimeActivity, observed, record, report_to


def tail(root: Path) -> ProgressTail:
    return ProgressTail(root=root, mission_id="m-1", sequence=3)


class TestTheAmbientSink:
    def test_nothing_happens_without_a_sink(self, tmp_path: Path) -> None:
        """싱크가 없으면 기존 동작이 한 글자도 바뀌지 않는다."""
        assert observed() is False
        record(RuntimeActivity(kind="tool", tool="command_execution", detail="pytest"))

        assert list(tmp_path.iterdir()) == []

    def test_a_sink_receives_what_was_recorded(self) -> None:
        seen: list[RuntimeActivity] = []
        with report_to(seen.append):
            assert observed() is True
            record(RuntimeActivity(kind="tool", tool="x", detail="y"))

        assert [item.detail for item in seen] == ["y"]
        assert observed() is False


class TestTheTailFile:
    def test_it_appends_and_reads_back_the_last_line(self, tmp_path: Path) -> None:
        writer = tail(tmp_path)
        writer.record(RuntimeActivity(kind="tool", tool="command_execution", detail="a"), at="t1")
        writer.record(RuntimeActivity(kind="tool", tool="file_change", detail="src/b.py"), at="t2")

        line = last_activity(root=tmp_path, mission_id="m-1", sequence=3)

        assert line is not None
        assert line.render() == "file_change src/b.py"
        assert line.at == "t2"

    def test_the_file_is_owner_only(self, tmp_path: Path) -> None:
        writer = tail(tmp_path)
        writer.record(RuntimeActivity(kind="tool", tool="x", detail="y"), at="t1")

        assert stat.S_IMODE(writer.path.stat().st_mode) == 0o600

    def test_its_name_is_the_job_coordinate(self, tmp_path: Path) -> None:
        assert progress_path(root=tmp_path, mission_id="m-1", sequence=3).name == (
            "progress_m-1_3.jsonl"
        )

    def test_an_unsafe_mission_id_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="쓸 수 없는 mission id"):
            progress_path(root=tmp_path, mission_id="../escape", sequence=1)

    def test_no_file_means_no_activity(self, tmp_path: Path) -> None:
        assert last_activity(root=tmp_path, mission_id="m-1", sequence=3) is None

    def test_a_broken_line_does_not_kill_the_read(self, tmp_path: Path) -> None:
        """진행 기록 한 줄 때문에 job 조회가 죽으면 관측 수단을 잃는다."""
        writer = tail(tmp_path)
        writer.record(RuntimeActivity(kind="tool", tool="x", detail="good"), at="t1")
        with writer.path.open("a", encoding="utf-8") as handle:
            handle.write("{broken\n")

        line = last_activity(root=tmp_path, mission_id="m-1", sequence=3)

        assert line is not None
        assert line.detail == "good"

    def test_a_credential_never_reaches_the_file(self, tmp_path: Path) -> None:
        secret = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
        writer = tail(tmp_path)
        writer.record(
            RuntimeActivity(kind="tool", tool="command_execution", detail=f"export TOKEN={secret}"),
            at="t1",
        )

        assert secret not in writer.path.read_text(encoding="utf-8")
