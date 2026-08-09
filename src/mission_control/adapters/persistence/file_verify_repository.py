"""Verify 상태를 Mission 단위 JSON 문서로 저장하는 adapter.

:class:`~mission_control.adapters.persistence.file_brief_repository.FileBriefRepository`
와 같은 계약, 같은 기법이다 — 원자 교체로 부분 기록을 막고, ``sequence``로
조용한 덮어쓰기를 거부하고, 경로에 실을 수 없는 mission id를 거부한다. 기법의
근거는 그쪽 모듈 docstring에 있다.

원문 출력은 이 문서에 없다 — :class:`FileVerificationOutputStore`가 보존하고
여기는 참조만 담긴 evidence를 기록한다 (ADR-0028 §4).

계약: ``docs/adr/0028-verify-v1-mechanical-contract.md`` §4,
``docs/adr/0013-brief-durable-state-baseline.md`` §3
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import re
import tempfile

from mission_control.domain.errors import StaleWriteError
from mission_control.domain.verify.evidence import VerifyState

_SAFE_MISSION_ID = re.compile(r"\A[A-Za-z0-9_-]+\Z")

_OWNER_ONLY = 0o600


class FileVerifyRepository:
    """``<root>/verify_<mission_id>.json`` 하나에 Verify 상태 전체를 보관한다."""

    def __init__(self, *, root: Path) -> None:
        self._root = root

    async def load(self, mission_id: str) -> VerifyState | None:
        path = self._path_for(mission_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                content = handle.read()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return VerifyState.model_validate_json(content)

    async def save(self, state: VerifyState) -> None:
        path = self._path_for(state.mission_id)
        self._root.mkdir(parents=True, exist_ok=True)

        stored = await self.load(state.mission_id)
        if stored is not None and state.sequence <= stored.sequence:
            raise StaleWriteError(
                mission_id=state.mission_id,
                stored_sequence=stored.sequence,
                incoming_sequence=state.sequence,
            )

        self._write_atomically(path, state.model_dump_json(indent=2))

    def _path_for(self, mission_id: str) -> Path:
        if not _SAFE_MISSION_ID.match(mission_id):
            raise ValueError(
                f"파일 경로에 쓸 수 없는 mission id다: {mission_id!r}; "
                "영문자·숫자·하이픈·밑줄만 쓴다"
            )
        return self._root / f"verify_{mission_id}.json"

    def _write_atomically(self, path: Path, content: str) -> None:
        descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            os.chmod(temporary, _OWNER_ONLY)
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise


class FileVerificationOutputStore:
    """검증 명령의 합류 출력을 ``<root>`` 아래 파일로 보존한다.

    상태 문서가 출력 크기에 오염되지 않도록 분리한다 — upstream의 파일 트리
    + manifest 배치와 같은 축이다 (ADR-0027 §1).
    """

    def __init__(self, *, root: Path) -> None:
        self._root = root

    async def preserve(self, *, mission_id: str, sequence: int, ac_key: str, content: str) -> str:
        if not _SAFE_MISSION_ID.match(mission_id):
            raise ValueError(f"파일 경로에 쓸 수 없는 mission id다: {mission_id!r}")
        if not _SAFE_MISSION_ID.match(ac_key):
            raise ValueError(f"파일 경로에 쓸 수 없는 AC key다: {ac_key!r}")
        self._root.mkdir(parents=True, exist_ok=True)

        path = self._root / f"verify_output_{mission_id}_{sequence:04d}_{ac_key}.txt"
        descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, _OWNER_ONLY)
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return str(path)
