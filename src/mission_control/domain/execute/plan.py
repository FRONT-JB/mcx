"""Execute 실행 순서 — 순차 next와 durable parallel stage plan.

순차 ``execute next``는 승인된 Blueprint의 선언 순서를 유지한다
(``docs/adr/0024-execute-v1-execution-model.md`` §3). 병렬 ``execute stage``는
strict dependency 응답을 결정적 topological stage로 만들고 승인 revision에
고정한다 (ADR-0053). 선택과 readiness 계산은 모두 순수 함수로 남는다.

계약: ``docs/07_EXECUTE.md`` §6.3, §6.4
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.errors import MissionControlError

if TYPE_CHECKING:
    from mission_control.domain.execute.state import ExecuteState


class DependencyPlanError(MissionControlError):
    """dependency 응답을 현재 Blueprint의 안전한 stage plan으로 만들 수 없다."""


class CriterionDependency(BaseModel):
    """AC 하나의 direct dependency. AC identity는 content key다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ac_key: str = Field(min_length=1)
    depends_on: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _edges_are_unique_and_not_self_referential(self) -> CriterionDependency:
        if self.ac_key in self.depends_on:
            raise ValueError(f"{self.ac_key}가 자기 자신에 의존할 수 없다")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError(f"{self.ac_key}의 dependency가 중복된다")
        return self


