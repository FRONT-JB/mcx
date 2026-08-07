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

from mission_control.domain.brief.clarity import ClarityAssessment, ClarityDimension
from mission_control.domain.brief.state import BriefState, UnresolvedItem


class BriefRepository(Protocol):
    """Brief 상태의 durable 저장소.

    구현은 다음을 보장해야 한다.

    - 부분 기록된 상태가 읽히지 않는다.
    - 저장된 것보다 앞서지 않는 쓰기를 거부한다
      (:class:`~mission_control.domain.errors.StaleWriteError`).
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
    """위임 역할에 전달하는 이전 대화 한 턴.

    저장된 ``BriefRound``를 그대로 넘기지 않는다. 위임받은 역할은 답변의
    authority나 revision 이력을 알 필요가 없고, 알면 그것을 근거로 요구사항을
    지어낼 수 있다.
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


class AssessmentRequest(BaseModel):
    """clarity를 평가하기 위해 필요한 최소 context.

    ``dimensions``는 현재 정책이 가중치를 부여한 축이다. 평가자가 임의의 축을
    고르면 집계가 성립하지 않으므로 무엇을 채점해야 하는지 명시한다.

    threshold, floor, weight는 전달하지 않는다. 평가자의 일은 채점이지 판정이
    아니고, 통과 기준을 알려 주면 그 기준에 맞춰 점수를 조정할 여지가 생긴다.
    판정은 :class:`~mission_control.domain.brief.clarity.ClarityPolicy`가 한다.
    """

    model_config = ConfigDict(frozen=True)

    initial_intent: str
    previous_rounds: tuple[AskedRound, ...]
    unresolved_items: tuple[UnresolvedItem, ...]
    dimensions: tuple[ClarityDimension, ...]


class ClarityAssessor(Protocol):
    """현재 Brief의 축별 clarity를 채점하는 제한된 역할.

    질문 생성과 분리된 port인 이유는 두 역할이 서로를 정당화하지 못하게 하기
    위해서다. 같은 호출이 질문을 만들고 그 결과를 채점하면 "충분히 물었다"는
    판단을 자기 자신이 내린다 (``docs/adr/0004-stage-scoped-minimum-capability.md``).

    평가 실패는 낮은 점수가 아니라 결과 없음이다. 구현은 결과를 추측해 반환하지
    말고 예외를 올린다 (``docs/05_BRIEF.md`` §11.3).
    """

    async def assess(self, request: AssessmentRequest) -> ClarityAssessment:
        """요청된 모든 dimension의 clarity 점수를 반환한다."""
        ...
