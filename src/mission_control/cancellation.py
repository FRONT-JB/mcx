"""실행 중 취소 신호 (ADR-0041 §5).

취소 마커를 디스크에 놓는 것만으로는 **아무것도 멈추지 않는다.** 돌고 있는
프로세스가 그것을 관측해야 한다. upstream이 정확히 이 지점에서 계약을 조용히
깼다 — 마커는 잘 쓰였는데 실행 프로세스가 볼 수 없어서, 사용자는 취소했다고
믿고 작업은 계속 돌았다 (``tools/background.py:16-26``).

관측 지점을 ContextVar로 두는 이유는 실행 adapter가 "누가 왜 취소하는지"를
몰라야 하기 때문이다. adapter는 ``is_cancelled()``만 묻는다 — 마커 파일도,
mission id도, 원장 sequence도 모른다.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_CANCELLED: ContextVar[Callable[[], bool] | None] = ContextVar("mcx_cancelled", default=None)


def is_cancelled() -> bool:
    """지금 이 작업에 취소가 요청되었는가. 검사기가 없으면 항상 거짓이다."""
    check = _CANCELLED.get()
    return bool(check()) if check is not None else False


def observed() -> bool:
    """취소 검사기가 설치되어 있는가 — 관측이 가능한 상태인가."""
    return _CANCELLED.get() is not None


@contextmanager
def cancel_when(check: Callable[[], bool]) -> Iterator[None]:
    """이 블록 안의 실행이 ``check``를 취소 신호로 관측하게 한다."""
    token = _CANCELLED.set(check)
    try:
        yield
    finally:
        _CANCELLED.reset(token)
