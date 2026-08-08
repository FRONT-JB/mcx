"""Blueprint 위임 port들의 Codex 구현 — 초안 생성과 QA 채점.

생성기의 granularity contract는 upstream `agents/seed-architect.md` §3의
영어 원문과 정렬하고, 채점자의 quality bar는 요청에 담겨 오는 정책 원문
(2026-08-08부터 upstream 영어 원문 — ADR-0019 §4 재평가)을 그대로 싣는다.

제약·Non-goal의 원문 보존은 프롬프트 지시이자 결정적 검사다 — 어겨도
조립 단계(:func:`check_scope`)가 거부한다 (ADR-0018).

계약: ``docs/adr/0034-codex-text-backend-contract.md``,
``docs/adr/0018-blueprint-generation-contract.md``,
``docs/adr/0019-blueprint-qa-loop.md``
"""

from __future__ import annotations

from mission_control.adapters.text.codex_completion import CodexCompletion, strict_schema
from mission_control.application.ports import BlueprintGenerationRequest, QaRequest
from mission_control.domain.blueprint.assembly import BlueprintDraft
from mission_control.domain.blueprint.qa import QaAssessment, QaDimension, QaFinding
from mission_control.domain.blueprint.spec import AcceptanceCriterion

#: upstream `agents/seed-architect.md` §3 granularity contract의 핵심 원문.
_GRANULARITY_CONTRACT = """\
An acceptance criterion names a state of the finished work that a user can see \
is true. An implementation step names a means of reaching that state. These are \
different categories, and only the first belongs here — deciding means is the \
execution engine's work at runtime, and it decides them better with the outcome \
in hand than with your guess at the path. If a criterion is intelligible only \
as a move toward a sibling, it is that sibling's means wearing an outcome's \
clothes, and it belongs merged into the outcome it serves."""

_GENERATOR_ROLE = """\
You are a specification architect. Concretize the approved success criteria \
below into verifiable acceptance criteria.

Rules:
- Copy every constraint and non-goal EXACTLY as given, word for word. Any \
rewording is rejected by a deterministic scope check.
- Do not invent requirements that are not in the inputs.
- For each acceptance criterion, attach a success contract when possible: \
verify_command is exactly one single-line shell command; expected_artifacts \
are exact workspace-relative paths (never descriptive labels); \
output_assertion is a literal string present verbatim in the command output. \
Use an empty string (or empty array) when a field does not apply."""

_DRAFT_SCHEMA = strict_schema(
    {
        "goal": {"type": "string"},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "non_goals": {"type": "array", "items": {"type": "string"}},
        "acceptance_criteria": {
            "type": "array",
            "items": strict_schema(
                {
                    "description": {"type": "string"},
                    "verify_command": {
                        "type": "string",
                        "description": "one single-line shell command, or empty string",
                    },
                    "expected_artifacts": {"type": "array", "items": {"type": "string"}},
                    "output_assertion": {
                        "type": "string",
                        "description": "literal expected output, or empty string",
                    },
                }
            ),
        },
    }
)


class CodexBlueprintGenerator:
    """승인된 handoff를 확인 가능한 초안으로 구체화하는 Codex 구현."""

    def __init__(self, *, completion: CodexCompletion) -> None:
        self._completion = completion

    def render_prompt(self, request: BlueprintGenerationRequest) -> str:
        def block(title: str, items: tuple[str, ...]) -> str:
            body = "\n".join(f"- {item}" for item in items) if items else "(none)"
            return f"## {title}\n{body}"

        return "\n\n".join(
            [
                _GENERATOR_ROLE,
                "## Granularity contract (verbatim)\n" + _GRANULARITY_CONTRACT,
                block("Goals", request.goals),
                block("Constraints (copy verbatim)", request.constraints),
                block("Non-goals (copy verbatim)", request.non_goals),
                block("Success criteria to concretize", request.success_criteria),
                block("Observed context (facts, not requirements)", request.context),
            ]
        )

    async def generate(self, request: BlueprintGenerationRequest) -> BlueprintDraft:
        data = await self._completion.complete_json(
            prompt=self.render_prompt(request), schema=_DRAFT_SCHEMA
        )
        criteria = tuple(
            AcceptanceCriterion(
                description=item["description"],
                verify_command=item["verify_command"] or None,
                expected_artifacts=tuple(item["expected_artifacts"]),
                output_assertion=item["output_assertion"] or None,
            )
            for item in data["acceptance_criteria"]
        )
        return BlueprintDraft(
            goal=data["goal"],
            constraints=tuple(data["constraints"]),
            non_goals=tuple(data["non_goals"]),
            acceptance_criteria=criteria,
        )


_JUDGE_ROLE = """\
You are a rigorous specification QA judge. Score the draft below against the \
quality bar. Your job is scoring, not deciding — report scores and findings; \
the pass threshold is owned by policy and is not your concern.

Return an overall score 0.0-1.0, a score per dimension, and concrete findings \
(each with an actionable suggestion when one exists, otherwise an empty string)."""

_QA_SCHEMA = strict_schema(
    {
        "score": {"type": "number", "description": "overall 0.0-1.0"},
        "dimension_scores": {
            "type": "array",
            "items": strict_schema(
                {
                    "dimension": {
                        "type": "string",
                        "enum": [dimension.value for dimension in QaDimension],
                    },
                    "score": {"type": "number"},
                }
            ),
        },
        "findings": {
            "type": "array",
            "items": strict_schema(
                {
                    "detail": {"type": "string"},
                    "suggestion": {
                        "type": "string",
                        "description": "empty string when no concrete suggestion exists",
                    },
                }
            ),
        },
    }
)


class CodexBlueprintQaJudge:
    """주어진 quality bar로 초안을 채점하는 Codex 구현."""

    def __init__(self, *, completion: CodexCompletion) -> None:
        self._completion = completion

    def render_prompt(self, request: QaRequest) -> str:
        criteria_lines = []
        for criterion in request.acceptance_criteria:
            criteria_lines.append(f"- {criterion.description}")
            if criterion.verify_command:
                criteria_lines.append(f"  verify_command: {criterion.verify_command}")
            if criterion.expected_artifacts:
                criteria_lines.append(
                    "  expected_artifacts: " + ", ".join(criterion.expected_artifacts)
                )
            if criterion.output_assertion:
                criteria_lines.append(f"  output_assertion: {criterion.output_assertion}")

        parts = [
            _JUDGE_ROLE,
            f"## Quality bar (verbatim policy)\n{request.quality_bar}",
            f"## Draft under review\nGoal: {request.goal}",
            "Constraints:\n" + ("\n".join(f"- {item}" for item in request.constraints) or "(none)"),
            "Non-goals:\n" + ("\n".join(f"- {item}" for item in request.non_goals) or "(none)"),
            "Acceptance criteria:\n" + "\n".join(criteria_lines),
        ]
        if request.previous_findings:
            parts.append(
                "## Findings from the previous round (check what was fixed)\n"
                + "\n".join(f"- {finding.detail}" for finding in request.previous_findings)
            )
        return "\n\n".join(parts)

    async def assess(self, request: QaRequest) -> QaAssessment:
        data = await self._completion.complete_json(
            prompt=self.render_prompt(request), schema=_QA_SCHEMA
        )
        return QaAssessment(
            score=data["score"],
            dimension_scores=tuple(
                (QaDimension(item["dimension"]), item["score"]) for item in data["dimension_scores"]
            ),
            findings=tuple(
                QaFinding(detail=item["detail"], suggestion=item["suggestion"] or None)
                for item in data["findings"]
            ),
        )
