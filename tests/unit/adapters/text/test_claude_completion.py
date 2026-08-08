"""Claude 완성 엔진 conformance — 명령 구성, 봉투, structured_output, 재시도.

CLI 실물 없이 stub 실행 파일로 계약을 고정한다. 실물 플래그와 envelope 형태는
2026-08-08 스모크로 확인되었다 (RUNTIME_UPSTREAM_FINDINGS §10).

계약: docs/adr/0036-claude-text-lane-contract.md
"""

import json
from pathlib import Path
import stat
import sys
import textwrap

import pytest

from mission_control.adapters.text.claude_completion import (
    ClaudeCompletion,
    ClaudeCompletionError,
)
from mission_control.adapters.text.semantic_evaluator import PromptedSemanticEvaluator
from mission_control.application.ports import SemanticEvaluationRequest
from mission_control.domain.blueprint.spec import AcceptanceCriterion

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "number"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def _write_stub(directory: Path, name: str, body: str) -> str:
    script = directory / f"{name}.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    launcher = directory / name
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return str(launcher)


def _echo_stub(directory: Path) -> str:
    """stdin 프롬프트·argv·cwd를 structured_output으로 되돌려 주는 성공 stub."""
    return _write_stub(
        directory,
        "claude-echo",
        """
        import json, os, sys
        prompt = sys.stdin.read()
        print(json.dumps({
            "is_error": False,
            "subtype": "success",
            "result": "ignored string form",
            "structured_output": {
                "echo": prompt,
                "argv": sys.argv[1:],
                "cwd": os.getcwd(),
            },
        }))
        """,
    )


class TestBuildCommand:
    def test_the_no_tools_envelope_empties_the_catalog(self) -> None:
        """--tools ""가 카탈로그를 비우고 --allowedTools는 억제일 뿐 — 둘 다
        넘긴다 (upstream claude_code_adapter.py:697-702)."""
        engine = ClaudeCompletion(cli_path="claude")
        assert engine.build_command(schema_json="{}") == (
            "claude",
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            "{}",
            "--tools",
            "",
            "--allowedTools",
            "",
            "--max-turns",
            "1",
            "--strict-mcp-config",
            "--setting-sources",
            "",
        )

    def test_the_observe_envelope_grants_read_tools_only(self) -> None:
        """upstream "20-turn read-only envelope" 정렬 (ADR-0036 §4)."""
        engine = ClaudeCompletion(cli_path="claude", model="haiku")
        command = engine.build_command(schema_json="{}", workspace="/tmp/ws")
        assert ("--model", "haiku") == command[4:6]
        assert ("--tools", "Read Glob Grep") in zip(command, command[1:], strict=False)
        assert ("--max-turns", "20") in zip(command, command[1:], strict=False)
        assert "Write" not in " ".join(command)
        assert "Bash" not in " ".join(command)


