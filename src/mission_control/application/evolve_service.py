"""Evolve use case — Wonder→Reflect checkpoint와 successor Blueprint 조율.

이 첫 vertical slice는 application이 이미 투영한 ``EvolveSourceSnapshot``을
입력으로 받는다. Execute·Verify 저장소에서 snapshot을 만드는 합성은 다음
integration slice의 책임이다. 여기서는 각 위임 **전에** checkpoint를 저장하고,
완료 시 successor revision과 record를 한 BlueprintState 저장으로 묶는다
(ADR-0051 §8).
"""

from __future__ import annotations

from dataclasses import dataclass

from mission_control.application.ports import (
    BlueprintRepository,
    EvolveReflector,
    EvolveWonderer,
    ReflectRequest,
    WonderRequest,
)
from mission_control.domain.blueprint.evolution import (
    assemble_evolved_blueprint,
    check_evolve_scope,
)
from mission_control.domain.blueprint.state import BlueprintState, EvolutionNotAllowedError
from mission_control.domain.evolve.models import EvolutionPhase, EvolveSourceSnapshot


class EvolveBlueprintNotFoundError(LookupError):
    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}의 Blueprint가 없다")
        self.mission_id = mission_id


@dataclass(frozen=True, slots=True)
class EvolveService:
    """vendor-neutral Wonder/Reflect를 durable successor proposal로 만든다."""

    repository: BlueprintRepository
    wonderer: EvolveWonderer
    reflector: EvolveReflector

    async def propose(
        self, *, mission_id: str, source: EvolveSourceSnapshot
    ) -> BlueprintState:
        state = await self._require(mission_id)
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
                        item.wonder
                        for item in state.evolutions[:-1]
                        if item.wonder is not None
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
