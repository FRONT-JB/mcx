"""Blueprint use case의 조율과 실패 처리.

계약: docs/06_BLUEPRINT.md §7, §8 / docs/adr/0021-blueprint-state-and-revisions.md
Test Matrix: Entry·Generation·Scope·Refinement·Approval·Persistence 행
(docs/06_BLUEPRINT.md §14)
"""

import pytest

from mission_control.application.blueprint_service import (
    BlueprintAlreadyExistsError,
    BlueprintNotFoundError,
    BlueprintService,
    QaAssessmentError,
    StaleBriefRevisionError,
)
from mission_control.application.brief_service import BriefNotFoundError
from mission_control.application.ports import BlueprintGenerationRequest, QaRequest
from mission_control.domain.blueprint.assembly import BlueprintDraft, BlueprintScopeError
from mission_control.domain.blueprint.gate import BlueprintGateBlockingCondition
from mission_control.domain.blueprint.qa import (
    QaAssessment,
    QaFinding,
    QaPolicy,
)
from mission_control.domain.blueprint.spec import AcceptanceCriterion
from mission_control.domain.blueprint.state import (
    BlueprintState,
    QaAlreadyPassedError,
    QaBudgetExhaustedError,
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
    ClosureAudit,
    ClosureSeverity,
)
from mission_control.domain.brief.handoff import HandoffNotClearedError
from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    ConfirmationAuthority,
    RequirementSection,
)
from mission_control.domain.brief.state import BriefState

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()


def _clarity() -> ClarityAssessment:
    return ClarityAssessment(
        scores=(
            DimensionScore(dimension="goal", clarity=0.9, justification="t"),
            DimensionScore(dimension="constraint", clarity=0.9, justification="t"),
            DimensionScore(dimension="success_criteria", clarity=0.9, justification="t"),
        ),
        policy_version=BRIEF_POLICY.version,
    )


def _ready_audit() -> ClosureAudit:
    return ClosureAudit(
        closer=CloserReport(verdict=CloserVerdict.READY, reason="nothing material remains"),
        contrarian=AdvisoryReport(
            lane=AdvisoryLane.CONTRARIAN, severity=ClosureSeverity.LOW, finding="minor"
        ),
        gap_hunter=AdvisoryReport(
            lane=AdvisoryLane.GAP_HUNTER, severity=ClosureSeverity.LOW, finding="minor"
        ),
    )


def _confirmed(state: BriefState, *, section: RequirementSection, text: str) -> BriefState:
    return state.record_candidate(
        section=section,
        text=text,
        content_source=CandidateContentSource.USER_STATED,
        resolution=CandidateResolution.CONFIRMED,
        confirmation_authority=ConfirmationAuthority.USER,
    )


def _reclear(state: BriefState) -> BriefState:
    """현재 내용 그대로 평가·감사·승인을 다시 채워 ``CLEAR``로 만든다."""
    for _ in range(BRIEF_POLICY.required_stability):
        state = state.record_assessment(assessment=_clarity(), policy=BRIEF_POLICY)
    return state.record_closure_audit(audit=_ready_audit()).approve(statement="진행 승인")


def _cleared_brief() -> BriefState:
    state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    state = state.record_answer(
        question="댓글은 누가 쓸 수 있나요?", answer="로그인 사용자만", authority="decision"
    )
    state = state.record_answer(
        question="완료 확인은?", answer="목록에 보이면 완료", authority="decision"
    )
    state = state.record_answer(
        question="범위 밖은?", answer="수정·삭제는 제외", authority="decision"
    )
    state = _confirmed(state, section=RequirementSection.GOAL, text="댓글을 쓰고 볼 수 있다")
    state = _confirmed(state, section=RequirementSection.CONSTRAINT, text="로그인 사용자만 작성")
    state = _confirmed(
        state, section=RequirementSection.NON_GOAL, text="수정·삭제는 이번 범위 아님"
    )
    state = _confirmed(
        state,
        section=RequirementSection.ACCEPTANCE_CRITERION,
        text="목록 맨 위에 새 댓글이 보인다",
    )
    return _reclear(state)


class InMemoryBriefRepository:
    def __init__(self) -> None:
        self.states: dict[str, BriefState] = {}

    async def load(self, mission_id: str) -> BriefState | None:
        return self.states.get(mission_id)

    async def save(self, state: BriefState) -> None:
        self.states[state.mission_id] = state


