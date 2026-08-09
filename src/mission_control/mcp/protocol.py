"""MCP 표면의 자체 타입 — SDK를 모른다 (ADR-0041 §1).

SDK 의존은 ``server.py`` 하나에 가둔다. 이 모듈과 ``surface.py``는 SDK 없이
테스트된다 — upstream도 protocol 층과 adapter를 나눠 둔다
(``mcp/server/protocol.py`` vs ``mcp/server/adapter.py``).

오류는 예외가 아니라 **플래그**다. 그리고 ``HOLD``는 오류가 아니다 (§2) —
``is_error=True``로 보내면 host가 무의미한 재시도를 건다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ResultType(StrEnum):
    """결과의 성격. CLI exit code와 1:1이다 (ADR-0041 §2)."""

    COMPLETE = "complete"
    HOLD = "hold"
    ERROR = "error"
    ACCEPTED = "accepted"
    """비동기 접수증 — 작업은 시작됐고 결과는 아직 없다 (§4)."""


#: CLI exit code → (is_error, result_type). 이 표가 계약이다.
EXIT_CODES: dict[int, tuple[bool, ResultType]] = {
    0: (False, ResultType.COMPLETE),
    2: (False, ResultType.HOLD),
    1: (True, ResultType.ERROR),
}


@dataclass(frozen=True)
class ToolDefinition:
    """host에게 노출되는 tool 하나."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """tool 호출 하나의 결과 (upstream ``MCPToolResult`` 정렬)."""

    text: str = ""
    is_error: bool = False
    result_type: ResultType = ResultType.COMPLETE
    structured_content: Any = None
    meta: dict[str, Any] = field(default_factory=dict)


def classify(exit_code: int) -> tuple[bool, ResultType]:
    """알 수 없는 exit code는 오류로 접는다 — 조용히 성공으로 만들지 않는다."""
    return EXIT_CODES.get(exit_code, (True, ResultType.ERROR))