class TestCompleteJson:
    async def test_structured_output_is_consumed_first_class(self, tmp_path: Path) -> None:
        engine = ClaudeCompletion(cli_path=_echo_stub(tmp_path))
        data = await engine.complete_json(prompt="the prompt", schema=SCHEMA)

        assert data["echo"] == "the prompt"
        schema_index = data["argv"].index("--json-schema") + 1
        assert json.loads(data["argv"][schema_index]) == SCHEMA

    async def test_workspace_becomes_the_working_directory(self, tmp_path: Path) -> None:
        """평가자는 작업물 안에서 관찰한다 — cwd가 곧 workspace 경계다."""
        workspace = tmp_path / "ws"
        workspace.mkdir()
        engine = ClaudeCompletion(cli_path=_echo_stub(tmp_path))

        data = await engine.complete_json(prompt="p", schema=SCHEMA, workspace=str(workspace))

        assert Path(data["cwd"]).resolve() == workspace.resolve()
        assert ("--tools", "Read Glob Grep") in zip(data["argv"], data["argv"][1:], strict=False)

    async def test_transient_error_envelope_is_retried(self, tmp_path: Path) -> None:
        marker = tmp_path / "attempts"
        stub = _write_stub(
            tmp_path,
            "claude-flaky",
            f"""
            import json, pathlib, sys
            sys.stdin.read()
            marker = pathlib.Path({str(marker)!r})
            attempt = int(marker.read_text()) if marker.exists() else 0
            marker.write_text(str(attempt + 1))
            if attempt == 0:
                print(json.dumps({{"is_error": True, "result": "429 rate limit"}}))
            else:
                print(json.dumps({{"is_error": False, "structured_output": {{"answer": 42}}}}))
            """,
        )
        engine = ClaudeCompletion(cli_path=stub)

        data = await engine.complete_json(prompt="p", schema=SCHEMA)

        assert data == {"answer": 42}
        assert marker.read_text() == "2"

    async def test_non_transient_error_fails_without_retry(self, tmp_path: Path) -> None:
        marker = tmp_path / "attempts"
        stub = _write_stub(
            tmp_path,
            "claude-denied",
            f"""
            import json, pathlib, sys
            sys.stdin.read()
            marker = pathlib.Path({str(marker)!r})
            attempt = int(marker.read_text()) if marker.exists() else 0
            marker.write_text(str(attempt + 1))
            print(json.dumps({{"is_error": True, "subtype": "error", "result": "invalid schema"}}))
            """,
        )
        engine = ClaudeCompletion(cli_path=stub)

        with pytest.raises(ClaudeCompletionError, match="invalid schema"):
            await engine.complete_json(prompt="p", schema=SCHEMA)
        assert marker.read_text() == "1"

    async def test_missing_structured_output_is_corruption_not_success(
        self, tmp_path: Path
    ) -> None:
        stub = _write_stub(
            tmp_path,
            "claude-prose",
            """
            import json, sys
            sys.stdin.read()
            print(json.dumps({"is_error": False, "result": "prose without structure"}))
            """,
        )
        engine = ClaudeCompletion(cli_path=stub)

        with pytest.raises(ClaudeCompletionError, match="no structured_output"):
            await engine.complete_json(prompt="p", schema=SCHEMA)

    async def test_a_non_json_body_reports_the_cli_failure(self, tmp_path: Path) -> None:
        stub = _write_stub(
            tmp_path,
            "claude-broken",
            """
            import sys
            sys.stdin.read()
            print("usage: unknown flag", file=sys.stderr)
            print("not json")
            sys.exit(2)
            """,
        )
        engine = ClaudeCompletion(cli_path=stub)

        with pytest.raises(ClaudeCompletionError, match="no JSON envelope"):
            await engine.complete_json(prompt="p", schema=SCHEMA)

    async def test_total_timeout_terminates_the_process(self, tmp_path: Path) -> None:
        """print 모드는 끝에 한 번 보고하므로 timeout은 침묵이 아니라 총 시간이다
        (ADR-0036 §3)."""
        stub = _write_stub(
            tmp_path,
            "claude-hang",
            """
            import sys, time
            sys.stdin.read()
            time.sleep(30)
            """,
        )
        engine = ClaudeCompletion(cli_path=stub, timeout_seconds=0.5)

        with pytest.raises(ClaudeCompletionError, match="exceeded"):
            await engine.complete_json(prompt="p", schema=SCHEMA)


class TestPromptedClassesAcceptTheClaudeEngine:
    async def test_semantic_evaluator_runs_over_claude(self, tmp_path: Path) -> None:
        """프롬프트 클래스는 엔진 protocol만 요구한다 (ADR-0036 §2) — 같은
        클래스가 Codex 엔진 테스트(test_semantic_evaluator.py)와 이 Claude
        엔진 양쪽에서 돈다."""
        stub = _write_stub(
            tmp_path,
            "claude-verdict",
            """
            import json, sys
            sys.stdin.read()
            print(json.dumps({
                "is_error": False,
                "structured_output": {
                    "satisfied": True,
                    "score": 0.95,
                    "uncertainty": 0.05,
                    "reward_hacking_risk": 0.0,
                    "reasoning": "the contract is demonstrated",
                    "evidence": ["command output line"],
                    "questions_used": [],
                },
            }))
            """,
        )
        evaluator = PromptedSemanticEvaluator(completion=ClaudeCompletion(cli_path=stub))

        verdict = await evaluator.assess(
            SemanticEvaluationRequest(
                goal="댓글 기능",
                constraints=(),
                non_goals=(),
                criterion=AcceptanceCriterion(description="목록에 댓글이 보인다"),
                workspace=str(tmp_path),
            )
        )

        assert verdict.satisfied is True
        assert verdict.ac_key == AcceptanceCriterion(description="목록에 댓글이 보인다").key
