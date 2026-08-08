"""Brief 위임 port들의 Codex 구현 — 프롬프트 정렬, 바인딩, 변환.

계약: docs/adr/0034-codex-text-backend-contract.md, docs/adr/0020 §4~§5
"""

from pathlib import Path
import stat
import sys
import textwrap

import pytest

from mission_control.adapters.text.brief_backends import (
    ClarityDimensionMismatchError,
    PromptedClarityAssessor,
    PromptedClosureAssessor,
    PromptedClosureChallenger,
    PromptedQuestionGenerator,
)
from mission_control.adapters.text.codex_completion import CodexCompletion
from mission_control.application.ports import (
    AskedRound,
    AssessmentRequest,
    CloserAuditRequest,
    ClosureChallengeRequest,
    QuestionRequest,
    RequirementView,
)
from mission_control.domain.brief.closure import AdvisoryLane, CloserVerdict, ClosureSeverity
from mission_control.domain.brief.requirement import CandidateResolution, RequirementSection


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


ROUNDS = (AskedRound(question="누가 쓰나요?", answer="로그인 사용자"),)
OPEN = (
    RequirementView(
        section=RequirementSection.NON_GOAL,
        text="댓글 수정은 범위 밖",
        resolution=CandidateResolution.NEEDS_CONFIRMATION,
        required=True,
    ),
)


class TestQuestionGenerator:
    def test_the_role_boundary_is_upstream_aligned(self, tmp_path: Path) -> None:
        generator = PromptedQuestionGenerator(completion=_engine(tmp_path, "q", "{}"))
        prompt = generator.render_prompt(
            QuestionRequest(
                initial_intent="댓글 기능", previous_rounds=ROUNDS, requirement_candidates=OPEN
            )
        )
        assert "You are ONLY an interviewer" in prompt
        assert 'NEVER say "I will implement X"' in prompt
        assert "Q: 누가 쓰나요?" in prompt
        assert "[non_goal] 댓글 수정은 범위 밖" in prompt

    async def test_a_question_round_trips(self, tmp_path: Path) -> None:
        generator = PromptedQuestionGenerator(
            completion=_engine(
                tmp_path,
                "codex-q",
                '{"question": "완료 확인은 무엇으로 하나요?", "targeted_gap": "success_criteria"}',
            )
        )
        result = await generator.generate(
            QuestionRequest(
                initial_intent="댓글 기능", previous_rounds=(), requirement_candidates=()
            )
        )
        assert result.question == "완료 확인은 무엇으로 하나요?"
        assert result.targeted_gap == "success_criteria"


class TestClarityAssessor:
    async def test_scores_carry_the_injected_policy_version(self, tmp_path: Path) -> None:
        assessor = PromptedClarityAssessor(
            completion=_engine(
                tmp_path,
                "codex-clarity",
                '{"scores": [{"dimension": "goal", "clarity": 0.8, "justification": "명확"},'
                ' {"dimension": "constraint", "clarity": 0.5, "justification": "부분"}]}',
            ),
            policy_version="greenfield-v1",
        )
        assessment = await assessor.assess(
            AssessmentRequest(
                initial_intent="댓글 기능",
                previous_rounds=(),
                requirement_candidates=(),
                dimensions=("goal", "constraint"),
            )
        )
        assert assessment.policy_version == "greenfield-v1"
        assert assessment.clarity_of("goal") == 0.8

    async def test_wrong_dimensions_are_rejected(self, tmp_path: Path) -> None:
        """요청하지 않은 축의 채점은 집계에 들어가지 못한다."""
        assessor = PromptedClarityAssessor(
            completion=_engine(
                tmp_path,
                "codex-wrongdim",
                '{"scores": [{"dimension": "goal", "clarity": 0.8, "justification": "명확"}]}',
            ),
            policy_version="greenfield-v1",
        )
        with pytest.raises(ClarityDimensionMismatchError):
            await assessor.assess(
                AssessmentRequest(
                    initial_intent="댓글 기능",
                    previous_rounds=(),
                    requirement_candidates=(),
                    dimensions=("goal", "constraint"),
                )
            )


class TestCloser:
    async def test_a_ready_verdict_has_no_blocking_question(self, tmp_path: Path) -> None:
        assessor = PromptedClosureAssessor(
            completion=_engine(
                tmp_path,
                "codex-closer",
                '{"verdict": "ready", "reason": "nothing material remains",'
                ' "blocking_question": ""}',
            )
        )
        report = await assessor.audit(
            CloserAuditRequest(
                initial_intent="댓글 기능",
                previous_rounds=(),
                requirement_candidates=(),
                gate_summary="no unresolved decisions that materially change implementation",
            )
        )
        assert report.verdict is CloserVerdict.READY
        assert report.blocking_question is None

    def test_the_gate_summary_is_carried_verbatim(self, tmp_path: Path) -> None:
        assessor = PromptedClosureAssessor(completion=_engine(tmp_path, "c", "{}"))
        prompt = assessor.render_prompt(
            CloserAuditRequest(
                initial_intent="댓글 기능",
                previous_rounds=(),
                requirement_candidates=(),
                gate_summary="VERBATIM POLICY SENTENCE",
            )
        )
        assert "VERBATIM POLICY SENTENCE" in prompt


class TestChallenger:
    async def test_the_lane_is_bound_from_the_request(self, tmp_path: Path) -> None:
        """lane은 응답이 아니라 요청에서 온다 (ADR-0034 §5와 같은 축)."""
        challenger = PromptedClosureChallenger(
            completion=_engine(
                tmp_path,
                "codex-chall",
                '{"severity": "high", "finding": "삭제 권한 결정이 비어 있다",'
                ' "question": "누가 삭제할 수 있나요?"}',
            )
        )
        report = await challenger.challenge(
            ClosureChallengeRequest(
                lane=AdvisoryLane.GAP_HUNTER,
                challenge="find the missing decision",
                severity_rule="high blocks closure",
                initial_intent="댓글 기능",
                previous_rounds=(),
                requirement_candidates=(),
            )
        )
        assert report.lane is AdvisoryLane.GAP_HUNTER
        assert report.severity is ClosureSeverity.HIGH
        assert report.question == "누가 삭제할 수 있나요?"
