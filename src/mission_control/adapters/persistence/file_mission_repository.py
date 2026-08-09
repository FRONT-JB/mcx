"""Mission record를 JSON 문서로 저장하는 adapter.

Brief 저장소와 같은 세 가지 실패를 같은 방식으로 막는다 — 부분 기록(원자적
교체), 조용한 덮어쓰기(``sequence`` 기반 stale 거부), 경로 조작(안전한 id만
허용). 근거와 보장 수준은 ``file_brief_repository.py``와 ADR-0013 §3.

이 저장소의 소비자는 CLI 합성뿐이다 — Stage service는 mission record를
읽지도 쓰지도 않는다 (ADR-0037 §1).
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import re
import tempfile

from mission_control.domain.errors import StaleWriteError
from mission_control.domain.mission import MissionRecord

_SAFE_MISSION_ID = re.compile(r"\A[A-Za-z0-9_-]+\Z")

_OWNER_ONLY = 0o600


class FileMissionRepository:
    """``<root>/mission_<mission_id>.json`` 하나에 mission record를 보관한다."""

    def __init__(self, *, root: Path) -> None:
        self._root = root

    async def load(self, mission_id: str) -> MissionRecord | None:
        path = self._path_for(mission_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                content = handle.read()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return MissionRecord.model_validate_json(content)

    async def save(self, record: MissionRecord) -> None:
        path = self._path_for(record.mission_id)
        self._root.mkdir(parents=True, exist_ok=True)

        stored = await self.load(record.mission_id)
        if stored is not None and record.sequence <= stored.sequence:
            raise StaleWriteError(
                mission_id=record.mission_id,
                stored_sequence=stored.sequence,
                incoming_sequence=record.sequence,
            )

        self._write_atomically(path, record.model_dump_json(indent=2))

    def _path_for(self, mission_id: str) -> Path:
        if not _SAFE_MISSION_ID.match(mission_id):
            raise ValueError(
                f"파일 경로에 쓸 수 없는 mission id다: {mission_id!r}; "
                "영문자·숫자·하이픈·밑줄만 쓴다"
            )
        return self._root / f"mission_{mission_id}.json"

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
