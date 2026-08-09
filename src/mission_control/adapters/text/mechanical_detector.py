"""확인 명령 제안 — vendor 중립 프롬프트 (ADR-0044 §3).

여덟 번째 위임 port다. 다른 일곱과 같은 규율을 따른다 — 프롬프트는 vendor를
모르고 ``CompletionEngine``만 요구하며, 출력은 구조화 스키마로 강제된다.

다른 일곱과 **다른 점 하나**: 이 역할의 출력은 그대로 쓰이지 않는다. 반환
타입이 :class:`ProposedCommands`이고, 디스크 대조를 지나야 쓸 수 있는 명령이
된다 (``adapters/verification/entry_points.py``). 모델에게 묻되 답을 계산으로
검산하는 형태이며 upstream ``evaluation/detector.py``와 같은 축이다.
"""

from __future__ import annotations

from mission_control.adapters.text.completion_engine import CompletionEngine, strict_schema
from mission_control.application.ports import MechanicalDetectionRequest
from mission_control.domain.mechanical import CommandKind, ProposedCommands

_ROLE = """You detect how an existing repository is checked.

Read the manifests and propose the commands this project already uses. Propose
only what the manifests support — a script that exists, a Make target that
exists, a tool the project depends on. Do not propose a command you would have
to invent, and do not propose a plausible default just to fill a slot.

Leave a kind out entirely when the manifests do not show it. An omitted kind
costs nothing; a wrong one is worse than nothing, because it fails at
verification time and the failure looks like broken code rather than a bad
guess.

Propose one command per kind, exactly as it would be typed:

- lint: style and correctness checks that do not run the program
- build: compile or package
- test: the automated test suite
- static: type checking or static analysis
- coverage: the test suite with coverage measurement

Keep each command to a single invocation. Do not chain with `&&`, pipes, or
semicolons — a chained command cannot be checked against an entry point and
will be discarded."""


class PromptedMechanicalDetector:
    """manifest에서 확인 명령을 제안한다. 검증하지 않는다."""

    def __init__(self, *, completion: CompletionEngine) -> None:
        self._completion = completion

    def render_prompt(self, request: MechanicalDetectionRequest) -> str:
        manifests = "\n\n".join(
            f"### {name}\n```\n{excerpt}\n```" for name, excerpt in request.manifests
        )
        return f"{_ROLE}\n\n## Manifests\n\n{manifests}"

    async def propose(self, request: MechanicalDetectionRequest) -> ProposedCommands:
        """호출은 **1회**다 (ADR-0044 §3). manifest가 없으면 부르지 않는다."""
        if not request.manifests:
            return ProposedCommands()

        schema = strict_schema(
            {
                kind.value: {
                    "type": "string",
                    "description": f"the {kind.value} command, or an empty string if none",
                }
                for kind in CommandKind
            }
        )
        payload = await self._completion.complete_json(
            prompt=self.render_prompt(request),
            schema=schema,
            workspace=request.workspace,
        )

        commands = {
            kind: str(payload[kind.value]).strip()
            for kind in CommandKind
            if isinstance(payload.get(kind.value), str) and str(payload[kind.value]).strip()
        }
        return ProposedCommands(commands=commands)
