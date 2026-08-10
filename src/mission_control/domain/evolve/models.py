"""Evolve 중립 모델 — Verify 결과를 후속 Blueprint 제안으로 잇는 기록.

이 패키지는 canonical Stage가 아니다. Blueprint·Execute·Verify의 구체 타입을
import하지 않고 application이 투영한 값만 받는다. 그래야 Blueprint 상태가
``EvolutionRecord``를 품어도 역방향 의존이 생기지 않는다 (ADR-0051 §8).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mission_control.security import redact_credentials


class CriterionOutcomeSnapshot(BaseModel):
    """parent AC 하나의 Verify 결과를 vendor-neutral 값으로 고정한다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ac_key: str = Field(min_length=1)
    mechanical_passed: bool | None
    mechanical_detail: str | None = None
    semantic_passed: bool
    semantic_score: float = Field(ge=0.0, le=1.0)
    semantic_uncertainty: float = Field(ge=0.0, le=1.0)
    reward_hacking_risk: float = Field(ge=0.0, le=1.0)
    semantic_reasoning: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
    proven: bool

    @field_validator("mechanical_detail", "semantic_reasoning", mode="after")
    @classmethod
    def _mask_credentials(cls, value: str | None) -> str | None:
        return value if value is None else redact_credentials(value)

    @model_validator(mode="after")
    def _proven_means_both_required_layers_passed(self) -> CriterionOutcomeSnapshot:
        if self.proven and (not self.semantic_passed or self.mechanical_passed is False):
            raise ValueError("proven AC는 필요한 mechanical·semantic 판정을 통과해야 한다")
        if self.mechanical_passed is False and not self.mechanical_detail:
            raise ValueError("mechanical 실패 outcome에는 detail이 필요하다")
        return self


class EvolveSourceSnapshot(BaseModel):
    """Wonder/Reflect가 읽는 Execute·Verify 입력의 고정 projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mission_id: str = Field(min_length=1)
    mission_status: Literal["active"] = "active"
    blueprint_revision: int = Field(ge=1)
    blueprint_generation: int = Field(ge=1)
    verify_sequence: int = Field(ge=1)
    verify_gate: Literal["HOLD"] = "HOLD"
    gate_blockers: tuple[str, ...] = Field(min_length=1)
    execution_attempt_numbers: tuple[int, ...] = Field(min_length=1)
    criteria: tuple[CriterionOutcomeSnapshot, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _criterion_keys_are_unique(self) -> EvolveSourceSnapshot:
        keys = [item.ac_key for item in self.criteria]
        if len(keys) != len(set(keys)):
            raise ValueError("Evolve source에는 같은 AC outcome이 둘 이상 있을 수 없다")
        if len(self.execution_attempt_numbers) != len(set(self.execution_attempt_numbers)):
            raise ValueError("execution attempt number는 중복될 수 없다")
        return self

    def outcome_for(self, ac_key: str) -> CriterionOutcomeSnapshot | None:
        for item in self.criteria:
            if item.ac_key == ac_key:
                return item
        return None


class ChallengeKind(StrEnum):
    CHALLENGE = "challenge"
    GAP = "gap"


class WonderChallenge(BaseModel):
    """Wonder가 parent AC를 공격하거나 Goal의 빈틈을 제안한 한 항목."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ChallengeKind
    detail: str = Field(min_length=1)
    parent_ac_key: str | None = None

    @model_validator(mode="after")
    def _challenge_is_grounded(self) -> WonderChallenge:
        if self.kind is ChallengeKind.CHALLENGE and self.parent_ac_key is None:
            raise ValueError("challenge에는 parent_ac_key가 필요하다")
        if self.kind is ChallengeKind.GAP and self.parent_ac_key is not None:
            raise ValueError("gap은 parent AC에 가장하지 않는다")
        return self


