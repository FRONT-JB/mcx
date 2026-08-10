"""파일 상태의 Execute·Verify HOLD에서 Evolve successor를 재구성한다."""

from pathlib import Path

from mission_control.adapters.persistence.file_blueprint_repository import (
    FileBlueprintRepository,
)
from mission_control.adapters.persistence.file_execute_repository import (
    FileExecuteRepository,
)
from mission_control.adapters.persistence.file_verify_repository import FileVerifyRepository
from mission_control.application.evolve_service import EvolveService
from mission_control.application.ports import ReflectRequest, WonderRequest
from mission_control.domain.blueprint.qa import QaAssessment, QaPolicy
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import BlueprintState
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

QA_POLICY = QaPolicy.blueprint_v1()
SEMANTIC_POLICY = SemanticPolicy.verify_v1()


class FakeWonderer:
    async def wonder(self, request: WonderRequest) -> WonderOutput:
        return WonderOutput(
            challenges=(
                WonderChallenge(
                    kind=ChallengeKind.CHALLENGE,
                    parent_ac_key=request.acceptance_criteria[0].key,
                    detail="실패한 재시도 경계를 구체화한다",
                ),
            ),
            reasoning="durable Verify evidence를 따른다",
        )


class FakeReflector:
    async def reflect(self, request: ReflectRequest) -> ReflectOutput:
        return ReflectOutput(
            refined_goal=request.goal,
            refined_constraints=request.constraints,
            ac_patches=(
                AcceptanceCriterionPatch(
                    operation=AcPatchOperation.REVISE,
                    parent_ac_key=request.acceptance_criteria[0].key,
                    description="429 응답은 Retry-After와 jitter를 지켜 재시도한다",
                ),
            ),
            reasoning="실패한 AC의 의미만 좁힌다",
        )


async def test_file_states_project_a_verify_hold_into_one_successor(tmp_path: Path) -> None:
    mission_id = "m-1"
    criterion = AcceptanceCriterion(
        description="429 응답은 재시도한다",
        verify_command="pytest tests/test_retry.py",
    )
    blueprint = Blueprint(
        mission_id=mission_id,
        brief_revision=2,
        goal="429 응답을 안전하게 재시도한다",
        acceptance_criteria=(criterion,),
    )
    blueprint_state = BlueprintState.start(blueprint=blueprint)
    blueprint_state = blueprint_state.record_qa(
        assessment=QaAssessment(score=0.94), policy=QA_POLICY
    ).approve(statement="실행 승인", policy=QA_POLICY)

    execute = ExecuteState.start(mission_id=mission_id).dispatch(
        execution_id="exec-1",
        runtime_backend="fake",
        blueprint_revision=1,
        ac_key=criterion.key,
        envelope=CapabilityEnvelope(workspace=str(tmp_path)),
    )
    execute = execute.record_result(succeeded=True, result_summary="실행 완료")

    verify = VerifyState.start(mission_id=mission_id).record(
        VerificationEvidence(
            mission_id=mission_id,
            blueprint_revision=1,
            execution_attempt_numbers=(1,),
            runs=(
                VerificationRun(
                    ac_key=criterion.key,
                    command=criterion.verify_command,
                    exit_code=1,
                    passed=False,
                    output_ref=str(tmp_path / "verify-output.txt"),
                    output_tail="retry test failed",
                ),
            ),
        )
    )
    verify = verify.record_verdicts(
        SemanticAssessment(
            blueprint_revision=1,
            policy_version=SEMANTIC_POLICY.version,
            verdicts=(
                CriterionVerdict(
                    ac_key=criterion.key,
                    satisfied=False,
                    score=0.4,
                    uncertainty=0.1,
                    reward_hacking_risk=0.0,
                    reasoning="Retry-After 처리가 관찰되지 않았다",
                    evidence=("semantic-report.json",),
                ),
            ),
        )
    )

    blueprint_repository = FileBlueprintRepository(root=tmp_path)
    execute_repository = FileExecuteRepository(root=tmp_path)
    verify_repository = FileVerifyRepository(root=tmp_path)
    await blueprint_repository.save(blueprint_state)
    await execute_repository.save(execute)
    await verify_repository.save(verify)

    result = await EvolveService(
        repository=blueprint_repository,
        executes=execute_repository,
        verifies=verify_repository,
        wonderer=FakeWonderer(),
        reflector=FakeReflector(),
        policy=SEMANTIC_POLICY,
    ).propose(mission_id=mission_id)

    restored = await blueprint_repository.load(mission_id)
    assert restored == result
    assert restored is not None
    assert restored.revision == 2
    assert restored.generation == 2
    assert not restored.has_current_approval
    assert restored.evolutions[-1].phase is EvolutionPhase.COMPLETED
    assert restored.evolutions[-1].source.execution_attempt_numbers == (1,)
    assert restored.evolutions[-1].source.verify_sequence == verify.sequence
