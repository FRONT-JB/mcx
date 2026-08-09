"""Blueprint 상태를 Mission 단위 JSON 문서로 저장하는 adapter.

:class:`~mission_control.adapters.persistence.file_brief_repository.FileBriefRepository`
와 같은 계약, 같은 기법이다 — 원자 교체로 부분 기록을 막고, ``sequence``로
조용한 덮어쓰기를 거부하고, 경로에 실을 수 없는 mission id를 거부한다. 기법의
근거는 그쪽 모듈 docstring에 있다.

한 문서가 revision·QA 기록·승인을 함께 담으므로 원자 교체가 곧 "승인만
유실되거나 내용만 유실된 상태가 없다"는 보장이다 (ADR-0021 §1).

계약: ``docs/adr/0021-blueprint-state-and-revisions.md`` §1,
``docs/adr/0013-brief-durable-state-baseline.md`` §3
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import re
import tempfile

from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.errors import StaleWriteError

#: 파일명에 그대로 넣어도 안전한 형태만 허용한다. 경로 구분자, 상위 참조, 공백,
#: 확장자로 오인될 점(.)을 배제한다.
_SAFE_MISSION_ID = re.compile(r"\A[A-Za-z0-9_-]+\Z")

_OWNER_ONLY = 0o600


class FileBlueprintRepository:
    """``<root>/blueprint_<mission_id>.json`` 하나에 Blueprint 상태 전체를 보관한다."""

    def __init__(self, *, root: Path) -> None:
        self._root = root

    async def load(self, mission_id: str) -> BlueprintState | None:
        path = self._path_for(mission_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                content = handle.read()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return BlueprintState.model_validate_json(content)

    async def save(self, state: BlueprintState) -> None:
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
        return self._root / f"blueprint_{mission_id}.json"

    def _write_atomically(self, path: Path, content: str) -> None:
        """임시 파일에 기록한 뒤 교체한다.

        같은 디렉터리에 임시 파일을 만드는 이유는 :func:`os.replace`가 같은
        파일시스템 안에서만 원자적이기 때문이다. 실패하면 임시 파일을 정리해
        디렉터리에 잔해를 남기지 않는다.
        """
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
