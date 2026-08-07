"""Brief 전체 흐름 — 실제 파일 저장소로 시작부터 Gate 판정까지.

단위 테스트가 각 조각을 검증한다면 여기서는 조각들이 실제로 맞물리는지 본다.
특히 프로세스가 끊긴 뒤 다른 인스턴스가 이어받는 경로를 확인한다.

계약: docs/05_BRIEF.md §10
Test Matrix: B-019
"""

from pathlib import Path

from mission_control.adapters.persistence.file_brief_repository import FileBriefRepository
from mission_control.application.brief_service import BriefService
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
    AdvisoryReport,
    CloserReport,
    CloserVerdict,
    ClosureSeverity,
)
from mission_control.domain.brief.gate import next_stage_after_brief
from mission_control.domain.stage import Stage

POLICY = ClarityPolicy.greenfield_v1()

QUESTIONS = (
    "댓글은 누가 쓸 수 있나요?",
    "수정과 삭제도 이번 범위에 포함되나요?",
    "완료되었다는 것을 어떻게 확인하면 될까요?",
)


class SequentialQuestionGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: QuestionRequest) -> GeneratedQuestion:
        question = QUESTIONS[min(self.calls, len(QUESTIONS) - 1)]
        self.calls += 1
        return GeneratedQuestion(question=question, targeted_gap="scope")


class ClearingAssessor:
    """네 조건을 통과하는 점수를 반환한다."""

    async def assess(self, request: AssessmentRequest) -> ClarityAssessment:
        return ClarityAssessment(
            scores=(
                DimensionScore(
                    dimension="goal", clarity=0.9, justification="목표가 한 문장으로 정리됨"
                ),
                DimensionScore(
                    dimension="constraint", clarity=0.85, justification="권한 제약 확정"
                ),
                DimensionScore(
                    dimension="success_criteria", clarity=0.8, justification="확인 방법 합의"
                ),
            ),
            policy_version=POLICY.version,
        )


class ReadyClosureAssessor:
    """차단할 material 결정이 없다고 판정한다."""

    async def audit(self, request: CloserAuditRequest) -> CloserReport:
        return CloserReport(verdict=CloserVerdict.READY, reason="nothing material remains")


class CalmClosureChallenger:
    """요청받은 lane에서 LOW 심각도 finding만 낸다."""

    async def challenge(self, request: ClosureChallengeRequest) -> AdvisoryReport:
        return AdvisoryReport(
            lane=request.lane, severity=ClosureSeverity.LOW, finding="minor wording polish"
        )


def _service(root: Path) -> BriefService:
    return BriefService(
        repository=FileBriefRepository(root=root),
        question_generator=SequentialQuestionGenerator(),
        clarity_assessor=ClearingAssessor(),
        closure_assessor=ReadyClosureAssessor(),
        closure_challenger=CalmClosureChallenger(),
        policy=POLICY,
    )


async def _answer_the_minimum_rounds(service: BriefService) -> None:
    for answer in ("로그인 사용자만", "이번에는 작성과 조회만", "목록에 새 댓글이 보이면 완료"):
        await service.ask_next_question(mission_id="m-1")
        await service.record_answer(mission_id="m-1", answer=answer, authority="decision")
        await service.assess_clarity(mission_id="m-1")


async def test_brief_reaches_clear_after_answers_and_approval(tmp_path: Path) -> None:
    service = _service(tmp_path)
    await service.start(mission_id="m-1", initial_intent="기존 서비스에 댓글 기능을 추가하고 싶다")

    await _answer_the_minimum_rounds(service)
    # 최소 round 이전의 평가는 생략되므로 통과한 평가는 아직 한 번뿐이다.
    await service.assess_clarity(mission_id="m-1")
    await service.audit_closure(mission_id="m-1")
    state = await service.approve(mission_id="m-1", statement="이대로 진행해 주세요")

    decision = await service.decide_gate(mission_id="m-1")

    assert decision.outcome == "CLEAR"
    assert next_stage_after_brief(state=state, decision=decision) is Stage.BLUEPRINT


