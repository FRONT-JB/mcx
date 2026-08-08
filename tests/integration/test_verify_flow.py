"""Verify 흐름 — 실행된 미션 위에서 진짜 명령이 돌고 증거가 남는다.

이 테스트의 verify_command는 fake가 아니다 — LocalMechanicalRunner가 실제
subprocess를 띄운다. Brief → Blueprint → Execute(결정적 fake)까지 이어진
미션에서, Verify가 명령을 직접 실행해 증거를 파일로 남기고, mechanical이
전부 통과해도 semantic 부재가 Gate에 드러나는지 확인한다.

계약: docs/08_VERIFY.md §8 / docs/adr/0026, 0028
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
from mission_control.adapters.persistence.file_verify_repository import (
    FileVerificationOutputStore,
    FileVerifyRepository,
)
from mission_control.adapters.verification.local_mechanical_runner import (
    LocalMechanicalRunner,
)
from mission_control.application.execute_service import ExecuteService
from mission_control.application.ports import (
    ExecutionOutcome,
    ExecutionRequest,
    SemanticEvaluationRequest,
)
from mission_control.application.verify_service import (
    ExecuteNotClearedError,
    VerifyService,
)
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
from mission_control.domain.execute.state import CapabilityEnvelope
from mission_control.domain.verify.gate import VerifyGateBlockingCondition
from mission_control.domain.verify.verdict import CriterionVerdict, SemanticPolicy

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()

ECHOING = AcceptanceCriterion(
    description="확인 출력이 남는다", verify_command="echo OK", output_assertion="OK"
)
REPORTING = AcceptanceCriterion(description="보고서가 남는다", expected_artifacts=("report.md",))
FAILING = AcceptanceCriterion(description="깨진 검사", verify_command="exit 3")


class ScriptedRuntime:
    backend = "fake"

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        return ExecutionOutcome(succeeded=True, result_summary="구현 완료라고 주장")


class ApprovingEvaluator:
    """모든 AC를 확신 있게 만족으로 판정하는 결정적 평가자."""

    async def assess(self, request: SemanticEvaluationRequest) -> CriterionVerdict:
        return CriterionVerdict(
            ac_key=request.criterion.key,
            satisfied=True,
            score=0.9,
            uncertainty=0.1,
            reward_hacking_risk=0.0,
            reasoning="계약이 증거로 입증된다",
        )


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


async def _store_approved_pipeline(root: Path, criteria: tuple[AcceptanceCriterion, ...]) -> None:
    brief = _cleared_brief()
    await FileBriefRepository(root=root).save(brief)

    blueprint = Blueprint(
        mission_id="m-1",
        revision=1,
        brief_revision=brief.revision,
        goal="댓글 기능",
        acceptance_criteria=criteria,
    )
    state = BlueprintState.start(blueprint=blueprint)
    state = state.record_qa(assessment=QaAssessment(score=0.92), policy=QA_POLICY)
    await FileBlueprintRepository(root=root).save(
        state.approve(statement="이대로 진행", policy=QA_POLICY)
    )


async def _execute_all(root: Path, workspace: Path, count: int) -> None:
    service = ExecuteService(
        briefs=FileBriefRepository(root=root),
        blueprints=FileBlueprintRepository(root=root),
        repository=FileExecuteRepository(root=root),
        runtime=ScriptedRuntime(),
        envelope=CapabilityEnvelope(workspace=str(workspace), allowed_tools=("edit",)),
    )
    for _ in range(count):
        await service.dispatch_next(mission_id="m-1")


def _verify_service(root: Path) -> VerifyService:
    return VerifyService(
        briefs=FileBriefRepository(root=root),
        blueprints=FileBlueprintRepository(root=root),
        executes=FileExecuteRepository(root=root),
        repository=FileVerifyRepository(root=root),
        runner=LocalMechanicalRunner(),
        outputs=FileVerificationOutputStore(root=root / "outputs"),
        evaluator=ApprovingEvaluator(),
        policy=SemanticPolicy.verify_v1(),
    )


async def test_both_layers_reach_mission_complete(tmp_path: Path) -> None:
    """실제 명령 실행 → 증거 → semantic 판정 → 첫 MISSION COMPLETE."""
    store, workspace = tmp_path / "store", tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report.md").write_text("done", encoding="utf-8")
    await _store_approved_pipeline(store, (ECHOING, REPORTING))
    await _execute_all(store, workspace, count=2)

    state = await _verify_service(store).run_mechanical(mission_id="m-1")

    assert state.evidence is not None
    echo_run = state.evidence.run_for(ECHOING.key)
    assert echo_run is not None
    assert echo_run.passed is True
    assert echo_run.exit_code == 0
    assert echo_run.output_ref is not None
    assert "OK" in Path(echo_run.output_ref).read_text(encoding="utf-8")

    # mechanical만으로는 CLEAR가 아니다 — verdict 부재가 AC마다 드러난다.
    held = await _verify_service(store).decide_gate(mission_id="m-1")
    assert held.outcome == "HOLD"
    assert tuple(blocker.condition for blocker in held.gate_blockers) == (
        VerifyGateBlockingCondition.SEMANTIC_VERDICT_MISSING,
        VerifyGateBlockingCondition.SEMANTIC_VERDICT_MISSING,
    )

    await _verify_service(store).assess_semantics(mission_id="m-1")
    decision = await _verify_service(store).decide_gate(mission_id="m-1")
    assert decision.outcome == "CLEAR"
    assert decision.mission_complete is True


async def test_a_worker_claim_fails_against_the_real_command(tmp_path: Path) -> None:
    """Execute가 성공을 주장해도 깨진 검사는 Gate에서 드러난다."""
    store, workspace = tmp_path / "store", tmp_path / "workspace"
    workspace.mkdir()
    await _store_approved_pipeline(store, (FAILING,))
    await _execute_all(store, workspace, count=1)

    service = _verify_service(store)
    await service.run_mechanical(mission_id="m-1")
    decision = await service.decide_gate(mission_id="m-1")

    conditions = tuple(blocker.condition for blocker in decision.gate_blockers)
    assert VerifyGateBlockingCondition.VERIFICATION_FAILED in conditions
    assert any("status 3" in reason for reason in decision.blocking_reasons)


async def test_verification_needs_the_execution_to_be_complete(tmp_path: Path) -> None:
    store, workspace = tmp_path / "store", tmp_path / "workspace"
    workspace.mkdir()
    await _store_approved_pipeline(store, (ECHOING, REPORTING))
    await _execute_all(store, workspace, count=1)  # 둘 중 하나만 실행

    with pytest.raises(ExecuteNotClearedError):
        await _verify_service(store).run_mechanical(mission_id="m-1")


async def test_evidence_and_verdicts_survive_a_fresh_process(tmp_path: Path) -> None:
    store, workspace = tmp_path / "store", tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report.md").write_text("done", encoding="utf-8")
    await _store_approved_pipeline(store, (ECHOING, REPORTING))
    await _execute_all(store, workspace, count=2)
    await _verify_service(store).run_mechanical(mission_id="m-1")
    await _verify_service(store).assess_semantics(mission_id="m-1")

    second_process = _verify_service(store)
    decision = await second_process.decide_gate(mission_id="m-1")

    assert decision.mission_complete is True
