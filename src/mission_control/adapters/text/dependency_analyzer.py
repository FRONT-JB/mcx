"""Parallel Execute dependency analyzer — vendor-neutral prompt + strict output."""

from __future__ import annotations

from pydantic import ValidationError

from mission_control.adapters.text.completion_engine import CompletionEngine, strict_schema
from mission_control.application.ports import DependencyAnalysisRequest
from mission_control.domain.execute.plan import CriterionDependency, DependencyPlanError

_ROLE = """You derive direct logical prerequisites between approved acceptance criteria.

Return every supplied AC key exactly once. A dependency means the parent AC must be
implemented before the child can be implemented against a meaningful artifact. Do not infer
file-write separation, do not add keys, and do not turn uncertainty into a dependency. Return
only direct dependencies; transitive ordering is computed by Mission Control."""


class PromptedDependencyAnalyzer:
    """CompletionEngine 한 번으로 direct dependency 후보를 구조화한다."""

    def __init__(self, *, completion: CompletionEngine) -> None:
        self._completion = completion

    @property
    def backend(self) -> str:
        return self._completion.backend

    def render_prompt(self, request: DependencyAnalysisRequest) -> str:
        criteria = "\n".join(
            f"- {item.key}: {item.description}" for item in request.acceptance_criteria
        )
        constraints = "\n".join(f"- {item}" for item in request.constraints) or "- none"
        non_goals = "\n".join(f"- {item}" for item in request.non_goals) or "- none"
        return (
            f"{_ROLE}\n\n## Goal\n{request.goal}\n\n## Constraints\n{constraints}"
            f"\n\n## Non-goals\n{non_goals}\n\n## Acceptance criteria\n{criteria}"
        )

    async def analyze(
        self, request: DependencyAnalysisRequest
    ) -> tuple[CriterionDependency, ...]:
        schema = strict_schema(
            {
                "criteria": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ac_key": {"type": "string"},
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["ac_key", "depends_on"],
                        "additionalProperties": False,
                    },
                }
            }
        )
        payload = await self._completion.complete_json(
            prompt=self.render_prompt(request), schema=schema
        )
        raw = payload.get("criteria")
        if not isinstance(raw, list):
            raise DependencyPlanError("dependency 응답의 criteria가 배열이 아니다")
        try:
            return tuple(CriterionDependency.model_validate(item) for item in raw)
        except (ValidationError, TypeError) as error:
            raise DependencyPlanError(f"dependency 응답 schema가 잘못됐다: {error}") from error
