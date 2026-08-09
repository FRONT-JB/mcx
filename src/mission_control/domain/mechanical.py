"""workspace가 실제로 제공하는 확인 명령 (ADR-0044 §3).

brownfield에서 Verify가 도는 유일한 길이다. 기존 저장소는 자기만의 테스트·
린트·빌드 명령을 갖고 있고, 그것을 모르면 AC에 확인 수단을 쓸 수 없다 —
그러면 [ADR-0043]의 ``NO_VERIFIABLE_CRITERION``이 곧바로 벽이 된다.

**제안과 검증을 나눈다.** 제안은 모델이 하고(:class:`ProposedCommands`), 검증은
계산이 한다 — 이 모듈은 *"이 명령이 성립하려면 무엇이 있어야 하는가"* 만
결정적으로 답하고, 그것이 실제로 있는지는 adapter가 디스크에서 확인한다.

upstream 계약을 그대로 받는다: 대조에 실패한 제안은 **버린다.** 추측을 남기면
Verify가 없는 진입점을 실행해 실패하고, 그 실패는 코드의 문제가 아니라 우리가
명령을 틀리게 안 것이다 — upstream은 그것을 *"phantom failure"* 라 부르고
금지한다 (`evaluation/detector.py`).

계약: ``docs/adr/0044-brownfield-entry-contract.md``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

#: 패키지 매니저 실행자 — ``<pm> run <script>`` 또는 ``<pm> <script>`` 형태로
#: package.json의 scripts를 부른다.
_PACKAGE_MANAGERS = frozenset({"npm", "yarn", "pnpm", "bun"})

#: 하위 명령을 하나 건너뛰고 실제 실행 대상을 보는 실행자.
_RUNNERS = frozenset({"uv", "uvx", "npx", "poetry", "pipenv", "rye"})


class CommandKind(StrEnum):
    """확인 명령의 종류. upstream ``DetectedCommands``와 같은 다섯이다."""

    LINT = "lint"
    BUILD = "build"
    TEST = "test"
    STATIC = "static"
    COVERAGE = "coverage"


class EntryPointKind(StrEnum):
    """명령이 성립하기 위해 디스크에 있어야 하는 것."""

    PACKAGE_SCRIPT = "package_script"
    MAKE_TARGET = "make_target"
    EXECUTABLE = "executable"


@dataclass(frozen=True, slots=True)
class EntryPointRequirement:
    """``command``가 성립하려면 ``kind``의 ``name``이 있어야 한다."""

    kind: EntryPointKind
    name: str


class ProposedCommands(BaseModel):
    """모델이 제안한 것. **아직 아무것도 확인되지 않았다.**

    타입을 나눈 이유는 검증을 건너뛸 수 없게 하기 위해서다 — 제안을 그대로
    쓰려면 이 타입을 그대로 쓰게 되고, 그러면 이름이 그 사실을 드러낸다.
    """

    model_config = ConfigDict(frozen=True)

    commands: dict[CommandKind, str] = {}


class DroppedCommand(BaseModel):
    """대조에 실패해 버려진 제안. 무엇을 버렸는지는 증거다."""

    model_config = ConfigDict(frozen=True)

    kind: CommandKind
    command: str
    reason: str


class MechanicalCommands(BaseModel):
    """디스크 대조를 통과한 명령만 담는다.

    ``dropped``를 함께 들고 있는 이유는 조용한 누락을 막기 위해서다. 검출이
    아무것도 못 찾은 것과 찾았는데 전부 버려진 것은 다른 상황이며, 후자는
    사용자에게 보여야 한다.
    """

    model_config = ConfigDict(frozen=True)

    commands: dict[CommandKind, str] = {}
    dropped: tuple[DroppedCommand, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.commands)


def required_entry_point(command: str) -> EntryPointRequirement | None:
    """이 명령이 성립하려면 무엇이 있어야 하는가. 순수 함수다.

    ``None``은 "무엇을 요구하는지 알 수 없다"이며, 호출자는 그것을 통과가
    아니라 **탈락**으로 다룬다 — 확인할 수 없는 것을 확인된 것으로 취급하지
    않는다.

    한계: 셸 연산자(``&&``, ``|``, ``;``)가 있는 명령은 판정하지 않는다.
    upstream은 패키지 매니저별 플래그 파싱에 상당한 코드를 쓰지만
    (`evaluation/detector.py`의 workspace·filter 처리), 우리는 그 범위를
    도입하지 않고 판정 불가로 떨어뜨린다. 대가는 복합 명령을 못 받는 것이고,
    이득은 틀린 통과가 없는 것이다.
    """
    if any(operator in command for operator in ("&&", "||", "|", ";", ">", "<")):
        return None

    tokens = [token for token in command.strip().split() if token]
    if not tokens:
        return None

    head = tokens[0]
    rest = [token for token in tokens[1:] if not token.startswith("-")]

    if head == "make":
        # `make` 단독은 기본 target이라 이름이 없다 — 판정하지 않는다.
        return EntryPointRequirement(EntryPointKind.MAKE_TARGET, rest[0]) if rest else None

    if head in _PACKAGE_MANAGERS:
        script = rest[1] if rest and rest[0] == "run" else (rest[0] if rest else None)
        return (
            EntryPointRequirement(EntryPointKind.PACKAGE_SCRIPT, script) if script else None
        )

    if head in _RUNNERS:
        # `uv run pytest` → pytest가 실행 대상이다. `uv run` 뒤가 비면 판정 불가.
        target = rest[1] if rest and rest[0] in {"run", "tool"} else (rest[0] if rest else None)
        return EntryPointRequirement(EntryPointKind.EXECUTABLE, target) if target else None

    return EntryPointRequirement(EntryPointKind.EXECUTABLE, head)
