"""Core가 외부에 요구하는 계약.

application은 구체 adapter가 아니라 이 port에 의존한다. 저장 매체나 Runtime이
바뀌어도 use case가 바뀌지 않아야 하기 때문이다
(``docs/01_ARCHITECTURE.md`` §6.4, §7.1).

port는 ``async``로 정의한다. Phase 1의 파일 구현은 그 안에서 동기 I/O를
호출하지만, Phase 3 이후 구현이 subprocess와 네트워크를 다루게 되어도 시그니처가
바뀌지 않는다 (``docs/adr/0012-python-toolchain-and-layout.md``).
"""

from __future__ import annotations

from typing import Protocol

from mission_control.domain.brief.state import BriefState


class BriefRepository(Protocol):
    """Brief 상태의 durable 저장소.

    구현은 다음을 보장해야 한다.

    - 부분 기록된 상태가 읽히지 않는다.
    - 이미 지난 revision으로의 갱신을 거부한다
      (:class:`~mission_control.domain.errors.StaleRevisionError`).
    - 저장 실패를 성공으로 가장하지 않는다. 실패는 예외로 드러나며, 호출자는
      이를 전이 실패로 처리한다 (``docs/05_BRIEF.md`` §15).
    """

    async def load(self, mission_id: str) -> BriefState | None:
        """저장된 Brief를 반환한다. 없으면 ``None``."""
        ...

    async def save(self, state: BriefState) -> None:
        """Brief를 durable하게 기록한다.

        저장이 성공적으로 끝나기 전에는 호출자가 전이 완료를 보고해서는 안 된다.
        """
        ...
