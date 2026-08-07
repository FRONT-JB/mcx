"""Brief use case의 조율과 실패 처리.

계약: docs/05_BRIEF.md §4.2, §10, §14.1
Test Matrix: B-002, B-003, B-016
"""

import pytest

from mission_control.application.brief_service import (
    BriefAlreadyExistsError,
    BriefNotFoundError,
    BriefService,
    QuestionContractError,
)
from mission_control.application.ports import GeneratedQuestion, QuestionRequest
from mission_control.domain.brief.state import BriefState


class InMemoryBriefRepository:
    """저장 성공과 실패를 제어할 수 있는 test double."""

    def __init__(self) -> None:
        self.states: dict[str, BriefState] = {}
        self.fail_next_save = False
        self.save_calls = 0

    async def load(self, mission_id: str) -> BriefState | None:
        return self.states.get(mission_id)

    async def save(self, state: BriefState) -> None:
        self.save_calls += 1
        if self.fail_next_save:
            self.fail_next_save = False
            raise OSError("disk is unavailable")
        self.states[state.mission_id] = state


class ScriptedQuestionGenerator:
    """미리 정한 질문을 순서대로 반환하고 호출을 기록한다."""

    def __init__(self, *questions: str) -> None:
        self.questions = list(questions) or ["기본 질문입니까?"]
        self.requests: list[QuestionRequest] = []

    @property
    def call_count(self) -> int:
        return len(self.requests)

    async def generate(self, request: QuestionRequest) -> GeneratedQuestion:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.questions) - 1)
        return GeneratedQuestion(question=self.questions[index], targeted_gap="scope")


@pytest.fixture
def repository() -> InMemoryBriefRepository:
    return InMemoryBriefRepository()


@pytest.fixture
def generator() -> ScriptedQuestionGenerator:
    return ScriptedQuestionGenerator("댓글은 누가 쓸 수 있나요?", "수정과 삭제도 필요한가요?")


@pytest.fixture
def service(
    repository: InMemoryBriefRepository, generator: ScriptedQuestionGenerator
) -> BriefService:
    return BriefService(repository=repository, question_generator=generator)


async def _started(service: BriefService) -> BriefState:
    return await service.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")


class TestStart:
    async def test_started_brief_is_persisted(
        self, service: BriefService, repository: InMemoryBriefRepository
    ) -> None:
        await _started(service)

        assert await repository.load("m-1") is not None

    async def test_starting_twice_is_rejected(self, service: BriefService) -> None:
        await _started(service)

        with pytest.raises(BriefAlreadyExistsError):
            await _started(service)

    async def test_operations_require_an_existing_brief(self, service: BriefService) -> None:
        with pytest.raises(BriefNotFoundError):
            await service.ask_next_question(mission_id="m-unknown")


class TestQuestionDispatch:
    """B-002 — dispatch당 한 번, 실행 수단 없는 최소 context."""

    async def test_generator_is_called_exactly_once_per_dispatch(
        self, service: BriefService, generator: ScriptedQuestionGenerator
    ) -> None:
        await _started(service)

        await service.ask_next_question(mission_id="m-1")

        assert generator.call_count == 1

    async def test_request_carries_only_interview_context(
        self, service: BriefService, generator: ScriptedQuestionGenerator
    ) -> None:
        await _started(service)

        await service.ask_next_question(mission_id="m-1")

        request = generator.requests[0]
        assert request.initial_intent == "댓글 기능을 추가하고 싶다"
        assert set(request.model_dump()) == {
            "initial_intent",
            "previous_rounds",
            "unresolved_items",
        }

    async def test_request_does_not_expose_authority_or_revision(
        self, service: BriefService, generator: ScriptedQuestionGenerator
    ) -> None:
        """생성기가 저장 구조를 알면 그것을 근거로 요구사항을 지어낼 수 있다."""
        await _started(service)
        await service.record_answer(
            mission_id="m-1", answer="로그인 사용자만", authority="decision", question="권한은?"
        )

        await service.ask_next_question(mission_id="m-1")

        round_fields = set(generator.requests[0].previous_rounds[0].model_dump())
        assert round_fields == {"question", "answer"}

    async def test_posed_question_is_persisted_before_the_answer(
        self, service: BriefService, repository: InMemoryBriefRepository
    ) -> None:
        """생성 직후 세션이 끊겨도 같은 질문으로 재개할 수 있어야 한다."""
        await _started(service)

        generated = await service.ask_next_question(mission_id="m-1")

        stored = await repository.load("m-1")
        assert stored is not None
        assert stored.pending_question is not None
        assert stored.pending_question.question == generated.question

    async def test_resume_returns_the_pending_question_without_regenerating(
        self, service: BriefService, generator: ScriptedQuestionGenerator
    ) -> None:
        await _started(service)
        first = await service.ask_next_question(mission_id="m-1")

        resumed = await service.ask_next_question(mission_id="m-1")

        assert resumed.question == first.question
        assert generator.call_count == 1


