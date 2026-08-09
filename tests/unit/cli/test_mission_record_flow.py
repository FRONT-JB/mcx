"""mission record의 CLI 수명 — 생성, 전이 기록, 어긋남 경고, MISSION COMPLETE.

계약: ADR-0037 (Gate가 이긴다), ADR-0038 §5 (쓰는 주체는 CLI뿐).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_control.adapters.persistence.file_mission_repository import (
    FileMissionRepository,
)
from mission_control.cli import composition
from mission_control.cli.composition import StateLayout, default_adapters
from mission_control.cli.main import amain
from mission_control.domain.errors import StaleWriteError
from mission_control.domain.mission import MissionRecord, MissionStatus
from mission_control.domain.stage import Stage


def repository(tmp_path: Path) -> FileMissionRepository:
    return FileMissionRepository(root=StateLayout.under(tmp_path).state)


def argv(mission: str, tmp_path: Path) -> list[str]:
    return ["--mission", mission, "--state-dir", str(tmp_path)]


async def test_brief_start_creates_record_with_workspace(tmp_path: Path) -> None:
    code = await amain(
        [
            "brief",
            "start",
            "g",
            "--workspace",
            "/some/ws",
            *argv("m", tmp_path),
        ],
        default_adapters(),
    )
    assert code == 0
    record = await repository(tmp_path).load("m")
    assert record is not None
    assert record.current_stage is Stage.BRIEF
    assert record.workspace == "/some/ws"


async def test_stage_entry_records_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class StubService:
        async def generate(self, *, mission_id: str) -> SimpleNamespace:
            return SimpleNamespace(current=None)

    monkeypatch.setattr(
        composition, "blueprint_service", lambda layout, adapters, **_: StubService()
    )
    adapters = default_adapters()

    assert await amain(["brief", "start", "g", *argv("m", tmp_path)], adapters) == 0
    assert await amain(["blueprint", "generate", *argv("m", tmp_path)], adapters) == 0

    record = await repository(tmp_path).load("m")
    assert record is not None
    assert record.current_stage is Stage.BLUEPRINT
    assert record.transitions[-1].reason == "mcx blueprint generate"


async def test_illegal_transition_warns_but_command_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """기록이 BRIEF인데 Verify 진입 — Gate가 이기고 기록은 경고만 남긴다."""

    class StubService:
        async def run_mechanical(self, *, mission_id: str) -> SimpleNamespace:
            return SimpleNamespace(evidence=SimpleNamespace(runs=[]))

    monkeypatch.setattr(composition, "verify_service", lambda layout, adapters: StubService())
    adapters = default_adapters()

    assert await amain(["brief", "start", "g", *argv("m", tmp_path)], adapters) == 0
    assert await amain(["verify", "mechanical", *argv("m", tmp_path)], adapters) == 0

    assert "전이를 기록하지 않았다" in capsys.readouterr().err
    record = await repository(tmp_path).load("m")
    assert record is not None
    assert record.current_stage is Stage.BRIEF


async def test_verify_gate_clear_records_mission_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repository(tmp_path)
    record = MissionRecord.create(mission_id="m", workspace="/ws")
    for destination in (Stage.BLUEPRINT, Stage.EXECUTE, Stage.VERIFY):
        record = record.transit(destination=destination, at="t", reason="setup")
    await repo.save(record)

    class StubService:
        async def decide_gate(self, *, mission_id: str) -> SimpleNamespace:
            return SimpleNamespace(outcome="CLEAR")

    monkeypatch.setattr(composition, "verify_service", lambda layout, adapters: StubService())

    assert await amain(["verify", "gate", *argv("m", tmp_path)], default_adapters()) == 0
    stored = await repo.load("m")
    assert stored is not None
    assert stored.status is MissionStatus.COMPLETE
    assert stored.completed_at is not None


async def test_verify_gate_clear_outside_verify_warns_not_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class StubService:
        async def decide_gate(self, *, mission_id: str) -> SimpleNamespace:
            return SimpleNamespace(outcome="CLEAR")

    monkeypatch.setattr(composition, "verify_service", lambda layout, adapters: StubService())
    adapters = default_adapters()

    assert await amain(["brief", "start", "g", *argv("m", tmp_path)], adapters) == 0
    assert await amain(["verify", "gate", *argv("m", tmp_path)], adapters) == 0

    assert "MISSION COMPLETE를 기록하지 않았다" in capsys.readouterr().err
    record = await repository(tmp_path).load("m")
    assert record is not None
    assert record.status is MissionStatus.ACTIVE


async def test_status_reports_record_and_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    adapters = default_adapters()
    assert await amain(["status", *argv("missing", tmp_path)], adapters) == 1

    assert await amain(["brief", "start", "g", *argv("m", tmp_path)], adapters) == 0
    capsys.readouterr()
    # --json은 개정 2 이전과 같은 계약이다 (ADR-0038 §6.1 d).
    assert await amain(["status", "--json", *argv("m", tmp_path)], adapters) == 0
    output = capsys.readouterr().out
    assert '"mismatch": null' in output

    repo = repository(tmp_path)
    stored = await repo.load("m")
    assert stored is not None
    await repo.save(stored.transit(destination=Stage.BLUEPRINT, at="t", reason="drift"))
    assert await amain(["status", "--json", *argv("m", tmp_path)], adapters) == 0
    assert "Gate 재계산이 이긴다" in capsys.readouterr().out
    # 사람용 렌더도 같은 어긋남을 표시한다.
    assert await amain(["status", *argv("m", tmp_path)], adapters) == 0
    assert "Gate 재계산이 이긴다" in capsys.readouterr().out


async def test_repository_rejects_stale_writes(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    record = MissionRecord.create(mission_id="m", workspace="/ws")
    await repo.save(record)
    moved = record.transit(destination=Stage.BLUEPRINT, at="t", reason="r")
    await repo.save(moved)
    with pytest.raises(StaleWriteError):
        await repo.save(record)

    loaded = await repo.load("m")
    assert loaded == moved
