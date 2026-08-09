"""비동기 job — **원장에서 유도한다** (ADR-0041 §4·§5).

새 저장소를 만들지 않는다. 명령 원장이 이미 같은 사실을 담고 있다: 짝 없는
``start``가 "진행 중"이고 ``end``의 exit code가 결과다. 별도 job 테이블을 두면
프로세스가 죽는 순간 두 기록이 어긋나고, 그때 "누가 이기는가"를 또 정해야
한다 — ADR-0037에서 이미 치른 값이다.

``job_id``는 ``<mission_id>#<sequence>``이며 sequence는 원장의 것이다.

취소는 디스크 마커다. **마커를 놓는 것만으로는 아무것도 멈추지 않는다** —
실행 중인 프로세스가 그것을 관측해야 한다. upstream이 정확히 이 지점에서
계약을 조용히 깼다 (``tools/background.py:16-26``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import re

from mission_control.cli.journal import MissionJournal
from mission_control.cli.progress import last_activity

_JOB_ID = re.compile(r"\A(?P<mission>[A-Za-z0-9_-]+)#(?P<sequence>[1-9][0-9]*)\Z")

_OWNER_ONLY = 0o600


class JobState(StrEnum):
    """원장에서 유도되는 상태. upstream 일곱에서 둘이 빠진다 (§5).

    ``queued``가 없는 이유는 큐를 두지 않기 때문이고, ``interrupted``가 없는
    이유는 **짝 없는 ``start`` 자체가 그 사실**이기 때문이다 — 프로세스가
    죽어도 원장이 남는다.
    """

    RUNNING = "running"
    COMPLETED = "completed"
    HOLD = "hold"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"


@dataclass(frozen=True)
class JobView:
    job_id: str
    command: str
    state: JobState
    started_at: str
    finished_at: str | None
    duration_seconds: float | None
    exit_code: int | None
    #: 마지막 진행 줄 — 원장이 답하지 못하는 "그 안에서 무엇을 하는가"
    #: (ADR-0049 §4). 진행 기록이 없으면 ``None``이고, 그것이 조회를 막지 않는다.
    activity: str | None = None


class UnknownJobError(Exception):
    """형식이 틀렸거나 원장에 없는 job id."""


def job_id(*, mission_id: str, sequence: int) -> str:
    return f"{mission_id}#{sequence}"


def parse_job_id(value: str) -> tuple[str, int]:
    match = _JOB_ID.match(value)
    if match is None:
        raise UnknownJobError(f"job id 형식이 아니다: {value!r}")
    return match["mission"], int(match["sequence"])


def cancel_marker(*, root: Path, mission_id: str, sequence: int) -> Path:
    return root / f"cancel_{mission_id}_{sequence}"


def request_cancel(*, root: Path, mission_id: str, sequence: int) -> Path:
    """취소를 요청한다. 실행 중인 작업을 **직접 멈추지는 않는다**."""
    root.mkdir(parents=True, exist_ok=True)
    marker = cancel_marker(root=root, mission_id=mission_id, sequence=sequence)
    marker.write_text("cancel\n", encoding="utf-8")
    marker.chmod(_OWNER_ONLY)
    return marker


def job_view(*, root: Path, job: str) -> JobView:
    """원장 한 구간을 job으로 본다."""
    mission_id, sequence = parse_job_id(job)
    entries = MissionJournal(root=root, mission_id=mission_id).entries()
    for entry in entries:
        if entry.sequence != sequence:
            continue
        return JobView(
            job_id=job,
            command=entry.command,
            state=_state(
                root=root,
                mission_id=mission_id,
                sequence=sequence,
                in_progress=entry.in_progress,
                exit_code=entry.exit_code,
            ),
            started_at=entry.started_at,
            finished_at=entry.finished_at,
            duration_seconds=entry.duration_seconds,
            exit_code=entry.exit_code,
            activity=_activity(root=root, mission_id=mission_id, sequence=sequence),
        )
    raise UnknownJobError(f"원장에 없는 job이다: {job}")


def _activity(*, root: Path, mission_id: str, sequence: int) -> str | None:
    line = last_activity(root=root, mission_id=mission_id, sequence=sequence)
    return line.render() if line is not None else None


def _state(
    *,
    root: Path,
    mission_id: str,
    sequence: int,
    in_progress: bool,
    exit_code: int | None,
) -> JobState:
    if in_progress:
        if cancel_marker(root=root, mission_id=mission_id, sequence=sequence).exists():
            return JobState.CANCEL_REQUESTED
        return JobState.RUNNING
    if exit_code == 0:
        return JobState.COMPLETED
    if exit_code == 2:
        return JobState.HOLD
    return JobState.FAILED
