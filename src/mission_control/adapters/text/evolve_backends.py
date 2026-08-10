"""Wonder/Reflect의 vendor-neutral ``CompletionEngine`` adapters.

LLM은 prompt 표시 좌표만 다룬다. Wonder의 1-based ``ac_refs``와 Reflect의
0-based ``index``는 이 파일을 벗어나기 전에 parent AC content key로 바뀐다.
도구 없는 text lane이며 workspace를 완성 엔진에 전달하지 않는다 (ADR-0051).
"""

from __future__ import annotations

import json
from typing import NoReturn

from mission_control.adapters.text.completion_engine import CompletionEngine, strict_schema
from mission_control.application.ports import ReflectRequest, WonderRequest
from mission_control.domain.blueprint.evolution import (
    EvolveOntologyError,
    apply_ontology_mutations,
)
from mission_control.domain.blueprint.spec import AcceptanceCriterion
from mission_control.domain.errors import MissionControlError
from mission_control.domain.evolve.models import (
    AcceptanceCriterionPatch,
    AcPatchOperation,
    ChallengeKind,
    CriterionOutcomeSnapshot,
    OntologyFieldProposal,
    OntologyMutation,
    OntologyMutationOperation,
    ReflectOutput,
    WonderChallenge,
    WonderOutput,
)


class EvolveAdapterError(MissionControlError):
    """구조화 응답이 Evolve의 identity·scope transport 계약을 어겼다."""

    def __init__(self, *, role: str, reason: str) -> None:
        super().__init__(f"{role} 응답을 Evolve proposal로 변환할 수 없다: {reason}")
        self.role = role
        self.reason = reason


def _reject(role: str, reason: str) -> NoReturn:
    raise EvolveAdapterError(role=role, reason=reason)


WONDER_SCHEMA = strict_schema(
    {
        "questions": {
            "type": "array",
            "items": strict_schema(
                {
                    "question": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": [item.value for item in ChallengeKind],
                    },
                    "ac_refs": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 1},
                        "description": (
                            "1-based parent AC references for challenge; empty for gap"
                        ),
                    },
                }
            ),
        },
        "reasoning": {"type": "string"},
    }
)


REFLECT_SCHEMA = strict_schema(
    {
        "refined_goal": {"type": "string"},
        "refined_constraints": {"type": "array", "items": {"type": "string"}},
        "ac_patches": {
            "type": "array",
            "items": strict_schema(
                {
                    "op": {
                        "type": "string",
                        "enum": [item.value for item in AcPatchOperation],
                    },
                    "index": {
                        "type": "integer",
                        "minimum": -1,
                        "description": "0-based parent index; -1 only for add",
                    },
                    "content": {
                        "type": "string",
                        "description": "replacement/add text; empty only for keep",
                    },
                    "reason": {"type": "string"},
                }
            ),
        },
        "ontology_mutations": {
            "type": "array",
            "items": strict_schema(
                {
                    "action": {
                        "type": "string",
                        "enum": [item.value for item in OntologyMutationOperation],
                    },
                    "field_name": {"type": "string"},
                    "field_type": {
                        "type": "string",
                        "description": "full replacement type; empty only for remove",
                    },
                    "description": {
                        "type": "string",
                        "description": "full replacement description; empty only for remove",
                    },
                    "required": {
                        "type": "boolean",
                        "description": "replacement value; false sentinel for remove",
                    },
                    "reason": {"type": "string"},
                }
            ),
        },
        "reasoning": {"type": "string"},
    }
)


_WONDER_ROLE = """\
You are the Wonder role for a bounded successor Blueprint proposal. Identify
what the verified result still leaves unknown. Ask ontological questions about
what must be true, not implementation questions about how to code it.

Every question must be grounded:
- challenge: cite one or more CURRENT acceptance criteria with 1-based ac_refs.
- gap: name something required by the Goal that no current AC covers, with an
  empty ac_refs array.
- Challenge a proven AC only when the supplied evidence concretely contradicts it.
- Stay inside Goal, Constraints, and Non-goals. Ontology incompleteness by itself
  is not a gap. Do not propose unrelated concepts or implementation mechanisms."""


