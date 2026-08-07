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

from pydantic import BaseModel, ConfigDict

from mission_control.domain.brief.state import BriefState, UnresolvedItem


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


class AskedRound(BaseModel):
    """질문 생성기에 전달하는 이전 대화 한 턴.

    저장된 ``BriefRound``를 그대로 넘기지 않는다. 생성기는 답변의 authority나
    revision 이력을 알 필요가 없고, 알면 그것을 근거로 요구사항을 지어낼 수 있다.
    """

    model_config = ConfigDict(frozen=True)

    question: str
    answer: str | None


class QuestionRequest(BaseModel):
    """질문 하나를 생성하기 위해 필요한 최소 context.

    Mission Control이 선별해서 전달한다. 파일 경로, 도구 목록, 자격 증명 같은
    실행 수단은 담기지 않는다. 질문 생성 역할은 저장소를 조사하지 않으며 필요한
    사실은 별도의 read-only 경로가 제공한다 (``docs/05_BRIEF.md`` §4.3, §4.4).
    """

    model_config = ConfigDict(frozen=True)

    initial_intent: str
    previous_rounds: tuple[AskedRound, ...]
    unresolved_items: tuple[UnresolvedItem, ...]


class GeneratedQuestion(BaseModel):
    """생성기가 반환하는 질문 하나와 그 질문이 겨냥한 gap.

    구조적으로 하나만 담는다. 여러 질문을 한 번에 던지면 사용자가 일부만 답하고,
    어느 답이 어느 질문의 것인지 알 수 없게 된다.
    """

    model_config = ConfigDict(frozen=True)

    question: str
    targeted_gap: str


class QuestionGenerator(Protocol):
    """한 번의 dispatch에서 질문 하나를 생성하는 제한된 역할.

    이 port에는 파일 쓰기, Shell, Git, 네트워크, Mission Control 재귀 호출 수단이
    없다. 계약을 프롬프트 문구가 아니라 시그니처로 강제하기 위해서다
    (``docs/adr/0004-stage-scoped-minimum-capability.md``).

    Phase 1의 강제 범위는 여기까지다. 실제 runtime에서 도구를 차단하는 것은
    Runtime Adapter를 도입할 때 함께 다룬다.
    """

    async def generate(self, request: QuestionRequest) -> GeneratedQuestion:
        """질문 하나를 반환한다. 호출자는 dispatch당 한 번만 호출한다."""
        ...
