"""호출 계수 — 원장의 ``calls``를 실측으로 채운다 (ADR-0038 §6.1 b).

명령 수로 근사하지 않는다. 명령 하나가 호출 N번인 경우가 실재하고(9-AC
semantic 판정), 근사값을 사용량으로 표시하면 사용자가 비용을 잘못 읽는다.
upstream도 같은 규율을 명문화한다 — per-AC token spend는 "a real
runtime-usage measurement (never a character proxy)" (``tui/events.py``).

계수는 CLI 층에서만 일어난다. adapter도 service도 자기가 세어지고 있다는
사실을 모른다.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from mission_control.application.ports import ExecutionOutcome, ExecutionRequest
from mission_control.cli.composition import Adapters


class CallCounter:
    """backend 이름별 호출 횟수. 명령 하나의 수명 동안만 산다."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def record(self, backend: str) -> None:
        self._counts[backend] = self._counts.get(backend, 0) + 1

    @property
    def counts(self) -> dict[str, int]:
        return dict(self._counts)

    def wrap(self, adapters: Adapters) -> Adapters:
        """AI를 부르는 두 port만 감싼다 — mechanical runner는 로컬 실행이다.

        Stage별로 라우팅된 실물도 함께 감싼다 (ADR-0039). 하나라도 빠지면 그
        Stage의 호출만 원장에서 사라져 사용량이 조용히 작아 보인다.
        """
        return dataclasses.replace(
            adapters,
            completion=_CountedCompletion(adapters.completion, self),
            runtime=_CountedRuntime(adapters.runtime, self),
            routed_completion={
                stage: _CountedCompletion(engine, self)
                for stage, engine in adapters.routed_completion.items()
            },
            routed_runtime={
                stage: _CountedRuntime(runtime, self)
                for stage, runtime in adapters.routed_runtime.items()
            },
        )


class _CountedCompletion:
    def __init__(self, inner: Any, counter: CallCounter) -> None:
        self._inner = inner
        self._counter = counter

    @property
    def backend(self) -> str:
        return str(self._inner.backend)

    async def complete_json(
        self, *, prompt: str, schema: dict[str, Any], workspace: str | None = None
    ) -> dict[str, Any]:
        self._counter.record(self.backend)
        result: dict[str, Any] = await self._inner.complete_json(
            prompt=prompt, schema=schema, workspace=workspace
        )
        return result


class _CountedRuntime:
    def __init__(self, inner: Any, counter: CallCounter) -> None:
        self._inner = inner
        self._counter = counter

    @property
    def backend(self) -> str:
        return str(self._inner.backend)

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        self._counter.record(self.backend)
        outcome: ExecutionOutcome = await self._inner.execute(request)
        return outcome