_REFLECT_ROLE = """\
You are the Reflect role for a bounded successor Blueprint proposal. Convert the
Wonder questions and Verify evidence into an explicit acceptance-criterion patch
and ontology mutations.

Rules:
- Copy refined_goal and refined_constraints verbatim unless you are explicitly
  proposing a user-owned scope change. Such a proposal will HOLD for user review.
- Address parent ACs by 0-based index. Emit one keep/revise patch for EVERY parent
  index in current order, then add patches only at the tail.
- keep: index plus empty content. revise: index plus full replacement description.
- add: index -1 plus full new description. Delete and reorder do not exist.
- Proven, unchallenged ACs are protected and must be kept verbatim.
- Do not invent verify commands or artifact contracts; application preserves them.
- Ontology add/modify must provide the full replacement field name, type,
  description, and required flag. remove uses empty type/description and required=false.
- Change only what the failure evidence or grounded Wonder questions require."""


def _direction_lines(request: WonderRequest | ReflectRequest) -> list[str]:
    return [
        "## Parent direction (hard boundary)",
        "Goal: " + json.dumps(request.goal, ensure_ascii=False),
        "Constraints: " + json.dumps(request.constraints, ensure_ascii=False),
        "Non-goals: " + json.dumps(request.non_goals, ensure_ascii=False),
    ]


def _criterion_context(
    request: WonderRequest | ReflectRequest,
) -> tuple[tuple[AcceptanceCriterion, CriterionOutcomeSnapshot], ...]:
    criteria = request.acceptance_criteria
    keys = tuple(item.key for item in criteria)
    source_keys = tuple(item.ac_key for item in request.source.criteria)
    if len(source_keys) != len(keys) or set(source_keys) != set(keys):
        _reject("Evolve", "source outcome과 parent AC identity가 정확히 일치하지 않는다")

    pairs: list[tuple[AcceptanceCriterion, CriterionOutcomeSnapshot]] = []
    for criterion in criteria:
        outcome = request.source.outcome_for(criterion.key)
        if outcome is None:
            _reject("Evolve", f"{criterion.key}의 source outcome이 없다")
        pairs.append((criterion, outcome))
    return tuple(pairs)


def _criteria_lines(request: WonderRequest | ReflectRequest) -> list[str]:
    lines = ["## Parent acceptance criteria and Verify outcomes"]
    for index, (criterion, outcome) in enumerate(_criterion_context(request)):
        lines.extend(
            [
                f"AC {index + 1} (Reflect index {index})",
                "  description: " + criterion.description,
                f"  proven: {str(outcome.proven).lower()}",
                f"  mechanical_passed: {outcome.mechanical_passed}",
                f"  semantic_passed: {str(outcome.semantic_passed).lower()}",
                f"  semantic_score: {outcome.semantic_score:.3f}",
                f"  semantic_uncertainty: {outcome.semantic_uncertainty:.3f}",
                f"  reward_hacking_risk: {outcome.reward_hacking_risk:.3f}",
                "  semantic_reasoning: " + outcome.semantic_reasoning,
            ]
        )
        if outcome.mechanical_detail:
            lines.append("  mechanical_detail: " + outcome.mechanical_detail)
        if outcome.evidence_refs:
            lines.append("  evidence_refs: " + json.dumps(outcome.evidence_refs))
        if criterion.verify_command:
            lines.append("  immutable verify_command: " + criterion.verify_command)
        if criterion.expected_artifacts:
            lines.append(
                "  immutable expected_artifacts: "
                + json.dumps(criterion.expected_artifacts)
            )
        if criterion.output_assertion:
            lines.append("  immutable output_assertion: " + criterion.output_assertion)
    return lines


def _ontology_lines(request: WonderRequest | ReflectRequest) -> list[str]:
    lines = [
        "## Current ontology",
        "name: " + request.ontology.name,
        "description: " + request.ontology.description,
    ]
    if not request.ontology.fields:
        lines.append("fields: (none)")
    else:
        lines.append("fields:")
        lines.extend(
            f"- {item.name}: {item.field_type}; required={str(item.required).lower()}; "
            f"{item.description}"
            for item in request.ontology.fields
        )
    return lines