class InMemoryBlueprintRepository:
    """저장 성공과 실패를 제어할 수 있는 test double."""

    def __init__(self) -> None:
        self.states: dict[str, BlueprintState] = {}
        self.fail_next_save = False

    async def load(self, mission_id: str) -> BlueprintState | None:
        return self.states.get(mission_id)

    async def save(self, state: BlueprintState) -> None:
        if self.fail_next_save:
            self.fail_next_save = False
            raise OSError("disk is unavailable")
        self.states[state.mission_id] = state


class EchoGenerator:
    """경계를 그대로 옮기고 성공 조건을 확인 가능한 AC로 바꾸는 결정적 생성기."""

    def __init__(self) -> None:
        self.requests: list[BlueprintGenerationRequest] = []

    @property
    def call_count(self) -> int:
        return len(self.requests)

    async def generate(self, request: BlueprintGenerationRequest) -> BlueprintDraft:
        self.requests.append(request)
        return BlueprintDraft(
            goal=" / ".join(request.goals),
            constraints=request.constraints,
            non_goals=request.non_goals,
            acceptance_criteria=tuple(
                AcceptanceCriterion(description=item, verify_command="pytest")
                for item in request.success_criteria
            ),
        )


class RogueGenerator(EchoGenerator):
    """handoff에 없는 제약을 발명하는 생성기."""

    async def generate(self, request: BlueprintGenerationRequest) -> BlueprintDraft:
        draft = await super().generate(request)
        return BlueprintDraft(
            goal=draft.goal,
            constraints=(*draft.constraints, "발명된 제약"),
            non_goals=draft.non_goals,
            acceptance_criteria=draft.acceptance_criteria,
        )


class ScriptedJudge:
    """미리 정한 점수를 순서대로 반환하고 호출을 기록한다."""

    def __init__(self, *scores: float) -> None:
        self.scores = list(scores) or [0.92]
        self.requests: list[QaRequest] = []
        self.fail_next = False

    @property
    def call_count(self) -> int:
        return len(self.requests)

    async def assess(self, request: QaRequest) -> QaAssessment:
        self.requests.append(request)
        if self.fail_next:
            self.fail_next = False
            raise ValueError("judge returned unparseable output")
        index = min(len(self.requests) - 1, len(self.scores) - 1)
        return QaAssessment(
            score=self.scores[index],
            findings=(QaFinding(detail="기준이 모호하다", suggestion="관찰 조건을 명시"),),
        )


def _service(
    *,
    generator: EchoGenerator | None = None,
    judge: ScriptedJudge | None = None,
    with_brief: bool = True,
) -> tuple[BlueprintService, InMemoryBriefRepository, InMemoryBlueprintRepository]:
    briefs = InMemoryBriefRepository()
    if with_brief:
        briefs.states["m-1"] = _cleared_brief()
    blueprints = InMemoryBlueprintRepository()
    service = BlueprintService(
        briefs=briefs,
        brief_policy=BRIEF_POLICY,
        repository=blueprints,
        generator=generator or EchoGenerator(),
        qa_judge=judge or ScriptedJudge(),
        qa_policy=QA_POLICY,
    )
    return service, briefs, blueprints


def _revised_draft(state: BlueprintState) -> BlueprintDraft:
    current = state.current
    return BlueprintDraft(
        goal=current.goal,
        constraints=current.constraints,
        non_goals=current.non_goals,
        acceptance_criteria=(
            AcceptanceCriterion(
                description="목록 맨 위에 새 댓글이 보인다",
                verify_command="pytest tests/test_comments.py",
                output_assertion="1 passed",
            ),
        ),
    )


