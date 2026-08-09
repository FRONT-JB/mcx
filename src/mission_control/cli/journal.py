"""명령 단위 원장 — CLI만 쓴다 (ADR-0038 §6.1).

append-only JSONL이다. 명령 시작에 ``start`` 한 줄, 종료에 ``end`` 한 줄을
쓰고 이미 쓴 줄을 고치지 않는다. 짝이 없는 ``start``가 곧 "진행 중"이며,
프로세스가 중간에 죽어도 그 사실이 남는다 — 중단된 명령이 조용히 사라지지
않는다.

Stage service는 이 모듈을 모른다. mission record와 같은 소유 경계다
(ADR-0037 §1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from pathlib import Path
import re

from mission_control.security import reject_replay_unsafe

_SAFE_MISSION_ID = re.compile(r"\A[A-Za-z0-9_-]+\Z")

_OWNER_ONLY = 0o600


@dataclass(frozen=True)
class JournalEntry:
    """명령 하나의 구간. ``finished_at``이 없으면 아직 끝나지 않았다."""

    sequence: int
    command: str
    started_at: str
    finished_at: str | None = None
    duration_seconds: float | None = None
    exit_code: int | None = None
    #: backend 이름 → 실제 port 호출 횟수. 명령 수 근사가 아니다 (§6.1 b).
    calls: Mapping[str, int] = field(default_factory=dict)

    @property
    def in_progress(self) -> bool:
        return self.finished_at is None


class MissionJournal:
    """``<root>/journal_<mission_id>.jsonl``.

    저장소들과 같은 경로 조작 방어를 쓴다 (안전한 id만 허용).
    """

    def __init__(self, *, root: Path, mission_id: str) -> None:
        if not _SAFE_MISSION_ID.match(mission_id):
            raise ValueError(f"원장 경로에 쓸 수 없는 mission id다: {mission_id!r}")
        self._root = root
        self._mission_id = mission_id

    @property
    def path(self) -> Path:
        return self._root / f"journal_{self._mission_id}.jsonl"

    def open(self, *, command: str, at: str) -> int:
        """구간을 열고 sequence를 돌려준다. 반드시 :meth:`close`와 짝이 된다."""
        sequence = len(self.entries()) + 1
        self._append({"event": "start", "sequence": sequence, "command": command, "at": at})
        return sequence

    def close(
        self,
        *,
        sequence: int,
        at: str,
        duration_seconds: float,
        exit_code: int,
        calls: Mapping[str, int],
    ) -> None:
        self._append(
            {
                "event": "end",
                "sequence": sequence,
                "at": at,
                "duration_seconds": round(duration_seconds, 3),
                "exit_code": exit_code,
                "calls": dict(calls),
            }
        )

    def entries(self) -> tuple[JournalEntry, ...]:
        """start/end 줄을 sequence로 접어 구간 목록을 만든다.

        읽을 수 없는 줄은 건너뛴다 — 원장 한 줄이 깨졌다고 status 전체가
        죽으면 관측 수단을 잃는다. 짝 없는 ``end``도 무시된다.
        """
        if not self.path.exists():
            return ()

        opened: dict[int, JournalEntry] = {}
        order: list[int] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            sequence = record.get("sequence")
            if not isinstance(sequence, int):
                continue
            if record.get("event") == "start":
                opened[sequence] = JournalEntry(
                    sequence=sequence,
                    command=str(record.get("command", "?")),
                    started_at=str(record.get("at", "")),
                )
                order.append(sequence)
            elif record.get("event") == "end" and sequence in opened:
                started = opened[sequence]
                calls = record.get("calls")
                opened[sequence] = JournalEntry(
                    sequence=sequence,
                    command=started.command,
                    started_at=started.started_at,
                    finished_at=str(record.get("at", "")),
                    duration_seconds=record.get("duration_seconds"),
                    exit_code=record.get("exit_code"),
                    calls=dict(calls) if isinstance(calls, dict) else {},
                )
        return tuple(opened[sequence] for sequence in order)

    def _append(self, record: dict[str, object]) -> None:
        # 원장은 lifecycle 기록이다 — 프롬프트·원시 출력은 마스킹이 아니라
        # **거부**다 (ADR-0040 §2). 쓰기 직전에 검사하므로 새 필드를 추가하는
        # 경로가 이 가드를 우회할 수 없다.
        reject_replay_unsafe(record, where="명령 원장")
        self._root.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")
        self.path.chmod(_OWNER_ONLY)


def total_calls(entries: tuple[JournalEntry, ...]) -> dict[str, int]:
    """backend별 호출 합계 — 등장 순서를 보존한다."""
    totals: dict[str, int] = {}
    for entry in entries:
        for backend, count in entry.calls.items():
            totals[backend] = totals.get(backend, 0) + int(count)
    return totals
