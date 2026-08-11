"""위임 port들이 공유하는 Codex 구조화 완성 엔진.

`codex exec` 단발 호출로 프롬프트를 보내고 strict JSON schema로 구조화
출력을 받는다 (``docs/research/RUNTIME_UPSTREAM_FINDINGS.md`` §7). 완성은
부작용이 없으므로 transient 실패에 한해 재시도한다 — 실행 adapter와의
의도적 비대칭이다 (ADR-0033 §4, ADR-0034 §3).

위임 role은 텍스트만 만든다 — sandbox는 **읽기 전용**이다 (ADR-0034 §2).
구조화 출력의 파싱 실패는 성공으로 해석하지 않고 예외로 드러낸다 (§4).

계약: ``docs/adr/0034-codex-text-backend-contract.md``
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path
import signal
import tempfile
from typing import Any

from mission_control.adapters.codex_stream import (
    BoundedCodexJsonlReader,
    CodexJsonlLineTooLong,
)
from mission_control.adapters.text.completion_engine import (
    MAX_ATTEMPTS,
    CompletionError,
    is_transient,
)

#: upstream stall 기준 채택 — 침묵이지 총 시간이 아니다 (ADR-0033 §4).
SILENCE_TIMEOUT_SECONDS = 900.0

_OUTPUT_TAIL_CHARS = 2_000


class CodexCompletionError(CompletionError):
    """완성 호출이 사용할 수 있는 구조화 출력을 만들지 못했다.

    파싱 실패·schema 위반·timeout·비일시적 오류가 전부 여기다 — 어느 것도
    조용히 성공으로 해석되지 않는다 (ADR-0034 §4).
    """

    def __init__(self, *, reason: str) -> None:
        super().__init__(reason=reason, engine="codex")


class CodexCompletion:
    """프롬프트 하나를 보내고 schema에 맞는 JSON 하나를 받는다."""

    def __init__(
        self,
        *,
        cli_path: str = "codex",
        silence_timeout_seconds: float = SILENCE_TIMEOUT_SECONDS,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self._cli_path = cli_path
        self._silence_timeout_seconds = silence_timeout_seconds
        self._max_attempts = max_attempts

    @property
    def backend(self) -> str:
        return "codex"

    def build_command(
        self, *, last_message_path: str, schema_path: str, workspace: str | None = None
    ) -> tuple[str, ...]:
        """완성 명령을 구성한다 — 읽기 전용 sandbox, 쓰기 플래그 없음.

        ``workspace``가 있으면 ``-C``로 그 안에서 관찰한다 — 판정류 role이
        실제 작업물을 검사해야 할 때 필수다 (실물 스모크에서 관측된 결함의
        수정, ADR-0034 정정).
        """
        command = [
            self._cli_path,
            "exec",
            "--json",
            "--skip-git-repo-check",
        ]
        if workspace is not None:
            command.extend(["-C", workspace])
        command.extend(
            [
                "--output-last-message",
                last_message_path,
                "--output-schema",
                schema_path,
                "--sandbox",
                "read-only",
            ]
        )
        return tuple(command)

    async def complete_json(
        self, *, prompt: str, schema: dict[str, Any], workspace: str | None = None
    ) -> dict[str, Any]:
        """구조화 완성 한 번 — transient 실패만 재시도한다."""
        last_error = "no attempt was made"
        for attempt in range(self._max_attempts):
            outcome = await self._attempt(prompt, schema, workspace)
            if isinstance(outcome, dict):
                return outcome
            last_error = outcome
            if not is_transient(outcome) or attempt >= self._max_attempts - 1:
                raise CodexCompletionError(reason=outcome)
            await asyncio.sleep(2**attempt)
        raise CodexCompletionError(reason=last_error)

    async def _attempt(
        self, prompt: str, schema: dict[str, Any], workspace: str | None
    ) -> dict[str, Any] | str:
        """한 번의 호출. 성공이면 dict, 실패면 오류 설명 문자열을 반환한다.

        timeout과 파싱 실패는 즉시 예외다 — transient가 아니므로 재시도
        루프로 돌아가지 않는다 (ADR-0034 §3~§4).
        """
        message_fd, message_name = tempfile.mkstemp(suffix=".codex-last-message.txt")
        os.close(message_fd)
        schema_fd, schema_name = tempfile.mkstemp(suffix=".codex-schema.json")
        os.close(schema_fd)
        message_path, schema_path = Path(message_name), Path(schema_name)
        try:
            schema_path.write_text(json.dumps(schema), encoding="utf-8")
            if workspace is not None:
                return await self._invoke(prompt, message_path, schema_path, workspace)
            # ``None``은 부모 cwd 상속이 아니라 작업물 관찰 권한 없음이다.
            # Codex에는 도구 allowlist가 없으므로 빈 cwd로 capability를 실제로
            # 좁힌다 (ADR-0034 §2, dogfood 2026-08-11).
            with tempfile.TemporaryDirectory(prefix="mcx-codex-context-") as neutral_workspace:
                return await self._invoke(prompt, message_path, schema_path, neutral_workspace)
        finally:
            message_path.unlink(missing_ok=True)
            schema_path.unlink(missing_ok=True)

    async def _invoke(
        self, prompt: str, message_path: Path, schema_path: Path, workspace: str | None
    ) -> dict[str, Any] | str:
        command = self.build_command(
            last_message_path=str(message_path),
            schema_path=str(schema_path),
            workspace=workspace,
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(prompt.encode("utf-8"))
        await process.stdin.drain()
        process.stdin.close()

        output_tail = ""
        stdout = BoundedCodexJsonlReader(process.stdout)
        while True:
            try:
                line = await asyncio.wait_for(
                    stdout.readline(), timeout=self._silence_timeout_seconds
                )
            except TimeoutError:
                await self._terminate(process)
                raise CodexCompletionError(
                    reason=(
                        f"{self._silence_timeout_seconds:.0f}초 동안 출력이 없었다; "
                        "process group을 정리했다"
                    )
                ) from None
            except CodexJsonlLineTooLong as error:
                await self._terminate(process)
                raise CodexCompletionError(reason=str(error)) from error
            if not line:
                break
            output_tail = (output_tail + line.decode("utf-8", errors="replace"))[
                -_OUTPUT_TAIL_CHARS:
            ]

        exit_code = await process.wait()
        if exit_code != 0:
            return f"codex exec exited with status {exit_code}: {output_tail.strip()}"

        raw = message_path.read_text(encoding="utf-8", errors="replace").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise CodexCompletionError(
                reason=f"구조화 출력이 올바른 JSON이 아니다 ({error}): {raw[:200]!r}"
            ) from error
        if not isinstance(parsed, dict):
            raise CodexCompletionError(reason=f"구조화 출력이 JSON 객체가 아니다: {raw[:200]!r}")
        return parsed

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
