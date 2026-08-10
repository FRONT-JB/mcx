"""Evolve domain/state vertical slice — fake Wonder/Reflect와 durable replay."""

import pytest

from mission_control.application.evolve_service import EvolveService
from mission_control.application.ports import ReflectRequest, WonderRequest
from mission_control.domain.blueprint.qa import QaAssessment, QaPolicy
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import (
    BlueprintState,
    EvolutionNotAllowedError,
    QaBudgetExhaustedError,
)
from mission_control.domain.evolve.models import (
    AcceptanceCriterionPatch,
    AcPatchOperation,
    ChallengeKind,
    CriterionOutcomeSnapshot,
    EvolutionPhase,
    EvolveSourceSnapshot,
    ReflectOutput,
    WonderChallenge,
    WonderOutput,
)

POLICY = QaPolicy.blueprint_v1()


def _blueprint() -> Blueprint:
    return Blueprint(
        mission_id="m-1",
        brief_revision=3,
        goal="429 응답을 안전하게 재시도한다",
        constraints=("기존 HTTP client를 유지한다",),
        non_goals=("새 queue 도입은 제외",),
        acceptance_criteria=(
            AcceptanceCriterion(
                description="429 응답은 재시도한다",
                verify_command="pytest tests/test_retry.py",
                output_assertion="1 passed",
            ),
        ),
    )


def _approved_state(*, exhausted: bool = False) -> BlueprintState:
    state = BlueprintState.start(blueprint=_blueprint())
    if exhausted:
        for _ in range(POLICY.max_iterations):
            state = state.record_qa(assessment=QaAssessment(score=0.85), policy=POLICY)
        return state.approve(
            statement="미달이지만 실행", policy=POLICY, accept_below_threshold=True
        )
    state = state.record_qa(assessment=QaAssessment(score=0.93), policy=POLICY)
    return state.approve(statement="실행 승인", policy=POLICY)


def _source(state: BlueprintState) -> EvolveSourceSnapshot:
    criterion = state.current.acceptance_criteria[0]
    return EvolveSourceSnapshot(
        mission_id=state.mission_id,
        blueprint_revision=state.revision,
        blueprint_generation=state.generation,
        verify_sequence=4,
        gate_blockers=(f"{criterion.key} verification failed",),
        execution_attempt_numbers=(2,),
        criteria=(
            CriterionOutcomeSnapshot(
                ac_key=criterion.key,
                mechanical_passed=False,
                mechanical_detail="retry test status 1",
                semantic_passed=False,
                semantic_score=0.35,
                semantic_uncertainty=0.1,
                reward_hacking_risk=0.05,
                semantic_reasoning="Retry-After 경계가 구현되지 않았다",
                evidence_refs=("verify/m-1/4",),
                proven=False,
            ),
        ),
    )


class InMemoryBlueprintRepository:
    def __init__(self, state: BlueprintState) -> None:
        self.state = state
        self.saved: list[BlueprintState] = []
        self.fail_next_save = False

    async def load(self, mission_id: str) -> BlueprintState | None:
        return self.state if mission_id == self.state.mission_id else None

    async def save(self, state: BlueprintState) -> None:
        if self.fail_next_save:
            self.fail_next_save = False
            raise OSError("disk unavailable")
        self.state = state
        self.saved.append(state)


class ScriptedWonderer:
    def __init__(self) -> None:
        self.requests: list[WonderRequest] = []
        self.fail_next = False

    async def wonder(self, request: WonderRequest) -> WonderOutput:
        self.requests.append(request)
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("wonder crashed")
        return WonderOutput(
            challenges=(
                WonderChallenge(
                    kind=ChallengeKind.CHALLENGE,
                    parent_ac_key=request.acceptance_criteria[0].key,
                    detail="Retry-After 경계가 빠졌다",
                ),
            ),
            reasoning="실패 evidence에 직접 연결한다",
        )


class ScriptedReflector:
    def __init__(self, *, change_scope: bool = False) -> None:
        self.requests: list[ReflectRequest] = []
        self.fail_next = False
        self.change_scope = change_scope

    async def reflect(self, request: ReflectRequest) -> ReflectOutput:
        self.requests.append(request)
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("reflect crashed")
        return ReflectOutput(
            refined_goal=("다른 목표" if self.change_scope else request.goal),
            refined_constraints=request.constraints,
            ac_patches=(
                AcceptanceCriterionPatch(
                    operation=AcPatchOperation.REVISE,
                    parent_ac_key=request.acceptance_criteria[0].key,
                    description="429 응답은 Retry-After와 jitter를 지켜 재시도한다",
                ),
            ),
            reasoning="실패한 계약만 구체화한다",
        )


