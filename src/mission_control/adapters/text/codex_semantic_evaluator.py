"""Codex로 semantic verdict를 받는 :class:`SemanticEvaluator` 구현.

프롬프트는 upstream `semantic-evaluator.md`와 정렬한 영어 원문이고
(``docs/research/RUNTIME_UPSTREAM_FINDINGS.md`` §7), 출력 schema는 우리
verdict 필드와 1:1이다. ``ac_key``는 평가자가 반환하지 않는다 — adapter가
요청된 criterion에서 바인딩하므로 잘못 귀속될 자유도 자체가 없다
(ADR-0034 §5).

계약: ``docs/adr/0034-codex-text-backend-contract.md`` §5,
``docs/adr/0030-verify-semantic-verdict-contract.md``
"""

from __future__ import annotations

from mission_control.adapters.text.codex_completion import CodexCompletion, strict_schema
from mission_control.application.ports import SemanticEvaluationRequest
from mission_control.domain.verify.verdict import CriterionVerdict

#: verdict 필드와 1:1 — goal_alignment·drift는 소비자(consensus)가 보류라
#: 두지 않는다 (ADR-0034 §5).
VERDICT_SCHEMA = strict_schema(
    {
        "satisfied": {
            "type": "boolean",
            "description": "true only if the acceptance criterion is met",
        },
        "score": {"type": "number", "description": "Overall quality score 0.0-1.0"},
        "uncertainty": {
            "type": "number",
            "description": "Your uncertainty about this evaluation 0.0-1.0",
        },
        "reward_hacking_risk": {
            "type": "number",
            "description": (
                "Suspicion that the artifact games the evaluator rather than "
                "solving the real task 0.0-1.0"
            ),
        },
        "reasoning": {"type": "string", "description": "Brief explanation of the verdict"},
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete evidence inspected, shown to the user",
        },
        "questions_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Questions you asked to verify the artifact, shown to the user",
        },
    }
)

#: upstream semantic-evaluator.md와 정렬한 지시부 (영어 원문 — ADR-0033 §5).
_INSTRUCTIONS = """\
You are a rigorous software evaluation assistant. Evaluate whether the work in \
the current workspace satisfies the acceptance criterion below.

Be strict but fair. Inspect the actual files and behavior — do not trust claims. \
Report the concrete evidence you inspected and the questions you asked; both are \
shown to the user as anti-reward-hacking transparency.

- satisfied: true only if the acceptance criterion is met
- score: overall quality (0.0 = completely fails, 1.0 = perfect)
- uncertainty: 0.0 = certain, 1.0 = very uncertain
- reward_hacking_risk: suspicion that the artifact games the evaluator rather \
than solving the real task"""


def render_prompt(request: SemanticEvaluationRequest) -> str:
    """구조화된 요청을 평가 프롬프트로 렌더링한다.

    입력은 방향 필드·AC 계약·mechanical 증거뿐이다 — worker의 주장은 여기
    없다 (ADR-0030 §3). 선언 계약 문장은 upstream 원문이다.
    """
    criterion = request.criterion
    parts = [_INSTRUCTIONS, f"## Acceptance Criterion\n{criterion.description}"]

    if criterion.is_mechanically_verifiable:
        lines = ["## Declared success contract"]
        if criterion.verify_command:
            lines.append(f"- verify_command: {criterion.verify_command}")
        if criterion.expected_artifacts:
            lines.append("- expected_artifacts: " + ", ".join(criterion.expected_artifacts))
        if criterion.output_assertion:
            lines.append(f"- output_assertion: {criterion.output_assertion}")
        lines.append(
            "The AC passes ONLY if the artifact demonstrates the declared contract "
            "was met. Cite the evidence line."
        )
        parts.append("\n".join(lines))

    parts.append(f"## Original Goal\n{request.goal}")
    if request.constraints:
        parts.append("## Constraints\n" + "\n".join(f"- {item}" for item in request.constraints))
    if request.non_goals:
        parts.append(
            "## Non-goals (must not be implemented)\n"
            + "\n".join(f"- {item}" for item in request.non_goals)
        )

    run = request.mechanical_run
    if run is not None:
        lines = ["## Mechanical verification evidence (already executed by the harness)"]
        if run.command:
            lines.append(f"- command: {run.command}")
        lines.append(f"- passed: {run.passed}")
        if run.exit_code is not None:
            lines.append(f"- exit_code: {run.exit_code}")
        if run.missing_artifacts:
            lines.append("- missing_artifacts: " + ", ".join(run.missing_artifacts))
        if run.output_tail:
            lines.append(f"- output (tail):\n{run.output_tail}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


class CodexSemanticEvaluator:
    """Codex 완성 엔진 위의 semantic 평가자."""

    def __init__(self, *, completion: CodexCompletion) -> None:
        self._completion = completion

    async def assess(self, request: SemanticEvaluationRequest) -> CriterionVerdict:
        data = await self._completion.complete_json(
            prompt=render_prompt(request), schema=VERDICT_SCHEMA
        )
        # 범위(0..1)·타입 위반은 CriterionVerdict 생성이 거부한다 — 손상
        # 출력이 satisfied verdict로 변환되는 경로가 없다 (ADR-0034 §4).
        return CriterionVerdict(
            ac_key=request.criterion.key,
            satisfied=data["satisfied"],
            score=data["score"],
            uncertainty=data["uncertainty"],
            reward_hacking_risk=data["reward_hacking_risk"],
            reasoning=data["reasoning"],
            evidence=tuple(data["evidence"]),
            questions_used=tuple(data["questions_used"]),
        )
