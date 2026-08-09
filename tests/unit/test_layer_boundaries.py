"""계층 의존 방향을 검사로 고정한다.

ADR-0037 Verification의 세 번째 항목은 *"Stage service 코드가 mission 문서
모듈에 의존하지 않는다 (import 방향 검사)"* 인데, Phase 6 종료 검토(2026-08-09)
시점까지 그 검사가 없었다 — 사실로는 지켜지고 있었으나 회귀를 막는 것이 산문뿐이었다.

mission record는 **합성 계층 소유**다 (ADR-0037 §2). Stage service가 그것을
읽기 시작하면 진실이 둘로 갈리고, "Gate 재계산이 이긴다"는 보증이 깨진다.
"""

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "mission_control"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_stage_services_do_not_depend_on_the_mission_record() -> None:
    """mission record는 합성 계층 소유다 — application이 읽으면 진실이 둘이 된다."""
    offenders = {
        path.name
        for path in sorted((_SRC / "application").glob("*.py"))
        if any(name.endswith("domain.mission") for name in _imported_modules(path))
    }

    assert offenders == set()


def test_the_domain_does_not_depend_on_the_cli() -> None:
    """도메인이 표면을 알면 표면 교체(Phase 7 MCP)가 도메인 변경이 된다."""
    offenders = {
        path.relative_to(_SRC).as_posix()
        for path in sorted(_SRC.rglob("*.py"))
        if path.is_relative_to(_SRC / "domain")
        and any("mission_control.cli" in name for name in _imported_modules(path))
    }

    assert offenders == set()


def test_the_domain_does_not_depend_on_the_adapters() -> None:
    """vendor 세부는 adapter 경계 안에만 있다 (Constitution — Core는 Runtime-neutral)."""
    offenders = {
        path.relative_to(_SRC).as_posix()
        for path in sorted((_SRC / "domain").rglob("*.py"))
        if any("mission_control.adapters" in name for name in _imported_modules(path))
    }

    assert offenders == set()
