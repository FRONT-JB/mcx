"""Evolve proposal을 successor Blueprint로 결정적으로 조립한다 (ADR-0051)."""

from __future__ import annotations

from mission_control.domain.blueprint.spec import (
    AcceptanceCriterion,
    Blueprint,
    OntologyField,
    OntologySchema,
)
from mission_control.domain.errors import MissionControlError
from mission_control.domain.evolve.models import (
    AcPatchOperation,
    EvolveSourceSnapshot,
    OntologyMutationOperation,
    ReflectOutput,
    ScopeChangeFinding,
    ScopeChangeKind,
    WonderOutput,
)


class EvolvePatchError(MissionControlError):
    """Reflect AC patch가 parent identity 또는 보존 규칙을 어겼다."""


class EvolveOntologyError(MissionControlError):
    """ontology mutation이 현재 schema에 적용될 수 없다."""


def check_evolve_scope(
    *, parent: Blueprint, reflect: ReflectOutput
) -> tuple[ScopeChangeFinding, ...]:
    """사용자 소유 방향의 변경 제안을 durable finding으로 바꾼다."""

    findings: list[ScopeChangeFinding] = []
    if reflect.refined_goal != parent.goal:
        findings.append(
            ScopeChangeFinding(
                kind=ScopeChangeKind.GOAL,
                current=parent.goal,
                proposed=reflect.refined_goal,
            )
        )
    if reflect.refined_constraints != parent.constraints:
        findings.append(
            ScopeChangeFinding(
                kind=ScopeChangeKind.CONSTRAINTS,
                current=repr(parent.constraints),
                proposed=repr(reflect.refined_constraints),
            )
        )
    return tuple(findings)


def _validate_source(
    *, parent: Blueprint, source: EvolveSourceSnapshot, wonder: WonderOutput
) -> None:
    if source.mission_id != parent.mission_id:
        raise EvolvePatchError("Evolve source와 parent Blueprint의 mission이 다르다")
    if source.blueprint_revision != parent.revision:
        raise EvolvePatchError("Evolve source와 parent Blueprint revision이 다르다")
    if source.blueprint_generation != parent.generation:
        raise EvolvePatchError("Evolve source와 parent Blueprint generation이 다르다")

    parent_keys = parent.criterion_keys
    source_keys = tuple(item.ac_key for item in source.criteria)
    if set(source_keys) != set(parent_keys) or len(source_keys) != len(parent_keys):
        raise EvolvePatchError("Evolve source는 모든 parent AC outcome을 정확히 하나씩 가져야 한다")

    unknown_challenges = wonder.challenged_keys - set(parent_keys)
    if unknown_challenges:
        raise EvolvePatchError(
            "Wonder가 알 수 없는 parent AC를 challenge했다: "
            + ", ".join(sorted(unknown_challenges))
        )


