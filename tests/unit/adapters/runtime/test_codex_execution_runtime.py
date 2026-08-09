"""Codex ExecutionRuntime — 명령 구성·프롬프트·실행 정규화의 conformance.

CLI 실물 없이 검증한다 — 명령 구성과 프롬프트는 순수 함수이고, 실행 계약은
stub 실행 파일(진짜 subprocess)로 고정한다. Runtime 문서 §15 conformance
suite의 첫 적용이다.

계약: docs/adr/0033-first-runtime-adapter-contract.md §4~§5
"""

from pathlib import Path
import stat
import sys
import textwrap

import pytest

from mission_control.adapters.runtime.codex_execution_runtime import (
    CodexExecutionRuntime,
    render_prompt,
)
from mission_control.application.ports import ExecutionRequest
from mission_control.cancellation import cancel_when
from mission_control.domain.blueprint.spec import AcceptanceCriterion
from mission_control.domain.recover.packet import (
    FailureClassification,
    FailureSource,
    PreviousFailure,
)

CONTRACTED = AcceptanceCriterion(
    description="목록에 댓글이 보인다",
    verify_command="pytest -k list",
    expected_artifacts=("report.md",),
    output_assertion="passed",
)
PROSE = AcceptanceCriterion(description="코드가 읽기 좋다")


def _request(
    criterion: AcceptanceCriterion = CONTRACTED,
    *,
    workspace: str = "/tmp/mission",
    previous_failure: PreviousFailure | None = None,
) -> ExecutionRequest:
    return ExecutionRequest(
        goal="댓글 기능",
        constraints=("로그인 사용자만",),
        non_goals=("수정·삭제 제외",),
        criterion=criterion,
        workspace=workspace,
        allowed_tools=("edit",),
        previous_failure=previous_failure,
    )


class TestCommand:
    def test_the_exact_contracted_flags(self) -> None:
        runtime = CodexExecutionRuntime(cli_path="/usr/local/bin/codex")
        command = runtime.build_command(workspace="/w", last_message_path="/tmp/last.txt")

        assert command == (
            "/usr/local/bin/codex",
            "exec",
            "--json",
            "--skip-git-repo-check",
            "-C",
            "/w",
            "--output-last-message",
            "/tmp/last.txt",
            "--sandbox",
            "workspace-write",
        )

    def test_no_bypass_path_exists(self) -> None:
        """권한 상향 플래그로 가는 코드 경로가 없다 (ADR-0033 §4)."""
        command = CodexExecutionRuntime().build_command(workspace="/w", last_message_path="/l")
        assert not any("bypass" in part or "dangerously" in part for part in command)

    def test_the_prompt_is_not_in_the_argv(self) -> None:
        command = CodexExecutionRuntime().build_command(workspace="/w", last_message_path="/l")
        assert all("댓글" not in part for part in command)


class TestPrompt:
    def test_direction_fields_are_rendered(self) -> None:
        prompt = render_prompt(_request())
        assert "## Goal\n댓글 기능" in prompt
        assert "- 로그인 사용자만" in prompt
        assert "## Non-goals (do not implement)\n- 수정·삭제 제외" in prompt
        assert "## Acceptance criterion\n목록에 댓글이 보인다" in prompt

    def test_the_success_contract_block_is_verbatim(self) -> None:
        """계약 블록 문장은 upstream과 정렬된 영어 원문이다 (ADR-0033 §5)."""
        prompt = render_prompt(_request())
        assert "SUCCESS CONTRACT for this AC:" in prompt
        assert (
            "- Run locally before completion: pytest -k list. "
            "The verify gate re-runs it and records authoritative evidence." in prompt
        )
        assert "- Expected artifacts: report.md — ensure they exist in the workspace" in prompt
        assert "- Expected output: passed" in prompt

    def test_a_contract_less_criterion_renders_no_contract_block(self) -> None:
        prompt = render_prompt(_request(PROSE))
        assert "SUCCESS CONTRACT" not in prompt

    def test_a_prior_failure_is_carried(self) -> None:
        failure = PreviousFailure(
            source=FailureSource.MECHANICAL_FAILED,
            classification=FailureClassification.UNCLASSIFIED,
            error_excerpt="verify command exited with status 3",
        )
        prompt = render_prompt(_request(previous_failure=failure))
        assert "## Prior failure" in prompt
        assert "verify command exited with status 3" in prompt
        assert "Do not repeat the failed path" not in prompt

    def test_the_final_attempt_asks_for_a_new_approach(self) -> None:
        failure = PreviousFailure(
            source=FailureSource.EXECUTION_FAILED,
            classification=FailureClassification.UNCLASSIFIED,
            error_excerpt="boom",
            change_approach=True,
        )
        prompt = render_prompt(_request(previous_failure=failure))
        assert "Do not repeat the failed path." in prompt


def _write_stub(directory: Path, name: str, body: str) -> str:
    """stub codex 실행 파일을 만든다 — 진짜 subprocess로 실행 계약을 고정한다."""
    script = directory / f"{name}.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    launcher = directory / name
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return str(launcher)


