"""Recover use case의 조율 — 진입 근거, 교정 dispatch, 증거 전달.

계약: docs/09_RECOVER.md §5, §8 / docs/adr/0031
"""

import pytest

from mission_control.application.execute_service import ExecuteService
from mission_control.application.ports import ExecutionOutcome, ExecutionRequest
from mission_control.application.recover_service import (
    NoRetryableFailureError,
    NothingToRecoverError,
    RecoverService,
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
from mission_control.domain.checkpoint import Rollback
from mission_control.domain.execute.state import CapabilityEnvelope
from mission_control.domain.recover.gate import RecoverGateBlockingCondition
from mission_control.domain.recover.packet import FailureSource, RecoverPolicy
from mission_control.domain.verify.evidence import (
    VerificationEvidence,
    VerificationRun,
    VerifyState,
)
from mission_control.domain.verify.verdict import (
    CriterionVerdict,
    SemanticAssessment,
    SemanticPolicy,
)

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()
ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission", allowed_tools=("edit",))

COMMANDED = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")


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
        acceptance_criteria=(COMMANDED,),
    )
    state = BlueprintState.start(blueprint=blueprint)
    state = state.record_qa(assessment=QaAssessment(score=0.92), policy=QA_POLICY)
    return state.approve(statement="이대로 진행", policy=QA_POLICY)


class InMemoryRepository:
    def __init__(self) -> None:
        self.states: dict[str, object] = {}

    async def load(self, mission_id: str):
        return self.states.get(mission_id)

    async def save(self, state) -> None:
        self.states[state.mission_id] = state


class ScriptedRuntime:
    backend = "fake"

    def __init__(self, *outcomes: ExecutionOutcome) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[ExecutionRequest] = []

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.outcomes) - 1)
        return self.outcomes[index]


