"""Evolve patch의 content-key 매핑과 successor Blueprint 조립."""

import pytest

from mission_control.domain.blueprint.evolution import (
    EvolveOntologyError,
    EvolvePatchError,
    apply_ontology_mutations,
    assemble_evolved_blueprint,
    check_evolve_scope,
)
from mission_control.domain.blueprint.spec import (
    AcceptanceCriterion,
    Blueprint,
    OntologyField,
    OntologySchema,
)
from mission_control.domain.evolve.models import (
    AcceptanceCriterionPatch,
    AcPatchOperation,
    ChallengeKind,
    CriterionOutcomeSnapshot,
    EvolveSourceSnapshot,
    OntologyFieldProposal,
    OntologyMutation,
    OntologyMutationOperation,
    ReflectOutput,
    ScopeChangeKind,
    WonderChallenge,
    WonderOutput,
)


def _parent() -> Blueprint:
    return Blueprint(
        mission_id="m-1",
        revision=3,
        brief_revision=2,
        goal="요청이 중복돼도 한 번만 처리한다",
        constraints=("기존 API를 유지한다",),
        non_goals=("새 큐 도입은 제외",),
        acceptance_criteria=(
            AcceptanceCriterion(
                description="동일 요청은 한 번만 반영된다",
                verify_command="pytest tests/test_idempotency.py",
                expected_artifacts=("reports/idempotency.json",),
            ),
            AcceptanceCriterion(
                description="429 응답은 재시도한다",
                verify_command="pytest tests/test_retry.py",
                output_assertion="1 passed",
            ),
        ),
        ontology=OntologySchema(
            name="RequestHandling",
            description="요청 처리 경계",
            fields=(
                OntologyField(
                    name="request_id",
                    field_type="string",
                    description="중복 판별 키",
                    required=True,
                ),
            ),
        ),
    )


def _source(parent: Blueprint) -> EvolveSourceSnapshot:
    first, second = parent.criterion_keys
    return EvolveSourceSnapshot(
        mission_id=parent.mission_id,
        blueprint_revision=parent.revision,
        blueprint_generation=parent.generation,
        verify_sequence=8,
        gate_blockers=(f"{second} failed",),
        execution_attempt_numbers=(3, 4),
        criteria=(
            CriterionOutcomeSnapshot(
                ac_key=first,
                mechanical_passed=True,
                semantic_passed=True,
                semantic_score=0.94,
                semantic_uncertainty=0.04,
                reward_hacking_risk=0.01,
                semantic_reasoning="중복 요청이 한 번만 반영된다",
                evidence_refs=("verify/first",),
                proven=True,
            ),
            CriterionOutcomeSnapshot(
                ac_key=second,
                mechanical_passed=False,
                mechanical_detail="retry test status 1",
                semantic_passed=False,
                semantic_score=0.4,
                semantic_uncertainty=0.12,
                reward_hacking_risk=0.03,
                semantic_reasoning="Retry-After와 jitter를 지키지 않는다",
                evidence_refs=("verify/second",),
                proven=False,
            ),
        ),
    )


def _wonder(parent: Blueprint) -> WonderOutput:
    return WonderOutput(
        challenges=(
            WonderChallenge(
                kind=ChallengeKind.CHALLENGE,
                parent_ac_key=parent.criterion_keys[1],
                detail="Retry-After와 jitter 경계가 없다",
            ),
        ),
        reasoning="실패한 retry 계약만 다듬는다",
    )


def _reflect(parent: Blueprint) -> ReflectOutput:
    first, second = parent.criterion_keys
    return ReflectOutput(
        refined_goal=parent.goal,
        refined_constraints=parent.constraints,
        ac_patches=(
            AcceptanceCriterionPatch(operation=AcPatchOperation.KEEP, parent_ac_key=first),
            AcceptanceCriterionPatch(
                operation=AcPatchOperation.REVISE,
                parent_ac_key=second,
                description="429 응답은 Retry-After와 jitter를 지켜 재시도한다",
            ),
            AcceptanceCriterionPatch(
                operation=AcPatchOperation.ADD,
                description="재시도 소진이 관측 가능하다",
            ),
        ),
        ontology_mutations=(
            OntologyMutation(
                operation=OntologyMutationOperation.ADD,
                field_name="retry_after",
                field=OntologyFieldProposal(
                    name="retry_after",
                    field_type="duration",
                    description="서버가 지시한 대기 시간",
                    required=False,
                ),
            ),
        ),
        settled_ac_keys=(first,),
        reasoning="통과 계약은 보존하고 실패 계약만 명시화한다",
    )


