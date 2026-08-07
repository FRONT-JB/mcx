"""Brief use case — 상태 로드, 질문 생성, 답변 기록, 승인의 조율.

도메인 규칙은 여기에 두지 않는다. 이 계층은 **순서와 경계**를 담당한다. 무엇을
읽고, 누구에게 무엇을 위임하고, 언제 저장하고, 무엇을 호출자에게 돌려줄지를
결정한다.

가장 중요한 규칙은 **저장이 성공한 뒤에만 전이가 일어났다고 보고한다**는 것이다.
메모리의 새 상태를 반환해 놓고 저장이 실패하면, 호출자는 기록되지 않은 답변을
기록된 것으로 취급하게 된다. 그래서 저장 실패는 예외로 드러나며 이 계층은 그것을
삼키지 않는다 (``docs/05_BRIEF.md`` §14.1, Appendix A 9번).

계약: ``docs/05_BRIEF.md`` §4.2, §10
"""

from __future__ import annotations

from dataclasses import dataclass

from mission_control.application.ports import (
    AskedRound,
    BriefRepository,
    GeneratedQuestion,
    QuestionGenerator,
    QuestionRequest,
)
from mission_control.domain.brief.provenance import AnswerAuthority
from mission_control.domain.brief.state import BriefState


class BriefNotFoundError(LookupError):
    """존재하지 않는 Mission의 Brief를 조작하려 했다."""

    def __init__(self, mission_id: str) -> None:
        super().__init__(f"no Brief exists for mission {mission_id}")
        self.mission_id = mission_id


class BriefAlreadyExistsError(ValueError):
    """이미 시작된 Brief를 다시 시작하려 했다.

    덮어쓰면 기존 대화와 승인이 사라진다. 재개는 시작이 아니라 로드다.
    """

    def __init__(self, mission_id: str) -> None:
        super().__init__(f"Brief for mission {mission_id} already exists")
        self.mission_id = mission_id


class QuestionContractError(RuntimeError):
    """질문 생성기가 계약을 위반한 결과를 반환했다.

    빈 질문을 상태에 저장하면 사용자에게 보여 줄 것이 없는 round가 남고, 이후
    clarity 평가가 그 round를 정상적인 근거로 셈한다.
    """


@dataclass(frozen=True, slots=True)
class BriefService:
    """Brief Stage의 application 경계."""

    repository: BriefRepository
    question_generator: QuestionGenerator

    async def start(self, *, mission_id: str, initial_intent: str) -> BriefState:
        """새 Brief를 시작하고 저장한다."""
        if await self.repository.load(mission_id) is not None:
            raise BriefAlreadyExistsError(mission_id)

        state = BriefState.start(mission_id=mission_id, initial_intent=initial_intent)
        await self.repository.save(state)
        return state

    async def ask_next_question(self, *, mission_id: str) -> GeneratedQuestion:
        """다음 질문 하나를 생성하고 답변 대기 상태로 저장한다.

        이미 대기 중인 질문이 있으면 생성기를 호출하지 않고 그 질문을 다시
        돌려준다. 세션이 끊겼다 재개된 경우 같은 질문이 두 번 생성되어 사용자가
        비슷한 질문을 연달아 받는 일을 막는다.

        생성기는 dispatch당 정확히 한 번 호출된다.
        """
        state = await self._require(mission_id)

        pending = state.pending_question
        if pending is not None:
            return GeneratedQuestion(question=pending.question, targeted_gap="resumed")

        generated = await self.question_generator.generate(self._request_for(state))
        if not generated.question.strip():
            raise QuestionContractError("question generator returned an empty question")

        posed = state.pose_question(question=generated.question)
        await self.repository.save(posed)
        return generated

    async def record_answer(
        self,
        *,
        mission_id: str,
        answer: str,
        authority: AnswerAuthority,
        question: str | None = None,
    ) -> BriefState:
        """답변을 기록하고 저장한다.

        저장에 실패하면 예외가 전파되고 저장소는 이전 상태를 유지한다. 호출자는
        답변이 기록되지 않은 것으로 처리해야 한다.
        """
        state = await self._require(mission_id)
        updated = state.record_answer(answer=answer, authority=authority, question=question)
        await self.repository.save(updated)
        return updated

    async def approve(self, *, mission_id: str, statement: str) -> BriefState:
        """현재 revision에 대한 사용자 승인을 기록하고 저장한다.

        승인은 Gate를 대신하지 않는다. 저장이 실패하면 승인받지 않은 것으로
        취급한다 (``docs/05_BRIEF.md`` §12.2).
        """
        state = await self._require(mission_id)
        approved = state.approve(statement=statement)
        await self.repository.save(approved)
        return approved

    async def _require(self, mission_id: str) -> BriefState:
        state = await self.repository.load(mission_id)
        if state is None:
            raise BriefNotFoundError(mission_id)
        return state

    @staticmethod
    def _request_for(state: BriefState) -> QuestionRequest:
        """생성기에 전달할 최소 context를 구성한다.

        authority와 revision 이력은 전달하지 않는다. 생성기는 무엇을 더 물어야
        하는지만 판단하면 되고, 저장 구조를 알면 그것을 근거로 요구사항을 지어낼
        여지가 생긴다.
        """
        return QuestionRequest(
            initial_intent=state.initial_intent,
            previous_rounds=tuple(
                AskedRound(question=item.question, answer=item.answer) for item in state.rounds
            ),
            unresolved_items=state.unresolved_items,
        )