class ParallelExecutionPlan(BaseModel):
    """승인된 Blueprint revision 전체에 고정된 불변 stage plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str = Field(min_length=1)
    blueprint_revision: int = Field(ge=1)
    analyzer_backend: str = Field(min_length=1)
    dependencies: tuple[CriterionDependency, ...]
    stages: tuple[tuple[str, ...], ...]

    @model_validator(mode="after")
    def _stages_cover_dependencies_once(self) -> ParallelExecutionPlan:
        dependency_keys = tuple(item.ac_key for item in self.dependencies)
        if len(dependency_keys) != len(set(dependency_keys)):
            raise ValueError("plan의 AC key가 중복된다")
        stage_keys = tuple(key for stage in self.stages for key in stage)
        if len(stage_keys) != len(set(stage_keys)):
            raise ValueError("stage의 AC key가 중복된다")
        if set(stage_keys) != set(dependency_keys):
            raise ValueError("stage는 dependency plan의 AC를 정확히 한 번씩 포함해야 한다")
        known = set(dependency_keys)
        positions = {key: index for index, stage in enumerate(self.stages) for key in stage}
        for item in self.dependencies:
            unknown = set(item.depends_on) - known
            if unknown:
                raise ValueError(
                    f"{item.ac_key}가 unknown dependency를 가리킨다: {sorted(unknown)}"
                )
            if any(positions[parent] >= positions[item.ac_key] for parent in item.depends_on):
                raise ValueError(f"{item.ac_key}의 dependency가 앞 stage에 있지 않다")
        return self

    def dependency_for(self, ac_key: str) -> tuple[str, ...]:
        for item in self.dependencies:
            if item.ac_key == ac_key:
                return item.depends_on
        raise KeyError(ac_key)


class PlanReadiness(BaseModel):
    """현재 attempt 결과에서 결정적으로 계산한 다음 실행 가능 stage."""

    model_config = ConfigDict(frozen=True)

    stage_index: int | None = Field(default=None, ge=0)
    ready_ac_keys: tuple[str, ...] = ()
    blocked_ac_keys: tuple[str, ...] = ()


def build_parallel_plan(
    *,
    blueprint: Blueprint,
    dependencies: tuple[CriterionDependency, ...],
    analyzer_backend: str,
) -> ParallelExecutionPlan:
    """strict dependency 응답을 선언 순서 보존 topological stage로 바꾼다.

    누락·중복·unknown·cycle은 전부 오류다. unknown을 독립성으로 바꾸는 fallback은
    없다 (ADR-0052·0053).
    """
    expected = blueprint.criterion_keys
    actual = tuple(item.ac_key for item in dependencies)
    if len(actual) != len(set(actual)):
        raise DependencyPlanError("dependency 응답에 중복 AC가 있다")
    if set(actual) != set(expected):
        missing = tuple(key for key in expected if key not in actual)
        unknown = tuple(key for key in actual if key not in expected)
        raise DependencyPlanError(
            f"dependency 응답이 현재 Blueprint와 다르다; missing={missing}, unknown={unknown}"
        )

    known = set(expected)
    by_key = {item.ac_key: item for item in dependencies}
    for key in expected:
        unknown_dependencies = set(by_key[key].depends_on) - known
        if unknown_dependencies:
            raise DependencyPlanError(
                f"{key}가 unknown dependency를 가리킨다: {sorted(unknown_dependencies)}"
            )

    remaining = set(expected)
    resolved: set[str] = set()
    stages: list[tuple[str, ...]] = []
    while remaining:
        ready = tuple(
            key
            for key in expected
            if key in remaining and set(by_key[key].depends_on).issubset(resolved)
        )
        if not ready:
            raise DependencyPlanError(f"dependency cycle이 있다: {tuple(sorted(remaining))}")
        stages.append(ready)
        remaining.difference_update(ready)
        resolved.update(ready)

    payload = {
        "revision": blueprint.revision,
        "dependencies": [item.model_dump(mode="json") for item in dependencies],
        "stages": stages,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return ParallelExecutionPlan(
        plan_id=f"plan_{digest}",
        blueprint_revision=blueprint.revision,
        analyzer_backend=analyzer_backend,
        dependencies=tuple(by_key[key] for key in expected),
        stages=tuple(stages),
    )


def plan_readiness(
    *, blueprint: Blueprint, plan: ParallelExecutionPlan, state: ExecuteState
) -> PlanReadiness:
    """실패 의존자는 BLOCKED로 닫고 가장 이른 ready stage를 고른다."""
    from mission_control.domain.execute.state import AttemptStatus

    succeeded: set[str] = set()
    failed: set[str] = set()
    open_keys: set[str] = set()
    for criterion in blueprint.acceptance_criteria:
        latest = state.latest_for(ac_key=criterion.key, blueprint_revision=blueprint.revision)
        if latest is None:
            continue
        if latest.status is AttemptStatus.EXECUTED_UNVERIFIED:
            succeeded.add(criterion.key)
        elif latest.status is AttemptStatus.EXECUTION_FAILED:
            failed.add(criterion.key)
        else:
            open_keys.add(criterion.key)

    blocked = set(failed)
    changed = True
    while changed:
        changed = False
        for item in plan.dependencies:
            if item.ac_key not in blocked and any(parent in blocked for parent in item.depends_on):
                blocked.add(item.ac_key)
                changed = True

    for index, stage in enumerate(plan.stages):
        ready = tuple(
            key
            for key in stage
            if key not in succeeded
            and key not in blocked
            and key not in open_keys
            and set(plan.dependency_for(key)).issubset(succeeded)
        )
        if ready:
            return PlanReadiness(
                stage_index=index,
                ready_ac_keys=ready,
                blocked_ac_keys=tuple(key for key in blueprint.criterion_keys if key in blocked),
            )
    return PlanReadiness(
        blocked_ac_keys=tuple(key for key in blueprint.criterion_keys if key in blocked)
    )


def next_criterion(*, blueprint: Blueprint, state: ExecuteState) -> AcceptanceCriterion | None:
    """선언 순서에서 아직 실행되지 않은 첫 AC. 전부 실행됐으면 ``None``.

    "실행됨"의 기준은 **현재 Blueprint revision**의 ``EXECUTED_UNVERIFIED``
    attempt다. 이전 revision의 실행은 세지 않는다 — 새 revision이 승인되면
    이전 결과를 자동 재사용하지 않는다 (``docs/06_BLUEPRINT.md`` §9).

    실패한 AC는 여전히 "실행되지 않음"이므로 다시 선택된다. 실패 후 재시도가
    자연스럽게 첫 순위가 되고, 다른 AC로의 진행은 상태의 실패 중단 규칙이
    막는다 (ADR-0024 §3).
    """
    from mission_control.domain.execute.state import AttemptStatus

    for criterion in blueprint.acceptance_criteria:
        latest = state.latest_for(ac_key=criterion.key, blueprint_revision=blueprint.revision)
        if latest is None or latest.status is not AttemptStatus.EXECUTED_UNVERIFIED:
            return criterion
    return None
