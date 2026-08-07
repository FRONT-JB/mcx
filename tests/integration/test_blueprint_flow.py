"""Blueprint 흐름 — 생성부터 Execute 진입 Gate까지 파일 저장소로 닫는다.

CLEAR된 Brief에서 출발해 생성 → QA → 수정 → 재채점 → 승인 → Gate가 실제
저장소를 거쳐 이어지는지, 그리고 프로세스가 바뀌어도(저장소 재생성) 상태가
유지되는지 확인한다.

계약: docs/06_BLUEPRINT.md §8 / docs/adr/0021-blueprint-state-and-revisions.md
"""

from pathlib import Path

import pytest

from mission_control.adapters.persistence.file_blueprint_repository import (
    FileBlueprintRepository,
)
from mission_control.adapters.persistence.file_brief_repository import FileBriefRepository
from mission_control.application.blueprint_service import BlueprintService
from mission_control.application.ports import BlueprintGenerationRequest, QaRequest
from mission_control.domain.blueprint.assembly import BlueprintDraft
from mission_control.domain.blueprint.gate import next_stage_after_blueprint
from mission_control.domain.blueprint.qa import QaAssessment, QaFinding, QaPolicy
from mission_control.domain.blueprint.spec import AcceptanceCriterion
from mission_control.domain.blueprint.state import QaBudgetExhaustedError
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
from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    ConfirmationAuthority,
    RequirementSection,
)
from mission_control.domain.brief.state import BriefState
from mission_control.domain.stage import Stage

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()


class EchoGenerator:
    async def generate(self, request: BlueprintGenerationRequest) -> BlueprintDraft:
        return BlueprintDraft(
            goal=" / ".join(request.goals),
            constraints=request.constraints,
            non_goals=request.non_goals,
            acceptance_criteria=tuple(
                AcceptanceCriterion(description=item, verify_command="pytest")
                for item in request.success_criteria
            ),
        )


class ScriptedJudge:
    def __init__(self, *scores: float) -> None:
        self.scores = list(scores)
        self.calls = 0

    async def assess(self, request: QaRequest) -> QaAssessment:
        score = self.scores[min(self.calls, len(self.scores) - 1)]
        self.calls += 1
        return QaAssessment(
            score=score,
            findings=(
                QaFinding(detail="확인 방법이 느슨하다", suggestion="출력 조건을 명시"),
            ),
        )


def _cleared_brief() -> BriefState:
    state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    for question, answer in (
        ("댓글은 누가 쓸 수 있나요?", "로그인 사용자만"),
        ("완료 확인은?", "목록에 보이면 완료"),
        ("범위 밖은?", "수정·삭제는 제외"),
    ):
        state = state.record_answer(question=question, answer=answer, authority="decision")
    for section, text in (
        (RequirementSection.GOAL, "댓글을 쓰고 볼 수 있다"),
        (RequirementSection.CONSTRAINT, "로그인 사용자만 작성"),
        (RequirementSection.NON_GOAL, "수정·삭제는 이번 범위 아님"),
        (RequirementSection.ACCEPTANCE_CRITERION, "목록 맨 위에 새 댓글이 보인다"),
    ):
        state = state.record_candidate(
            section=section,
            text=text,
            content_source=CandidateContentSource.USER_STATED,
            resolution=CandidateResolution.CONFIRMED,
            confirmation_authority=ConfirmationAuthority.USER,
        )
    assessment = ClarityAssessment(
        scores=(
            DimensionScore(dimension="goal", clarity=0.9, justification="t"),
            DimensionScore(dimension="constraint", clarity=0.9, justification="t"),
            DimensionScore(dimension="success_criteria", clarity=0.9, justification="t"),
        ),
        policy_version=BRIEF_POLICY.version,
    )
    for _ in range(BRIEF_POLICY.required_stability):
        state = state.record_assessment(assessment=assessment, policy=BRIEF_POLICY)
    audit = ClosureAudit(
        closer=CloserReport(verdict=CloserVerdict.READY, reason="nothing material remains"),
        contrarian=AdvisoryReport(
            lane=AdvisoryLane.CONTRARIAN, severity=ClosureSeverity.LOW, finding="minor"
        ),
        gap_hunter=AdvisoryReport(
            lane=AdvisoryLane.GAP_HUNTER, severity=ClosureSeverity.LOW, finding="minor"
        ),
    )
    return state.record_closure_audit(audit=audit).approve(statement="이대로 진행")


