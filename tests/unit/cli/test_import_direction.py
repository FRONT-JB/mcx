"""의존 방향 — Stage service·도메인·어댑터가 mission record와 표면을 모른다.

ADR-0037 Verification: mission record의 소비자는 **표면 계층**뿐이다. 이 검사가
깨지면 Stage service가 자기 Stage를 스스로 전이시키는 문이 열린다.

2026-08-09(Phase 7)에 표면 계층이 둘이 됐다 — CLI와 MCP. MCP는 CLI의 ``dispatch``를
그대로 부른다 (ADR-0041 §1): 두 벌의 핸들러를 만들지 않기 위해서다. 그래서
``mcp/``가 ``cli/``에 의존하는 것은 **허용된 방향**이고, 그 반대는 아니다 —
CLI는 MCP 없이 서야 한다(upstream과 반대 방향의 등록된 divergence).
"""

from pathlib import Path

import mission_control

SOURCE_ROOT = Path(mission_control.__file__).parent

#: mission record를 알아도 되는 모듈 — 정의 자신과 그 저장소.
_RECORD_ALLOWED = {
    SOURCE_ROOT / "domain" / "mission.py",
    SOURCE_ROOT / "adapters" / "persistence" / "file_mission_repository.py",
}

#: 표면 계층. mission record와 dispatch를 아는 것이 이들의 일이다.
_SURFACE = (SOURCE_ROOT / "cli", SOURCE_ROOT / "mcp")


def _is_under(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(root in path.parents for root in roots)


def test_only_the_surface_layer_knows_the_mission_record() -> None:
    offenders: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        if path in _RECORD_ALLOWED or _is_under(path, _SURFACE):
            continue
        text = path.read_text(encoding="utf-8")
        if "domain.mission" in text or "mission_control.cli" in text:
            offenders.append(str(path.relative_to(SOURCE_ROOT)))
    assert offenders == []


def test_the_cli_does_not_depend_on_mcp() -> None:
    """표면 둘의 의존은 한 방향이다 — MCP를 지워도 CLI가 서야 한다.

    upstream은 반대다(CLI가 MCP handler를 부른다 — MCP findings §4). 이 방향을
    뒤집는 것이 ADR-0041 §1의 등록된 divergence이며, 그 실효를 여기서 지킨다.
    """
    offenders = [
        str(path.relative_to(SOURCE_ROOT))
        for path in (SOURCE_ROOT / "cli").rglob("*.py")
        if "mission_control.mcp" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_the_mcp_surface_holds_no_stage_logic() -> None:
    """MCP handler는 CLI와 같은 dispatch를 부를 뿐 자기 판단을 갖지 않는다 (§8).

    application service를 직접 부르기 시작하면 두 표면의 동작이 갈린다 —
    parity를 테스트로 쫓아다녀야 하는 상태가 된다.
    """
    offenders = [
        str(path.relative_to(SOURCE_ROOT))
        for path in (SOURCE_ROOT / "mcp").rglob("*.py")
        if "mission_control.application" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
