"""위임 port들이 공유하는 완성 엔진 계약.

프롬프트+변환 클래스(``Prompted*``)는 vendor 중립이고 엔진만 vendor별이다 —
upstream이 persona를 vendor 중립으로, LLMAdapter를 vendor별로 두는 것과 같은
분리다 (ADR-0036 §2). 구현은 ``codex_completion.CodexCompletion``과
``claude_completion.ClaudeCompletion``.

계약: ``docs/adr/0034-codex-text-backend-contract.md``,
``docs/adr/0036-claude-text-lane-contract.md``
"""

from __future__ import annotations

from typing import Any, Protocol

from mission_control.domain.errors import MissionControlError

#: transient 재시도 상한과 backoff — upstream 완성 adapter 채택 (findings §7).
MAX_ATTEMPTS = 3

#: upstream 공용 transient 코어의 부분집합. 소문자 대조. 두 엔진이 공유한다 —
#: 무엇이 재시도할 만한 실패인지는 vendor가 아니라 정책이 정한다 (ADR-0034 §3).
TRANSIENT_PATTERNS = (
    "rate limit",
    "429",
    "temporarily",
    "overloaded",
    "connection",
    "try again",
    "500",
    "502",
    "503",
    "504",
)


def is_transient(error: str) -> bool:
    """오류 설명이 일시적 실패로 분류되는가."""
    lowered = error.lower()
    return any(pattern in lowered for pattern in TRANSIENT_PATTERNS)


class CompletionError(MissionControlError):
    """완성 호출이 사용할 수 있는 구조화 출력을 만들지 못했다.

    파싱 실패·schema 위반·timeout·비일시적 오류가 전부 여기다 — 어느 것도
    조용히 성공으로 해석되지 않는다 (ADR-0034 §4).
    """

    def __init__(self, *, reason: str, engine: str) -> None:
        super().__init__(f"{engine} completion failed: {reason}")
        self.reason = reason
        self.engine = engine


def strict_schema(properties: dict[str, Any]) -> dict[str, Any]:
    """모든 property가 필수이고 추가 속성이 없는 schema를 구성한다.

    codex는 이 shape를 요구하고(upstream `_normalize_schema_for_codex`,
    findings §7), claude `--json-schema`도 유효한 JSON Schema로 받는다 —
    한 벌의 스키마가 두 엔진에서 같은 계약을 강제한다.
    """
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
        "additionalProperties": False,
    }


class CompletionEngine(Protocol):
    """프롬프트 하나를 보내고 schema에 맞는 JSON 하나를 받는 엔진의 계약.

    ``workspace``가 주어지면 엔진은 그 안에서 **읽기 전용으로만** 관찰할 수
    있어야 한다 — 판정류 role이 실제 작업물을 검사하는 유일한 통로다
    (ADR-0034 정정, ADR-0036 §4).
    """

    @property
    def backend(self) -> str:
        """이 엔진의 backend 이름 (예: ``claude``, ``codex``).

        ``ExecutionRuntime.backend``와 같은 축이다 (ADR-0033 §1) — 원장의
        호출 계수 키이고 (ADR-0038 §6.1), lane별 backend 지정이 쓰는 이름과
        같다 (ADR-0039).
        """
        ...

    async def complete_json(
        self, *, prompt: str, schema: dict[str, Any], workspace: str | None = None
    ) -> dict[str, Any]:
        """구조화 완성 한 번 — transient 실패만 재시도한다."""
        ...