def _service(root: Path, judge: ScriptedJudge) -> BlueprintService:
    return BlueprintService(
        briefs=FileBriefRepository(root=root),
        brief_policy=BRIEF_POLICY,
        repository=FileBlueprintRepository(root=root),
        generator=EchoGenerator(),
        qa_judge=judge,
        qa_policy=QA_POLICY,
    )


async def _store_cleared_brief(root: Path) -> None:
    await FileBriefRepository(root=root).save(_cleared_brief())


async def test_refine_approve_and_clear_for_execute(tmp_path: Path) -> None:
    await _store_cleared_brief(tmp_path)
    service = _service(tmp_path, ScriptedJudge(0.85, 0.92))

    generated = await service.generate(mission_id="m-1")
    first = await service.assess_qa(mission_id="m-1")
    assert first.loop(policy=QA_POLICY).is_open

    suggestion = first.qa_records[-1].assessment.findings[0].suggestion
    assert suggestion is not None
    revised = await service.revise(
        mission_id="m-1",
        draft=BlueprintDraft(
            goal=generated.current.goal,
            constraints=generated.current.constraints,
            non_goals=generated.current.non_goals,
            acceptance_criteria=(
                AcceptanceCriterion(
                    description="목록 맨 위에 새 댓글이 보인다",
                    verify_command="pytest tests/test_comments.py",
                    output_assertion="1 passed",
                ),
            ),
        ),
    )
    assert revised.revision == 2

    passed = await service.assess_qa(mission_id="m-1")
    assert passed.qa_records[-1].revision == 2

    approved = await service.approve(mission_id="m-1", statement="이대로 진행")
    decision = await service.decide_gate(mission_id="m-1")

    assert decision.outcome == "CLEAR"
    assert next_stage_after_blueprint(state=approved, decision=decision) is Stage.EXECUTE


async def test_the_flow_survives_a_fresh_process(tmp_path: Path) -> None:
    await _store_cleared_brief(tmp_path)
    first_process = _service(tmp_path, ScriptedJudge(0.92))
    await first_process.generate(mission_id="m-1")
    await first_process.assess_qa(mission_id="m-1")

    second_process = _service(tmp_path, ScriptedJudge(0.99))
    state = await second_process.approve(mission_id="m-1", statement="재시작 후 승인")
    assert state.approval is not None
    assert state.approval.qa_best_score == 0.92

    decision = await second_process.decide_gate(mission_id="m-1")
    assert decision.outcome == "CLEAR"


async def test_the_qa_budget_survives_a_fresh_process(tmp_path: Path) -> None:
    """재시작으로 반복 상한이 초기화되지 않는다 (ADR-0021 §4)."""
    await _store_cleared_brief(tmp_path)
    judge = ScriptedJudge(0.85)
    first_process = _service(tmp_path, judge)
    await first_process.generate(mission_id="m-1")
    for _ in range(QA_POLICY.max_iterations):
        await first_process.assess_qa(mission_id="m-1")

    second_process = _service(tmp_path, ScriptedJudge(0.85))
    with pytest.raises(QaBudgetExhaustedError):
        await second_process.assess_qa(mission_id="m-1")

    accepted = await second_process.approve(
        mission_id="m-1", statement="미달이지만 수락", accept_below_threshold=True
    )
    assert accepted.approval is not None
    assert accepted.approval.accepted_below_threshold is True
    assert accepted.approval.qa_iterations == QA_POLICY.max_iterations


async def test_a_brief_change_after_approval_holds_the_gate(tmp_path: Path) -> None:
    await _store_cleared_brief(tmp_path)
    service = _service(tmp_path, ScriptedJudge(0.92))
    await service.generate(mission_id="m-1")
    await service.assess_qa(mission_id="m-1")
    await service.approve(mission_id="m-1", statement="이대로 진행")

    briefs = FileBriefRepository(root=tmp_path)
    brief = await briefs.load("m-1")
    assert brief is not None
    await briefs.save(
        brief.record_answer(answer="새 결정", authority="decision", question="추가 질문?")
    )

    decision = await service.decide_gate(mission_id="m-1")
    assert decision.outcome == "HOLD"
