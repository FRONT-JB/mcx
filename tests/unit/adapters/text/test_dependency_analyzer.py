"""Parallel dependency analyzer의 prompt·strict output 계약."""

from typing import Any

from mission_control.adapters.text.dependency_analyzer import PromptedDependencyAnalyzer
from mission_control.application.ports import DependencyAnalysisRequest
from mission_control.domain.blueprint.spec import AcceptanceCriterion

FIRST = AcceptanceCriterion(description="기반 API가 생긴다", verify_command="pytest -k api")
SECOND = AcceptanceCriterion(description="UI가 API를 쓴다", verify_command="pytest -k ui")


class FakeCompletion:
    backend = "fake_text"

    def __init__(self) -> None:
        self.prompt = ""
        self.schema: dict[str, Any] = {}

    async def complete_json(
        self, *, prompt: str, schema: dict[str, Any], workspace: str | None = None
    ) -> dict[str, Any]:
        self.prompt = prompt
        self.schema = schema
        assert workspace is None
        return {
            "criteria": [
                {"ac_key": FIRST.key, "depends_on": []},
                {"ac_key": SECOND.key, "depends_on": [FIRST.key]},
            ]
        }


async def test_all_ac_keys_and_direction_are_sent_once() -> None:
    completion = FakeCompletion()
    analyzer = PromptedDependencyAnalyzer(completion=completion)
    request = DependencyAnalysisRequest(
        goal="댓글",
        constraints=("기존 API 유지",),
        non_goals=("관리자 UI 제외",),
        acceptance_criteria=(FIRST, SECOND),
    )

    result = await analyzer.analyze(request)

    assert result[1].depends_on == (FIRST.key,)
    assert FIRST.key in completion.prompt
    assert SECOND.key in completion.prompt
    assert completion.schema["additionalProperties"] is False
    assert analyzer.backend == "fake_text"
