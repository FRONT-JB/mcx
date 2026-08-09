"""Codex 완성 엔진 — 명령·strict schema·재시도·파싱 실패의 conformance.

계약: docs/adr/0034-codex-text-backend-contract.md §1~§4
"""

from pathlib import Path
import stat
import sys
import textwrap

import pytest

from mission_control.adapters.text.codex_completion import (
    CodexCompletion,
    CodexCompletionError,
)
from mission_control.adapters.text.completion_engine import strict_schema

SCHEMA = strict_schema({"answer": {"type": "string"}})


def _write_stub(directory: Path, name: str, body: str) -> str:
    script = directory / f"{name}.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    launcher = directory / name
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return str(launcher)


class TestCommand:
    def test_the_sandbox_is_read_only(self) -> None:
        """위임 role은 텍스트만 만든다 — 쓰기 플래그가 없다 (ADR-0034 §2)."""
        command = CodexCompletion(cli_path="codex").build_command(
            last_message_path="/l", schema_path="/s"
        )
        assert command == (
            "codex",
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--output-last-message",
            "/l",
            "--output-schema",
            "/s",
            "--sandbox",
            "read-only",
        )
        assert "--full-auto" not in command

    def test_strict_schema_shape(self) -> None:
        """Codex 요구: 전 필드 required + additionalProperties false."""
        schema = strict_schema({"a": {"type": "string"}, "b": {"type": "number"}})
        assert schema["required"] == ["a", "b"]
        assert schema["additionalProperties"] is False


SUCCESS_STUB = """
    import json, sys
    arguments = sys.argv[1:]
    last_message_path = arguments[arguments.index("--output-last-message") + 1]
    schema_path = arguments[arguments.index("--output-schema") + 1]
    prompt = sys.stdin.read()
    with open(schema_path) as handle:
        schema = json.load(handle)
    assert schema["additionalProperties"] is False, "schema must be strict"
    with open(last_message_path, "w") as handle:
        json.dump({"answer": "구조화 응답"}, handle)
    sys.exit(0)
"""

TRANSIENT_THEN_OK_STUB = """
    import json, os, sys
    arguments = sys.argv[1:]
    last_message_path = arguments[arguments.index("--output-last-message") + 1]
    sys.stdin.read()
    marker = os.environ["STUB_MARKER"]
    if not os.path.exists(marker):
        open(marker, "w").close()
        print("rate limit exceeded, try again")
        sys.exit(1)
    with open(last_message_path, "w") as handle:
        json.dump({"answer": "두 번째에 성공"}, handle)
    sys.exit(0)
"""

HARD_FAILURE_STUB = """
    import os, sys
    sys.stdin.read()
    with open(os.environ["STUB_CALLS"], "a") as handle:
        handle.write("called\\n")
    print("invalid api key")
    sys.exit(1)
"""

GARBAGE_STUB = """
    import sys
    arguments = sys.argv[1:]
    last_message_path = arguments[arguments.index("--output-last-message") + 1]
    sys.stdin.read()
    with open(last_message_path, "w") as handle:
        handle.write("this is not json {")
    sys.exit(0)
"""


class TestCompleteJson:
    async def test_a_structured_response_round_trips(self, tmp_path: Path) -> None:
        engine = CodexCompletion(cli_path=_write_stub(tmp_path, "codex-ok", SUCCESS_STUB))
        result = await engine.complete_json(prompt="질문", schema=SCHEMA)
        assert result == {"answer": "구조화 응답"}

    async def test_a_transient_failure_is_retried(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("STUB_MARKER", str(tmp_path / "marker"))
        engine = CodexCompletion(
            cli_path=_write_stub(tmp_path, "codex-flaky", TRANSIENT_THEN_OK_STUB)
        )
        result = await engine.complete_json(prompt="질문", schema=SCHEMA)
        assert result == {"answer": "두 번째에 성공"}

    async def test_a_hard_failure_is_not_retried(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = tmp_path / "calls.txt"
        monkeypatch.setenv("STUB_CALLS", str(calls))
        engine = CodexCompletion(cli_path=_write_stub(tmp_path, "codex-hard", HARD_FAILURE_STUB))
        with pytest.raises(CodexCompletionError, match="invalid api key"):
            await engine.complete_json(prompt="질문", schema=SCHEMA)
        assert calls.read_text(encoding="utf-8") == "called\n"

    async def test_garbage_output_is_never_interpreted_as_success(self, tmp_path: Path) -> None:
        """손상 출력은 성공이 아니라 예외다 (ADR-0034 §4)."""
        engine = CodexCompletion(cli_path=_write_stub(tmp_path, "codex-junk", GARBAGE_STUB))
        with pytest.raises(CodexCompletionError, match="올바른 JSON이 아니다"):
            await engine.complete_json(prompt="질문", schema=SCHEMA)
