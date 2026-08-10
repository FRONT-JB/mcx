"""Evolve use case — 실 Verify HOLD를 후속 Blueprint proposal로 조율한다.

호출자가 만든 source snapshot은 받지 않는다. application이 Blueprint·Execute·
Verify durable state를 읽어 exact current lineage와 Verify ``HOLD``를 재계산한
뒤 ``EvolveSourceSnapshot``으로 투영한다. 그 뒤 각 text 위임 전에
checkpoint를 저장하고, 완료 시 successor revision과 record를 한 BlueprintState
저장으로 묶는다 (ADR-0051 §1·§8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from mission_control.application.ports import (
    BlueprintRepository,
    EvolveReflector,
    EvolveWonderer,
    ExecuteRepository,
    ReflectRequest,
    VerifyRepository,
    WonderRequest,
)
from mission_control.domain.blueprint.evolution import (
    assemble_evolved_blueprint,
    check_evolve_scope,
)
from mission_control.domain.blueprint.state import BlueprintState, EvolutionNotAllowedError
from mission_control.domain.errors import MissionControlError
from mission_control.domain.evolve.models import (
    CriterionOutcomeSnapshot,
    EvolutionPhase,
    EvolveSourceSnapshot,
)
from mission_control.domain.execute.gate import evaluate_execute_gate
from mission_control.domain.execute.state import AttemptStatus, ExecuteState
from mission_control.domain.verify.evidence import VerifyState
from mission_control.domain.verify.gate import (
    evaluate_verify_gate,
    mechanical_failure_reason,
    proven_criteria,
)
from mission_control.domain.verify.verdict import SemanticPolicy


class EvolveBlueprintNotFoundError(LookupError):
    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}의 Blueprint가 없다")
        self.mission_id = mission_id


class EvolveEntryError(MissionControlError):
    """durable source가 Evolve entry contract를 충족하지 않는다."""

    def __init__(self, *, mission_id: str, reason: str) -> None:
        super().__init__(f"mission {mission_id}는 Evolve를 시작할 수 없다: {reason}")
        self.mission_id = mission_id
        self.reason = reason


def _reject(mission_id: str, reason: str) -> NoReturn:
    raise EvolveEntryError(mission_id=mission_id, reason=reason)


def project_evolve_source(
    *,
    blueprints: BlueprintState,
    executes: ExecuteState,
    verify: VerifyState,
    policy: SemanticPolicy,
) -> EvolveSourceSnapshot:
    """세 durable state를 exact current Verify ``HOLD`` snapshot으로 투영한다."""

    mission_id = blueprints.mission_id
    if executes.mission_id != mission_id or verify.mission_id != mission_id:
        _reject(mission_id, "Blueprint·Execute·Verify state의 mission identity가 다르다")
    if not blueprints.has_current_approval:
        _reject(mission_id, "current Blueprint revision에 exact user approval이 없다")

    blueprint = blueprints.current
    execute_decision = evaluate_execute_gate(state=executes, blueprint=blueprint)
    if execute_decision.outcome != "CLEAR":
        _reject(
            mission_id,
            "current Blueprint의 Execute Gate가 CLEAR가 아니다: "
            + "; ".join(execute_decision.blocking_reasons),
        )

    evidence = verify.evidence
    verdicts = verify.verdicts
    if evidence is None:
        _reject(mission_id, "Verify mechanical evidence가 없다")
    if verdicts is None:
        _reject(mission_id, "Verify semantic assessment가 없다")
    if (
        evidence.blueprint_revision != blueprint.revision
        or verdicts.blueprint_revision != blueprint.revision
    ):
        _reject(mission_id, "Verify evidence·assessment가 current Blueprint revision이 아니다")

    executed_numbers = tuple(
        attempt.number
        for attempt in executes.attempts
        if attempt.blueprint_revision == blueprint.revision
        and attempt.status is AttemptStatus.EXECUTED_UNVERIFIED
    )
    if evidence.execution_attempt_numbers != executed_numbers:
        _reject(
            mission_id,
            "Verify evidence의 execution attempt lineage가 current Execute state와 다르다",
        )

    criterion_keys = blueprint.criterion_keys
    mechanical_keys = tuple(
        item.key for item in blueprint.acceptance_criteria if item.is_mechanically_verifiable
    )
    run_keys = tuple(item.ac_key for item in evidence.runs)
    verdict_keys = tuple(item.ac_key for item in verdicts.verdicts)
    if len(run_keys) != len(mechanical_keys) or set(run_keys) != set(mechanical_keys):
        _reject(mission_id, "mechanical AC별 run이 정확히 하나씩 있지 않다")
    if len(verdict_keys) != len(criterion_keys) or set(verdict_keys) != set(criterion_keys):
        _reject(mission_id, "AC별 semantic verdict가 정확히 하나씩 있지 않다")

    gate = evaluate_verify_gate(
        evidence=evidence,
        verdicts=verdicts,
        blueprint=blueprint,
        policy=policy,
    )
    if gate.outcome != "HOLD":
        _reject(mission_id, "Verify Gate 재계산 결과가 HOLD가 아니다")

    proven = set(
        proven_criteria(
            evidence=evidence,
            verdicts=verdicts,
            blueprint=blueprint,
            policy=policy,
        )
    )
    criteria: list[CriterionOutcomeSnapshot] = []
    for criterion in blueprint.acceptance_criteria:
        run = evidence.run_for(criterion.key)
        verdict = verdicts.verdict_for(criterion.key)
        if verdict is None:  # exact-key 검사 뒤의 타입 narrowing.
            raise AssertionError(f"{criterion.key}의 semantic verdict가 사라졌다")
        evidence_refs = tuple(
            dict.fromkeys(
                ((run.output_ref,) if run is not None and run.output_ref else ()) + verdict.evidence
            )
        )
        criteria.append(
            CriterionOutcomeSnapshot(
                ac_key=criterion.key,
                mechanical_passed=(run.passed if run is not None else None),
                mechanical_detail=(
                    mechanical_failure_reason(criterion.key, run)
                    if run is not None and not run.passed
                    else None
                ),
                semantic_passed=verdict.passes(policy),
                semantic_score=verdict.score,
                semantic_uncertainty=verdict.uncertainty,
                reward_hacking_risk=verdict.reward_hacking_risk,
                semantic_reasoning=verdict.reasoning,
                evidence_refs=evidence_refs,
                proven=criterion.key in proven,
            )
        )

    return EvolveSourceSnapshot(
        mission_id=mission_id,
        blueprint_revision=blueprint.revision,
        blueprint_generation=blueprint.generation,
        verify_sequence=verify.sequence,
        gate_blockers=gate.blocking_reasons,
        execution_attempt_numbers=evidence.execution_attempt_numbers,
        criteria=tuple(criteria),
    )


@dataclass(frozen=True, slots=True)
class EvolveService:
    """vendor-neutral Wonder/Reflect를 durable successor proposal로 만든다."""

    repository: BlueprintRepository
    executes: ExecuteRepository
    verifies: VerifyRepository
    wonderer: EvolveWonderer
    reflector: EvolveReflector
    policy: SemanticPolicy

    async def propose(self, *, mission_id: str) -> BlueprintState:
        state = await self._require(mission_id)
        source = await self._project_source(mission_id=mission_id, blueprints=state)
        record = state.active_evolution
        if record is None:
            state = state.begin_evolution(source=source)
            await self.repository.save(state)
            record = state.active_evolution
        elif record.source != source:
            raise EvolutionNotAllowedError("진행 중인 Evolve checkpoint와 source가 다르다")

        if record is None:  # begin_evolution의 불변식을 타입 검사기에 드러낸다.
            raise AssertionError("Evolve checkpoint가 생성되지 않았다")
        parent = state.revisions[record.parent_blueprint_revision - 1]

        if record.phase is EvolutionPhase.WONDERING:
            wonder_output = await self.wonderer.wonder(
                WonderRequest(
                    goal=parent.goal,
                    constraints=parent.constraints,
                    non_goals=parent.non_goals,
                    acceptance_criteria=parent.acceptance_criteria,
                    ontology=parent.ontology,
                    source=record.source,
                    previous_wonders=tuple(
                        item.wonder for item in state.evolutions[:-1] if item.wonder is not None
                    ),
                )
            )
            state = state.record_wonder(output=wonder_output)
            await self.repository.save(state)
            record = state.active_evolution

        if record is None:
            raise AssertionError("Wonder checkpoint 뒤 active record가 사라졌다")
        if record.phase is EvolutionPhase.REFLECTING:
            recorded_wonder = record.wonder
            if recorded_wonder is None:
                raise AssertionError("Reflect request에 Wonder output이 없다")
            reflect_output = await self.reflector.reflect(
                ReflectRequest(
                    goal=parent.goal,
                    constraints=parent.constraints,
                    non_goals=parent.non_goals,
                    acceptance_criteria=parent.acceptance_criteria,
                    ontology=parent.ontology,
                    source=record.source,
                    wonder=recorded_wonder,
                )
            )
            state = state.record_reflect(output=reflect_output)
            await self.repository.save(state)
            record = state.active_evolution

        if record is None or record.phase is not EvolutionPhase.SEEDING:
            raise AssertionError("Reflect checkpoint가 seeding으로 진행하지 않았다")
        if record.scope_change_findings:
            return state
        recorded_wonder = record.wonder
        recorded_reflect = record.reflect
        if recorded_wonder is None or recorded_reflect is None:
            raise AssertionError("seeding checkpoint에 Wonder·Reflect output이 없다")

        scope_findings = check_evolve_scope(parent=parent, reflect=recorded_reflect)
        if scope_findings:
            state = state.hold_evolution_for_scope(findings=scope_findings)
            await self.repository.save(state)
            return state

        successor = assemble_evolved_blueprint(
            parent=parent,
            source=record.source,
            wonder=recorded_wonder,
            reflect=recorded_reflect,
            revision=state.revision + 1,
        )
        completed = state.complete_evolution(blueprint=successor)
        await self.repository.save(completed)
        return completed

    async def _require(self, mission_id: str) -> BlueprintState:
        state = await self.repository.load(mission_id)
        if state is None:
            raise EvolveBlueprintNotFoundError(mission_id)
        return state

    async def _project_source(
        self, *, mission_id: str, blueprints: BlueprintState
    ) -> EvolveSourceSnapshot:
        executes = await self.executes.load(mission_id)
        if executes is None:
            raise EvolveEntryError(mission_id=mission_id, reason="Execute state가 없다")
        verify = await self.verifies.load(mission_id)
        if verify is None:
            raise EvolveEntryError(mission_id=mission_id, reason="Verify state가 없다")
        return project_evolve_source(
            blueprints=blueprints,
            executes=executes,
            verify=verify,
            policy=self.policy,
        )
