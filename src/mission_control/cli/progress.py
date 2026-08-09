"""진행 꼬리 — 원장이 비워 둔 칸 하나 (ADR-0049 §4).

원장은 **명령 단위**다. 답하지 못하는 질문이 정확히 하나 있다: *"한 명령이
도는 **동안** 그 안에서 무슨 일이 일어나는가."* 화면 출력만으로는 이 칸이
안 채워진다 — MCP 백그라운드 job에는 볼 화면이 없다.

**두 번째 저장소가 아니다.** 원장이 담는 사실(명령의 시작·끝·결과)을 하나도
중복하지 않는다.

``<root>/progress_<mission_id>_<sequence>.jsonl`` — 원장·취소 마커와 같은 이름
규칙이고 ``job_id``가 그대로 좌표다 (ADR-0041 §4).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from mission_control.progress import RuntimeActivity

_SAFE_MISSION_ID = re.compile(r"\A[A-Za-z0-9_-]+\Z")

_OWNER_ONLY = 0o600


@dataclass(frozen=True)
class ProgressLine:
    at: str
    tool: str | None
    detail: str

    def render(self) -> str:
        return f"{self.tool} {self.detail}".strip() if self.tool else self.detail


def progress_path(*, root: Path, mission_id: str, sequence: int) -> Path:
    if not _SAFE_MISSION_ID.match(mission_id):
        raise ValueError(f"진행 기록 경로에 쓸 수 없는 mission id다: {mission_id!r}")
    return root / f"progress_{mission_id}_{sequence}.jsonl"


class ProgressTail:
    """job 하나의 진행 줄. append-only이며 이미 쓴 줄을 고치지 않는다."""

    def __init__(self, *, root: Path, mission_id: str, sequence: int) -> None:
        self._path = progress_path(root=root, mission_id=mission_id, sequence=sequence)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, activity: RuntimeActivity, *, at: str) -> None:
        """한 줄 붙인다.

        마스킹은 ``RuntimeActivity`` 생성 시점에 이미 끝나 있다 (ADR-0049 §6) —
        여기서 다시 부르지 않는 이유는 강제 지점이 하나여야 하기 때문이다.
        """
        record = {"at": at, "kind": activity.kind, "tool": activity.tool, "detail": activity.detail}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(f"{json.dumps(record, ensure_ascii=False)}\n")
        self._path.chmod(_OWNER_ONLY)


def last_activity(*, root: Path, mission_id: str, sequence: int) -> ProgressLine | None:
    """마지막 진행 줄. 파일이 없거나 읽을 줄이 없으면 ``None``.

    깨진 줄은 건너뛴다 — 진행 기록 한 줄 때문에 job 조회가 죽으면 관측 수단을
    잃는다 (원장과 같은 규율).
    """
    path = progress_path(root=root, mission_id=mission_id, sequence=sequence)
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        tool = record.get("tool")
        return ProgressLine(
            at=str(record.get("at", "")),
            tool=tool if isinstance(tool, str) else None,
            detail=str(record.get("detail", "")),
        )
    return None