async def test_clear_needs_a_second_qualifying_assessment(tmp_path: Path) -> None:
    """단발성으로 통과한 평가 하나로는 진행하지 않는다 (B-028)."""
    service = _service(tmp_path)
    await service.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    await _answer_the_minimum_rounds(service)
    await service.approve(mission_id="m-1", statement="진행")

    decision = await service.decide_gate(mission_id="m-1")

    assert decision.outcome == "HOLD"
    assert any(
        blocker.condition.value == "stability_not_established"
        for blocker in decision.clarity_blockers
    )


async def test_interview_resumes_in_a_fresh_process(tmp_path: Path) -> None:
    """B-019 — 다른 인스턴스가 이어받아도 이전 rounds와 대기 질문을 잃지 않는다."""
    first = _service(tmp_path)
    await first.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    await first.ask_next_question(mission_id="m-1")
    await first.record_answer(mission_id="m-1", answer="로그인 사용자만", authority="decision")
    posed = await first.ask_next_question(mission_id="m-1")

    # 프로세스가 끊기고 새 인스턴스가 같은 디렉터리를 이어받는다.
    second = _service(tmp_path)
    resumed = await second.ask_next_question(mission_id="m-1")

    assert resumed.question == posed.question

    state = await second.record_answer(
        mission_id="m-1", answer="이번에는 작성과 조회만", authority="decision"
    )
    assert len(state.answered_rounds) == 2
    assert state.rounds[0].answer == "로그인 사용자만"


async def test_stored_assessment_survives_a_fresh_process(tmp_path: Path) -> None:
    """평가와 signal도 durable해야 재개한 세션이 처음부터 다시 쌓지 않는다."""
    first = _service(tmp_path)
    await first.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    await _answer_the_minimum_rounds(first)

    second = _service(tmp_path)
    state = await second.assess_clarity(mission_id="m-1")

    assert state.assessment is not None
    assert state.stability_signal == POLICY.required_stability


async def test_observation_never_becomes_a_requirement(tmp_path: Path) -> None:
    """코드에서 읽은 사실이 요구사항 도출 입력에 남지 않는다."""
    from mission_control.domain.brief.provenance import (
        WITHHELD_ANSWER_NOTE,
        observed_facts,
        project_requirement_input,
    )

    service = _service(tmp_path)
    await service.start(mission_id="m-1", initial_intent="재시도 정책을 정리하고 싶다")
    await service.ask_next_question(mission_id="m-1")
    await service.record_answer(
        mission_id="m-1", answer="3회, 2s/4s/8s 백오프", authority="observation"
    )
    await service.ask_next_question(mission_id="m-1")
    state = await service.record_answer(
        mission_id="m-1", answer="실패하면 사용자에게 알린다", authority="decision"
    )

    projected = project_requirement_input(state.rounds)
    facts = observed_facts(state.rounds)

    assert projected[0].answer == WITHHELD_ANSWER_NOTE
    assert projected[1].answer == "실패하면 사용자에게 알린다"
    assert facts[0].answer == "3회, 2s/4s/8s 백오프"


async def test_gate_holds_until_approval_is_current(tmp_path: Path) -> None:
    service = _service(tmp_path)
    await service.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    await _answer_the_minimum_rounds(service)
    await service.assess_clarity(mission_id="m-1")
    await service.audit_closure(mission_id="m-1")
    await service.approve(mission_id="m-1", statement="진행")
    assert (await service.decide_gate(mission_id="m-1")).outcome == "CLEAR"

    # 승인 후 답변이 하나 더 들어오면 그 승인으로는 진행할 수 없다.
    await service.ask_next_question(mission_id="m-1")
    await service.record_answer(
        mission_id="m-1", answer="비로그인 사용자는 조회만", authority="decision"
    )

    decision = await service.decide_gate(mission_id="m-1")

    assert decision.outcome == "HOLD"
    assert any("approval" in blocker.condition.value for blocker in decision.gate_blockers)