class WonderOutput(BaseModel):
    """Wonder의 도구 없는 제안. 판정이나 승인을 담지 않는다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    challenges: tuple[WonderChallenge, ...] = ()
    reasoning: str = Field(min_length=1)

    @property
    def challenged_keys(self) -> frozenset[str]:
        return frozenset(
            item.parent_ac_key
            for item in self.challenges
            if item.parent_ac_key is not None
        )


class AcPatchOperation(StrEnum):
    KEEP = "keep"
    REVISE = "revise"
    ADD = "add"


class AcceptanceCriterionPatch(BaseModel):
    """Reflect의 explicit AC patch. 위치 index는 이미 content key로 변환됐다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: AcPatchOperation
    parent_ac_key: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _fields_match_the_operation(self) -> AcceptanceCriterionPatch:
        if self.operation is AcPatchOperation.KEEP:
            if self.parent_ac_key is None or self.description is not None:
                raise ValueError("keep에는 parent_ac_key만 필요하다")
        elif self.operation is AcPatchOperation.REVISE:
            if self.parent_ac_key is None or not self.description:
                raise ValueError("revise에는 parent_ac_key와 새 description이 필요하다")
        elif self.parent_ac_key is not None or not self.description:
            raise ValueError("add에는 description만 필요하다")
        return self


class OntologyMutationOperation(StrEnum):
    ADD = "add"
    MODIFY = "modify"
    REMOVE = "remove"


class OntologyFieldProposal(BaseModel):
    """Blueprint OntologyField로 조립하기 전의 중립 제안."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    field_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required: bool


class OntologyMutation(BaseModel):
    """ontology field 하나에 대한 add·modify·remove."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: OntologyMutationOperation
    field_name: str = Field(min_length=1)
    field: OntologyFieldProposal | None = None

    @model_validator(mode="after")
    def _field_matches_the_operation(self) -> OntologyMutation:
        if self.operation is OntologyMutationOperation.REMOVE:
            if self.field is not None:
                raise ValueError("remove는 replacement field를 가질 수 없다")
        else:
            if self.field is None:
                raise ValueError("add·modify에는 field가 필요하다")
            if self.field.name != self.field_name:
                raise ValueError("mutation field_name과 field.name이 같아야 한다")
        return self


class ReflectOutput(BaseModel):
    """Reflect의 구조화된 제안. application이 결정적으로 검증·조립한다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    refined_goal: str = Field(min_length=1)
    refined_constraints: tuple[str, ...]
    ac_patches: tuple[AcceptanceCriterionPatch, ...] = Field(min_length=1)
    ontology_mutations: tuple[OntologyMutation, ...] = ()
    settled_ac_keys: tuple[str, ...] = ()
    reasoning: str = Field(min_length=1)

    @model_validator(mode="after")
    def _declared_identities_are_unique(self) -> ReflectOutput:
        parent_keys = [
            item.parent_ac_key
            for item in self.ac_patches
            if item.parent_ac_key is not None
        ]
        if len(parent_keys) != len(set(parent_keys)):
            raise ValueError("Reflect patch는 parent AC를 중복 참조할 수 없다")
        targets = [item.field_name for item in self.ontology_mutations]
        if len(targets) != len(set(targets)):
            raise ValueError("한 Reflect output에서 같은 ontology field를 두 번 바꿀 수 없다")
        if len(self.settled_ac_keys) != len(set(self.settled_ac_keys)):
            raise ValueError("settled_ac_keys는 중복될 수 없다")
        return self


class ScopeChangeKind(StrEnum):
    GOAL = "goal"
    CONSTRAINTS = "constraints"


class ScopeChangeFinding(BaseModel):
    """Reflect가 사용자 소유 방향을 바꾸려 한 durable finding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ScopeChangeKind
    current: str
    proposed: str


class EvolutionPhase(StrEnum):
    WONDERING = "wondering"
    REFLECTING = "reflecting"
    SEEDING = "seeding"
    COMPLETED = "completed"


