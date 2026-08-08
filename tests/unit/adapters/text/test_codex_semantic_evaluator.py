"""Codex semantic 평가자 — 프롬프트 정렬, verdict 바인딩, 손상 출력 거부.

계약: docs/adr/0034-codex-text-backend-contract.md §5
"""

from pathlib import Path
import stat
import sys
import textwrap

from pydantic import ValidationError
import pytest

from mission_control.adapters.text.codex_completion import CodexCompletion
from mission_control.adapters.text.codex_semantic_evaluator import (
    VERDICT_SCHEMA,
    CodexSemanticEvaluator,
    render_prompt,
)
from mission_control.application.ports import SemanticEvaluationRequest
from mission_control.domain.blueprint.spec import AcceptanceCriterion
from mission_control.domain.verify.evidence import VerificationRun

CONTRACTED = AcceptanceCriterion(
    description="목록에 댓글이 보인다",
    verify_command="pytest -k list",
    output_assertion="passed",
)


def _request(mechanical_run: VerificationRun | None = None) -> SemanticEvaluationRequest:
    return SemanticEvaluationRequest(
        goal="댓글 기능",
        constraints=("로그인 사용자만",),
        non_goals=("수정·삭제 제외",),
        criterion=CONTRACTED,
        mechanical_run=mechanical_run,
    )


class TestPrompt:
    def test_the_contract_sentence_is_upstream_verbatim(self) -> None:
        prompt = render_prompt(_request())
        assert (
            "The AC passes ONLY if the artifact demonstrates the declared contract "
            "was met. Cite the evidence line." in prompt
        )
        assert "- verify_command: pytest -k list" in prompt
        assert "## Original Goal\n댓글 기능" in prompt

    def test_mechanical_evidence_is_carried(self) -> None:
        run = VerificationRun(
            ac_key=CONTRACTED.key,
            command="pytest -k list",
            exit_code=0,
            passed=True,
            output_tail="3 passed",
        )
        prompt = render_prompt(_request(run))
        assert "## Mechanical verification evidence" in prompt
        assert "- exit_code: 0" in prompt
        assert "3 passed" in prompt

    def test_the_schema_matches_the_verdict_fields(self) -> None:
        assert set(VERDICT_SCHEMA["required"]) == {
            "satisfied",
            "score",
            "uncertainty",
            "reward_hacking_risk",
            "reasoning",
            "evidence",
            "questions_used",
        }
        assert VERDICT_SCHEMA["additionalProperties"] is False


def _write_stub(directory: Path, name: str, verdict_json: str) -> str:
    body = f"""
    import sys
    arguments = sys.argv[1:]
    last_message_path = arguments[arguments.index("--output-last-message") + 1]
    sys.stdin.read()
    with open(last_message_path, "w") as handle:
        handle.write('''{verdict_json}''')
    sys.exit(0)
    """
    script = directory / f"{name}.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    launcher = directory / name
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return str(launcher)


class TestAssess:
    async def test_the_verdict_is_bound_to_the_requested_criterion(self, tmp_path: Path) -> None:
        """ac_key는 평가자가 아니라 adapter가 바인딩한다 (ADR-0034 §5)."""
        stub = _write_stub(
            tmp_path,
            "codex-verdict",
            '{"satisfied": true, "score": 0.9, "uncertainty": 0.1, '
            '"reward_hacking_risk": 0.0, "reasoning": "contract demonstrated", '
            '"evidence": ["report.md exists"], "questions_used": ["does it render?"]}',
        )
        evaluator = CodexSemanticEvaluator(completion=CodexCompletion(cli_path=stub))

        verdict = await evaluator.assess(_request())

        assert verdict.ac_key == CONTRACTED.key
        assert verdict.satisfied is True
        assert verdict.score == 0.9
        assert verdict.evidence == ("report.md exists",)

    async def test_an_out_of_range_verdict_is_rejected_not_clamped(self, tmp_path: Path) -> None:
        stub = _write_stub(
            tmp_path,
            "codex-broken",
            '{"satisfied": true, "score": 1.7, "uncertainty": 0.1, '
            '"reward_hacking_risk": 0.0, "reasoning": "score out of range", '
            '"evidence": [], "questions_used": []}',
        )
        evaluator = CodexSemanticEvaluator(completion=CodexCompletion(cli_path=stub))

        with pytest.raises(ValidationError):
            await evaluator.assess(_request())
