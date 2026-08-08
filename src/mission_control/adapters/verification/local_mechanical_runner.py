"""검증 명령을 로컬에서 실행하는 :class:`MechanicalRunner` 구현.

upstream AC 수용 gate의 실행 방식을 그대로 따른다
(``docs/research/VERIFY_UPSTREAM_FINDINGS.md`` §2) — shell 실행(승인된 한 줄
명령이 shell 합성을 포함할 수 있다), stderr는 stdout에 합류, 별도 세션으로
시작해 timeout 시 process group 전체를 종료한다. timeout은 예외가 아니라
``timed_out`` 결과다 — 예외는 시작 자체가 불가능한 경우뿐이다.

계약: ``docs/adr/0028-verify-v1-mechanical-contract.md`` §3
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
import signal

from mission_control.domain.verify.evidence import CommandExecution


class LocalMechanicalRunner:
    """검증 워크스페이스에서 명령을 직접 실행한다."""

    async def missing_artifacts(
        self, *, workspace: str, artifacts: tuple[str, ...]
    ) -> tuple[str, ...]:
        """workspace 아래 존재하지 않는 artifact 경로 전부를 반환한다.

        경로는 승인된 Blueprint의 내용 그대로를 문자적으로 해석한다 —
        upstream과 같다 ("resolved literally").
        """
        root = Path(workspace)
        return tuple(item for item in artifacts if not (root / item).exists())

    async def run(self, *, command: str, workspace: str, timeout_seconds: int) -> CommandExecution:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            # timeout 시 process group 전체를 정리하기 위해 별도 세션으로
            # 시작한다. Windows에는 이 개념이 없다.
            start_new_session=os.name != "nt",
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            if os.name != "nt":
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
            else:  # pragma: no cover - windows 경로
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
            with contextlib.suppress(Exception):
                await process.wait()
            return CommandExecution(timed_out=True)

        exit_code = process.returncode if process.returncode is not None else 0
        return CommandExecution(
            exit_code=exit_code,
            output=(stdout or b"").decode("utf-8", errors="replace"),
        )