def _source_lines(request: WonderRequest | ReflectRequest) -> list[str]:
    return [
        "## Verify HOLD source",
        f"generation: {request.source.blueprint_generation}",
        f"blueprint_revision: {request.source.blueprint_revision}",
        f"verify_sequence: {request.source.verify_sequence}",
        "execution_attempt_numbers: "
        + json.dumps(request.source.execution_attempt_numbers),
        "gate_blockers:",
        *(f"- {item}" for item in request.source.gate_blockers),
    ]


def render_wonder_prompt(request: WonderRequest) -> str:
    parts = [
        _WONDER_ROLE,
        *_direction_lines(request),
        *_criteria_lines(request),
        *_ontology_lines(request),
        *_source_lines(request),
    ]
    if request.previous_wonders:
        parts.append("## Previous Wonder lineage")
        for number, wonder in enumerate(request.previous_wonders, start=1):
            parts.append(f"Generation {number}: {wonder.reasoning}")
            parts.extend(
                "- "
                + item.kind.value
                + (f"[{item.parent_ac_key}]" if item.parent_ac_key else "")
                + ": "
                + item.detail
                for item in wonder.challenges
            )
    parts.extend(
        [
            "## Your task",
            "Return only grounded questions and concise reasoning. An empty questions "
            "array is valid only when no in-scope unknown remains.",
        ]
    )
    return "\n".join(parts)


def render_reflect_prompt(request: ReflectRequest) -> str:
    unknown = request.wonder.challenged_keys - {
        item.key for item in request.acceptance_criteria
    }
    if unknown:
        _reject("Reflect", "Wonder가 current parent에 없는 AC key를 challenge했다")

    parts = [
        _REFLECT_ROLE,
        *_direction_lines(request),
        *_criteria_lines(request),
        *_ontology_lines(request),
        *_source_lines(request),
        "## Wonder output",
        "reasoning: " + request.wonder.reasoning,
    ]
    parts.extend(
        "- "
        + item.kind.value
        + (f"[{item.parent_ac_key}]" if item.parent_ac_key else "")
        + ": "
        + item.detail
        for item in request.wonder.challenges
    )
    parts.extend(
        [
            "## Your task",
            "Return the complete ordered AC patch and only the ontology mutations "
            "required by the evidence and Wonder output.",
        ]
    )
    return "\n".join(parts)


def _strict_integer(value: object, *, role: str, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _reject(role, f"{field}는 integer여야 한다")
    return value


def _strict_text(value: object, *, role: str, field: str, empty: bool = False) -> str:
    if not isinstance(value, str):
        _reject(role, f"{field}는 string이어야 한다")
    text = value.strip()
    if not empty and not text:
        _reject(role, f"{field}는 비어 있을 수 없다")
    return text


def _parse_wonder(request: WonderRequest, data: dict[str, object]) -> WonderOutput:
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list):
        _reject("Wonder", "questions는 array여야 한다")

    challenges: list[WonderChallenge] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            _reject("Wonder", "questions의 각 항목은 object여야 한다")
        detail = _strict_text(item.get("question"), role="Wonder", field="question")
        raw_kind = _strict_text(
            item.get("kind"), role="Wonder", field="question kind"
        )
        try:
            kind = ChallengeKind(raw_kind)
        except (TypeError, ValueError):
            _reject("Wonder", f"알 수 없는 question kind다: {item.get('kind')!r}")
        raw_refs = item.get("ac_refs")
        if not isinstance(raw_refs, list):
            _reject("Wonder", "ac_refs는 array여야 한다")

        if kind is ChallengeKind.GAP:
            if raw_refs:
                _reject("Wonder", "gap은 parent AC ref를 가질 수 없다")
            challenges.append(WonderChallenge(kind=kind, detail=detail))
            continue
        if not raw_refs:
            _reject("Wonder", "challenge에는 하나 이상의 parent AC ref가 필요하다")

        seen: set[int] = set()
        for raw_ref in raw_refs:
            one_based = _strict_integer(raw_ref, role="Wonder", field="ac_ref")
            index = one_based - 1
            if index < 0 or index >= len(request.acceptance_criteria):
                _reject("Wonder", f"parent AC ref {one_based}가 범위를 벗어났다")
            if index in seen:
                continue
            seen.add(index)
            challenges.append(
                WonderChallenge(
                    kind=kind,
                    parent_ac_key=request.acceptance_criteria[index].key,
                    detail=detail,
                )
            )

    reasoning = _strict_text(data.get("reasoning"), role="Wonder", field="reasoning")
    return WonderOutput(challenges=tuple(challenges), reasoning=reasoning)