class TestGenerate:
    async def test_the_first_revision_is_built_from_the_handoff_and_stored(self) -> None:
        service, briefs, blueprints = _service()
        state = await service.generate(mission_id="m-1")

        assert state.revision == 1
        assert state.current.brief_revision == briefs.states["m-1"].revision
        assert state.current.goal == "댓글을 쓰고 볼 수 있다"
        assert state.current.non_goals == ("수정·삭제는 이번 범위 아님",)
        assert blueprints.states["m-1"] == state

    async def test_the_generator_receives_only_handoff_fields(self) -> None:
        generator = EchoGenerator()
        service, _, _ = _service(generator=generator)
        await service.generate(mission_id="m-1")

        request = generator.requests[0]
        assert request.goals == ("댓글을 쓰고 볼 수 있다",)
        assert request.constraints == ("로그인 사용자만 작성",)
        assert request.success_criteria == ("목록 맨 위에 새 댓글이 보인다",)

    async def test_generation_happens_exactly_once(self) -> None:
        generator = EchoGenerator()
        service, _, _ = _service(generator=generator)
        await service.generate(mission_id="m-1")

        with pytest.raises(BlueprintAlreadyExistsError):
            await service.generate(mission_id="m-1")
        assert generator.call_count == 1

    async def test_a_missing_brief_is_reported(self) -> None:
        service, _, _ = _service(with_brief=False)
        with pytest.raises(BriefNotFoundError):
            await service.generate(mission_id="m-1")

    async def test_an_uncleared_brief_blocks_generation_entirely(self) -> None:
        generator = EchoGenerator()
        service, briefs, blueprints = _service(generator=generator)
        briefs.states["m-1"] = briefs.states["m-1"].record_answer(
            answer="새 결정", authority="decision", question="추가 질문?"
        )

        with pytest.raises(HandoffNotClearedError):
            await service.generate(mission_id="m-1")
        assert generator.call_count == 0
        assert blueprints.states == {}

    async def test_an_out_of_scope_draft_is_rejected_and_not_stored(self) -> None:
        service, _, blueprints = _service(generator=RogueGenerator())
        with pytest.raises(BlueprintScopeError):
            await service.generate(mission_id="m-1")
        assert blueprints.states == {}

    async def test_a_failed_save_is_not_reported_as_success(self) -> None:
        service, _, blueprints = _service()
        blueprints.fail_next_save = True
        with pytest.raises(OSError):
            await service.generate(mission_id="m-1")
        assert blueprints.states == {}


class TestAssessQa:
    async def test_an_assessment_is_recorded_and_stored(self) -> None:
        judge = ScriptedJudge(0.85)
        service, _, blueprints = _service(judge=judge)
        await service.generate(mission_id="m-1")

        state = await service.assess_qa(mission_id="m-1")
        assert state.qa_records[0].revision == 1
        assert state.qa_records[0].assessment.score == 0.85
        assert blueprints.states["m-1"] == state

    async def test_the_judge_gets_the_bar_threshold_and_trajectory(self) -> None:
        """upstream QA 프롬프트 정렬 — threshold와 반복 궤적을 전달한다
        (ADR-0019 §3 개정, ADR-0035 §3). 반복 상한은 여전히 전달하지 않는다.
        """
        judge = ScriptedJudge(0.85, 0.87)
        service, _, _ = _service(judge=judge)
        await service.generate(mission_id="m-1")
        await service.assess_qa(mission_id="m-1")
        await service.assess_qa(mission_id="m-1")

        first, second = judge.requests
        assert first.quality_bar == QA_POLICY.quality_bar
        assert first.pass_threshold == QA_POLICY.pass_threshold
        assert first.previous_iterations == ()
        assert not hasattr(first, "max_iterations")
        assert [
            (item.iteration, item.score, item.verdict) for item in second.previous_iterations
        ] == [(1, 0.85, "revise")]

    async def test_previous_findings_are_carried_into_the_next_round(self) -> None:
        judge = ScriptedJudge(0.85, 0.87)
        service, _, _ = _service(judge=judge)
        await service.generate(mission_id="m-1")
        await service.assess_qa(mission_id="m-1")
        await service.assess_qa(mission_id="m-1")

        assert judge.requests[1].previous_findings[0].detail == "기준이 모호하다"

    async def test_a_judge_failure_changes_nothing_and_spends_no_budget(self) -> None:
        judge = ScriptedJudge(0.85)
        service, _, blueprints = _service(judge=judge)
        await service.generate(mission_id="m-1")
        judge.fail_next = True

        with pytest.raises(QaAssessmentError):
            await service.assess_qa(mission_id="m-1")
        assert blueprints.states["m-1"].qa_records == ()

    async def test_a_passed_revision_is_not_sent_back_to_the_judge(self) -> None:
        judge = ScriptedJudge(0.92)
        service, _, _ = _service(judge=judge)
        await service.generate(mission_id="m-1")
        await service.assess_qa(mission_id="m-1")

        with pytest.raises(QaAlreadyPassedError):
            await service.assess_qa(mission_id="m-1")
        assert judge.call_count == 1

    async def test_the_exhausted_budget_blocks_the_call_itself(self) -> None:
        judge = ScriptedJudge(0.85)
        service, _, _ = _service(judge=judge)
        await service.generate(mission_id="m-1")
        for _ in range(QA_POLICY.max_iterations):
            await service.assess_qa(mission_id="m-1")

        with pytest.raises(QaBudgetExhaustedError):
            await service.assess_qa(mission_id="m-1")
        assert judge.call_count == QA_POLICY.max_iterations


