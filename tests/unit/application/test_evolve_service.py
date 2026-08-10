"""Evolve source projection + fake Wonder/Reflect durable replay."""

from dataclasses import dataclass

import pytest

from mission_control.application.evolve_service import EvolveEntryError, EvolveService
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
    EvolutionPhase,
    ReflectOutput,
    WonderChallenge,
    WonderOutput,
)
from mission_control.domain.execute.state import CapabilityEnvelope, ExecuteState
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

POLICY = QaPolicy.blueprint_v1()
SEMANTIC_POLICY = SemanticPolicy.verify_v1()
ENVELOPE = CapabilityEnvelope(workspace="/tmp/mission")


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


def _execute_state(state: BlueprintState) -> ExecuteState:
    criterion = state.current.acceptance_criteria[0]
    execute = ExecuteState.start(mission_id=state.mission_id).dispatch(
        execution_id="exec-1",
        runtime_backend="fake",
        blueprint_revision=state.revision,
        ac_key=criterion.key,
        envelope=ENVELOPE,
    )
    return execute.record_result(succeeded=True, result_summary="worker finished")


def _verify_state(
    state: BlueprintState,
    *,
    passed: bool = False,
    attempt_numbers: tuple[int, ...] = (1,),
) -> VerifyState:
    criterion = state.current.acceptance_criteria[0]
    verify = VerifyState.start(mission_id=state.mission_id).record(
        VerificationEvidence(
            mission_id=state.mission_id,
            blueprint_revision=state.revision,
            execution_attempt_numbers=attempt_numbers,
            runs=(
                VerificationRun(
                    ac_key=criterion.key,
                    command=criterion.verify_command,
                    exit_code=0 if passed else 1,
                    passed=passed,
                    output_ref="/tmp/verify-output.txt",
                    output_tail="1 passed" if passed else "retry test failed",
                ),
            ),
        )
    )
    return verify.record_verdicts(
        SemanticAssessment(
            blueprint_revision=state.revision,
            policy_version=SEMANTIC_POLICY.version,
            verdicts=(
                CriterionVerdict(
                    ac_key=criterion.key,
                    satisfied=passed,
                    score=0.95 if passed else 0.35,
                    uncertainty=0.1,
                    reward_hacking_risk=0.05,
                    reasoning=(
                        "계약이 입증됐다" if passed else "Retry-After 경계가 구현되지 않았다"
                    ),
                    evidence=("semantic-report.json",),
                ),
            ),
        )
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


class InMemoryReadRepository:
    def __init__(self, state: object) -> None:
        self.state = state

    async def load(self, mission_id: str):
        return self.state if mission_id == self.state.mission_id else None

    async def save(self, state: object) -> None:
        self.state = state


@dataclass(frozen=True)
class Harness:
    service: EvolveService
    blueprints: InMemoryBlueprintRepository
    executes: InMemoryReadRepository
    verifies: InMemoryReadRepository
    wonderer: ScriptedWonderer
    reflector: ScriptedReflector


def _service(
    state: BlueprintState,
    *,
    execute: ExecuteState | None = None,
    verify: VerifyState | None = None,
    reflector: ScriptedReflector | None = None,
) -> Harness:
    blueprints = InMemoryBlueprintRepository(state)
    executes = InMemoryReadRepository(execute or _execute_state(state))
    verifies = InMemoryReadRepository(verify or _verify_state(state))
    wonderer = ScriptedWonderer()
    chosen_reflector = reflector or ScriptedReflector()
    service = EvolveService(
        repository=blueprints,
        executes=executes,
        verifies=verifies,
        wonderer=wonderer,
        reflector=chosen_reflector,
        policy=SEMANTIC_POLICY,
    )
    return Harness(
        service=service,
        blueprints=blueprints,
        executes=executes,
        verifies=verifies,
        wonderer=wonderer,
        reflector=chosen_reflector,
    )


class TestEvolveProposal:
    async def test_normal_flow_stops_at_an_unapproved_successor(self) -> None:
        parent = _approved_state()
        harness = _service(parent)

        result = await harness.service.propose(mission_id="m-1")

        assert len(harness.wonderer.requests) == 1
        assert len(harness.reflector.requests) == 1
        assert result.revision == 2
        assert result.generation == 2
        assert result.current.evolved_from_revision == 1
        assert not result.has_current_approval
        assert result.evolutions[-1].phase is EvolutionPhase.COMPLETED
        assert result.evolutions[-1].result_blueprint_revision == 2
        assert harness.blueprints.state == result
        assert len(harness.blueprints.saved) == 4  # start, Wonder, Reflect, atomic completion

        source = harness.wonderer.requests[0].source
        outcome = source.criteria[0]
        assert source.verify_sequence == 3
        assert source.execution_attempt_numbers == (1,)
        assert outcome.mechanical_passed is False
        assert outcome.mechanical_detail is not None
        assert "status 1" in outcome.mechanical_detail
        assert outcome.semantic_passed is False
        assert outcome.evidence_refs == (
            "/tmp/verify-output.txt",
            "semantic-report.json",
        )

    async def test_qa_budget_resets_only_for_the_successor_generation(self) -> None:
        parent = _approved_state(exhausted=True)
        harness = _service(parent)
        result = await harness.service.propose(mission_id="m-1")

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
        harness = _service(parent, reflector=reflector)

        with pytest.raises(RuntimeError, match="reflect crashed"):
            await harness.service.propose(mission_id="m-1")
        assert harness.blueprints.state.active_evolution is not None
        assert harness.blueprints.state.active_evolution.phase is EvolutionPhase.REFLECTING

        result = await harness.service.propose(mission_id="m-1")
        assert result.generation == 2
        assert len(harness.wonderer.requests) == 1
        assert len(reflector.requests) == 2

    async def test_failed_start_save_happens_before_wonder_dispatch(self) -> None:
        parent = _approved_state()
        harness = _service(parent)
        harness.blueprints.fail_next_save = True

        with pytest.raises(OSError, match="disk unavailable"):
            await harness.service.propose(mission_id="m-1")
        assert harness.blueprints.state == parent
        assert harness.wonderer.requests == []

    async def test_scope_change_is_durable_hold_without_a_revision(self) -> None:
        parent = _approved_state()
        reflector = ScriptedReflector(change_scope=True)
        harness = _service(parent, reflector=reflector)

        held = await harness.service.propose(mission_id="m-1")
        assert held.revision == 1
        assert held.active_evolution is not None
        assert held.active_evolution.phase is EvolutionPhase.SEEDING
        assert held.active_evolution.scope_change_findings[0].proposed == "다른 목표"
        manual_revision = held.current.model_copy(
            update={"revision": 2, "goal": "checkpoint를 우회한 수정"}
        )
        with pytest.raises(EvolutionNotAllowedError, match="Evolve 진행 중"):
            held.revise(blueprint=manual_revision)

        same = await harness.service.propose(mission_id="m-1")
        assert same == harness.blueprints.state
        assert len(harness.wonderer.requests) == 1
        assert len(reflector.requests) == 1

    async def test_unapproved_parent_is_rejected_before_dispatch(self) -> None:
        parent = BlueprintState.start(blueprint=_blueprint())
        harness = _service(parent)

        with pytest.raises(EvolveEntryError, match="exact user approval"):
            await harness.service.propose(mission_id="m-1")
        assert harness.wonderer.requests == []


class TestEvolveEntryProjection:
    async def test_execute_hold_is_rejected_before_wonder(self) -> None:
        parent = _approved_state()
        criterion = parent.current.acceptance_criteria[0]
        open_execute = ExecuteState.start(mission_id="m-1").dispatch(
            execution_id="exec-open",
            runtime_backend="fake",
            blueprint_revision=parent.revision,
            ac_key=criterion.key,
            envelope=ENVELOPE,
        )
        harness = _service(parent, execute=open_execute)

        with pytest.raises(EvolveEntryError, match="Execute Gate가 CLEAR가 아니다"):
            await harness.service.propose(mission_id="m-1")
        assert harness.wonderer.requests == []

    async def test_verify_clear_is_rejected_before_wonder(self) -> None:
        parent = _approved_state()
        harness = _service(parent, verify=_verify_state(parent, passed=True))

        with pytest.raises(EvolveEntryError, match="재계산 결과가 HOLD가 아니다"):
            await harness.service.propose(mission_id="m-1")
        assert harness.wonderer.requests == []

    async def test_stale_execution_attempt_lineage_is_rejected(self) -> None:
        parent = _approved_state()
        harness = _service(parent, verify=_verify_state(parent, attempt_numbers=(2,)))

        with pytest.raises(EvolveEntryError, match="attempt lineage"):
            await harness.service.propose(mission_id="m-1")
        assert harness.wonderer.requests == []

    async def test_missing_mechanical_run_is_rejected_as_incomplete_source(self) -> None:
        parent = _approved_state()
        complete = _verify_state(parent)
        assert complete.evidence is not None
        incomplete = VerifyState(
            mission_id=complete.mission_id,
            sequence=complete.sequence,
            evidence=complete.evidence.model_copy(update={"runs": ()}),
            verdicts=complete.verdicts,
        )
        harness = _service(parent, verify=incomplete)

        with pytest.raises(EvolveEntryError, match="mechanical AC별 run"):
            await harness.service.propose(mission_id="m-1")
        assert harness.wonderer.requests == []

    async def test_missing_semantic_assessment_is_rejected(self) -> None:
        parent = _approved_state()
        complete = _verify_state(parent)
        assert complete.evidence is not None
        incomplete = VerifyState.start(mission_id="m-1").record(complete.evidence)
        harness = _service(parent, verify=incomplete)

        with pytest.raises(EvolveEntryError, match="semantic assessment가 없다"):
            await harness.service.propose(mission_id="m-1")
        assert harness.wonderer.requests == []

    async def test_unknown_semantic_key_is_rejected_as_incomplete_source(self) -> None:
        parent = _approved_state()
        complete = _verify_state(parent)
        assert complete.evidence is not None
        assert complete.verdicts is not None
        unknown = CriterionVerdict(
            ac_key="ac_unknown",
            satisfied=False,
            score=0.2,
            uncertainty=0.1,
            reward_hacking_risk=0.0,
            reasoning="다른 계약을 평가했다",
        )
        assessment = complete.verdicts.model_copy(update={"verdicts": (unknown,)})
        invalid = VerifyState(
            mission_id=complete.mission_id,
            sequence=complete.sequence,
            evidence=complete.evidence,
            verdicts=assessment,
        )
        harness = _service(parent, verify=invalid)

        with pytest.raises(EvolveEntryError, match="AC별 semantic verdict"):
            await harness.service.propose(mission_id="m-1")
        assert harness.wonderer.requests == []

    async def test_changed_source_cannot_resume_an_existing_checkpoint(self) -> None:
        parent = _approved_state()
        reflector = ScriptedReflector()
        reflector.fail_next = True
        harness = _service(parent, reflector=reflector)

        with pytest.raises(RuntimeError, match="reflect crashed"):
            await harness.service.propose(mission_id="m-1")
        changed = _verify_state(parent)
        harness.verifies.state = changed.model_copy(update={"sequence": changed.sequence + 1})

        with pytest.raises(EvolutionNotAllowedError, match="checkpoint와 source가 다르다"):
            await harness.service.propose(mission_id="m-1")
        assert len(harness.wonderer.requests) == 1
