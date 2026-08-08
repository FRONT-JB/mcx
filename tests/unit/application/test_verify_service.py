"""Verify use case의 조율 — 진입 재확인, 계약 기반 실행, 증거 기록.

계약: docs/08_VERIFY.md §3, §5.1 / docs/adr/0026, 0028
Test Matrix: Entry·Mechanical·Evidence 행 (docs/08_VERIFY.md §12)
"""

import pytest

from mission_control.application.blueprint_service import BlueprintNotFoundError
from mission_control.application.execute_service import BlueprintNotClearedError
from mission_control.application.ports import SemanticEvaluationRequest
from mission_control.application.verify_service import (
    ExecuteNotClearedError,
    VerdictMismatchError,
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
from mission_control.domain.execute.state import CapabilityEnvelope, ExecuteState
from mission_control.domain.verify.evidence import (
    CommandExecution,
    VerdictWithoutEvidenceError,
    VerifyState,
)
from mission_control.domain.verify.gate import VerifyGateBlockingCondition
from mission_control.domain.verify.verdict import CriterionVerdict, SemanticPolicy

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()
ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission", allowed_tools=("edit",))

COMMANDED = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")
ARTIFACTS_ONLY = AcceptanceCriterion(
    description="보고서가 남는다", expected_artifacts=("report.md",)
)
PROSE = AcceptanceCriterion(description="코드가 읽기 좋다")

CRITERIA = (COMMANDED, ARTIFACTS_ONLY, PROSE)


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


def _approved_blueprint(brief_revision: int) -> BlueprintState:
    blueprint = Blueprint(
        mission_id="m-1",
        revision=1,
        brief_revision=brief_revision,
        goal="댓글 기능",
        acceptance_criteria=CRITERIA,
    )
    state = BlueprintState.start(blueprint=blueprint)
    state = state.record_qa(assessment=QaAssessment(score=0.92), policy=QA_POLICY)
    return state.approve(statement="이대로 진행", policy=QA_POLICY)


def _executed_state(*ac_keys: str) -> ExecuteState:
    state = ExecuteState.start(mission_id="m-1")
    for index, key in enumerate(ac_keys):
        state = state.dispatch(
            execution_id=f"exec-m-1-{index + 1:04d}",
            runtime_backend="fake",
            blueprint_revision=1,
            ac_key=key,
            envelope=ENVELOPE,
        ).record_result(succeeded=True, result_summary="완료했다고 주장")
    return state


class InMemoryBriefRepository:
    def __init__(self) -> None:
        self.states: dict[str, BriefState] = {}

    async def load(self, mission_id: str) -> BriefState | None:
        return self.states.get(mission_id)

    async def save(self, state: BriefState) -> None:
        self.states[state.mission_id] = state


class InMemoryBlueprintRepository:
    def __init__(self) -> None:
        self.states: dict[str, BlueprintState] = {}

    async def load(self, mission_id: str) -> BlueprintState | None:
        return self.states.get(mission_id)

    async def save(self, state: BlueprintState) -> None:
        self.states[state.mission_id] = state


class InMemoryExecuteRepository:
    def __init__(self) -> None:
        self.states: dict[str, ExecuteState] = {}

    async def load(self, mission_id: str) -> ExecuteState | None:
        return self.states.get(mission_id)

    async def save(self, state: ExecuteState) -> None:
        self.states[state.mission_id] = state


class InMemoryVerifyRepository:
    def __init__(self) -> None:
        self.states: dict[str, VerifyState] = {}

    async def load(self, mission_id: str) -> VerifyState | None:
        return self.states.get(mission_id)

    async def save(self, state: VerifyState) -> None:
        self.states[state.mission_id] = state


class ScriptedRunner:
    """명령별로 정해진 결과를 돌려주고 호출을 기록하는 runner."""

    def __init__(
        self,
        *,
        executions: dict[str, CommandExecution] | None = None,
        missing: tuple[str, ...] = (),
    ) -> None:
        self.executions = executions or {}
        self.missing = missing
        self.ran_commands: list[str] = []
        self.artifact_checks: list[tuple[str, ...]] = []

    async def missing_artifacts(
        self, *, workspace: str, artifacts: tuple[str, ...]
    ) -> tuple[str, ...]:
        self.artifact_checks.append(artifacts)
        return tuple(item for item in artifacts if item in self.missing)

    async def run(self, *, command: str, workspace: str, timeout_seconds: int) -> CommandExecution:
        self.ran_commands.append(command)
        return self.executions.get(command, CommandExecution(exit_code=0, output="ok"))


class RecordingOutputStore:
    def __init__(self) -> None:
        self.preserved: list[tuple[str, int, str, str]] = []

    async def preserve(self, *, mission_id: str, sequence: int, ac_key: str, content: str) -> str:
        self.preserved.append((mission_id, sequence, ac_key, content))
        return f"ref-{ac_key}-{sequence}"


class ScriptedEvaluator:
    """AC별로 정해진 verdict를 돌려주고 요청을 기록하는 평가자."""

    def __init__(self, *, overrides: dict[str, CriterionVerdict] | None = None) -> None:
        self.overrides = overrides or {}
        self.requests: list[SemanticEvaluationRequest] = []

    async def assess(self, request: SemanticEvaluationRequest) -> CriterionVerdict:
        self.requests.append(request)
        key = request.criterion.key
        return self.overrides.get(
            key,
            CriterionVerdict(
                ac_key=key,
                satisfied=True,
                score=0.9,
                uncertainty=0.1,
                reward_hacking_risk=0.0,
                reasoning="계약이 증거로 입증된다",
            ),
        )


def _service(
    *,
    runner: ScriptedRunner | None = None,
    evaluator: ScriptedEvaluator | None = None,
    executed: ExecuteState | None = None,
    with_blueprint: bool = True,
) -> tuple[
    VerifyService,
    InMemoryBriefRepository,
    InMemoryVerifyRepository,
    ScriptedRunner,
    ScriptedEvaluator,
]:
    briefs = InMemoryBriefRepository()
    briefs.states["m-1"] = _cleared_brief()
    blueprints = InMemoryBlueprintRepository()
    if with_blueprint:
        blueprints.states["m-1"] = _approved_blueprint(briefs.states["m-1"].revision)
    executes = InMemoryExecuteRepository()
    executes.states["m-1"] = (
        executed
        if executed is not None
        else _executed_state(COMMANDED.key, ARTIFACTS_ONLY.key, PROSE.key)
    )
    verifies = InMemoryVerifyRepository()
    the_runner = runner if runner is not None else ScriptedRunner()
    the_evaluator = evaluator if evaluator is not None else ScriptedEvaluator()
    service = VerifyService(
        briefs=briefs,
        blueprints=blueprints,
        executes=executes,
        repository=verifies,
        runner=the_runner,
        outputs=RecordingOutputStore(),
        evaluator=the_evaluator,
        policy=SemanticPolicy.verify_v1(),
    )
    return service, briefs, verifies, the_runner, the_evaluator


class TestEntry:
    async def test_a_missing_blueprint_is_reported(self) -> None:
        service, _, _, runner, _ = _service(with_blueprint=False)
        with pytest.raises(BlueprintNotFoundError):
            await service.run_mechanical(mission_id="m-1")
        assert runner.ran_commands == []

    async def test_a_moved_brief_blocks_verification(self) -> None:
        service, briefs, _, runner, _ = _service()
        briefs.states["m-1"] = briefs.states["m-1"].record_answer(
            answer="새 결정", authority="decision", question="추가 질문?"
        )
        with pytest.raises(BlueprintNotClearedError):
            await service.run_mechanical(mission_id="m-1")
        assert runner.ran_commands == []

    async def test_unexecuted_work_blocks_verification(self) -> None:
        """실행 기록 없는 작업은 검증에 도달하지 못한다 (ADR-0026 §1)."""
        service, _, _, runner, _ = _service(executed=_executed_state(COMMANDED.key))
        with pytest.raises(ExecuteNotClearedError):
            await service.run_mechanical(mission_id="m-1")
        assert runner.ran_commands == []

    async def test_the_gate_rechecks_the_entry(self) -> None:
        service, briefs, _, _, _ = _service()
        await service.run_mechanical(mission_id="m-1")
        briefs.states["m-1"] = briefs.states["m-1"].record_answer(
            answer="새 결정", authority="decision", question="추가 질문?"
        )
        with pytest.raises(BlueprintNotClearedError):
            await service.decide_gate(mission_id="m-1")


class TestRunMechanical:
    async def test_only_contract_criteria_produce_runs(self) -> None:
        service, _, verifies, runner, _ = _service()
        state = await service.run_mechanical(mission_id="m-1")

        assert state.evidence is not None
        assert {run.ac_key for run in state.evidence.runs} == {
            COMMANDED.key,
            ARTIFACTS_ONLY.key,
        }
        assert runner.ran_commands == ["pytest -k list"]
        assert verifies.states["m-1"] == state

    async def test_missing_artifacts_skip_the_command(self) -> None:
        """artifacts 검사가 명령 실행보다 먼저다 (ADR-0028 §3)."""
        runner = ScriptedRunner(missing=("report.md",))
        service, _, _, _, _ = _service(runner=runner)
        state = await service.run_mechanical(mission_id="m-1")

        assert state.evidence is not None
        run = state.evidence.run_for(ARTIFACTS_ONLY.key)
        assert run is not None
        assert run.passed is False
        assert run.missing_artifacts == ("report.md",)

    async def test_the_output_is_preserved_with_a_reference(self) -> None:
        service, _, _, _, _ = _service()
        state = await service.run_mechanical(mission_id="m-1")

        assert state.evidence is not None
        run = state.evidence.run_for(COMMANDED.key)
        assert run is not None
        assert run.output_ref == f"ref-{COMMANDED.key}-1"

    async def test_evidence_carries_the_execution_lineage(self) -> None:
        service, _, _, _, _ = _service()
        state = await service.run_mechanical(mission_id="m-1")

        assert state.evidence is not None
        assert state.evidence.execution_attempt_numbers == (1, 2, 3)
        assert state.evidence.blueprint_revision == 1


class TestAssessSemantics:
    async def test_semantic_needs_the_mechanical_evidence_first(self) -> None:
        """증거 없는 판정은 도메인이 거부한다 (ADR-0030 §4)."""
        service, _, _, _, _ = _service()
        with pytest.raises(VerdictWithoutEvidenceError):
            await service.assess_semantics(mission_id="m-1")

    async def test_every_criterion_is_judged_with_its_mechanical_run(self) -> None:
        service, _, _, _, evaluator = _service()
        await service.run_mechanical(mission_id="m-1")
        state = await service.assess_semantics(mission_id="m-1")

        assert state.verdicts is not None
        assert {verdict.ac_key for verdict in state.verdicts.verdicts} == {
            COMMANDED.key,
            ARTIFACTS_ONLY.key,
            PROSE.key,
        }
        by_key = {req.criterion.key: req for req in evaluator.requests}
        assert by_key[COMMANDED.key].mechanical_run is not None
        assert by_key[PROSE.key].mechanical_run is None

    async def test_a_mislabeled_verdict_is_rejected(self) -> None:
        """평가자가 다른 AC의 verdict를 돌려주면 기록되지 않는다."""
        wrong = CriterionVerdict(
            ac_key="ac_0000000000000000",
            satisfied=True,
            score=0.9,
            uncertainty=0.1,
            reward_hacking_risk=0.0,
            reasoning="엉뚱한 판정",
        )
        service, _, verifies, _, _ = _service(
            evaluator=ScriptedEvaluator(overrides={COMMANDED.key: wrong})
        )
        await service.run_mechanical(mission_id="m-1")
        with pytest.raises(VerdictMismatchError):
            await service.assess_semantics(mission_id="m-1")
        assert verifies.states["m-1"].verdicts is None

    async def test_both_layers_passing_reach_mission_complete(self) -> None:
        """v1이 처음으로 도달하는 CLEAR — MISSION COMPLETE (ADR-0030 §4)."""
        service, _, _, _, _ = _service()
        await service.run_mechanical(mission_id="m-1")
        await service.assess_semantics(mission_id="m-1")

        decision = await service.decide_gate(mission_id="m-1")
        assert decision.outcome == "CLEAR"
        assert decision.mission_complete is True


class TestNoSelfApproval:
    async def test_a_worker_claim_does_not_survive_a_failing_command(self) -> None:
        """실행 attempt가 성공을 주장해도 판정은 직접 실행이 한다 (ADR-0028 §1)."""
        runner = ScriptedRunner(
            executions={"pytest -k list": CommandExecution(exit_code=1, output="1 failed")}
        )
        service, _, _, _, _ = _service(runner=runner)
        await service.run_mechanical(mission_id="m-1")

        decision = await service.decide_gate(mission_id="m-1")
        assert decision.outcome == "HOLD"
        assert VerifyGateBlockingCondition.VERIFICATION_FAILED in tuple(
            blocker.condition for blocker in decision.gate_blockers
        )
