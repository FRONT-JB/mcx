"""Codex CLI를 실행하는 :class:`ExecutionRuntime` 구현.

호출 계약은 upstream `codex exec` 단발 호출과 정렬한다
(``docs/research/RUNTIME_UPSTREAM_FINDINGS.md`` §3~§5) — 프롬프트는
stdin(ARG_MAX 회피), ``--json``으로 JSONL 이벤트, ``-C``로 workspace 경계,
``--output-last-message``로 최종 메시지 수집. 권한은 ``--full-auto``
(workspace-write) 하나이며 bypass로 가는 코드 경로가 없다 (ADR-0033 §4).

**adapter는 스스로 재시도하지 않는다** — 실행은 부작용 시점을 입증할 수
없으므로 실패는 outcome으로 반환하고, 재시도는 Recover의 예산·증거 경로가
소유한다. 예외는 프로세스 시작 자체가 불가능한 경우뿐이다(호출자인
ExecuteService가 실행 실패로 정규화한다).

timeout은 총 시간이 아니라 **출력 침묵**이다 — 마지막 출력 이후
``silence_timeout_seconds``가 지나면 process group을 정리하고 실패를
반환한다 (upstream stall 기준 채택).

계약: ``docs/03_RUNTIME.md`` §13.1
결정: ``docs/adr/0033-first-runtime-adapter-contract.md``
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path
import signal
import tempfile

from mission_control.application.ports import ExecutionOutcome, ExecutionRequest

#: upstream `STALL_TIMEOUT_SECONDS` 채택 — 침묵 기준이지 총 시간이 아니다.
SILENCE_TIMEOUT_SECONDS = 900.0

#: 실패 보고에 싣는 합류 출력 발췌 한도 (Verify 증거 발췌와 같은 값).
_OUTPUT_TAIL_CHARS = 2_000


def render_prompt(request: ExecutionRequest) -> str:
    """구조화된 요청을 worker 프롬프트로 렌더링한다.

    계약 블록의 문장은 영어 원문이다 — 문장이 곧 계약인 곳에 번역을 두지
    않는다 (ADR-0033 §5). SUCCESS CONTRACT 블록은 upstream
    ``_build_success_contract_block``과, 실패 전달 블록은 upstream 재시도
    프롬프트 3요소와 정렬한다.
    """
    criterion = request.criterion
    parts: list[str] = [f"## Goal\n{request.goal}"]
    if request.constraints:
        parts.append("## Constraints\n" + "\n".join(f"- {item}" for item in request.constraints))
    if request.non_goals:
        parts.append(
            "## Non-goals (do not implement)\n"
            + "\n".join(f"- {item}" for item in request.non_goals)
        )
    parts.append(f"## Acceptance criterion\n{criterion.description}")

    if criterion.is_mechanically_verifiable:
        lines = ["SUCCESS CONTRACT for this AC:"]
        if criterion.verify_command:
            lines.append(
                f"- Run locally before completion: {criterion.verify_command}. "
                "The verify gate re-runs it and records authoritative evidence."
            )
        if criterion.expected_artifacts:
            lines.append(
                "- Expected artifacts: "
                + ", ".join(criterion.expected_artifacts)
                + " — ensure they exist in the workspace"
            )
        if criterion.output_assertion:
            lines.append(f"- Expected output: {criterion.output_assertion}")
        parts.append("\n".join(lines))

    failure = request.previous_failure
    if failure is not None:
        lines = [
            "## Prior failure",
            f"- Classification: {failure.classification}",
            f"- Source: {failure.source}",
            "- Last error (tail):",
            failure.error_excerpt,
        ]
        if failure.change_approach:
            lines.append(
                "Do not repeat the failed path. Continue the same task, but switch "
                "strategy — take a different approach that advances the acceptance "
                "criterion."
            )
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


class CodexExecutionRuntime:
    """``codex exec`` 단발 호출로 AC 하나를 실행한다."""

    backend = "codex_cli"

    def __init__(
        self,
        *,
        cli_path: str = "codex",
        silence_timeout_seconds: float = SILENCE_TIMEOUT_SECONDS,
    ) -> None:
        self._cli_path = cli_path
        self._silence_timeout_seconds = silence_timeout_seconds

    def build_command(self, *, workspace: str, last_message_path: str) -> tuple[str, ...]:
        """`codex exec` 명령을 구성한다. 프롬프트는 여기 없다 — stdin이다.

        순수 함수로 분리한 이유는 conformance test가 CLI 실물 없이 명령
        구성을 고정하기 위해서다 (ADR-0033 Verification).
        """
        return (
            self._cli_path,
            "exec",
            "--json",
            "--skip-git-repo-check",
            "-C",
            workspace,
            "--output-last-message",
            last_message_path,
            # upstream은 `--full-auto`를 쓰지만 실물 codex 0.146.1 exec에는
            # 그 플래그가 없다 — 같은 의미의 sandbox 모드를 직접 지정한다
            # (2026-08-08 스모크에서 확인, ADR-0033 정정 노트).
            "--sandbox",
            "workspace-write",
        )

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        descriptor, last_message_name = tempfile.mkstemp(suffix=".codex-last-message.txt")
        os.close(descriptor)
        last_message_path = Path(last_message_name)
        try:
            return await self._run(request, last_message_path)
        finally:
            last_message_path.unlink(missing_ok=True)

    async def _run(self, request: ExecutionRequest, last_message_path: Path) -> ExecutionOutcome:
        command = self.build_command(
            workspace=request.workspace, last_message_path=str(last_message_path)
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )
        assert process.stdin is not None and process.stdout is not None

        process.stdin.write(render_prompt(request).encode("utf-8"))
        await process.stdin.drain()
        process.stdin.close()

        native_session_id: str | None = None
        output_tail = ""
        while True:
            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(), timeout=self._silence_timeout_seconds
                )
            except TimeoutError:
                await self._terminate(process)
                return ExecutionOutcome(
                    succeeded=False,
                    native_session_id=native_session_id,
                    error=(
                        f"codex exec went silent for {self._silence_timeout_seconds:.0f}s; "
                        "the process group was terminated"
                    ),
                )
            if not line:
                break
            text = line.decode("utf-8", errors="replace")
            output_tail = (output_tail + text)[-_OUTPUT_TAIL_CHARS:]
            native_session_id = self._thread_id_from(text) or native_session_id

        try:
            exit_code = await asyncio.wait_for(
                process.wait(), timeout=self._silence_timeout_seconds
            )
        except TimeoutError:
            await self._terminate(process)
            return ExecutionOutcome(
                succeeded=False,
                native_session_id=native_session_id,
                error="codex exec closed its output but did not exit; terminated",
            )

        if exit_code != 0:
            return ExecutionOutcome(
                succeeded=False,
                native_session_id=native_session_id,
                error=f"codex exec exited with status {exit_code}: {output_tail.strip()}",
            )

        summary = last_message_path.read_text(encoding="utf-8", errors="replace").strip()
        return ExecutionOutcome(
            succeeded=True,
            native_session_id=native_session_id,
            result_summary=summary or None,
        )

    @staticmethod
    def _thread_id_from(line: str) -> str | None:
        """JSONL 이벤트에서 thread id를 추출한다.

        upstream 이벤트 형태 채택: ``{"type": "thread.started", "thread_id": ...}``
        (RUNTIME_UPSTREAM_FINDINGS §5).
        """
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(event, dict) or event.get("type") != "thread.started":
            return None
        thread_id = event.get("thread_id")
        return thread_id if isinstance(thread_id, str) and thread_id else None

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
