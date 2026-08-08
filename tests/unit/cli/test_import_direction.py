"""의존 방향 — Stage service·도메인·어댑터가 mission record와 CLI를 모른다.

ADR-0037 Verification: mission record의 소비자는 합성(CLI)뿐이다. 이 검사가
깨지면 Stage service가 자기 Stage를 스스로 전이시키는 문이 열린다.
"""

from pathlib import Path

import mission_control

SOURCE_ROOT = Path(mission_control.__file__).parent

#: mission record를 알아도 되는 모듈 — 정의 자신과 그 저장소, CLI 합성.
ALLOWED = {
    SOURCE_ROOT / "domain" / "mission.py",
    SOURCE_ROOT / "adapters" / "persistence" / "file_mission_repository.py",
}


def test_only_cli_and_its_repository_know_the_mission_record() -> None:
    offenders: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        if path in ALLOWED or (SOURCE_ROOT / "cli") in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        if "domain.mission" in text or "mission_control.cli" in text:
            offenders.append(str(path.relative_to(SOURCE_ROOT)))
    assert offenders == []