class EvolutionRecord(BaseModel):
    """한 successor generation의 partial-phase durable checkpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    successor_generation: int = Field(ge=2)
    parent_blueprint_revision: int = Field(ge=1)
    source: EvolveSourceSnapshot
    phase: EvolutionPhase = EvolutionPhase.WONDERING
    wonder: WonderOutput | None = None
    reflect: ReflectOutput | None = None
    result_blueprint_revision: int | None = Field(default=None, ge=1)
    scope_change_findings: tuple[ScopeChangeFinding, ...] = ()

    @model_validator(mode="after")
    def _phase_matches_the_outputs(self) -> EvolutionRecord:
        if self.successor_generation != self.source.blueprint_generation + 1:
            raise ValueError("successor generation은 source generation의 다음 값이어야 한다")
        if self.parent_blueprint_revision != self.source.blueprint_revision:
            raise ValueError("record parent와 source Blueprint revision이 같아야 한다")
        if self.phase is EvolutionPhase.WONDERING:
            if self.wonder is not None or self.reflect is not None:
                raise ValueError("wondering checkpoint에는 phase output이 아직 없어야 한다")
        elif self.phase is EvolutionPhase.REFLECTING:
            if self.wonder is None or self.reflect is not None:
                raise ValueError("reflecting checkpoint에는 Wonder output만 있어야 한다")
        elif self.phase is EvolutionPhase.SEEDING:
            if self.wonder is None or self.reflect is None:
                raise ValueError("seeding checkpoint에는 Wonder·Reflect output이 필요하다")
        elif self.wonder is None or self.reflect is None or self.result_blueprint_revision is None:
            raise ValueError("completed record에는 두 output과 result revision이 필요하다")

        if (
            self.phase is not EvolutionPhase.COMPLETED
            and self.result_blueprint_revision is not None
        ):
            raise ValueError("완료 전에는 result Blueprint revision을 기록할 수 없다")
        if self.scope_change_findings and self.phase is not EvolutionPhase.SEEDING:
            raise ValueError("scope change finding은 seeding HOLD에만 기록한다")
        return self

    @classmethod
    def start(cls, *, source: EvolveSourceSnapshot) -> EvolutionRecord:
        return cls(
            successor_generation=source.blueprint_generation + 1,
            parent_blueprint_revision=source.blueprint_revision,
            source=source,
        )

    def record_wonder(self, output: WonderOutput) -> EvolutionRecord:
        if self.phase is not EvolutionPhase.WONDERING:
            raise ValueError("Wonder output을 기다리는 checkpoint가 아니다")
        return EvolutionRecord.model_validate(
            self.model_dump() | {"phase": EvolutionPhase.REFLECTING, "wonder": output}
        )

    def record_reflect(self, output: ReflectOutput) -> EvolutionRecord:
        if self.phase is not EvolutionPhase.REFLECTING:
            raise ValueError("Reflect output을 기다리는 checkpoint가 아니다")
        return EvolutionRecord.model_validate(
            self.model_dump() | {"phase": EvolutionPhase.SEEDING, "reflect": output}
        )

    def hold_for_scope(self, findings: tuple[ScopeChangeFinding, ...]) -> EvolutionRecord:
        if self.phase is not EvolutionPhase.SEEDING or not findings:
            raise ValueError("seeding checkpoint의 scope finding이 필요하다")
        return EvolutionRecord.model_validate(
            self.model_dump() | {"scope_change_findings": findings}
        )

    def complete(self, *, result_blueprint_revision: int) -> EvolutionRecord:
        if self.phase is not EvolutionPhase.SEEDING or self.scope_change_findings:
            raise ValueError("scope HOLD가 없는 seeding checkpoint만 완료할 수 있다")
        return EvolutionRecord.model_validate(
            self.model_dump()
            | {
                "phase": EvolutionPhase.COMPLETED,
                "result_blueprint_revision": result_blueprint_revision,
            }
        )