class RecordingRollback:
    """되돌리기 요청을 기록만 하는 대역 — git을 요구하지 않는다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def to_last_proven(self, workspace: str, *, mission_id: str) -> Rollback:
        self.calls.append((workspace, mission_id))
        return Rollback(reverted=True, commit="abc1234")


def _services(
    *outcomes: ExecutionOutcome,
    rollback: RecordingRollback | None = None,
) -> tuple[RecoverService, ExecuteService, InMemoryRepository, InMemoryRepository, ScriptedRuntime]:
    briefs = InMemoryRepository()
    briefs.states["m-1"] = _cleared_brief()
    blueprints = InMemoryRepository()
    blueprints.states["m-1"] = _approved_blueprint(briefs.states["m-1"].revision)
    executes = InMemoryRepository()
    verifies = InMemoryRepository()
    runtime = ScriptedRuntime(*(outcomes or (ExecutionOutcome(succeeded=True),)))
    execute_service = ExecuteService(
        briefs=briefs,
        blueprints=blueprints,
        repository=executes,
        runtime=runtime,
        envelope=ENVELOPE,
    )
    recover = RecoverService(
        briefs=briefs,
        blueprints=blueprints,
        executes=executes,
        verifies=verifies,
        execute=execute_service,
        semantic_policy=SemanticPolicy.verify_v1(),
        policy=RecoverPolicy.recover_v1(),
        rollback=rollback,
    )
    return recover, execute_service, executes, verifies, runtime


def _passing_verify_state(attempt_numbers: tuple[int, ...]) -> VerifyState:
    state = VerifyState.start(mission_id="m-1").record(
        VerificationEvidence(
            mission_id="m-1",
            blueprint_revision=1,
            execution_attempt_numbers=attempt_numbers,
            runs=(
                VerificationRun(
                    ac_key=COMMANDED.key, command="pytest -k list", exit_code=0, passed=True
                ),
            ),
        )
    )
    return state.record_verdicts(
        SemanticAssessment(
            blueprint_revision=1,
            policy_version=SemanticPolicy.verify_v1().version,
            verdicts=(
                CriterionVerdict(
                    ac_key=COMMANDED.key,
                    satisfied=True,
                    score=0.9,
                    uncertainty=0.1,
                    reward_hacking_risk=0.0,
                    reasoning="계약이 증거로 입증된다",
                ),
            ),
        )
    )


class TestEntry:
    async def test_a_completed_mission_has_nothing_to_recover(self) -> None:
        recover, execute_service, _, verifies, _ = _services(ExecutionOutcome(succeeded=True))
        await execute_service.dispatch_next(mission_id="m-1")
        verifies.states["m-1"] = _passing_verify_state((1,))

        with pytest.raises(NothingToRecoverError):
            await recover.plan(mission_id="m-1")


class TestCorrection:
    async def test_the_retry_carries_the_failure_evidence(self) -> None:
        """교정 요청에 실패 분류와 오류 발췌가 실린다 (ADR-0031 §5)."""
        recover, execute_service, _, _, runtime = _services(
            ExecutionOutcome(succeeded=False, error="tests exploded"),
            ExecutionOutcome(succeeded=True),
        )
        await execute_service.dispatch_next(mission_id="m-1")

        await recover.dispatch_correction(mission_id="m-1")

        correction = runtime.requests[-1]
        assert correction.previous_failure is not None
        assert correction.previous_failure.source is FailureSource.EXECUTION_FAILED
        assert correction.previous_failure.error_excerpt == "tests exploded"
        assert correction.previous_failure.change_approach is False

    async def test_the_last_budgeted_retry_asks_for_a_new_approach(self) -> None:
        recover, execute_service, _, _, runtime = _services(
            ExecutionOutcome(succeeded=False, error="first"),
            ExecutionOutcome(succeeded=False, error="second"),
            ExecutionOutcome(succeeded=True),
        )
        await execute_service.dispatch_next(mission_id="m-1")
        await recover.dispatch_correction(mission_id="m-1")  # 재시도 1
        await recover.dispatch_correction(mission_id="m-1")  # 재시도 2 — 마지막 예산

        final = runtime.requests[-1]
        assert final.previous_failure is not None
        assert final.previous_failure.change_approach is True

    async def test_an_exhausted_budget_refuses_further_corrections(self) -> None:
        recover, execute_service, _, _, _ = _services(
            ExecutionOutcome(succeeded=False, error="first"),
            ExecutionOutcome(succeeded=False, error="second"),
            ExecutionOutcome(succeeded=False, error="third"),
        )
        await execute_service.dispatch_next(mission_id="m-1")
        await recover.dispatch_correction(mission_id="m-1")
        await recover.dispatch_correction(mission_id="m-1")

        with pytest.raises(NoRetryableFailureError):
            await recover.dispatch_correction(mission_id="m-1")

        decision = await recover.decide_gate(mission_id="m-1")
        assert decision.outcome == "HOLD"
        assert RecoverGateBlockingCondition.RETRY_BUDGET_EXHAUSTED in tuple(
            blocker.condition for blocker in decision.gate_blockers
        )

    async def test_a_blocked_failure_is_not_retried(self) -> None:
        recover, execute_service, _, _, runtime = _services(
            ExecutionOutcome(succeeded=False, error="tool access denied by sandbox"),
        )
        await execute_service.dispatch_next(mission_id="m-1")

        with pytest.raises(NoRetryableFailureError):
            await recover.dispatch_correction(mission_id="m-1")
        assert len(runtime.requests) == 1  # 교정 실행이 일어나지 않았다

    async def test_a_successful_correction_clears_for_verify(self) -> None:
        recover, execute_service, _, _, _ = _services(
            ExecutionOutcome(succeeded=False, error="tests exploded"),
            ExecutionOutcome(succeeded=True),
        )
        await execute_service.dispatch_next(mission_id="m-1")
        await recover.dispatch_correction(mission_id="m-1")

        decision = await recover.decide_gate(mission_id="m-1")
        assert decision.outcome == "CLEAR"


class TestRewind:
    """되돌리기는 재투입보다 먼저다 (ADR-0047 §1)."""

    def test_nothing_happens_without_a_rollback(self) -> None:
        recover, _, _, _, _ = _services()

        assert recover.rewind(mission_id="m-1") is None

    def test_it_rewinds_where_the_execution_runs(self) -> None:
        rollback = RecordingRollback()
        recover, _, _, _, _ = _services(rollback=rollback)

        result = recover.rewind(mission_id="m-1")

        assert result is not None and result.reverted
        assert rollback.calls == [(ENVELOPE.workspace, "m-1")]

    def test_rewinding_does_not_dispatch(self) -> None:
        """되돌리기와 재투입은 별개 단계다 — 순서는 조율 계층이 정한다."""
        rollback = RecordingRollback()
        recover, _, _, _, runtime = _services(rollback=rollback)

        recover.rewind(mission_id="m-1")

        assert runtime.requests == []