class TestQuestionContractViolation:
    """B-003 — 계약을 위반한 생성 결과가 상태를 손상시키지 않는다."""

    async def test_empty_question_is_rejected(self, repository: InMemoryBriefRepository) -> None:
        service = BriefService(
            repository=repository, question_generator=ScriptedQuestionGenerator("   ")
        )
        await _started(service)

        with pytest.raises(QuestionContractError):
            await service.ask_next_question(mission_id="m-1")

    async def test_state_is_unchanged_after_a_contract_violation(
        self, repository: InMemoryBriefRepository
    ) -> None:
        service = BriefService(
            repository=repository, question_generator=ScriptedQuestionGenerator("")
        )
        await _started(service)

        with pytest.raises(QuestionContractError):
            await service.ask_next_question(mission_id="m-1")

        stored = await repository.load("m-1")
        assert stored is not None
        assert stored.rounds == ()


class TestPersistenceFailureBlocksTransition:
    """B-016 — 저장이 실패하면 전이가 일어난 것처럼 응답하지 않는다."""

    async def test_answer_is_not_recorded_when_save_fails(
        self, service: BriefService, repository: InMemoryBriefRepository
    ) -> None:
        await _started(service)
        repository.fail_next_save = True

        with pytest.raises(OSError):
            await service.record_answer(
                mission_id="m-1", answer="로그인 사용자만", authority="decision", question="권한은?"
            )

        stored = await repository.load("m-1")
        assert stored is not None
        assert stored.answered_rounds == ()

    async def test_approval_is_not_recorded_when_save_fails(
        self, service: BriefService, repository: InMemoryBriefRepository
    ) -> None:
        await _started(service)
        await service.record_answer(
            mission_id="m-1", answer="a", authority="decision", question="q"
        )
        repository.fail_next_save = True

        with pytest.raises(OSError):
            await service.approve(mission_id="m-1", statement="진행해 주세요")

        stored = await repository.load("m-1")
        assert stored is not None
        assert stored.approval is None
        assert stored.has_current_approval is False

    async def test_posed_question_is_not_kept_when_save_fails(
        self, service: BriefService, repository: InMemoryBriefRepository
    ) -> None:
        await _started(service)
        repository.fail_next_save = True

        with pytest.raises(OSError):
            await service.ask_next_question(mission_id="m-1")

        stored = await repository.load("m-1")
        assert stored is not None
        assert stored.pending_question is None


class TestAnswerFlow:
    async def test_answer_fills_the_pending_question(self, service: BriefService) -> None:
        await _started(service)
        generated = await service.ask_next_question(mission_id="m-1")

        state = await service.record_answer(
            mission_id="m-1", answer="로그인 사용자만", authority="decision"
        )

        assert len(state.rounds) == 1
        assert state.rounds[0].question == generated.question
        assert state.rounds[0].answer == "로그인 사용자만"

    async def test_observation_authority_is_preserved(self, service: BriefService) -> None:
        await _started(service)
        await service.ask_next_question(mission_id="m-1")

        state = await service.record_answer(
            mission_id="m-1", answer="JWT 사용 중", authority="observation"
        )

        assert state.rounds[0].authority == "observation"

    async def test_approval_binds_to_the_current_revision(self, service: BriefService) -> None:
        await _started(service)
        recorded = await service.record_answer(
            mission_id="m-1", answer="a", authority="decision", question="q"
        )

        approved = await service.approve(mission_id="m-1", statement="진행")

        assert approved.approval is not None
        assert approved.approval.revision == recorded.revision
        assert approved.has_current_approval is True
