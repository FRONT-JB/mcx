"""Execute 흐름 — 승인된 Blueprint에서 Clear for Verify까지 파일 저장소로 닫는다.

Brief CLEAR → Blueprint 승인 → 순차 실행 → 실패·재시도 → Gate가 실제
저장소를 거쳐 이어지는지, 프로세스가 바뀌어도 attempt 이력이 유지되는지
확인한다.

계약: docs/07_EXECUTE.md §8 / docs/adr/0023, 0024
"""

from pathlib import Path

import pytest

from mission_control.adapters.persistence.file_blueprint_repository import (
    FileBlueprintRepository,
)
from mission_control.adapters.persistence.file_brief_repository import FileBriefRepository
from mission_control.adapters.persistence.file_execute_repository import (
    FileExecuteRepository,
)
from mission_control.application.execute_service import (
    BlueprintNotClearedError,
    ExecuteService,
)
from mission_control.application.ports import ExecutionOutcome, ExecutionRequest
from mission_control.domain.blueprint.qa import QaAssessment, QaPolicy
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import BlueprintState
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
from mission_control.domain.brief.state import BriefState
from mission_control.domain.execute.state import AttemptStatus, CapabilityEnvelope
from mission_control.domain.stage import Stage

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()
ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission", allowed_tools=("edit", "bash"))

FIRST = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")
SECOND = AcceptanceCriterion(description="빈 댓글이 거부된다", verify_command="pytest -k empty")


class ScriptedRuntime:
    backend = "fake"

    def __init__(self, *outcomes: ExecutionOutcome) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        return outcome


def _cleared_brief() -> BriefState:
    state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    state = state.record_answer(
        question="누가 쓰나요?", answer="로그인 사용자", authority="decision"
    )
    state = state.record_answer(
        question="완료 확인은?", answer="목록에 보이면", authority="decision"
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


async def _store_approved_pipeline(root: Path) -> None:
    brief = _cleared_brief()
    await FileBriefRepository(root=root).save(brief)

    blueprint = Blueprint(
        mission_id="m-1",
        revision=1,
        brief_revision=brief.revision,
        goal="댓글 기능",
        constraints=("로그인 사용자만",),
        non_goals=("수정·삭제 제외",),
        acceptance_criteria=(FIRST, SECOND),
    )
    state = BlueprintState.start(blueprint=blueprint)
    state = state.record_qa(assessment=QaAssessment(score=0.92), policy=QA_POLICY)
    await FileBlueprintRepository(root=root).save(
        state.approve(statement="이대로 진행", policy=QA_POLICY)
    )


def _service(root: Path, runtime: ScriptedRuntime) -> ExecuteService:
    return ExecuteService(
        briefs=FileBriefRepository(root=root),
        blueprints=FileBlueprintRepository(root=root),
        repository=FileExecuteRepository(root=root),
        runtime=runtime,
        envelope=ENVELOPE,
    )


async def test_sequential_execution_clears_for_verify(tmp_path: Path) -> None:
    await _store_approved_pipeline(tmp_path)
    service = _service(tmp_path, ScriptedRuntime(ExecutionOutcome(succeeded=True)))

    await service.dispatch_next(mission_id="m-1")
    state = await service.dispatch_next(mission_id="m-1")

    assert [item.ac_key for item in state.attempts] == [FIRST.key, SECOND.key]
    decision = await service.decide_gate(mission_id="m-1")
    assert decision.outcome == "CLEAR"
    assert decision.next_destination is Stage.VERIFY


async def test_a_failure_holds_then_a_retry_recovers(tmp_path: Path) -> None:
    await _store_approved_pipeline(tmp_path)
    service = _service(
        tmp_path,
        ScriptedRuntime(
            ExecutionOutcome(succeeded=False, error="tests exploded"),
            ExecutionOutcome(succeeded=True),
        ),
    )

    await service.dispatch_next(mission_id="m-1")
    held = await service.decide_gate(mission_id="m-1")
    assert held.outcome == "HOLD"

    await service.dispatch_next(mission_id="m-1")  # 같은 AC 재시도
    await service.dispatch_next(mission_id="m-1")  # 다음 AC

    cleared = await service.decide_gate(mission_id="m-1")
    assert cleared.outcome == "CLEAR"


async def test_attempt_history_survives_a_fresh_process(tmp_path: Path) -> None:
    await _store_approved_pipeline(tmp_path)
    first_process = _service(tmp_path, ScriptedRuntime(ExecutionOutcome(succeeded=True)))
    await first_process.dispatch_next(mission_id="m-1")

    second_process = _service(tmp_path, ScriptedRuntime(ExecutionOutcome(succeeded=True)))
    state = await second_process.dispatch_next(mission_id="m-1")

    assert [item.ac_key for item in state.attempts] == [FIRST.key, SECOND.key]
    assert all(item.status is AttemptStatus.EXECUTED_UNVERIFIED for item in state.attempts)


async def test_a_brief_change_blocks_execution_and_the_gate(tmp_path: Path) -> None:
    await _store_approved_pipeline(tmp_path)
    service = _service(tmp_path, ScriptedRuntime(ExecutionOutcome(succeeded=True)))
    await service.dispatch_next(mission_id="m-1")

    briefs = FileBriefRepository(root=tmp_path)
    brief = await briefs.load("m-1")
    assert brief is not None
    await briefs.save(
        brief.record_answer(answer="새 결정", authority="decision", question="추가 질문?")
    )

    with pytest.raises(BlueprintNotClearedError):
        await service.dispatch_next(mission_id="m-1")
    with pytest.raises(BlueprintNotClearedError):
        await service.decide_gate(mission_id="m-1")
