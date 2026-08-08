"""명령 원장 — append-only, 짝 없는 start가 곧 "진행 중" (ADR-0038 §6.1 a)."""

from pathlib import Path

import pytest

from mission_control.cli.journal import MissionJournal, total_calls


def test_open_and_close_form_one_entry(tmp_path: Path) -> None:
    journal = MissionJournal(root=tmp_path, mission_id="m-1")
    sequence = journal.open(command="brief start", at="2026-08-09T00:00:00+00:00")
    journal.close(
        sequence=sequence,
        at="2026-08-09T00:00:12+00:00",
        duration_seconds=12.0,
        exit_code=0,
        calls={"claude": 3},
    )

    (entry,) = journal.entries()
    assert entry.command == "brief start"
    assert entry.exit_code == 0
    assert entry.duration_seconds == 12.0
    assert entry.calls == {"claude": 3}
    assert not entry.in_progress


def test_an_unclosed_command_stays_in_progress(tmp_path: Path) -> None:
    """프로세스가 중간에 죽어도 그 명령이 조용히 사라지지 않는다."""
    journal = MissionJournal(root=tmp_path, mission_id="m-1")
    journal.open(command="verify semantic", at="2026-08-09T00:00:00+00:00")

    (entry,) = journal.entries()
    assert entry.in_progress
    assert entry.exit_code is None


def test_lines_are_never_rewritten(tmp_path: Path) -> None:
    """append-only — close가 start 줄을 고치지 않는다."""
    journal = MissionJournal(root=tmp_path, mission_id="m-1")
    sequence = journal.open(command="brief ask", at="2026-08-09T00:00:00+00:00")
    journal.close(
        sequence=sequence,
        at="2026-08-09T00:00:01+00:00",
        duration_seconds=1.0,
        exit_code=0,
        calls={},
    )

    lines = journal.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert '"event": "start"' in lines[0]
    assert '"event": "end"' in lines[1]


def test_a_corrupt_line_does_not_kill_the_reader(tmp_path: Path) -> None:
    """원장 한 줄이 깨졌다고 관측 수단 전체를 잃지 않는다."""
    journal = MissionJournal(root=tmp_path, mission_id="m-1")
    sequence = journal.open(command="brief ask", at="2026-08-09T00:00:00+00:00")
    journal.close(
        sequence=sequence,
        at="2026-08-09T00:00:01+00:00",
        duration_seconds=1.0,
        exit_code=0,
        calls={},
    )
    with journal.path.open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")

    assert len(journal.entries()) == 1


def test_entries_keep_command_order(tmp_path: Path) -> None:
    journal = MissionJournal(root=tmp_path, mission_id="m-1")
    for index, command in enumerate(["brief start", "brief ask", "brief answer"]):
        sequence = journal.open(command=command, at=f"2026-08-09T00:00:0{index}+00:00")
        journal.close(
            sequence=sequence,
            at=f"2026-08-09T00:00:0{index + 1}+00:00",
            duration_seconds=1.0,
            exit_code=0,
            calls={"claude": index},
        )

    assert [entry.command for entry in journal.entries()] == [
        "brief start",
        "brief ask",
        "brief answer",
    ]
    assert total_calls(journal.entries()) == {"claude": 3}


def test_an_unsafe_mission_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        MissionJournal(root=tmp_path, mission_id="../escape")
