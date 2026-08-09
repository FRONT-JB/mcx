"""Brief use case의 조율과 실패 처리.

계약: docs/05_BRIEF.md §4.2, §10, §14.1
Test Matrix: B-002, B-003, B-016, B-029, B-034, B-035, B-036
"""

import asyncio

import pytest

from mission_control.application.brief_service import (
    BriefAlreadyExistsError,
    BriefNotFoundError,
    BriefService,
    ClarityAssessmentError,
    ClosureAuditError,
    ClosureContractError,
    QuestionContractError,
)
from mission_control.application.ports import (
    AssessmentRequest,
    CloserAuditRequest,
    ClosureChallengeRequest,
    GeneratedQuestion,
    QuestionRequest,
)
from mission_control.domain.brief.clarity import (
    ClarityAssessment,
    ClarityPolicy,
    DimensionScore,
)
from mission_control.domain.brief.closure import (
    AdvisoryLane,
    AdvisoryReport,
    CloserReport,
    CloserVerdict,
    ClosureSeverity,
)
from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    ConfirmationAuthority,
    RequirementSection,
)
from mission_control.domain.brief.state import BriefState

POLICY = ClarityPolicy.greenfield_v1()


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


class ScriptedClarityAssessor:
    """고정된 점수를 반환하고 호출을 기록한다. 실패도 재현할 수 있다."""

    def __init__(self, *, goal: float = 0.9, constraint: float = 0.9, success: float = 0.9) -> None:
        self.scores = (goal, constraint, success)
        self.requests: list[AssessmentRequest] = []
        self.fail_next = False

    @property
    def call_count(self) -> int:
        return len(self.requests)

    async def assess(self, request: AssessmentRequest) -> ClarityAssessment:
        self.requests.append(request)
        if self.fail_next:
            self.fail_next = False
            raise ValueError("assessor returned unparseable output")
        goal, constraint, success = self.scores
        return ClarityAssessment(
            scores=(
                DimensionScore(dimension="goal", clarity=goal, justification="t"),
                DimensionScore(dimension="constraint", clarity=constraint, justification="t"),
                DimensionScore(dimension="success_criteria", clarity=success, justification="t"),
            ),
            policy_version=POLICY.version,
        )


class ScriptedClosureAssessor:
    """고정된 closer 판정을 반환한다. 실패도 재현할 수 있다."""

    def __init__(
        self,
        verdict: CloserVerdict = CloserVerdict.READY,
        *,
        blocking_question: str | None = None,
    ) -> None:
        self.verdict = verdict
        self.blocking_question = blocking_question
        self.requests: list[CloserAuditRequest] = []
        self.fail_next = False

    async def audit(self, request: CloserAuditRequest) -> CloserReport:
        self.requests.append(request)
        if self.fail_next:
            self.fail_next = False
            raise ValueError("closer returned unparseable output")
        return CloserReport(
            verdict=self.verdict,
            reason="scripted reason",
            blocking_question=self.blocking_question,
        )


class ScriptedClosureChallenger:
    """요청받은 lane 그대로 고정 심각도를 반환한다. lane 위반도 재현할 수 있다."""

    def __init__(self, severity: ClosureSeverity = ClosureSeverity.LOW) -> None:
        self.severity = severity
        self.requests: list[ClosureChallengeRequest] = []
        self.wrong_lane = False

    async def challenge(self, request: ClosureChallengeRequest) -> AdvisoryReport:
        self.requests.append(request)
        lane = request.lane
        if self.wrong_lane:
            lane = (
                AdvisoryLane.GAP_HUNTER
                if request.lane is AdvisoryLane.CONTRARIAN
                else AdvisoryLane.CONTRARIAN
            )
        return AdvisoryReport(lane=lane, severity=self.severity, finding="scripted finding")


@pytest.fixture
def repository() -> InMemoryBriefRepository:
    return InMemoryBriefRepository()


@pytest.fixture
def generator() -> ScriptedQuestionGenerator:
    return ScriptedQuestionGenerator("댓글은 누가 쓸 수 있나요?", "수정과 삭제도 필요한가요?")


@pytest.fixture
def assessor() -> ScriptedClarityAssessor:
    return ScriptedClarityAssessor()