class TestSuccessorAssembly:
    def test_keep_revise_add_and_ontology_mutation_are_deterministic(self) -> None:
        parent = _parent()
        successor = assemble_evolved_blueprint(
            parent=parent,
            source=_source(parent),
            wonder=_wonder(parent),
            reflect=_reflect(parent),
            revision=4,
        )

        assert successor.generation == 2
        assert successor.evolved_from_revision == 3
        assert successor.goal == parent.goal
        assert successor.constraints == parent.constraints
        assert successor.non_goals == parent.non_goals

        kept, revised, added = successor.acceptance_criteria
        assert kept == parent.acceptance_criteria[0]
        assert revised.key != parent.acceptance_criteria[1].key
        assert revised.verify_command == parent.acceptance_criteria[1].verify_command
        assert revised.output_assertion == parent.acceptance_criteria[1].output_assertion
        assert added.verify_command is None
        assert successor.ontology.fields[-1].name == "retry_after"

    def test_a_proven_unchallenged_ac_is_forced_to_exact_keep(self) -> None:
        parent = _parent()
        reflect = _reflect(parent)
        patches = list(reflect.ac_patches)
        patches[0] = AcceptanceCriterionPatch(
            operation=AcPatchOperation.REVISE,
            parent_ac_key=parent.criterion_keys[0],
            description="통과했지만 다시 쓴다",
        )

        with pytest.raises(EvolvePatchError, match="exact keep"):
            assemble_evolved_blueprint(
                parent=parent,
                source=_source(parent),
                wonder=_wonder(parent),
                reflect=reflect.model_copy(update={"ac_patches": tuple(patches)}),
                revision=4,
            )

    def test_parent_reorder_is_rejected(self) -> None:
        parent = _parent()
        reflect = _reflect(parent)
        first, second, added = reflect.ac_patches
        reordered = reflect.model_copy(update={"ac_patches": (second, first, added)})

        with pytest.raises(EvolvePatchError, match="순서를 바꾸는"):
            assemble_evolved_blueprint(
                parent=parent,
                source=_source(parent),
                wonder=_wonder(parent),
                reflect=reordered,
                revision=4,
            )

    def test_add_before_parent_mapping_is_rejected(self) -> None:
        parent = _parent()
        reflect = _reflect(parent)
        first, second, added = reflect.ac_patches
        misplaced = reflect.model_copy(update={"ac_patches": (first, added, second)})

        with pytest.raises(EvolvePatchError, match="add는"):
            assemble_evolved_blueprint(
                parent=parent,
                source=_source(parent),
                wonder=_wonder(parent),
                reflect=misplaced,
                revision=4,
            )


class TestScopeAndOntology:
    def test_goal_and_constraint_changes_are_findings_not_revisions(self) -> None:
        parent = _parent()
        reflect = _reflect(parent).model_copy(
            update={
                "refined_goal": "범위를 넓힌 목표",
                "refined_constraints": ("새 데이터베이스를 쓴다",),
            }
        )

        findings = check_evolve_scope(parent=parent, reflect=reflect)
        assert tuple(item.kind for item in findings) == (
            ScopeChangeKind.GOAL,
            ScopeChangeKind.CONSTRAINTS,
        )

    def test_unknown_ontology_modify_is_rejected(self) -> None:
        parent = _parent()
        reflect = _reflect(parent).model_copy(
            update={
                "ontology_mutations": (
                    OntologyMutation(
                        operation=OntologyMutationOperation.MODIFY,
                        field_name="missing",
                        field=OntologyFieldProposal(
                            name="missing",
                            field_type="string",
                            description="없는 필드",
                            required=False,
                        ),
                    ),
                )
            }
        )

        with pytest.raises(EvolveOntologyError, match="없는 ontology field"):
            apply_ontology_mutations(ontology=parent.ontology, reflect=reflect)
