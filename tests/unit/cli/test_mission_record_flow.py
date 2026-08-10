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
from mission_control.domain.evolve.models import EvolutionPhase
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
            # 실제 VerificationEvidence의 축을 그대로 갖는다 — stub이 얇으면
            # 표시 경로가 추가될 때 계약이 아니라 stub이 깨진다.
            return SimpleNamespace(
                evidence=SimpleNamespace(runs=[], changed_files=(), changed_files_error=None)
            )

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


def _evolve_state(*, scope_hold: bool = False) -> SimpleNamespace:
    finding = SimpleNamespace(kind="goal", current="기존", proposed="다른 목표")
    return SimpleNamespace(
        evolutions=[
            SimpleNamespace(
                phase=(EvolutionPhase.SEEDING if scope_hold else EvolutionPhase.COMPLETED),
                successor_generation=2,
                parent_blueprint_revision=1,
                result_blueprint_revision=None if scope_hold else 2,
                scope_change_findings=(finding,) if scope_hold else (),
            )
        ]
    )


async def _verify_record(tmp_path: Path, *, complete: bool = False) -> None:
    record = MissionRecord.create(mission_id="m", workspace="/ws")
    for destination in (Stage.BLUEPRINT, Stage.EXECUTE, Stage.VERIFY):
        record = record.transit(destination=destination, at="t", reason="setup")
    if complete:
        record = record.complete(at="t")
    await repository(tmp_path).save(record)


async def test_evolve_success_records_verify_to_blueprint_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _verify_record(tmp_path)

    class StubService:
        async def propose(self, *, mission_id: str) -> SimpleNamespace:
            return _evolve_state()

    monkeypatch.setattr(composition, "evolve_service", lambda *_: StubService())

    assert await amain(["blueprint", "evolve", *argv("m", tmp_path)], default_adapters()) == 0

    stored = await repository(tmp_path).load("m")
    assert stored is not None
    assert stored.current_stage is Stage.BLUEPRINT
    assert stored.transitions[-1].reason == "mcx blueprint evolve"


async def test_evolve_scope_hold_keeps_the_mission_at_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _verify_record(tmp_path)

    class StubService:
        async def propose(self, *, mission_id: str) -> SimpleNamespace:
            return _evolve_state(scope_hold=True)

    monkeypatch.setattr(composition, "evolve_service", lambda *_: StubService())

    assert await amain(["blueprint", "evolve", *argv("m", tmp_path)], default_adapters()) == 2

    stored = await repository(tmp_path).load("m")
    assert stored is not None
    assert stored.current_stage is Stage.VERIFY


async def test_evolve_rejects_a_complete_mission_before_service_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _verify_record(tmp_path, complete=True)
    dispatched = False

    class StubService:
        async def propose(self, *, mission_id: str) -> SimpleNamespace:
            nonlocal dispatched
            dispatched = True
            return _evolve_state()

    monkeypatch.setattr(composition, "evolve_service", lambda *_: StubService())

    assert await amain(["blueprint", "evolve", *argv("m", tmp_path)], default_adapters()) == 1
    assert dispatched is False


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


class TestChangedFilesAreShown:
    """ADR-0048 §5는 목록을 *"사용자를 위한 표시"* 라고 적었는데 표시 경로가
    없었다 — Phase 9 종료 검토 §2.1이 잡았다.

    목록은 rollback이 지울 집합과 같으므로(§1) 되돌리기 전에 무엇이 사라질지
    이기도 하다.
    """

    @staticmethod
    def _stub(monkeypatch: pytest.MonkeyPatch, **evidence: object) -> None:
        class StubService:
            async def run_mechanical(self, *, mission_id: str) -> SimpleNamespace:
                return SimpleNamespace(evidence=SimpleNamespace(runs=[], **evidence))

        monkeypatch.setattr(composition, "verify_service", lambda layout, adapters: StubService())

    async def test_the_changed_files_are_named(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._stub(
            monkeypatch, changed_files=("src/app.py", "tests/test_app.py"), changed_files_error=None
        )
        adapters = default_adapters()
        assert await amain(["brief", "start", "g", *argv("m", tmp_path)], adapters) == 0
        capsys.readouterr()

        assert await amain(["verify", "mechanical", *argv("m", tmp_path)], adapters) == 0

        assert "변경 2건: src/app.py, tests/test_app.py" in capsys.readouterr().err

    async def test_a_collection_failure_is_named_not_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """빈 목록과 수집 실패를 구분한다 (ADR-0048 §4) — 표시에서도 같다."""
        self._stub(monkeypatch, changed_files=(), changed_files_error="git 저장소가 아니다")
        adapters = default_adapters()
        assert await amain(["brief", "start", "g", *argv("m", tmp_path)], adapters) == 0
        capsys.readouterr()

        await amain(["verify", "mechanical", *argv("m", tmp_path)], adapters)

        assert "변경 목록 없음: git 저장소가 아니다" in capsys.readouterr().err

    async def test_a_clean_tree_says_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """할 말이 없으면 하지 않는다 — 빈 줄이 관측을 흐린다."""
        self._stub(monkeypatch, changed_files=(), changed_files_error=None)
        adapters = default_adapters()
        assert await amain(["brief", "start", "g", *argv("m", tmp_path)], adapters) == 0
        capsys.readouterr()

        await amain(["verify", "mechanical", *argv("m", tmp_path)], adapters)

        assert "변경" not in capsys.readouterr().err
