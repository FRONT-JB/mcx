"""Brief 상태를 Mission 단위 JSON 문서로 저장하는 adapter.

Phase 1의 durable state baseline이다. 외부 의존성 없이
:class:`~mission_control.application.ports.BriefRepository`의 보장을 만족한다.

세 가지 실패를 막는다.

**부분 기록** — 임시 파일에 쓴 뒤 원자적으로 교체한다. 쓰는 도중 프로세스가
죽어도 독자는 이전의 완전한 문서를 보거나 아무것도 보지 못한다. 반쯤 쓰인 JSON을
읽는 일은 없다.

**조용한 덮어쓰기** — 저장된 revision보다 앞서지 않는 쓰기를 거부한다. 두 경로가
같은 상태에서 출발해 각자 답변을 기록하면, 거부가 없을 때 나중 쓰기가 먼저 쓰기를
삼켜 사용자의 답변 하나가 흔적 없이 사라진다.

**경로 조작** — mission id를 파일명에 넣으므로 경로 구분자나 상위 참조가 든 id를
거부한다. id는 CLI 인자나 MCP 요청으로 들어올 수 있다.

동시 접근은 file lock으로 직렬화한다 (ADR-0013 §3). 다중 프로세스 환경에서의
보장 수준은 그 ADR의 Cost에 기록되어 있다.

계약: ``docs/adr/0013-brief-durable-state-baseline.md``
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import re
import tempfile

from mission_control.domain.brief.state import BriefState
from mission_control.domain.errors import StaleRevisionError

#: 파일명에 그대로 넣어도 안전한 형태만 허용한다. 경로 구분자, 상위 참조, 공백,
#: 확장자로 오인될 점(.)을 배제한다.
_SAFE_MISSION_ID = re.compile(r"\A[A-Za-z0-9_-]+\Z")

_OWNER_ONLY = 0o600


class FileBriefRepository:
    """``<root>/brief_<mission_id>.json`` 하나에 Brief 전체를 보관한다."""

    def __init__(self, *, root: Path) -> None:
        self._root = root

    async def load(self, mission_id: str) -> BriefState | None:
        path = self._path_for(mission_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            try:
                content = handle.read()
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return BriefState.model_validate_json(content)

    async def save(self, state: BriefState) -> None:
        path = self._path_for(state.mission_id)
        self._root.mkdir(parents=True, exist_ok=True)

        stored = await self.load(state.mission_id)
        if stored is not None and state.revision <= stored.revision:
            raise StaleRevisionError(
                mission_id=state.mission_id,
                stored_revision=stored.revision,
                incoming_revision=state.revision,
            )

        self._write_atomically(path, state.model_dump_json(indent=2))

    def _path_for(self, mission_id: str) -> Path:
        if not _SAFE_MISSION_ID.match(mission_id):
            raise ValueError(
                f"unsafe mission id for a file path: {mission_id!r}; "
                "expected letters, digits, hyphen, or underscore"
            )
        return self._root / f"brief_{mission_id}.json"

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
