"""Recover 흐름 — 실패 → 교정 → 재검증 → MISSION COMPLETE.

다섯 Stage 전부가 파일 저장소를 거쳐 이어지는 첫 테스트다. 검증 명령은
진짜 subprocess이고, 교정은 실패 증거를 받은 runtime이 워크스페이스를 실제로
고치는 것으로 재현된다.

계약: docs/09_RECOVER.md §5, §10 / docs/adr/0031
"""

from pathlib import Path

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
from mission_control.application.recover_service import RecoverService
from mission_control.application.verify_service import VerifyService
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
from mission_control.domain.recover.gate import RecoverGateBlockingCondition
from mission_control.domain.recover.packet import FailureSource, RecoverPolicy
from mission_control.domain.stage import Stage
from mission_control.domain.verify.verdict import CriterionVerdict, SemanticPolicy

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()

FIXABLE = AcceptanceCriterion(
    description="수정 파일이 검증을 통과한다",
    verify_command="cat fix.txt",
    output_assertion="fixed",
)


class FixingRuntime:
    """교정 요청(실패 증거 포함)을 받았을 때만 워크스페이스를 고치는 runtime."""

    backend = "fake"

    def __init__(self, workspace: Path, *, fixes: bool = True) -> None:
        self.workspace = workspace
        self.fixes = fixes
        self.requests: list[ExecutionRequest] = []

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        self.requests.append(request)
        if request.previous_failure is not None and self.fixes:
            (self.workspace / "fix.txt").write_text("fixed", encoding="utf-8")
        return ExecutionOutcome(succeeded=True, result_summary="구현 완료라고 주장")


class ApprovingEvaluator:
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


async def _store_approved_pipeline(root: Path) -> None:
    brief = _cleared_brief()
    await FileBriefRepository(root=root).save(brief)
    blueprint = Blueprint(
        mission_id="m-1",
        revision=1,
        brief_revision=brief.revision,
        goal="댓글 기능",
        acceptance_criteria=(FIXABLE,),
    )
    state = BlueprintState.start(blueprint=blueprint)
    state = state.record_qa(assessment=QaAssessment(score=0.92), policy=QA_POLICY)
    await FileBlueprintRepository(root=root).save(
        state.approve(statement="이대로 진행", policy=QA_POLICY)
    )


def _services(
    root: Path, runtime: FixingRuntime
) -> tuple[ExecuteService, VerifyService, RecoverService]:
    execute = ExecuteService(
        briefs=FileBriefRepository(root=root),
        blueprints=FileBlueprintRepository(root=root),
        repository=FileExecuteRepository(root=root),
        runtime=runtime,
        envelope=CapabilityEnvelope(workspace=str(runtime.workspace), allowed_tools=("edit",)),
    )
    verify = VerifyService(
        briefs=FileBriefRepository(root=root),
        blueprints=FileBlueprintRepository(root=root),
        executes=FileExecuteRepository(root=root),
        repository=FileVerifyRepository(root=root),
        runner=LocalMechanicalRunner(),
        outputs=FileVerificationOutputStore(root=root / "outputs"),
        evaluator=ApprovingEvaluator(),
        policy=SemanticPolicy.verify_v1(),
    )
    recover = RecoverService(
        briefs=FileBriefRepository(root=root),
        blueprints=FileBlueprintRepository(root=root),
        executes=FileExecuteRepository(root=root),
        verifies=FileVerifyRepository(root=root),
        execute=execute,
        semantic_policy=SemanticPolicy.verify_v1(),
        policy=RecoverPolicy.recover_v1(),
    )
    return execute, verify, recover


async def test_failure_correction_reverification_reaches_mission_complete(
    tmp_path: Path,
) -> None:
    """다섯 Stage의 전체 순환 — 실패한 검증이 교정과 재검증으로 완료에 닿는다."""
    store, workspace = tmp_path / "store", tmp_path / "workspace"
    workspace.mkdir()
    await _store_approved_pipeline(store)
    runtime = FixingRuntime(workspace)
    execute, verify, recover = _services(store, runtime)

    # Execute — 작업자는 성공을 주장하지만 fix.txt는 만들지 않았다.
    await execute.dispatch_next(mission_id="m-1")

    # Verify — 진짜 명령이 실패를 드러낸다.
    await verify.run_mechanical(mission_id="m-1")
    held = await verify.decide_gate(mission_id="m-1")
    assert held.outcome == "HOLD"

    # Recover — 실패 packet을 파생하고 증거를 실어 교정을 보낸다.
    packets = await recover.plan(mission_id="m-1")
    assert packets[0].source is FailureSource.MECHANICAL_FAILED
    await recover.dispatch_correction(mission_id="m-1")
    assert runtime.requests[-1].previous_failure is not None

    corrected = await recover.decide_gate(mission_id="m-1")
    assert corrected.outcome == "CLEAR"
    assert corrected.next_destination is Stage.VERIFY

    # 재검증 — 교정된 워크스페이스에서 명령이 통과하고 판정까지 완료.
    await verify.run_mechanical(mission_id="m-1")
    await verify.assess_semantics(mission_id="m-1")
    final = await verify.decide_gate(mission_id="m-1")
    assert final.mission_complete is True


async def test_a_correction_that_never_fixes_exhausts_the_budget(tmp_path: Path) -> None:
    store, workspace = tmp_path / "store", tmp_path / "workspace"
    workspace.mkdir()
    await _store_approved_pipeline(store)
    runtime = FixingRuntime(workspace, fixes=False)
    execute, verify, recover = _services(store, runtime)

    await execute.dispatch_next(mission_id="m-1")
    for _ in range(RecoverPolicy.recover_v1().retry_budget):
        await verify.run_mechanical(mission_id="m-1")
        await recover.dispatch_correction(mission_id="m-1")
    await verify.run_mechanical(mission_id="m-1")

    decision = await recover.decide_gate(mission_id="m-1")
    assert decision.outcome == "HOLD"
    assert RecoverGateBlockingCondition.RETRY_BUDGET_EXHAUSTED in tuple(
        blocker.condition for blocker in decision.gate_blockers
    )