def _parse_reflect(request: ReflectRequest, data: dict[str, object]) -> ReflectOutput:
    context = _criterion_context(request)
    protected = {
        criterion.key
        for criterion, outcome in context
        if outcome.proven and criterion.key not in request.wonder.challenged_keys
    }

    raw_patches = data.get("ac_patches")
    if not isinstance(raw_patches, list):
        _reject("Reflect", "ac_patches는 array여야 한다")
    patches: list[AcceptanceCriterionPatch] = []
    parent_indices: list[int] = []
    add_started = False
    for item in raw_patches:
        if not isinstance(item, dict):
            _reject("Reflect", "ac_patches의 각 항목은 object여야 한다")
        raw_operation = _strict_text(item.get("op"), role="Reflect", field="patch op")
        try:
            patch_operation = AcPatchOperation(raw_operation)
        except (TypeError, ValueError):
            _reject("Reflect", f"알 수 없는 patch op다: {item.get('op')!r}")
        index = _strict_integer(item.get("index"), role="Reflect", field="patch index")
        content = _strict_text(
            item.get("content"), role="Reflect", field="patch content", empty=True
        )

        if patch_operation is AcPatchOperation.ADD:
            add_started = True
            if index != -1:
                _reject("Reflect", "add patch index는 transport sentinel -1이어야 한다")
            if not content:
                _reject("Reflect", "add patch에는 새 AC content가 필요하다")
            patches.append(
                AcceptanceCriterionPatch(operation=patch_operation, description=content)
            )
            continue

        if add_started:
            _reject("Reflect", "keep/revise patch는 add 뒤에 올 수 없다")
        if index < 0 or index >= len(context):
            _reject("Reflect", f"parent AC index {index}가 범위를 벗어났다")
        expected = len(parent_indices)
        if index != expected:
            _reject(
                "Reflect",
                f"parent AC는 index {expected}가 와야 하는데 {index}가 왔다",
            )
        parent_indices.append(index)
        criterion = context[index][0]
        if patch_operation is AcPatchOperation.KEEP:
            if content:
                _reject("Reflect", "keep patch content는 빈 문자열이어야 한다")
            patches.append(
                AcceptanceCriterionPatch(
                    operation=patch_operation,
                    parent_ac_key=criterion.key,
                )
            )
            continue

        if not content:
            _reject("Reflect", "revise patch에는 replacement content가 필요하다")
        if criterion.key in protected:
            patches.append(
                AcceptanceCriterionPatch(
                    operation=AcPatchOperation.KEEP,
                    parent_ac_key=criterion.key,
                )
            )
            continue
        if content == criterion.description:
            _reject("Reflect", f"index {index}의 revise가 description을 바꾸지 않았다")
        patches.append(
            AcceptanceCriterionPatch(
                operation=patch_operation,
                parent_ac_key=criterion.key,
                description=content,
            )
        )

    if parent_indices != list(range(len(context))):
        _reject("Reflect", "모든 parent AC index가 순서대로 정확히 한 번 필요하다")

    raw_mutations = data.get("ontology_mutations")
    if not isinstance(raw_mutations, list):
        _reject("Reflect", "ontology_mutations는 array여야 한다")
    mutations: list[OntologyMutation] = []
    mutation_targets: set[str] = set()
    for item in raw_mutations:
        if not isinstance(item, dict):
            _reject("Reflect", "ontology_mutations의 각 항목은 object여야 한다")
        raw_action = _strict_text(
            item.get("action"), role="Reflect", field="ontology action"
        )
        try:
            mutation_operation = OntologyMutationOperation(raw_action)
        except (TypeError, ValueError):
            _reject("Reflect", f"알 수 없는 ontology action이다: {item.get('action')!r}")
        field_name = _strict_text(
            item.get("field_name"), role="Reflect", field="ontology field_name"
        )
        if field_name in mutation_targets:
            _reject("Reflect", f"ontology field {field_name}를 두 번 바꿀 수 없다")
        mutation_targets.add(field_name)
        field_type = _strict_text(
            item.get("field_type"),
            role="Reflect",
            field="ontology field_type",
            empty=True,
        )
        description = _strict_text(
            item.get("description"),
            role="Reflect",
            field="ontology description",
            empty=True,
        )
        required = item.get("required")
        if not isinstance(required, bool):
            _reject("Reflect", "ontology required는 boolean이어야 한다")

        if mutation_operation is OntologyMutationOperation.REMOVE:
            if field_type or description or required:
                _reject(
                    "Reflect",
                    "remove mutation은 빈 type/description과 required=false를 써야 한다",
                )
            mutations.append(
                OntologyMutation(
                    operation=mutation_operation,
                    field_name=field_name,
                )
            )
            continue
        if not field_type or not description:
            _reject("Reflect", "add/modify mutation에는 full replacement field가 필요하다")
        mutations.append(
            OntologyMutation(
                operation=mutation_operation,
                field_name=field_name,
                field=OntologyFieldProposal(
                    name=field_name,
                    field_type=field_type,
                    description=description,
                    required=required,
                ),
            )
        )

    refined_goal = _strict_text(
        data.get("refined_goal"), role="Reflect", field="refined_goal"
    )
    raw_constraints = data.get("refined_constraints")
    if not isinstance(raw_constraints, list):
        _reject("Reflect", "refined_constraints는 array여야 한다")
    constraints = tuple(
        _strict_text(item, role="Reflect", field="refined_constraint")
        for item in raw_constraints
    )
    reasoning = _strict_text(data.get("reasoning"), role="Reflect", field="reasoning")

    settled = tuple(
        patch.parent_ac_key
        for patch in patches
        if patch.operation is AcPatchOperation.KEEP
        and patch.parent_ac_key is not None
        and patch.parent_ac_key in protected
    )
    output = ReflectOutput(
        refined_goal=refined_goal,
        refined_constraints=constraints,
        ac_patches=tuple(patches),
        ontology_mutations=tuple(mutations),
        settled_ac_keys=settled,
        reasoning=reasoning,
    )
    try:
        apply_ontology_mutations(ontology=request.ontology, reflect=output)
    except EvolveOntologyError as error:
        raise EvolveAdapterError(role="Reflect", reason=str(error)) from error
    return output


class PromptedEvolveWonderer:
    """CompletionEngine 출력을 grounded Wonder proposal로 바꾼다."""

    def __init__(self, *, completion: CompletionEngine) -> None:
        self._completion = completion

    def render_prompt(self, request: WonderRequest) -> str:
        return render_wonder_prompt(request)

    async def wonder(self, request: WonderRequest) -> WonderOutput:
        data = await self._completion.complete_json(
            prompt=self.render_prompt(request),
            schema=WONDER_SCHEMA,
        )
        return _parse_wonder(request, data)


class PromptedEvolveReflector:
    """CompletionEngine 출력을 content-key Reflect proposal로 바꾼다."""

    def __init__(self, *, completion: CompletionEngine) -> None:
        self._completion = completion

    def render_prompt(self, request: ReflectRequest) -> str:
        return render_reflect_prompt(request)

    async def reflect(self, request: ReflectRequest) -> ReflectOutput:
        data = await self._completion.complete_json(
            prompt=self.render_prompt(request),
            schema=REFLECT_SCHEMA,
        )
        return _parse_reflect(request, data)