def _evolve_criteria(
    *,
    parent: Blueprint,
    source: EvolveSourceSnapshot,
    wonder: WonderOutput,
    reflect: ReflectOutput,
) -> tuple[AcceptanceCriterion, ...]:
    parent_keys = parent.criterion_keys
    parent_patches = tuple(
        item for item in reflect.ac_patches if item.operation is not AcPatchOperation.ADD
    )
    added_patches = tuple(
        item for item in reflect.ac_patches if item.operation is AcPatchOperation.ADD
    )

    if len(parent_patches) != len(parent_keys):
        raise EvolvePatchError("모든 parent AC는 keep 또는 revise로 정확히 한 번 매핑돼야 한다")
    if reflect.ac_patches != (*parent_patches, *added_patches):
        raise EvolvePatchError("add는 모든 parent AC patch 뒤에만 올 수 있다")

    mapped_keys = tuple(item.parent_ac_key for item in parent_patches)
    if mapped_keys != parent_keys:
        if set(mapped_keys) != set(parent_keys):
            raise EvolvePatchError("unknown·missing parent AC key가 있는 patch다")
        raise EvolvePatchError("parent AC의 순서를 바꾸는 patch는 허용하지 않는다")

    unknown_settled = set(reflect.settled_ac_keys) - set(parent_keys)
    if unknown_settled:
        raise EvolvePatchError(
            "Reflect가 알 수 없는 AC를 settled로 표시했다: "
            + ", ".join(sorted(unknown_settled))
        )

    evolved: list[AcceptanceCriterion] = []
    for criterion, patch in zip(parent.acceptance_criteria, parent_patches, strict=True):
        outcome = source.outcome_for(criterion.key)
        if outcome is None:  # _validate_source가 먼저 막지만 타입 narrowing을 위해 남긴다.
            raise EvolvePatchError(f"{criterion.key}의 source outcome이 없다")
        protected = outcome.proven and criterion.key not in wonder.challenged_keys
        if protected and patch.operation is not AcPatchOperation.KEEP:
            raise EvolvePatchError(
                f"통과했고 challenge되지 않은 {criterion.key}는 exact keep이어야 한다"
            )

        if patch.operation is AcPatchOperation.KEEP:
            evolved.append(criterion)
            continue
        if patch.description == criterion.description:
            raise EvolvePatchError(f"{criterion.key}의 revise가 description을 바꾸지 않았다")
        evolved.append(
            AcceptanceCriterion(
                description=patch.description or "",
                verify_command=criterion.verify_command,
                expected_artifacts=criterion.expected_artifacts,
                output_assertion=criterion.output_assertion,
            )
        )

    evolved.extend(
        AcceptanceCriterion(description=patch.description or "") for patch in added_patches
    )
    return tuple(evolved)


def apply_ontology_mutations(
    *, ontology: OntologySchema, reflect: ReflectOutput
) -> OntologySchema:
    """기존 field 순서를 유지하고 add만 꼬리에 붙인다."""

    fields = list(ontology.fields)
    for mutation in reflect.ontology_mutations:
        index = next(
            (position for position, item in enumerate(fields) if item.name == mutation.field_name),
            None,
        )
        if mutation.operation is OntologyMutationOperation.ADD:
            if index is not None:
                raise EvolveOntologyError(
                    f"이미 있는 ontology field를 add할 수 없다: {mutation.field_name}"
                )
            proposal = mutation.field
            if proposal is None:
                raise EvolveOntologyError("add mutation에 field가 없다")
            fields.append(OntologyField(**proposal.model_dump()))
        elif mutation.operation is OntologyMutationOperation.MODIFY:
            if index is None:
                raise EvolveOntologyError(
                    f"없는 ontology field를 modify할 수 없다: {mutation.field_name}"
                )
            proposal = mutation.field
            if proposal is None:
                raise EvolveOntologyError("modify mutation에 field가 없다")
            fields[index] = OntologyField(**proposal.model_dump())
        else:
            if index is None:
                raise EvolveOntologyError(
                    f"없는 ontology field를 remove할 수 없다: {mutation.field_name}"
                )
            fields.pop(index)

    return OntologySchema(
        name=ontology.name,
        description=ontology.description,
        fields=tuple(fields),
    )


def assemble_evolved_blueprint(
    *,
    parent: Blueprint,
    source: EvolveSourceSnapshot,
    wonder: WonderOutput,
    reflect: ReflectOutput,
    revision: int,
) -> Blueprint:
    """검증된 patch를 parent에 적용해 pending successor revision을 만든다."""

    scope_findings = check_evolve_scope(parent=parent, reflect=reflect)
    if scope_findings:
        raise ValueError("scope change finding은 successor 조립 전에 처리해야 한다")
    _validate_source(parent=parent, source=source, wonder=wonder)
    criteria = _evolve_criteria(
        parent=parent,
        source=source,
        wonder=wonder,
        reflect=reflect,
    )
    ontology = apply_ontology_mutations(ontology=parent.ontology, reflect=reflect)
    return Blueprint(
        mission_id=parent.mission_id,
        revision=revision,
        generation=parent.generation + 1,
        evolved_from_revision=parent.revision,
        brief_revision=parent.brief_revision,
        goal=parent.goal,
        constraints=parent.constraints,
        non_goals=parent.non_goals,
        acceptance_criteria=criteria,
        ontology=ontology,
    )