def _service(
    state: BlueprintState,
    *,
    reflector: ScriptedReflector | None = None,
) -> tuple[
    EvolveService,
    InMemoryBlueprintRepository,
    ScriptedWonderer,
    ScriptedReflector,
]:
    repository = InMemoryBlueprintRepository(state)
    wonderer = ScriptedWonderer()
    chosen_reflector = reflector or ScriptedReflector()
    return (
        EvolveService(
            repository=repository,
            wonderer=wonderer,
            reflector=chosen_reflector,
        ),
        repository,
        wonderer,
        chosen_reflector,
    )


class TestEvolveProposal:
    async def test_normal_flow_stops_at_an_unapproved_successor(self) -> None:
        parent = _approved_state()
        service, repository, wonderer, reflector = _service(parent)

        result = await service.propose(mission_id="m-1", source=_source(parent))

        assert len(wonderer.requests) == 1
        assert len(reflector.requests) == 1
        assert result.revision == 2
        assert result.generation == 2
        assert result.current.evolved_from_revision == 1
        assert not result.has_current_approval
        assert result.evolutions[-1].phase is EvolutionPhase.COMPLETED
        assert result.evolutions[-1].result_blueprint_revision == 2
        assert repository.state == result
        assert len(repository.saved) == 4  # start, Wonder, Reflect, atomic completion

    async def test_qa_budget_resets_only_for_the_successor_generation(self) -> None:
        parent = _approved_state(exhausted=True)
        service, _, _, _ = _service(parent)
        result = await service.propose(mission_id="m-1", source=_source(parent))

        for _ in range(POLICY.max_iterations):
            result = result.record_qa(assessment=QaAssessment(score=0.85), policy=POLICY)
        with pytest.raises(QaBudgetExhaustedError):
            result.record_qa(assessment=QaAssessment(score=0.85), policy=POLICY)

        assert len(result.records_for_generation(1)) == POLICY.max_iterations
        assert len(result.records_for_generation(2)) == POLICY.max_iterations

    async def test_reflect_failure_resumes_without_repeating_wonder(self) -> None:
        parent = _approved_state()
        reflector = ScriptedReflector()
        reflector.fail_next = True
        service, repository, wonderer, _ = _service(parent, reflector=reflector)
        source = _source(parent)

        with pytest.raises(RuntimeError, match="reflect crashed"):
            await service.propose(mission_id="m-1", source=source)
        assert repository.state.active_evolution is not None
        assert repository.state.active_evolution.phase is EvolutionPhase.REFLECTING

        result = await service.propose(mission_id="m-1", source=source)
        assert result.generation == 2
        assert len(wonderer.requests) == 1
        assert len(reflector.requests) == 2

    async def test_failed_start_save_happens_before_wonder_dispatch(self) -> None:
        parent = _approved_state()
        service, repository, wonderer, _ = _service(parent)
        repository.fail_next_save = True

        with pytest.raises(OSError, match="disk unavailable"):
            await service.propose(mission_id="m-1", source=_source(parent))
        assert repository.state == parent
        assert wonderer.requests == []

    async def test_scope_change_is_durable_hold_without_a_revision(self) -> None:
        parent = _approved_state()
        reflector = ScriptedReflector(change_scope=True)
        service, repository, wonderer, _ = _service(parent, reflector=reflector)
        source = _source(parent)

        held = await service.propose(mission_id="m-1", source=source)
        assert held.revision == 1
        assert held.active_evolution is not None
        assert held.active_evolution.phase is EvolutionPhase.SEEDING
        assert held.active_evolution.scope_change_findings[0].proposed == "다른 목표"
        manual_revision = held.current.model_copy(
            update={"revision": 2, "goal": "checkpoint를 우회한 수정"}
        )
        with pytest.raises(EvolutionNotAllowedError, match="Evolve 진행 중"):
            held.revise(blueprint=manual_revision)

        same = await service.propose(mission_id="m-1", source=source)
        assert same == repository.state
        assert len(wonderer.requests) == 1
        assert len(reflector.requests) == 1

    async def test_unapproved_parent_is_rejected_before_dispatch(self) -> None:
        parent = BlueprintState.start(blueprint=_blueprint())
        service, _, wonderer, _ = _service(parent)

        with pytest.raises(EvolutionNotAllowedError, match="승인된 current"):
            await service.propose(mission_id="m-1", source=_source(parent))
        assert wonderer.requests == []
