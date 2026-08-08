"""Blueprint 위임 port들의 Codex 구현 — 원문 보존 지시, 변환, quality bar.

계약: docs/adr/0034, docs/adr/0018, docs/adr/0019 §4 (원문 재평가)
"""

from pathlib import Path
import stat
import sys
import textwrap

from mission_control.adapters.text.codex_blueprint_backends import (
    CodexBlueprintGenerator,
    CodexBlueprintQaJudge,
)
from mission_control.adapters.text.codex_completion import CodexCompletion
from mission_control.application.ports import (
    BlueprintGenerationRequest,
    QaIteration,
    QaRequest,
)
from mission_control.domain.blueprint.qa import BLUEPRINT_QUALITY_BAR, QaDimension, QaFinding
from mission_control.domain.blueprint.spec import AcceptanceCriterion


def _write_stub(directory: Path, name: str, response_json: str) -> str:
    body = f"""
    import sys
    arguments = sys.argv[1:]
    last_message_path = arguments[arguments.index("--output-last-message") + 1]
    sys.stdin.read()
    with open(last_message_path, "w") as handle:
        handle.write('''{response_json}''')
    sys.exit(0)
    """
    script = directory / f"{name}.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    launcher = directory / name
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return str(launcher)


def _engine(tmp_path: Path, name: str, response_json: str) -> CodexCompletion:
    return CodexCompletion(cli_path=_write_stub(tmp_path, name, response_json))


REQUEST = BlueprintGenerationRequest(
    goals=("댓글 기능",),
    constraints=("로그인 사용자만",),
    non_goals=("수정·삭제 제외",),
    success_criteria=("목록에 댓글이 보인다",),
    context=("이 프로젝트는 pytest를 쓴다",),
)


class TestGenerator:
    def test_verbatim_copy_and_granularity_contract(self, tmp_path: Path) -> None:
        generator = CodexBlueprintGenerator(completion=_engine(tmp_path, "g", "{}"))
        prompt = generator.render_prompt(REQUEST)
        assert "Copy every constraint and non-goal EXACTLY as given" in prompt
        assert (
            "An acceptance criterion names a state of the finished work that a "
            "user can see is true." in prompt
        )
        assert "## Constraints (copy verbatim)\n- 로그인 사용자만" in prompt

    async def test_the_draft_round_trips_with_empty_string_sentinels(self, tmp_path: Path) -> None:
        generator = CodexBlueprintGenerator(
            completion=_engine(
                tmp_path,
                "codex-draft",
                '{"goal": "댓글 기능", "constraints": ["로그인 사용자만"],'
                ' "non_goals": ["수정·삭제 제외"],'
                ' "acceptance_criteria": ['
                '{"description": "목록에 댓글이 보인다", "verify_command": "pytest -k list",'
                ' "expected_artifacts": [], "output_assertion": "passed"},'
                '{"description": "코드가 읽기 좋다", "verify_command": "",'
                ' "expected_artifacts": [], "output_assertion": ""}]}',
            )
        )
        draft = await generator.generate(REQUEST)

        assert draft.goal == "댓글 기능"
        assert draft.constraints == ("로그인 사용자만",)
        assert draft.acceptance_criteria[0].verify_command == "pytest -k list"
        assert draft.acceptance_criteria[1].verify_command is None
        assert draft.acceptance_criteria[1].output_assertion is None


class TestQaJudge:
    def test_the_quality_bar_is_the_upstream_original(self, tmp_path: Path) -> None:
        """ADR-0019 §4 재평가 — 채점 계약 문장은 영어 원문이다."""
        judge = CodexBlueprintQaJudge(completion=_engine(tmp_path, "j", "{}"))
        prompt = judge.render_prompt(
            QaRequest(
                goal="댓글 기능",
                constraints=(),
                non_goals=(),
                acceptance_criteria=(AcceptanceCriterion(description="목록에 댓글이 보인다"),),
                quality_bar=BLUEPRINT_QUALITY_BAR,
                pass_threshold=0.9,
                previous_iterations=(QaIteration(iteration=1, score=0.79, verdict="revise"),),
                previous_findings=(QaFinding(detail="확인 명령이 없다"),),
            )
        )
        assert "parsimonious in the ontological sense" in prompt
        assert "ontology_schema" not in prompt  # 유예 필드 절은 제거되었다
        assert "## Findings from the previous round" in prompt
        assert "- 확인 명령이 없다" in prompt

    def test_threshold_trajectory_and_fixed_fields_follow_upstream(self, tmp_path: Path) -> None:
        """upstream 프롬프트 자리 이름 정렬 + verbatim 잠금 보상 문장
        (ADR-0035 §3~§4)."""
        judge = CodexBlueprintQaJudge(completion=_engine(tmp_path, "j2", "{}"))
        prompt = judge.render_prompt(
            QaRequest(
                goal="댓글 기능",
                constraints=("로그인 사용자만",),
                non_goals=(),
                acceptance_criteria=(AcceptanceCriterion(description="목록에 댓글이 보인다"),),
                quality_bar=BLUEPRINT_QUALITY_BAR,
                pass_threshold=0.9,
                previous_iterations=(
                    QaIteration(iteration=1, score=0.79, verdict="revise"),
                    QaIteration(iteration=2, score=0.74, verdict="revise"),
                ),
            )
        )
        assert "## Pass Threshold\n0.9" in prompt
        assert "## Previous Iterations" in prompt
        assert "Iteration 2: score=0.74, verdict=revise" in prompt
        assert "Constraints and non-goals are FIXED inputs at this stage" in prompt

    async def test_the_assessment_round_trips(self, tmp_path: Path) -> None:
        judge = CodexBlueprintQaJudge(
            completion=_engine(
                tmp_path,
                "codex-qa",
                '{"score": 0.86, "dimension_scores": ['
                '{"dimension": "correctness", "score": 0.9},'
                ' {"dimension": "domain_specific", "score": 0.8}],'
                ' "findings": [{"detail": "제약이 모호하다", "suggestion": ""}]}',
            )
        )
        assessment = await judge.assess(
            QaRequest(
                goal="댓글 기능",
                constraints=(),
                non_goals=(),
                acceptance_criteria=(AcceptanceCriterion(description="목록에 댓글이 보인다"),),
                quality_bar=BLUEPRINT_QUALITY_BAR,
                pass_threshold=0.9,
            )
        )
        assert assessment.score == 0.86
        assert (QaDimension.CORRECTNESS, 0.9) in assessment.dimension_scores
        assert assessment.findings[0].suggestion is None
