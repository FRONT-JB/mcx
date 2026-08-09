"""확인 명령 제안 — 여덟 번째 위임 port (ADR-0044 §3).

이 역할의 출력은 그대로 쓰이지 않는다. 타입이 그 사실을 드러내는지, 그리고
근거 없이 호출하지 않는지를 고정한다.
"""

from typing import Any

from mission_control.adapters.text.mechanical_detector import PromptedMechanicalDetector
from mission_control.application.ports import MechanicalDetectionRequest
from mission_control.domain.mechanical import CommandKind, ProposedCommands


class _Engine:
    """호출 횟수와 프롬프트를 기록하는 결정적 완성 엔진."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.calls = 0
        self.prompts: list[str] = []
        self._payload = payload or {}

    async def complete_json(
        self, *, prompt: str, schema: dict[str, Any], workspace: str | None = None
    ) -> dict[str, Any]:
        self.calls += 1
        self.prompts.append(prompt)
        return {kind.value: self._payload.get(kind.value, "") for kind in CommandKind}


def _request(**manifests: str) -> MechanicalDetectionRequest:
    return MechanicalDetectionRequest(
        workspace="/w", manifests=tuple(manifests.items())
    )


class TestOneCallAtMost:
    async def test_no_manifests_means_no_call(self) -> None:
        """근거가 없으면 묻지 않는다 — upstream `no_manifests`와 같은 규칙."""
        engine = _Engine()

        result = await PromptedMechanicalDetector(completion=engine).propose(_request())

        assert engine.calls == 0
        assert result == ProposedCommands()

    async def test_detection_is_a_single_call(self) -> None:
        engine = _Engine({"test": "pytest -q"})

        await PromptedMechanicalDetector(completion=engine).propose(
            _request(pyproject_toml="[project]")
        )

        assert engine.calls == 1


class TestTheOutputIsOnlyAProposal:
    async def test_empty_strings_do_not_become_commands(self) -> None:
        """빈 칸은 "없다"이지 빈 명령이 아니다."""
        engine = _Engine({"test": "pytest -q", "lint": "   "})

        result = await PromptedMechanicalDetector(completion=engine).propose(
            _request(Makefile="check:")
        )

        assert result.commands == {CommandKind.TEST: "pytest -q"}

    async def test_the_return_type_says_it_is_unverified(self) -> None:
        """``ProposedCommands``는 디스크 대조를 지나야 명령이 된다."""
        engine = _Engine({"test": "npm run nope"})

        result = await PromptedMechanicalDetector(completion=engine).propose(
            _request(package_json="{}")
        )

        assert isinstance(result, ProposedCommands)


class TestThePrompt:
    async def test_the_manifests_are_carried_verbatim(self) -> None:
        engine = _Engine()

        await PromptedMechanicalDetector(completion=engine).propose(
            _request(Makefile="check:\n\tpytest")
        )

        assert "check:" in engine.prompts[0]

    async def test_it_forbids_chained_commands(self) -> None:
        """복합 명령은 진입점으로 환원되지 않아 어차피 버려진다 — 미리 말한다."""
        engine = _Engine()

        await PromptedMechanicalDetector(completion=engine).propose(_request(Makefile="x:"))

        assert "&&" in engine.prompts[0]

    async def test_it_tells_the_model_that_omitting_is_cheaper_than_guessing(self) -> None:
        engine = _Engine()

        await PromptedMechanicalDetector(completion=engine).propose(_request(Makefile="x:"))

        assert "worse than nothing" in engine.prompts[0]
