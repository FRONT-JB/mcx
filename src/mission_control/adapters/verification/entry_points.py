"""제안된 확인 명령을 디스크와 대조한다 (ADR-0044 §3).

모델이 제안한 것을 그대로 쓰지 않는다. package.json의 scripts, Makefile의
target, PATH의 실행 파일 — 셋 중 하나로 **실재가 확인된 명령만** 남기고
나머지는 버린다. upstream과 같은 계약이며 이유도 같다: 없는 진입점을 실행하면
Verify가 실패하는데, 그 실패는 코드의 문제가 아니라 우리가 명령을 틀리게 안
것이다 (*"must never produce a phantom failure"*).

``LocalMechanicalRunner``의 이웃에 두는 이유는 같은 축이기 때문이다 — 저쪽은
확인 명령을 **실행**하고, 이쪽은 그 명령이 **실행 가능한지** 본다.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil

from mission_control.domain.mechanical import (
    CommandKind,
    DroppedCommand,
    EntryPointKind,
    MechanicalCommands,
    ProposedCommands,
    required_entry_point,
)

#: 검출을 시도할 근거가 되는 파일. 하나도 없으면 AI 호출조차 하지 않는다 —
#: upstream ``detector.skipped reason=no_manifests``와 같은 규칙이다.
MANIFESTS: tuple[str, ...] = (
    "package.json",
    "Makefile",
    "makefile",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "build.gradle",
    "pom.xml",
)

#: Makefile의 target 줄. 들여쓰기된 본문 줄과 `.PHONY` 같은 특수 target은 뺀다.
_MAKE_TARGET = re.compile(r"^(?!\t)([A-Za-z0-9_./-]+)\s*:(?!=)")

_MAX_MANIFEST_CHARS = 4_000


def manifests(workspace: Path) -> tuple[tuple[str, str], ...]:
    """검출 근거로 쓸 (이름, 발췌) 쌍. 없으면 빈 튜플이다."""
    found: list[tuple[str, str]] = []
    for name in MANIFESTS:
        path = workspace / name
        if not path.is_file():
            continue
        try:
            found.append((name, path.read_text(encoding="utf-8")[:_MAX_MANIFEST_CHARS]))
        except (OSError, UnicodeDecodeError):
            continue
    return tuple(found)


def validate(proposed: ProposedCommands, *, workspace: Path) -> MechanicalCommands:
    """대조를 통과한 것만 남긴다. 통과 못 한 것은 이유와 함께 버린다."""
    scripts = _package_scripts(workspace)
    targets = _make_targets(workspace)

    kept: dict[CommandKind, str] = {}
    dropped: list[DroppedCommand] = []

    for kind, command in proposed.commands.items():
        requirement = required_entry_point(command)
        if requirement is None:
            dropped.append(
                DroppedCommand(
                    kind=kind, command=command, reason="무엇을 요구하는지 판정할 수 없다"
                )
            )
            continue

        if requirement.kind is EntryPointKind.PACKAGE_SCRIPT:
            ok = requirement.name in scripts
            detail = f"package.json scripts에 `{requirement.name}`가 없다"
        elif requirement.kind is EntryPointKind.MAKE_TARGET:
            ok = requirement.name in targets
            detail = f"Makefile에 target `{requirement.name}`가 없다"
        else:
            ok = shutil.which(requirement.name) is not None
            detail = f"`{requirement.name}`가 PATH에 없다"

        if ok:
            kept[kind] = command
        else:
            dropped.append(DroppedCommand(kind=kind, command=command, reason=detail))

    return MechanicalCommands(commands=kept, dropped=tuple(dropped))


def _package_scripts(workspace: Path) -> frozenset[str]:
    path = workspace / "package.json"
    if not path.is_file():
        return frozenset()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return frozenset()
    scripts = raw.get("scripts")
    return frozenset(scripts) if isinstance(scripts, dict) else frozenset()


def _make_targets(workspace: Path) -> frozenset[str]:
    for name in ("Makefile", "makefile"):
        path = workspace / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return frozenset()
        return frozenset(
            match.group(1)
            for line in text.splitlines()
            if (match := _MAKE_TARGET.match(line)) and not match.group(1).startswith(".")
        )
    return frozenset()
