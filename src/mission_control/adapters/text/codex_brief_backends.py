"""Brief 위임 port들의 Codex 구현 — 질문 생성, clarity 채점, closure 감사.

전부 공통 완성 엔진(:class:`CodexCompletion`) 위의 프롬프트+변환이다
(ADR-0034 §1). 프롬프트가 곧 계약인 지점 — 질문 생성기의 역할 경계와
closure 감사의 기준 문장 — 은 upstream 영어 원문과 정렬한다. closure의
기준 문장(gate_summary·challenge·severity_rule)은 요청에 담겨 오는 정책
원문을 그대로 싣는다 (ADR-0020 §4).

workspace는 없다 — Brief는 저장소를 조사하지 않는다 (Guide §4.3, 필요한
사실은 별도 read-only 경로가 제공한다).

계약: ``docs/adr/0034-codex-text-backend-contract.md``,
``docs/adr/0020-brief-closure-audit.md``
"""

from __future__ import annotations

from mission_control.adapters.text.codex_completion import CodexCompletion, strict_schema
from mission_control.application.ports import (
    AskedRound,
    AssessmentRequest,
    CloserAuditRequest,
    ClosureChallengeRequest,
    GeneratedQuestion,
    QuestionRequest,
    RequirementView,
)
from mission_control.domain.brief.clarity import ClarityAssessment, DimensionScore
from mission_control.domain.brief.closure import AdvisoryReport, CloserReport
from mission_control.domain.errors import MissionControlError


class ClarityDimensionMismatchError(MissionControlError):
    """평가자가 요청된 축과 다른 축을 채점해 돌려주었다.

    임의의 축을 받아들이면 정책의 가중 집계가 성립하지 않는다 (ports의
    AssessmentRequest 계약).
    """

    def __init__(self, *, expected: tuple[str, ...], received: tuple[str, ...]) -> None:
        super().__init__(
            f"assessor scored dimensions {received!r} while {expected!r} were requested"
        )
        self.expected = expected
        self.received = received


def _render_context(
    initial_intent: str,
    previous_rounds: tuple[AskedRound, ...],
    requirement_candidates: tuple[RequirementView, ...],
) -> str:
    parts = [f"## Initial intent\n{initial_intent}"]
    if previous_rounds:
        lines = ["## Previous rounds"]
        for round_ in previous_rounds:
            lines.append(f"Q: {round_.question}")
            lines.append(f"A: {round_.answer if round_.answer is not None else '(unanswered)'}")
        parts.append("\n".join(lines))
    if requirement_candidates:
        # 확정된 후보도 함께 싣는다 — 감추면 위임 역할이 이미 결정된 사안을
        # 다시 차단한다 (ADR-0035 §1). 열림/닫힘은 resolution이 구분한다.
        lines = ["## Requirement candidates (settled ones included; see resolution)"]
        for item in requirement_candidates:
            lines.append(
                f"- [{item.section}] {item.text} "
                f"(resolution: {item.resolution}, required: {item.required})"
            )
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


#: upstream `agents/socratic-interviewer.md`의 역할 경계와 정렬한 영어 원문.
_INTERVIEWER_ROLE = """\
You are an expert requirements engineer conducting a Socratic interview to \
clarify vague ideas into actionable requirements.

- You are ONLY an interviewer. You gather information through questions.
- NEVER say "I will implement X", "Let me build", "I'll create" — you gather \
requirements only.
- Your job: generate the single best Socratic question to reduce ambiguity.
- Keep the question focused (1-2 sentences). No preambles.
- Also report which requirement gap the question targets."""

_QUESTION_SCHEMA = strict_schema(
    {
        "question": {"type": "string", "description": "the single question, 1-2 sentences"},
        "targeted_gap": {
            "type": "string",
            "description": "which requirement gap this question targets",
        },
    }
)


class CodexQuestionGenerator:
    """질문 하나를 생성하는 제한된 역할의 Codex 구현."""

    def __init__(self, *, completion: CodexCompletion) -> None:
        self._completion = completion

    def render_prompt(self, request: QuestionRequest) -> str:
        return "\n\n".join(
            [
                _INTERVIEWER_ROLE,
                _render_context(
                    request.initial_intent, request.previous_rounds, request.requirement_candidates
                ),
            ]
        )

    async def generate(self, request: QuestionRequest) -> GeneratedQuestion:
        data = await self._completion.complete_json(
            prompt=self.render_prompt(request), schema=_QUESTION_SCHEMA
        )
        return GeneratedQuestion(question=data["question"], targeted_gap=data["targeted_gap"])


_ASSESSOR_ROLE = """\
You are a rigorous requirements clarity assessor. Score how clearly each \
requested dimension of this brief is defined, based ONLY on what was actually \
answered — not on what could plausibly be inferred.

For each requested dimension return clarity between 0.0 (completely unclear) \
and 1.0 (unambiguous) with a one-sentence justification. Score exactly the \
requested dimensions, nothing else."""


