"""실행 중 진행 관측 (ADR-0049).

**관측은 설치되어야 한다.** adapter는 ``record(activity)``만 부르고, 싱크가
없으면 아무 일도 일어나지 않는다 — 기존 동작이 한 글자도 바뀌지 않는다.
``cancellation.py``와 같은 배치이며 이유도 같다: 실행 adapter가 "누가 왜
보는지"를 몰라야 한다. adapter는 mission id도, 원장 sequence도, 파일 경로도
모른다.

여기 있는 :class:`RuntimeActivity`는 **정규화 층**이다 — vendor JSONL을
backend-neutral 한 줄로 접는다 (upstream ``ProjectedRuntimeMessage``의 축).
두 번째 Runtime이 오면 그 이벤트 이름을 이 자리에서 흡수한다.

생성 시점에 저장 프로필이 걸린다 (ADR-0040 §3). detail은 도구 입력에서 오므로
``curl --api-key=…``가 그대로 지나갈 수 있는 자리다 — "부르면 되는 함수"로 두면
새 생산 경로가 조용히 빠뜨린다.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from mission_control.security import redact_credentials

#: 한 줄의 상한. 원시 출력은 애초에 싣지 않으므로 도구 입력 한 줄이면 족하다.
MAX_DETAIL = 200


@dataclass(frozen=True, slots=True)
class RuntimeActivity:
    """Runtime이 방금 시작한 일 하나. 표시와 기록이 같은 것을 쓴다."""

    kind: str
    #: codex item type을 **그대로** 싣는다. 우리 어휘로 옮기지 않는 이유는
    #: upstream 매핑의 근거를 확인하지 못했기 때문이다 (ADR-0049 §1).
    tool: str | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        detail = redact_credentials(self.detail).strip()
        if len(detail) > MAX_DETAIL:
            detail = f"{detail[: MAX_DETAIL - 1]}…"
        object.__setattr__(self, "detail", detail)

    def line(self) -> str:
        """사람이 읽는 한 줄."""
        if self.tool is None:
            return self.detail
        return f"{self.tool} {self.detail}".strip()


_SINK: ContextVar[Callable[[RuntimeActivity], None] | None] = ContextVar(
    "mcx_progress", default=None
)


def record(activity: RuntimeActivity) -> None:
    """진행 한 줄을 보고한다. 싱크가 없으면 아무 일도 일어나지 않는다."""
    sink = _SINK.get()
    if sink is not None:
        sink(activity)


def observed() -> bool:
    """싱크가 설치되어 있는가 — 관측이 가능한 상태인가."""
    return _SINK.get() is not None


@contextmanager
def report_to(sink: Callable[[RuntimeActivity], None]) -> Iterator[None]:
    """이 블록 안의 실행이 진행을 ``sink``로 보고하게 한다."""
    token = _SINK.set(sink)
    try:
        yield
    finally:
        _SINK.reset(token)
