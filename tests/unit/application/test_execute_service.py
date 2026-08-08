"""Execute use case의 조율 — 진입 확인, 지속 우선 dispatch, 결과 기록.

계약: docs/07_EXECUTE.md §8 / docs/adr/0023, 0024
Test Matrix: Entry·Dispatch·Runtime·Sequence·Attempt·Telemetry 행
(docs/07_EXECUTE.md §13)
"""

import pytest

from mission_control.application.blueprint_service import BlueprintNotFoundError
from mission_control.application.brief_service import BriefNotFoundError
from mission_control.application.execute_service import (
    AllCriteriaExecutedError,
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
from mission_control.domain.execute.state import (
    AttemptStatus,
    CapabilityEnvelope,
    ExecuteState,
)

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()
ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission", allowed_tools=("edit", "bash"))

FIRST = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")
SECOND = AcceptanceCriterion(description="빈 댓글이 거부된다", verify_command="pytest -k empty")


def _cleared_brief() -> BriefState:
    state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    state = state.record_answer(
        question="누가 쓰나요?", answer="로그인 사용자", authority="decision"
    )
    state = state.record_answer(
        question="완료 확인은?", answer="목록에 보이면", authority="decision"
    )
    state = state.record_answer(
        question="범위 밖은?", answer="수정·삭제 제외", authority="decision"
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
        constraints=("로그인 사용자만",),
        non_goals=("수정·삭제 제외",),
        acceptance_criteria=(FIRST, SECOND),
    )
    state = BlueprintState.start(blueprint=blueprint)
    state = state.record_qa(assessment=QaAssessment(score=0.92), policy=QA_POLICY)
    return state.approve(statement="이대로 진행", policy=QA_POLICY)


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


class ScriptedRuntime:
    """미리 정한 결과를 순서대로 반환하고, 호출 시점의 저장 상태를 관찰한다."""

    backend = "fake"

    def __init__(self, *outcomes: ExecutionOutcome) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[ExecutionRequest] = []
        self.observed_open_at_call: list[bool] = []
        self.repository: InMemoryExecuteRepository | None = None
        self.raise_next: Exception | None = None

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        self.requests.append(request)
        if self.repository is not None:
            stored = self.repository.states.get("m-1")
            self.observed_open_at_call.append(
                stored is not None and stored.open_attempt is not None
            )
        if self.raise_next is not None:
            error, self.raise_next = self.raise_next, None
            raise error
        index = min(len(self.requests) - 1, len(self.outcomes) - 1)
        return self.outcomes[index]


def _service(
    *outcomes: ExecutionOutcome, with_blueprint: bool = True
) -> tuple[
    ExecuteService,
    InMemoryBriefRepository,
    InMemoryBlueprintRepository,
    InMemoryExecuteRepository,
    ScriptedRuntime,
]:
    briefs = InMemoryBriefRepository()
    briefs.states["m-1"] = _cleared_brief()
    blueprints = InMemoryBlueprintRepository()
    if with_blueprint:
        blueprints.states["m-1"] = _approved_blueprint(briefs.states["m-1"].revision)
    executes = InMemoryExecuteRepository()
    runtime = ScriptedRuntime(
        *(outcomes or (ExecutionOutcome(succeeded=True, result_summary="구현 완료"),))
    )
    runtime.repository = executes
    service = ExecuteService(
        briefs=briefs,
        blueprints=blueprints,
        repository=executes,
        runtime=runtime,
        envelope=ENVELOPE,
    )
    return service, briefs, blueprints, executes, runtime


class TestEntry:
    async def test_a_missing_blueprint_is_reported(self) -> None:
        service, _, _, _, _ = _service(with_blueprint=False)
        with pytest.raises(BlueprintNotFoundError):
            await service.dispatch_next(mission_id="m-1")

    async def test_a_missing_brief_is_reported(self) -> None:
        service, briefs, _, _, _ = _service()
        del briefs.states["m-1"]
        with pytest.raises(BriefNotFoundError):
            await service.dispatch_next(mission_id="m-1")

    async def test_an_unapproved_blueprint_blocks_execution_entirely(self) -> None:
        service, briefs, blueprints, executes, runtime = _service(with_blueprint=False)
        blueprint = Blueprint(
            mission_id="m-1",
            revision=1,
            brief_revision=briefs.states["m-1"].revision,
            goal="댓글 기능",
            acceptance_criteria=(FIRST,),
        )
        blueprints.states["m-1"] = BlueprintState.start(blueprint=blueprint)

        with pytest.raises(BlueprintNotClearedError):
            await service.dispatch_next(mission_id="m-1")
        assert executes.states == {}
        assert runtime.requests == []

    async def test_a_moved_brief_blocks_execution(self) -> None:
        service, briefs, _, _, _ = _service()
        briefs.states["m-1"] = briefs.states["m-1"].record_answer(
            answer="새 결정", authority="decision", question="추가 질문?"
        )
        with pytest.raises(BlueprintNotClearedError):
            await service.dispatch_next(mission_id="m-1")


class TestDispatch:
    async def test_a_successful_run_is_executed_unverified_with_provenance(self) -> None:
        service, _, _, executes, runtime = _service(
            ExecutionOutcome(succeeded=True, native_session_id="sess-9", result_summary="완료")
        )
        state = await service.dispatch_next(mission_id="m-1")

        attempt = state.attempts[-1]
        assert attempt.status is AttemptStatus.EXECUTED_UNVERIFIED
        assert attempt.execution_id == "exec-m-1-0001"
        assert attempt.runtime_backend == "fake"
        assert attempt.blueprint_revision == 1
        assert attempt.ac_key == FIRST.key
        assert attempt.native_session_id == "sess-9"
        assert attempt.envelope == ENVELOPE
        assert executes.states["m-1"] == state
        assert runtime.requests[0].criterion == FIRST
        assert runtime.requests[0].workspace == ENVELOPE.workspace

    async def test_the_attempt_is_persisted_before_the_runtime_runs(self) -> None:
        """지속이 dispatch보다 먼저다 (ADR-0024 §4)."""
        service, _, _, _, runtime = _service()
        await service.dispatch_next(mission_id="m-1")

        assert runtime.observed_open_at_call == [True]

    async def test_the_request_carries_only_the_target_criterion(self) -> None:
        service, _, _, _, runtime = _service()
        await service.dispatch_next(mission_id="m-1")

        request = runtime.requests[0]
        assert request.goal == "댓글 기능"
        assert request.constraints == ("로그인 사용자만",)
        assert request.non_goals == ("수정·삭제 제외",)
        assert request.criterion == FIRST

    async def test_criteria_run_in_declaration_order(self) -> None:
        service, _, _, _, runtime = _service()
        await service.dispatch_next(mission_id="m-1")
        await service.dispatch_next(mission_id="m-1")

        assert [item.criterion for item in runtime.requests] == [FIRST, SECOND]

    async def test_everything_executed_is_reported(self) -> None:
        service, _, _, _, _ = _service()
        await service.dispatch_next(mission_id="m-1")
        await service.dispatch_next(mission_id="m-1")
        with pytest.raises(AllCriteriaExecutedError):
            await service.dispatch_next(mission_id="m-1")


class TestFailure:
    async def test_a_failed_outcome_is_recorded_with_its_error(self) -> None:
        service, _, _, executes, _ = _service(
            ExecutionOutcome(succeeded=False, error="tests exploded")
        )
        state = await service.dispatch_next(mission_id="m-1")

        assert state.attempts[-1].status is AttemptStatus.EXECUTION_FAILED
        assert state.attempts[-1].error == "tests exploded"
        assert executes.states["m-1"] == state

    async def test_a_raising_runtime_becomes_an_execution_failure(self) -> None:
        service, _, _, executes, runtime = _service()
        runtime.raise_next = RuntimeError("process would not start")
        state = await service.dispatch_next(mission_id="m-1")

        attempt = state.attempts[-1]
        assert attempt.status is AttemptStatus.EXECUTION_FAILED
        assert attempt.error is not None
        assert "process would not start" in attempt.error
        assert executes.states["m-1"] == state

    async def test_a_failure_retries_the_same_criterion_next(self) -> None:
        service, _, _, _, runtime = _service(
            ExecutionOutcome(succeeded=False, error="tests exploded"),
            ExecutionOutcome(succeeded=True, result_summary="이번엔 통과"),
        )
        await service.dispatch_next(mission_id="m-1")
        state = await service.dispatch_next(mission_id="m-1")

        assert [item.criterion for item in runtime.requests] == [FIRST, FIRST]
        assert state.attempts[-1].status is AttemptStatus.EXECUTED_UNVERIFIED


class TestGate:
    async def test_all_executed_clears_for_verify(self) -> None:
        service, _, _, _, _ = _service()
        await service.dispatch_next(mission_id="m-1")
        await service.dispatch_next(mission_id="m-1")

        decision = await service.decide_gate(mission_id="m-1")
        assert decision.outcome == "CLEAR"

    async def test_unexecuted_criteria_hold(self) -> None:
        service, _, _, _, _ = _service()
        decision = await service.decide_gate(mission_id="m-1")
        assert decision.outcome == "HOLD"

    async def test_the_gate_rechecks_the_entry(self) -> None:
        service, briefs, _, _, _ = _service()
        await service.dispatch_next(mission_id="m-1")
        briefs.states["m-1"] = briefs.states["m-1"].record_answer(
            answer="새 결정", authority="decision", question="추가 질문?"
        )
        with pytest.raises(BlueprintNotClearedError):
            await service.decide_gate(mission_id="m-1")