class TestRevise:
    async def test_an_adopted_edit_becomes_the_next_revision(self) -> None:
        service, _, blueprints = _service(judge=ScriptedJudge(0.85))
        state = await service.generate(mission_id="m-1")
        await service.assess_qa(mission_id="m-1")

        revised = await service.revise(mission_id="m-1", draft=_revised_draft(state))
        assert revised.revision == 2
        assert revised.revisions[0] == state.current
        assert blueprints.states["m-1"] == revised

    async def test_an_edit_cannot_leave_the_handoff_scope(self) -> None:
        service, _, _ = _service()
        state = await service.generate(mission_id="m-1")
        rogue = BlueprintDraft(
            goal=state.current.goal,
            constraints=(*state.current.constraints, "발명된 제약"),
            non_goals=state.current.non_goals,
            acceptance_criteria=state.current.acceptance_criteria,
        )

        with pytest.raises(BlueprintScopeError):
            await service.revise(mission_id="m-1", draft=rogue)

    async def test_a_moved_brief_blocks_revision(self) -> None:
        service, briefs, _ = _service()
        state = await service.generate(mission_id="m-1")

        moved = briefs.states["m-1"].record_answer(
            answer="새 결정", authority="decision", question="추가 질문?"
        )
        briefs.states["m-1"] = _reclear(moved)

        with pytest.raises(StaleBriefRevisionError):
            await service.revise(mission_id="m-1", draft=_revised_draft(state))

    async def test_an_uncleared_brief_blocks_revision(self) -> None:
        service, briefs, _ = _service()
        state = await service.generate(mission_id="m-1")
        briefs.states["m-1"] = briefs.states["m-1"].record_answer(
            answer="새 결정", authority="decision", question="추가 질문?"
        )

        with pytest.raises(HandoffNotClearedError):
            await service.revise(mission_id="m-1", draft=_revised_draft(state))


class TestApproveAndGate:
    async def test_a_passing_revision_is_approved_and_clears_for_execute(self) -> None:
        service, _, blueprints = _service(judge=ScriptedJudge(0.92))
        await service.generate(mission_id="m-1")
        await service.assess_qa(mission_id="m-1")
        state = await service.approve(mission_id="m-1", statement="이대로 진행")

        assert state.has_current_approval
        assert blueprints.states["m-1"] == state

        decision = await service.decide_gate(mission_id="m-1")
        assert decision.outcome == "CLEAR"

    async def test_below_threshold_acceptance_is_recorded_after_exhaustion(self) -> None:
        service, _, _ = _service(judge=ScriptedJudge(0.85))
        await service.generate(mission_id="m-1")
        for _ in range(QA_POLICY.max_iterations):
            await service.assess_qa(mission_id="m-1")

        state = await service.approve(
            mission_id="m-1", statement="미달이지만 수락", accept_below_threshold=True
        )
        assert state.approval is not None
        assert state.approval.accepted_below_threshold is True

        decision = await service.decide_gate(mission_id="m-1")
        assert decision.outcome == "CLEAR"

    async def test_the_gate_holds_without_an_approval(self) -> None:
        service, _, _ = _service()
        await service.generate(mission_id="m-1")

        decision = await service.decide_gate(mission_id="m-1")
        assert decision.outcome == "HOLD"
        assert decision.gate_blockers[0].condition is (
            BlueprintGateBlockingCondition.APPROVAL_MISSING
        )

    async def test_the_gate_holds_when_the_brief_moves_on(self) -> None:
        service, briefs, _ = _service(judge=ScriptedJudge(0.92))
        await service.generate(mission_id="m-1")
        await service.assess_qa(mission_id="m-1")
        await service.approve(mission_id="m-1", statement="이대로 진행")

        briefs.states["m-1"] = briefs.states["m-1"].record_answer(
            answer="새 결정", authority="decision", question="추가 질문?"
        )

        decision = await service.decide_gate(mission_id="m-1")
        assert decision.outcome == "HOLD"
        assert decision.gate_blockers[0].condition is (
            BlueprintGateBlockingCondition.BRIEF_REVISION_STALE
        )

    async def test_a_missing_blueprint_is_reported(self) -> None:
        service, _, _ = _service()
        with pytest.raises(BlueprintNotFoundError):
            await service.decide_gate(mission_id="m-1")
