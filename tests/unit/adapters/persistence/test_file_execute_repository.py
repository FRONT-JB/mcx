"""Execute 파일 저장소 — 왕복 보존, stale write 거부, 경로 안전성.

계약: docs/adr/0024-execute-v1-execution-model.md §4,
docs/adr/0013-brief-durable-state-baseline.md §3
"""

from pathlib import Path

import pytest

from mission_control.adapters.persistence.file_execute_repository import (
    FileExecuteRepository,
)
from mission_control.domain.errors import StaleWriteError
from mission_control.domain.execute.state import CapabilityEnvelope, ExecuteState

ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission", allowed_tools=("edit",))


def _dispatched_state(mission_id: str = "m-1") -> ExecuteState:
    return ExecuteState.start(mission_id=mission_id).dispatch(
        execution_id=f"exec-{mission_id}-0001",
        runtime_backend="fake",
        blueprint_revision=1,
        ac_key="ac_a",
        envelope=ENVELOPE,
    )


@pytest.fixture
def repository(tmp_path: Path) -> FileExecuteRepository:
    return FileExecuteRepository(root=tmp_path)


class TestRoundTrip:
    async def test_load_returns_none_when_absent(self, repository: FileExecuteRepository) -> None:
        assert await repository.load("m-1") is None

    async def test_attempts_and_provenance_survive(self, repository: FileExecuteRepository) -> None:
        state = _dispatched_state().record_result(
            succeeded=True, native_session_id="sess-9", result_summary="완료"
        )
        await repository.save(state)

        restored = await repository.load("m-1")
        assert restored == state
        assert restored is not None
        assert restored.attempts[0].execution_id == "exec-m-1-0001"
        assert restored.attempts[0].envelope == ENVELOPE

    async def test_missions_are_isolated(self, repository: FileExecuteRepository) -> None:
        await repository.save(_dispatched_state("m-1"))
        await repository.save(_dispatched_state("m-2"))

        first = await repository.load("m-1")
        assert first is not None
        assert first.mission_id == "m-1"


class TestStaleWrites:
    async def test_same_sequence_is_rejected(self, repository: FileExecuteRepository) -> None:
        state = _dispatched_state()
        await repository.save(state)
        with pytest.raises(StaleWriteError):
            await repository.save(state)

    async def test_an_advancing_sequence_is_accepted(
        self, repository: FileExecuteRepository
    ) -> None:
        state = _dispatched_state()
        await repository.save(state)
        resolved = state.record_result(succeeded=True)
        await repository.save(resolved)

        assert await repository.load("m-1") == resolved


class TestFileSafety:
    async def test_unsafe_mission_id_is_rejected(self, repository: FileExecuteRepository) -> None:
        with pytest.raises(ValueError, match="unsafe mission id"):
            await repository.load("../escape")

    async def test_file_is_owner_only(
        self, repository: FileExecuteRepository, tmp_path: Path
    ) -> None:
        await repository.save(_dispatched_state())
        mode = (tmp_path / "execute_m-1.json").stat().st_mode & 0o777
        assert mode == 0o600
