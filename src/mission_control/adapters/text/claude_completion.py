"""위임 port들이 공유하는 Claude 구조화 완성 엔진.

`claude -p` 단발 호출로 프롬프트를 stdin으로 보내고, `--json-schema`로 CLI측
스키마 검증을 걸어 응답 envelope의 ``structured_output``을 1급으로 소비한다
(RUNTIME_UPSTREAM_FINDINGS §10 — Verified by execution, claude CLI 2.1.226).
upstream `claude_code_adapter.py`의 프롬프트 삽입 + prose 재질의는 CLI측
검증이 없던 시절의 보상책이므로 쓰지 않는다 — 등록된 divergence (ADR-0036 §3).

권한은 sandbox 모드가 아니라 **도구 카탈로그**로 강제된다 (ADR-0036 §4):
workspace가 없으면 무도구(`--tools ""`), 있으면 읽기 도구만
(`Read Glob Grep`, upstream "20-turn read-only envelope" 정렬).
`--strict-mcp-config --setting-sources ""`가 MCP 재발견과 설정 상속을
차단한다 — delegated role의 재귀 금지(ADR-0004)가 플래그로 강제되는 지점.

timeout은 총 시간이다 — print 모드는 끝에 한 번 보고하므로 침묵 기준이
성립하지 않는다 (codex 엔진과의 의도적 비대칭, ADR-0036 §3).

계약: ``docs/adr/0036-claude-text-lane-contract.md``
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
from typing import Any

from mission_control.adapters.text.completion_engine import (
    MAX_ATTEMPTS,
    CompletionError,
    is_transient,
)

#: upstream `_CLI_DEFAULT_TIMEOUT_SECONDS` 채택 (findings §10).
TOTAL_TIMEOUT_SECONDS = 600.0

#: 관찰 봉투의 읽기 도구 카탈로그와 턴 예산 (upstream 정렬, ADR-0036 §4).
_OBSERVE_TOOLS = "Read Glob Grep"
_OBSERVE_MAX_TURNS = "20"
#: json-schema lane의 구조화 출력이 내부 턴을 소비한다 (0002 실측 2, 0003의
#: 9-AC QA가 1에서 error_max_turns) — upstream max_turns=1 pairing은 prose
#: lane의 것이라 이전되지 않는다 (ADR-0036 §4 정정 note).
_NO_TOOL_MAX_TURNS = "8"

_STDERR_TAIL_CHARS = 2_000


class ClaudeCompletionError(CompletionError):
    """완성 호출이 사용할 수 있는 구조화 출력을 만들지 못했다 (ADR-0034 §4 규칙)."""

    def __init__(self, *, reason: str) -> None:
        super().__init__(reason=reason, engine="claude")


class ClaudeCompletion:
    """프롬프트 하나를 보내고 schema에 맞는 JSON 하나를 받는다."""

    def __init__(
        self,
        *,
        cli_path: str = "claude",
        model: str | None = None,
        timeout_seconds: float = TOTAL_TIMEOUT_SECONDS,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self._cli_path = cli_path
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts

    @property
    def backend(self) -> str:
        return "claude"

    def build_command(self, *, schema_json: str, workspace: str | None = None) -> tuple[str, ...]:
        """완성 명령을 구성한다 — 봉투는 도구 카탈로그다.

        순수 함수로 분리한 이유는 conformance test가 CLI 실물 없이 명령
        구성을 고정하기 위해서다. ``--tools``가 카탈로그를 비우고
        ``--allowedTools``는 권한 프롬프트 억제일 뿐이라 둘 다 넘긴다
        (upstream `claude_code_adapter.py:697-702`).
        """
        command = [self._cli_path, "-p", "--output-format", "json"]
        if self._model is not None:
            command.extend(["--model", self._model])
        command.extend(["--json-schema", schema_json])
        if workspace is None:
            command.extend(["--tools", "", "--allowedTools", "", "--max-turns", _NO_TOOL_MAX_TURNS])
        else:
            command.extend(
                [
                    "--tools",
                    _OBSERVE_TOOLS,
                    "--allowedTools",
                    _OBSERVE_TOOLS,
                    "--max-turns",
                    _OBSERVE_MAX_TURNS,
                ]
            )
        command.extend(["--strict-mcp-config", "--setting-sources", ""])
        return tuple(command)

    async def complete_json(
        self, *, prompt: str, schema: dict[str, Any], workspace: str | None = None
    ) -> dict[str, Any]:
        """구조화 완성 한 번 — transient 실패만 재시도한다."""
        last_error = "no attempt was made"
        for attempt in range(self._max_attempts):
            outcome = await self._invoke(prompt, schema, workspace)
            if isinstance(outcome, dict):
                return outcome
            last_error = outcome
            if not is_transient(outcome) or attempt >= self._max_attempts - 1:
                raise ClaudeCompletionError(reason=outcome)
            await asyncio.sleep(2**attempt)
        raise ClaudeCompletionError(reason=last_error)

    async def _invoke(
        self, prompt: str, schema: dict[str, Any], workspace: str | None
    ) -> dict[str, Any] | str:
        """한 번의 호출. 성공이면 dict, 실패면 오류 설명 문자열을 반환한다.

        timeout과 ``structured_output`` 부재는 즉시 예외다 — transient가
        아니므로 재시도 루프로 돌아가지 않는다 (ADR-0036 §3).
        """
        command = self.build_command(schema_json=json.dumps(schema), workspace=workspace)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace,
            start_new_session=os.name != "nt",
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(prompt.encode("utf-8")), timeout=self._timeout_seconds
            )
        except TimeoutError:
            await self._terminate(process)
            raise ClaudeCompletionError(
                reason=(
                    f"claude -p가 총 {self._timeout_seconds:.0f}초를 넘겼다; "
                    "process group을 정리했다"
                )
            ) from None

        stderr_tail = stderr.decode("utf-8", errors="replace").strip()[-_STDERR_TAIL_CHARS:]
        try:
            envelope = json.loads(stdout.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            # envelope조차 없으면 CLI 자체가 실패한 것이다(auth·flag·usage) —
            # 진단은 stderr에 있다 (upstream `:770-790`과 같은 해석).
            return f"claude -p returned no JSON envelope (exit {process.returncode}): {stderr_tail}"

        if envelope.get("is_error") or process.returncode != 0:
            detail = envelope.get("result") or envelope.get("subtype") or "unknown error"
            return f"claude -p reported an error (exit {process.returncode}): {detail}"

        structured = envelope.get("structured_output")
        if not isinstance(structured, dict):
            raise ClaudeCompletionError(
                reason=(
                    "성공 응답에 structured_output 객체가 없다; "
                    f"result 앞부분: {str(envelope.get('result'))[:200]!r}"
                )
            )
        return structured

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        if os.name != "nt":
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        else:  # pragma: no cover - windows 경로
            with contextlib.suppress(ProcessLookupError):
                process.kill()
        with contextlib.suppress(Exception):
            await process.wait()