class CodexClarityAssessor:
    """축별 clarity를 채점하는 제한된 역할의 Codex 구현.

    ``policy_version``은 구성에서 주입된다 — 평가자에게 threshold를 알려 주지
    않는 계약(ports)과 기록의 정책 추적(clarity.py)을 함께 만족하는 자리다.
    """

    def __init__(self, *, completion: CodexCompletion, policy_version: str) -> None:
        self._completion = completion
        self._policy_version = policy_version

    def render_prompt(self, request: AssessmentRequest) -> str:
        dimensions = ", ".join(request.dimensions)
        return "\n\n".join(
            [
                _ASSESSOR_ROLE,
                f"## Requested dimensions\n{dimensions}",
                _render_context(
                    request.initial_intent, request.previous_rounds, request.requirement_candidates
                ),
            ]
        )

    async def assess(self, request: AssessmentRequest) -> ClarityAssessment:
        schema = strict_schema(
            {
                "scores": {
                    "type": "array",
                    "items": strict_schema(
                        {
                            "dimension": {
                                "type": "string",
                                "enum": list(request.dimensions),
                            },
                            "clarity": {"type": "number"},
                            "justification": {"type": "string"},
                        }
                    ),
                }
            }
        )
        data = await self._completion.complete_json(
            prompt=self.render_prompt(request), schema=schema
        )
        scores = tuple(
            DimensionScore(
                dimension=item["dimension"],
                clarity=item["clarity"],
                justification=item["justification"],
            )
            for item in data["scores"]
        )
        received = tuple(score.dimension for score in scores)
        if sorted(received) != sorted(request.dimensions):
            raise ClarityDimensionMismatchError(
                expected=tuple(request.dimensions), received=received
            )
        return ClarityAssessment(scores=scores, policy_version=self._policy_version)


_CLOSER_ROLE = """\
You are the closer lane of a closure audit. Judge ONLY whether unresolved \
decisions remain that would materially change the implementation. Do not \
invent new requirements. If not ready, also return the single most impactful \
blocking question; if ready, return an empty blocking_question."""

_CLOSER_SCHEMA = strict_schema(
    {
        "verdict": {"type": "string", "enum": ["ready", "not_ready"]},
        "reason": {"type": "string"},
        "blocking_question": {
            "type": "string",
            "description": "empty string when the verdict is ready",
        },
    }
)


class CodexClosureAssessor:
    """closure gate 판정(closer lane)의 Codex 구현."""

    def __init__(self, *, completion: CodexCompletion) -> None:
        self._completion = completion

    def render_prompt(self, request: CloserAuditRequest) -> str:
        return "\n\n".join(
            [
                _CLOSER_ROLE,
                f"## Closure gate criteria (verbatim policy)\n{request.gate_summary}",
                _render_context(
                    request.initial_intent, request.previous_rounds, request.requirement_candidates
                ),
            ]
        )

    async def audit(self, request: CloserAuditRequest) -> CloserReport:
        data = await self._completion.complete_json(
            prompt=self.render_prompt(request), schema=_CLOSER_SCHEMA
        )
        return CloserReport(
            verdict=data["verdict"],
            reason=data["reason"],
            blocking_question=data["blocking_question"] or None,
        )


_CHALLENGER_ROLE = """\
You are one advisory lane of a closure audit. Attack the conclusion that this \
brief is ready, strictly from the assigned perspective below. Report your single \
strongest finding and its severity per the severity rule. If the finding blocks \
closure, also return the question the next round should ask; otherwise return an \
empty question."""

_CHALLENGER_SCHEMA = strict_schema(
    {
        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
        "finding": {"type": "string"},
        "question": {
            "type": "string",
            "description": "empty string unless the finding should block closure",
        },
    }
)


class CodexClosureChallenger:
    """advisory lane(contrarian·gap_hunter)의 Codex 구현.

    lane은 응답이 아니라 요청에서 바인딩된다 — semantic 평가자의 ``ac_key``와
    같은 이유다 (ADR-0034 §5).
    """

    def __init__(self, *, completion: CodexCompletion) -> None:
        self._completion = completion

    def render_prompt(self, request: ClosureChallengeRequest) -> str:
        return "\n\n".join(
            [
                _CHALLENGER_ROLE,
                f"## Assigned perspective (verbatim policy)\n{request.challenge}",
                f"## Severity rule (verbatim policy)\n{request.severity_rule}",
                _render_context(
                    request.initial_intent, request.previous_rounds, request.requirement_candidates
                ),
            ]
        )

    async def challenge(self, request: ClosureChallengeRequest) -> AdvisoryReport:
        data = await self._completion.complete_json(
            prompt=self.render_prompt(request), schema=_CHALLENGER_SCHEMA
        )
        return AdvisoryReport(
            lane=request.lane,
            severity=data["severity"],
            finding=data["finding"],
            question=data["question"] or None,
        )