@pytest.fixture
def closure_assessor() -> ScriptedClosureAssessor:
    return ScriptedClosureAssessor()


@pytest.fixture
def closure_challenger() -> ScriptedClosureChallenger:
    return ScriptedClosureChallenger()


@pytest.fixture
def service(
    repository: InMemoryBriefRepository,
    generator: ScriptedQuestionGenerator,
    assessor: ScriptedClarityAssessor,
    closure_assessor: ScriptedClosureAssessor,
    closure_challenger: ScriptedClosureChallenger,
) -> BriefService:
    return BriefService(
        repository=repository,
        question_generator=generator,
        clarity_assessor=assessor,
        closure_assessor=closure_assessor,
        closure_challenger=closure_challenger,
        policy=POLICY,
    )


async def _started(service: BriefService) -> BriefState:
    return await service.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")


async def _answered(service: BriefService, rounds: int = 3) -> BriefState:
    """최소 round를 채운 Brief를 만든다."""
    state = await _started(service)
    for index in range(rounds):
        state = await service.record_answer(
            mission_id="m-1", answer=f"a{index}", authority="decision", question=f"q{index}"
        )
    return state


async def _with_success_criterion(service: BriefService) -> BriefState:
    """승격되는 성공 조건 하나 — ADR-0050 §3 이후 CLEAR의 필수 재료다."""
    return await service.record_candidate(
        mission_id="m-1",
        section=RequirementSection.ACCEPTANCE_CRITERION,
        text="목록에 새 댓글이 보인다",
        content_source=CandidateContentSource.USER_STATED,
        resolution=CandidateResolution.CONFIRMED,
        confirmation_authority=ConfirmationAuthority.USER,
    )


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
            "requirement_candidates",
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
            repository=repository,
            question_generator=ScriptedQuestionGenerator("   "),
            clarity_assessor=ScriptedClarityAssessor(),
            closure_assessor=ScriptedClosureAssessor(),
            closure_challenger=ScriptedClosureChallenger(),
            policy=POLICY,
        )
        await _started(service)

        with pytest.raises(QuestionContractError):
            await service.ask_next_question(mission_id="m-1")

    async def test_state_is_unchanged_after_a_contract_violation(
        self, repository: InMemoryBriefRepository
    ) -> None:
        service = BriefService(
            repository=repository,
            question_generator=ScriptedQuestionGenerator(""),
            clarity_assessor=ScriptedClarityAssessor(),
            closure_assessor=ScriptedClosureAssessor(),
            closure_challenger=ScriptedClosureChallenger(),
            policy=POLICY,
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


class TestAssessmentIsSkippedBeforeMinimumRounds:
    """B-029 — 최소 round 전에는 평가하지 않고, 미평가가 미통과와 구분된다."""

    async def test_assessor_is_not_called(
        self, service: BriefService, assessor: ScriptedClarityAssessor
    ) -> None:
        await _answered(service, rounds=POLICY.minimum_rounds - 1)

        await service.assess_clarity(mission_id="m-1")

        assert assessor.call_count == 0

    async def test_state_is_untouched(
        self, service: BriefService, repository: InMemoryBriefRepository
    ) -> None:
        before = await _answered(service, rounds=POLICY.minimum_rounds - 1)
        saves = repository.save_calls

        await service.assess_clarity(mission_id="m-1")

        stored = await repository.load("m-1")
        assert stored is not None
        assert stored.sequence == before.sequence
        assert repository.save_calls == saves

    async def test_unassessed_is_distinguished_from_not_qualifying(
        self, service: BriefService
    ) -> None:
        """둘 다 HOLD지만 다음 행동이 다르므로 이유가 달라야 한다."""
        await _answered(service, rounds=POLICY.minimum_rounds - 1)
        await service.assess_clarity(mission_id="m-1")

        decision = await service.decide_gate(mission_id="m-1")

        conditions = {blocker.condition.value for blocker in decision.clarity_blockers}
        assert "assessment_missing" in conditions
        assert "ambiguity_above_threshold" not in conditions

    async def test_assessor_runs_once_the_minimum_is_reached(
        self, service: BriefService, assessor: ScriptedClarityAssessor
    ) -> None:
        await _answered(service, rounds=POLICY.minimum_rounds)

        state = await service.assess_clarity(mission_id="m-1")

        assert assessor.call_count == 1
        assert state.assessment is not None


class TestAssessmentRequest:
    async def test_request_names_the_policy_dimensions(
        self, service: BriefService, assessor: ScriptedClarityAssessor
    ) -> None:
        """평가자가 채점할 축을 스스로 고르면 누락된 축이 조용히 집계에서 빠진다."""
        await _answered(service)

        await service.assess_clarity(mission_id="m-1")

        assert assessor.requests[0].dimensions == tuple(POLICY.weights)

    async def test_request_does_not_carry_thresholds(
        self, service: BriefService, assessor: ScriptedClarityAssessor
    ) -> None:
        """통과 기준을 알려 주면 그 기준에 맞춰 점수를 조정할 여지가 생긴다."""
        await _answered(service)

        await service.assess_clarity(mission_id="m-1")

        assert set(assessor.requests[0].model_dump()) == {
            "initial_intent",
            "previous_rounds",
            "requirement_candidates",
            "dimensions",
        }


class TestStabilitySignalAdvancesOncePerAssessment:
    """§11.4 — 평가 하나당 정확히 한 번 갱신한다."""

    async def test_each_assessment_advances_by_one(self, service: BriefService) -> None:
        await _answered(service)

        first = await service.assess_clarity(mission_id="m-1")
        second = await service.assess_clarity(mission_id="m-1")

        assert first.stability_signal == 1
        assert second.stability_signal == 2

    async def test_gate_decision_does_not_advance_the_signal(
        self, service: BriefService, repository: InMemoryBriefRepository
    ) -> None:
        """판정을 다시 요청하는 것만으로 종료 조건이 충족되면 안 된다."""
        await _answered(service)
        await service.assess_clarity(mission_id="m-1")

        for _ in range(3):
            await service.decide_gate(mission_id="m-1")

        stored = await repository.load("m-1")
        assert stored is not None
        assert stored.stability_signal == 1

    async def test_non_qualifying_assessment_resets(
        self, repository: InMemoryBriefRepository, generator: ScriptedQuestionGenerator
    ) -> None:
        assessor = ScriptedClarityAssessor()
        service = BriefService(
            repository=repository,
            question_generator=generator,
            clarity_assessor=assessor,
            closure_assessor=ScriptedClosureAssessor(),
            closure_challenger=ScriptedClosureChallenger(),
            policy=POLICY,
        )
        await _answered(service)
        await service.assess_clarity(mission_id="m-1")

        assessor.scores = (0.9, 0.9, 0.4)
        state = await service.assess_clarity(mission_id="m-1")

        assert state.stability_signal == 0


class TestMaterialChangeInvalidatesAssessment:
    """B-034 — CLEAR 이후 답변이 추가되면 평가와 signal이 함께 초기화된다."""

    async def test_answer_resets_both(self, service: BriefService) -> None:
        await _answered(service)
        await _with_success_criterion(service)
        await service.assess_clarity(mission_id="m-1")
        qualified = await service.assess_clarity(mission_id="m-1")
        await service.audit_closure(mission_id="m-1")
        await service.approve(mission_id="m-1", statement="진행")
        assert (await service.decide_gate(mission_id="m-1")).outcome == "CLEAR"
        assert qualified.stability_signal == POLICY.required_stability

        reopened = await service.record_answer(
            mission_id="m-1", answer="비로그인은 조회만", authority="decision", question="추가"
        )

        assert reopened.assessment is None
        assert reopened.stability_signal == 0

    async def test_reopened_brief_requires_reapproval_and_reassessment(
        self, service: BriefService
    ) -> None:
        await _answered(service)
        await service.assess_clarity(mission_id="m-1")
        await service.assess_clarity(mission_id="m-1")
        await service.approve(mission_id="m-1", statement="진행")
        await service.record_answer(
            mission_id="m-1", answer="비로그인은 조회만", authority="decision", question="추가"
        )

        decision = await service.decide_gate(mission_id="m-1")

        assert decision.outcome == "HOLD"
        conditions = {blocker.condition.value for blocker in decision.clarity_blockers}
        assert "assessment_missing" in conditions
        assert any("approval" in blocker.condition.value for blocker in decision.gate_blockers)

    async def test_recording_a_candidate_resets_both(self, service: BriefService) -> None:
        await _answered(service)
        await service.assess_clarity(mission_id="m-1")

        state = await service.record_candidate(
            mission_id="m-1",
            section=RequirementSection.CONSTRAINT,
            text="비로그인 정책 미정",
            content_source=CandidateContentSource.USER_STATED,
            resolution=CandidateResolution.UNKNOWN,
            required=True,
        )

        assert state.assessment is None
        assert state.stability_signal == 0

    async def test_resolving_a_candidate_resets_both(self, service: BriefService) -> None:
        """미해결이던 후보가 확정되면 Gate 판정이 달라지므로 재평가가 필요하다."""
        await _answered(service)
        await service.record_candidate(
            mission_id="m-1",
            section=RequirementSection.CONSTRAINT,
            text="비로그인 정책",
            content_source=CandidateContentSource.USER_STATED,
            resolution=CandidateResolution.UNKNOWN,
            required=True,
        )
        await service.assess_clarity(mission_id="m-1")

        state = await service.resolve_candidate(
            mission_id="m-1",
            number=1,
            resolution=CandidateResolution.CONFIRMED,
            confirmation_authority=ConfirmationAuthority.USER,
        )

        assert state.assessment is None
        assert state.stability_signal == 0


class TestCandidateEntryPoint:
    """미해결 후보를 application 경계에서 만들 수 있어야 Gate가 실제로 막힌다."""

    async def test_required_unknown_candidate_blocks_the_gate(self, service: BriefService) -> None:
        await _answered(service)
        await service.record_candidate(
            mission_id="m-1",
            section=RequirementSection.NON_GOAL,
            text="수정·삭제를 이번 범위에 넣을지 미정",
            content_source=CandidateContentSource.USER_STATED,
            resolution=CandidateResolution.UNKNOWN,
            required=True,
        )
        await service.assess_clarity(mission_id="m-1")
        await service.assess_clarity(mission_id="m-1")
        await service.approve(mission_id="m-1", statement="그래도 진행")

        decision = await service.decide_gate(mission_id="m-1")

        assert decision.outcome == "HOLD"
        assert any(
            blocker.condition.value == "unpromotable_requirement"
            for blocker in decision.gate_blockers
        )

    async def test_confirming_the_candidate_clears_the_gate(self, service: BriefService) -> None:
        await _answered(service)
        await _with_success_criterion(service)
        await service.record_candidate(
            mission_id="m-1",
            section=RequirementSection.NON_GOAL,
            text="수정·삭제는 이번 범위가 아니다",
            content_source=CandidateContentSource.USER_STATED,
            resolution=CandidateResolution.UNKNOWN,
            required=True,
        )
        await service.resolve_candidate(
            mission_id="m-1",
            # 1은 ``brief start``가 파생한 goal, 2는 성공 조건이다 (ADR-0050 §1).
            number=3,
            resolution=CandidateResolution.CONFIRMED,
            confirmation_authority=ConfirmationAuthority.USER,
        )
        await service.assess_clarity(mission_id="m-1")
        await service.assess_clarity(mission_id="m-1")
        await service.audit_closure(mission_id="m-1")
        await service.approve(mission_id="m-1", statement="진행")

        decision = await service.decide_gate(mission_id="m-1")

        assert decision.outcome == "CLEAR"

    async def test_confirmed_candidates_are_sent_with_their_resolution(
        self, service: BriefService, generator: ScriptedQuestionGenerator
    ) -> None:
        """확정 후보를 감추면 위임 역할이 결정된 사안을 재차단한다 (ADR-0035 §1).

        도그푸딩 0001 §3.1 — 확정된 non-goal이 보이지 않아 감사가 HIGH로
        차단했다. 열림/닫힘은 목록이 아니라 resolution이 구분한다.
        """
        await _answered(service)
        await service.record_candidate(
            mission_id="m-1",
            section=RequirementSection.CONSTRAINT,
            text="로그인 사용자만 작성",
            content_source=CandidateContentSource.USER_STATED,
            resolution=CandidateResolution.CONFIRMED,
            confirmation_authority=ConfirmationAuthority.USER,
        )
        await service.record_candidate(
            mission_id="m-1",
            section=RequirementSection.NON_GOAL,
            text="알림을 보낼지 미정",
            content_source=CandidateContentSource.USER_STATED,
            resolution=CandidateResolution.UNKNOWN,
        )

        await service.ask_next_question(mission_id="m-1")

        sent = generator.requests[-1].requirement_candidates
        # 첫 항목은 ``brief start``가 파생한 goal이다 (ADR-0050 §1).
        assert [item.text for item in sent] == [
            "댓글 기능을 추가하고 싶다",
            "로그인 사용자만 작성",
            "알림을 보낼지 미정",
        ]
        assert [item.resolution for item in sent] == [
            CandidateResolution.CONFIRMED,
            CandidateResolution.CONFIRMED,
            CandidateResolution.UNKNOWN,
        ]


class TestAssessmentFailure:
    """B-035, B-036 — 평가 실패를 점수로 해석하지 않는다."""

    async def test_failure_is_not_reported_as_progress(
        self, service: BriefService, assessor: ScriptedClarityAssessor
    ) -> None:
        await _answered(service)
        assessor.fail_next = True

        with pytest.raises(ClarityAssessmentError):
            await service.assess_clarity(mission_id="m-1")

    async def test_failure_resets_a_previously_qualifying_signal(
        self,
        service: BriefService,
        assessor: ScriptedClarityAssessor,
        repository: InMemoryBriefRepository,
    ) -> None:
        """초기화를 저장하지 않으면 이전 통과 결과로 다음 Gate가 CLEAR한다."""
        await _answered(service)
        await service.assess_clarity(mission_id="m-1")
        assessor.fail_next = True

        with pytest.raises(ClarityAssessmentError):
            await service.assess_clarity(mission_id="m-1")

        stored = await repository.load("m-1")
        assert stored is not None
        assert stored.assessment is None
        assert stored.stability_signal == 0

    async def test_incomplete_scores_are_treated_as_no_result(
        self, repository: InMemoryBriefRepository, generator: ScriptedQuestionGenerator
    ) -> None:
        """가중치가 부여된 축이 빠진 결과는 높은 점수도 낮은 점수도 아니다."""

        class PartialAssessor:
            async def assess(self, request: AssessmentRequest) -> ClarityAssessment:
                return ClarityAssessment(
                    scores=(DimensionScore(dimension="goal", clarity=1.0, justification="t"),),
                    policy_version=POLICY.version,
                )

        service = BriefService(
            repository=repository,
            question_generator=generator,
            clarity_assessor=PartialAssessor(),
            closure_assessor=ScriptedClosureAssessor(),
            closure_challenger=ScriptedClosureChallenger(),
            policy=POLICY,
        )
        await _answered(service)

        with pytest.raises(ClarityAssessmentError):
            await service.assess_clarity(mission_id="m-1")

    async def test_reset_save_failure_surfaces(
        self,
        service: BriefService,
        assessor: ScriptedClarityAssessor,
        repository: InMemoryBriefRepository,
    ) -> None:
        """signal 저장이 실패하면 진행 가능 상태를 보고하지 않는다."""
        await _answered(service)
        assessor.fail_next = True
        repository.fail_next_save = True

        with pytest.raises(OSError):
            await service.assess_clarity(mission_id="m-1")

    async def test_assessment_is_not_stored_when_save_fails(
        self, service: BriefService, repository: InMemoryBriefRepository
    ) -> None:
        await _answered(service)
        repository.fail_next_save = True

        with pytest.raises(OSError):
            await service.assess_clarity(mission_id="m-1")

        stored = await repository.load("m-1")
        assert stored is not None
        assert stored.assessment is None


class TestClosureAuditUseCase:
    """§11.6 — 세 lane 감사의 조율과 실패 처리."""

    async def test_audit_runs_all_three_lanes_and_persists(
        self,
        service: BriefService,
        repository: InMemoryBriefRepository,
        closure_assessor: ScriptedClosureAssessor,
        closure_challenger: ScriptedClosureChallenger,
    ) -> None:
        await _answered(service)

        state = await service.audit_closure(mission_id="m-1")

        assert state.has_current_closure_audit
        assert len(closure_assessor.requests) == 1
        assert [item.lane for item in closure_challenger.requests] == [
            AdvisoryLane.CONTRARIAN,
            AdvisoryLane.GAP_HUNTER,
        ]
        stored = await repository.load("m-1")
        assert stored is not None and stored.has_current_closure_audit

    async def test_the_three_lanes_run_concurrently(
        self,
        repository: InMemoryBriefRepository,
        generator: ScriptedQuestionGenerator,
        assessor: ScriptedClarityAssessor,
    ) -> None:
        """lane은 서로의 결과를 보지 않으므로 동시에 수행된다 (ADR-0035 §2).

        upstream은 tripanel을 한 병렬 배치로 spawn한다. 세 lane 전부가 barrier에
        모여야 열리므로, 순차 실행이면 첫 lane에서 timeout으로 실패한다.
        """
        barrier = asyncio.Barrier(3)

        class BarrierCloser:
            async def audit(self, request: CloserAuditRequest) -> CloserReport:
                await asyncio.wait_for(barrier.wait(), timeout=2)
                return CloserReport(verdict=CloserVerdict.READY, reason="t")

        class BarrierChallenger:
            async def challenge(self, request: ClosureChallengeRequest) -> AdvisoryReport:
                await asyncio.wait_for(barrier.wait(), timeout=2)
                return AdvisoryReport(lane=request.lane, severity=ClosureSeverity.LOW, finding="t")

        service = BriefService(
            repository=repository,
            question_generator=generator,
            clarity_assessor=assessor,
            closure_assessor=BarrierCloser(),
            closure_challenger=BarrierChallenger(),
            policy=POLICY,
        )
        await service.start(mission_id="m-1", initial_intent="댓글 기능")

        state = await service.audit_closure(mission_id="m-1")

        assert state.has_current_closure_audit

    async def test_requests_carry_the_upstream_contract_texts(
        self,
        service: BriefService,
        closure_assessor: ScriptedClosureAssessor,
        closure_challenger: ScriptedClosureChallenger,
    ) -> None:
        """계약 문장은 정책이 정하고 역할이 바꿀 수 없다."""
        await _answered(service)

        await service.audit_closure(mission_id="m-1")

        assert "permission to audit closure" in closure_assessor.requests[0].gate_summary
        assert all(
            'Rate "high" ONLY when' in item.severity_rule for item in closure_challenger.requests
        )

    async def test_lane_failure_leaves_state_unchanged(
        self,
        service: BriefService,
        repository: InMemoryBriefRepository,
        closure_assessor: ScriptedClosureAssessor,
    ) -> None:
        """실패는 결과 없음이다 — 감사 없는 상태로 남아 Gate가 막는다."""
        await _answered(service)
        closure_assessor.fail_next = True

        with pytest.raises(ClosureAuditError):
            await service.audit_closure(mission_id="m-1")

        stored = await repository.load("m-1")
        assert stored is not None and stored.closure_audit is None

    async def test_wrong_lane_is_a_contract_violation(
        self,
        service: BriefService,
        closure_challenger: ScriptedClosureChallenger,
    ) -> None:
        """다른 lane의 결과를 받아들이면 감사의 근거 기록이 거짓이 된다."""
        await _answered(service)
        closure_challenger.wrong_lane = True

        with pytest.raises(ClosureContractError):
            await service.audit_closure(mission_id="m-1")

    async def test_blocked_audit_is_still_recorded(
        self,
        repository: InMemoryBriefRepository,
        generator: ScriptedQuestionGenerator,
    ) -> None:
        """차단 판정도 기록이다 — 무엇이 막았는지가 Gate 사유로 남아야 한다."""
        service = BriefService(
            repository=repository,
            question_generator=generator,
            clarity_assessor=ScriptedClarityAssessor(),
            closure_assessor=ScriptedClosureAssessor(
                CloserVerdict.NOT_READY, blocking_question="who owns the cache?"
            ),
            closure_challenger=ScriptedClosureChallenger(),
            policy=POLICY,
        )
        await _answered(service)

        state = await service.audit_closure(mission_id="m-1")

        assert state.has_current_closure_audit
        assert state.closure_audit is not None
        assert state.closure_audit.audit.decision.ready is False
        assert "who owns the cache?" in state.closure_audit.audit.decision.blocking_questions