SUCCESS_STUB = """
    import sys
    arguments = sys.argv[1:]
    last_message_path = arguments[arguments.index("--output-last-message") + 1]
    workspace = arguments[arguments.index("-C") + 1]
    received = sys.stdin.read()
    with open(f"{workspace}/received_prompt.txt", "w") as handle:
        handle.write(received)
    print('{"type": "thread.started", "thread_id": "th-123"}')
    print('{"type": "item.completed"}')
    print("plain text noise is tolerated")
    with open(last_message_path, "w") as handle:
        handle.write("구현을 마쳤고 검증 명령이 로컬에서 통과했다")
    sys.exit(0)
"""

FAILURE_STUB = """
    import sys
    arguments = sys.argv[1:]
    workspace = arguments[arguments.index("-C") + 1]
    with open(f"{workspace}/calls.txt", "a") as handle:
        handle.write("called\\n")
    sys.stdin.read()
    print('{"type": "thread.started", "thread_id": "th-fail"}')
    print("model backend exploded")
    sys.exit(7)
"""

SILENT_STUB = """
    import sys, time
    sys.stdin.read()
    print('{"type": "thread.started", "thread_id": "th-slow"}', flush=True)
    time.sleep(60)
"""


class TestExecute:
    async def test_success_collects_the_thread_and_the_last_message(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        runtime = CodexExecutionRuntime(cli_path=_write_stub(tmp_path, "codex-ok", SUCCESS_STUB))

        outcome = await runtime.execute(_request(workspace=str(workspace)))

        assert outcome.succeeded is True
        assert outcome.native_session_id == "th-123"
        assert outcome.result_summary == "구현을 마쳤고 검증 명령이 로컬에서 통과했다"
        received = (workspace / "received_prompt.txt").read_text(encoding="utf-8")
        assert "## Goal" in received  # 프롬프트가 stdin으로 전달되었다

    async def test_a_nonzero_exit_is_a_failure_outcome_without_a_retry(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        runtime = CodexExecutionRuntime(cli_path=_write_stub(tmp_path, "codex-fail", FAILURE_STUB))

        outcome = await runtime.execute(_request(workspace=str(workspace)))

        assert outcome.succeeded is False
        assert outcome.error is not None
        assert "status 7" in outcome.error
        assert "model backend exploded" in outcome.error
        assert outcome.native_session_id == "th-fail"
        # adapter는 스스로 재시도하지 않는다 (ADR-0033 §4).
        assert (workspace / "calls.txt").read_text(encoding="utf-8") == "called\n"

    async def test_silence_terminates_the_process_group(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        # 임계는 stub 기동(파이썬 프로세스 시작)보다 길고 sleep(60)보다 짧다.
        runtime = CodexExecutionRuntime(
            cli_path=_write_stub(tmp_path, "codex-slow", SILENT_STUB),
            silence_timeout_seconds=2.0,
        )

        outcome = await runtime.execute(_request(workspace=str(workspace)))

        assert outcome.succeeded is False
        assert outcome.error is not None
        assert "silent" in outcome.error
        assert outcome.native_session_id == "th-slow"  # 침묵 전에 받은 신호는 남는다

    async def test_a_cancel_request_terminates_the_running_process(self, tmp_path: Path) -> None:
        """마커를 놓는 것만으로는 안 멈춘다 — runtime이 관측해야 한다 (ADR-0041 §5).

        upstream이 정확히 이 지점에서 계약을 조용히 깼다: 마커는 디스크에
        쓰였는데 실행 프로세스가 볼 수 없었다 (``tools/background.py:16-26``).
        """
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        marker = tmp_path / "cancel_m_1"
        runtime = CodexExecutionRuntime(
            cli_path=_write_stub(tmp_path, "codex-slow", SILENT_STUB),
            # 침묵 기준은 멀리 둔다 — 취소가 끝냈다는 것이 분명해야 한다.
            silence_timeout_seconds=600.0,
            cancel_poll_seconds=0.2,
        )
        marker.write_text("cancel\n", encoding="utf-8")

        with cancel_when(marker.exists):
            outcome = await runtime.execute(_request(workspace=str(workspace)))

        assert outcome.succeeded is False
        assert outcome.error is not None
        assert "cancelled" in outcome.error
        assert "silent" not in outcome.error

    async def test_without_an_observer_the_silence_behaviour_is_unchanged(
        self, tmp_path: Path
    ) -> None:
        """취소 관측이 없으면 폴링도 없다 — 기존 동작이 한 글자도 바뀌지 않는다."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        runtime = CodexExecutionRuntime(
            cli_path=_write_stub(tmp_path, "codex-slow2", SILENT_STUB),
            silence_timeout_seconds=2.0,
        )

        outcome = await runtime.execute(_request(workspace=str(workspace)))

        assert outcome.error is not None
        assert "silent" in outcome.error

    async def test_an_unstartable_cli_raises_for_the_caller_to_normalize(
        self, tmp_path: Path
    ) -> None:
        runtime = CodexExecutionRuntime(cli_path=str(tmp_path / "missing-codex"))
        with pytest.raises(FileNotFoundError):
            await runtime.execute(_request(workspace=str(tmp_path)))
