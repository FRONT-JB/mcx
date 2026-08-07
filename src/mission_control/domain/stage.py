"""Mission의 canonical Stage 이름.

사용자와 CLI가 쓰는 용어이며 upstream 대응 용어(Interview/Seed/Run/Evaluate/
Repair)는 문서에만 남긴다. 코드에서 두 어휘를 섞으면 어느 쪽이 진짜 경계인지
알 수 없게 된다 (``docs/00_MISSION_CONTROL.md`` §5).

Phase 1이 구현하는 것은 Brief뿐이지만 이름 전체를 여기에 둔다. 전이 규칙은
"어디로 갈 수 있는가"만큼 "어디로 갈 수 없는가"도 규정하므로, 금지 대상을
가리킬 이름이 없으면 그 규칙을 테스트로 표현할 수 없다.

계약: ``docs/02_MISSION_LIFECYCLE.md`` §9
"""

from __future__ import annotations

from enum import StrEnum


class Stage(StrEnum):
    BRIEF = "brief"
    BLUEPRINT = "blueprint"
    EXECUTE = "execute"
    VERIFY = "verify"
    RECOVER = "recover"
