"""파일 상태의 Execute·Verify HOLD에서 Evolve successor를 재구성한다."""

from dataclasses import replace
from pathlib import Path
from typing import Any

from mission_control.adapters.persistence.file_blueprint_repository import (
    FileBlueprintRepository,
)
from mission_control.adapters.persistence.file_execute_repository import (
    FileExecuteRepository,
)
from mission_control.adapters.persistence.file_mission_repository import (
    FileMissionRepository,
)
from mission_control.adapters.persistence.file_verify_repository import FileVerifyRepository
from mission_control.cli.composition import StateLayout, default_adapters
from mission_control.cli.journal import MissionJournal
from mission_control.domain.blueprint.qa import QaAssessment, QaPolicy
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.evolve.models import EvolutionPhase
from mission_control.domain.execute.state import CapabilityEnvelope, ExecuteState
from mission_control.domain.mission import MissionRecord
from mission_control.domain.stage import Stage
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
from mission_control.mcp.protocol import ResultType
from mission_control.mcp.surface import call_tool

QA_POLICY = QaPolicy.blueprint_v1()
SEMANTIC_POLICY = SemanticPolicy.verify_v1()


class ScriptedCompletion:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []

    @property
    def backend(self) -> str:
        return "scripted"

    async def complete_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        workspace: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((prompt, schema, workspace))
        return self.responses[len(self.calls) - 1]


async def test_file_states_project_a_verify_hold_into_one_successor(tmp_path: Path) -> None:
    mission_id = "m-1"
    layout = StateLayout.under(tmp_path)
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

    blueprint_repository = FileBlueprintRepository(root=layout.state)
    execute_repository = FileExecuteRepository(root=layout.state)
    verify_repository = FileVerifyRepository(root=layout.state)
    mission_repository = FileMissionRepository(root=layout.state)
    await blueprint_repository.save(blueprint_state)
    await execute_repository.save(execute)
    await verify_repository.save(verify)
    mission = MissionRecord.create(mission_id=mission_id, workspace=str(tmp_path))
    for destination in (Stage.BLUEPRINT, Stage.EXECUTE, Stage.VERIFY):
        mission = mission.transit(destination=destination, at="t", reason="fixture")
    await mission_repository.save(mission)

    completion = ScriptedCompletion(
        [
            {
                "questions": [
                    {
                        "question": "Retry-After와 jitter 경계가 필요한가?",
                        "kind": "challenge",
                        "ac_refs": [1],
                    }
                ],
                "reasoning": "durable Verify evidence를 따른다",
            },
            {
                "refined_goal": blueprint.goal,
                "refined_constraints": [],
                "ac_patches": [
                    {
                        "op": "revise",
                        "index": 0,
                        "content": "429 응답은 Retry-After와 jitter를 지켜 재시도한다",
                        "reason": "실패한 AC의 의미만 좁힌다",
                    }
                ],
                "ontology_mutations": [],
                "reasoning": "실패한 AC의 의미만 좁힌다",
            },
        ]
    )
    result = await call_tool(
        "mcx_blueprint_evolve",
        {"mission": mission_id},
        state_dir=str(tmp_path),
        adapters=replace(default_adapters(), completion=completion),
    )

    restored = await blueprint_repository.load(mission_id)
    assert restored is not None
    assert result.result_type is ResultType.COMPLETE
    assert result.structured_content["result_blueprint_revision"] == 2
    assert restored.revision == 2
    assert restored.generation == 2
    assert not restored.has_current_approval
    assert restored.evolutions[-1].phase is EvolutionPhase.COMPLETED
    assert restored.evolutions[-1].source.execution_attempt_numbers == (1,)
    assert restored.evolutions[-1].source.verify_sequence == verify.sequence
    assert len(completion.calls) == 2
    assert all(workspace is None for _, _, workspace in completion.calls)
    stored_mission = await mission_repository.load(mission_id)
    assert stored_mission is not None
    assert stored_mission.current_stage is Stage.BLUEPRINT
    (entry,) = MissionJournal(root=layout.state, mission_id=mission_id).entries()
    assert entry.command == "blueprint evolve"
    assert entry.calls == {"scripted": 2}
