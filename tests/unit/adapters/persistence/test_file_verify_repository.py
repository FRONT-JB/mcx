"""Verify 파일 저장소와 출력 보존 — 왕복, stale write 거부, 경로 안전성.

계약: docs/adr/0028-verify-v1-mechanical-contract.md §4,
docs/adr/0013-brief-durable-state-baseline.md §3
"""

from pathlib import Path

import pytest

from mission_control.adapters.persistence.file_verify_repository import (
    FileVerificationOutputStore,
    FileVerifyRepository,
)
from mission_control.domain.errors import StaleWriteError
from mission_control.domain.verify.evidence import (
    VerificationEvidence,
    VerificationRun,
    VerifyState,
)


def _recorded_state(mission_id: str = "m-1") -> VerifyState:
    evidence = VerificationEvidence(
        mission_id=mission_id,
        blueprint_revision=1,
        execution_attempt_numbers=(1, 2),
        runs=(
            VerificationRun(
                ac_key="ac_a",
                command="pytest -k list",
                exit_code=0,
                passed=True,
                output_ref="/tmp/out.txt",
                output_tail="3 passed",
            ),
        ),
    )
    return VerifyState.start(mission_id=mission_id).record(evidence)


@pytest.fixture
def repository(tmp_path: Path) -> FileVerifyRepository:
    return FileVerifyRepository(root=tmp_path)


class TestRoundTrip:
    async def test_load_returns_none_when_absent(self, repository: FileVerifyRepository) -> None:
        assert await repository.load("m-1") is None

    async def test_evidence_and_references_survive(self, repository: FileVerifyRepository) -> None:
        state = _recorded_state()
        await repository.save(state)

        restored = await repository.load("m-1")
        assert restored == state
        assert restored is not None
        assert restored.evidence is not None
        assert restored.evidence.runs[0].output_ref == "/tmp/out.txt"


class TestStaleWrites:
    async def test_same_sequence_is_rejected(self, repository: FileVerifyRepository) -> None:
        state = _recorded_state()
        await repository.save(state)
        with pytest.raises(StaleWriteError):
            await repository.save(state)


class TestFileSafety:
    async def test_unsafe_mission_id_is_rejected(self, repository: FileVerifyRepository) -> None:
        with pytest.raises(ValueError, match="unsafe mission id"):
            await repository.load("../escape")

    async def test_file_is_owner_only(
        self, repository: FileVerifyRepository, tmp_path: Path
    ) -> None:
        await repository.save(_recorded_state())
        mode = (tmp_path / "verify_m-1.json").stat().st_mode & 0o777
        assert mode == 0o600


class TestOutputStore:
    async def test_preserve_writes_and_returns_the_reference(self, tmp_path: Path) -> None:
        store = FileVerificationOutputStore(root=tmp_path)
        ref = await store.preserve(
            mission_id="m-1", sequence=1, ac_key="ac_abc", content="3 passed"
        )

        path = Path(ref)
        assert path.read_text(encoding="utf-8") == "3 passed"
        assert path.stat().st_mode & 0o777 == 0o600

    async def test_unsafe_names_are_rejected(self, tmp_path: Path) -> None:
        store = FileVerificationOutputStore(root=tmp_path)
        with pytest.raises(ValueError, match="unsafe"):
            await store.preserve(mission_id="../m", sequence=1, ac_key="ac_a", content="")
        with pytest.raises(ValueError, match="unsafe"):
            await store.preserve(mission_id="m-1", sequence=1, ac_key="../k", content="")
