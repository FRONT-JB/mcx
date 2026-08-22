"""Execute use case — 진입 확인, dispatch, 결과 기록, Gate 판정의 조율.

:class:`~mission_control.application.brief_service.BriefService`와 같은 규칙을
따른다 — 도메인 규칙은 여기 두지 않고, 저장이 성공한 뒤에만 전이가 일어났다고
보고한다.

이 계층이 추가로 지키는 순서가 둘 있다.

**진입 확인이 모든 일보다 먼저다.** 작업을 만들 수 있는 것은 이 use case
하나이고, 그 진입은 Blueprint Gate의 ``CLEAR``다 (ADR-0023 §1). Gate가
``HOLD``면 dispatch도 Gate 판정도 시작하지 않는다.

**지속이 dispatch보다 먼저다.** attempt를 저장한 뒤에 Runtime에 위임한다
(ADR-0024 §4). 반대로 하면 결과를 받기 전에 죽었을 때 시도했다는 사실 자체가
사라지고, upstream 관측(§12.3)의 "아무도 모르는 작업"이 우리 쪽에서 재현된다.

계약: ``docs/07_EXECUTE.md`` §8
결정: ``docs/adr/0023-execute-entry-and-provenance.md``,
``docs/adr/0024-execute-v1-execution-model.md``
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from mission_control.application.blueprint_service import BlueprintNotFoundError
from mission_control.application.brief_service import BriefNotFoundError
from mission_control.application.ports import (
    BlueprintRepository,
    BriefRepository,
    CoordinatorRequest,
    CoordinatorRuntime,
    DependencyAnalysisRequest,
    DependencyAnalyzer,
    ExecuteRepository,
    ExecutionRequest,
    ExecutionRuntime,
    MechanicalRunner,
    RuntimeUnavailableError,
    WorkerExecutionSummary,
)
from mission_control.domain.blueprint.gate import evaluate_blueprint_gate
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.errors import MissionControlError
from mission_control.domain.execute.gate import ExecuteGateDecision, evaluate_execute_gate
from mission_control.domain.execute.plan import (
    build_parallel_plan,
    next_criterion,
    plan_readiness,
)
from mission_control.domain.execute.state import (
    AttemptStatus,
    CapabilityEnvelope,
    ExecuteState,
    ExecutionAttempt,
    SettledRevalidation,
    StageRun,
    StageRunStatus,
    WriteTelemetryStatus,
)
from mission_control.domain.recover.packet import PreviousFailure
from mission_control.domain.verify.evidence import OUTPUT_TAIL_CHARS, VERIFY_COMMAND_TIMEOUT_SECONDS

_QUOTA_PATTERNS = ("rate limit", "quota", "usage limit", "429")


class _QuotaPause(Exception):
    pass


def _is_quota_failure(error: str | None) -> bool:
    lowered = (error or "").lower()
    return any(pattern in lowered for pattern in _QUOTA_PATTERNS)


class BlueprintNotClearedError(MissionControlError):
    """Execute 진입 Gate가 ``CLEAR``가 아닌데 실행하려 했다.

    승인된 Blueprint 없이 Execute하지 않는다 (ADR-0002, ADR-0023 §1). 승인이
    없거나, 승인 뒤 내용이 바뀌었거나, Brief가 그 사이 바뀐 경우가 전부 여기서
    막힌다.
    """

    def __init__(self, *, mission_id: str, reasons: tuple[str, ...]) -> None:
        joined = "; ".join(reasons)
        super().__init__(
            f"mission {mission_id}의 Blueprint가 Execute 진입 CLEAR가 아니다: {joined}"
        )
        self.mission_id = mission_id
        self.reasons = reasons


class UnknownCriterionError(MissionControlError):
    """현재 승인된 Blueprint에 없는 AC의 교정을 요청했다.

    key가 내용 digest이므로 revision이 바뀌면 key도 바뀔 수 있다 — 이전
    revision의 실패를 새 revision에서 교정하는 것은 새 실행이지 재시도가
    아니다.
    """

    def __init__(self, *, mission_id: str, ac_key: str, blueprint_revision: int) -> None:
        super().__init__(
            f"mission {mission_id}의 Blueprint revision {blueprint_revision}에 {ac_key}가 없다"
        )
        self.mission_id = mission_id
        self.ac_key = ac_key
        self.blueprint_revision = blueprint_revision


class AllCriteriaExecutedError(MissionControlError):
    """모든 AC가 이미 실행된 상태에서 dispatch를 요청했다.

    남은 일은 실행이 아니라 Gate 판정과 Verify다. 조용히 아무것도 하지 않으면
    호출자는 새 작업이 시작됐다고 믿는다.
    """

    def __init__(self, *, mission_id: str, blueprint_revision: int) -> None:
        super().__init__(
            f"mission {mission_id}의 Blueprint revision {blueprint_revision}은 모든 수용 기준이 "
            f"이미 실행됐다; 대신 Gate를 판정한다"
        )
        self.mission_id = mission_id
        self.blueprint_revision = blueprint_revision


class ParallelExecutionHoldError(MissionControlError):
    """parallel stage를 안전하게 계속할 수 없어 `HOLD`해야 한다."""

    def __init__(self, *, mission_id: str, reason: str) -> None:
        super().__init__(f"mission {mission_id}의 parallel Execute HOLD: {reason}")
        self.mission_id = mission_id
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ExecuteService:
    """Execute Stage의 application 경계."""

    briefs: BriefRepository
    blueprints: BlueprintRepository
    repository: ExecuteRepository
    runtime: ExecutionRuntime
    #: 이 Mission Control 인스턴스가 dispatch에 부여하는 실행 경계. workspace
    #: 격리 방식은 미정이므로(Execute Guide §17) v1은 구성으로 주입한다.
    envelope: CapabilityEnvelope
    analyzer: DependencyAnalyzer | None = None
    coordinator: CoordinatorRuntime | None = None
    runner: MechanicalRunner | None = None

    async def dispatch_next(self, *, mission_id: str) -> ExecuteState:
        """다음 AC 하나를 실행하고 결과까지 기록한 상태를 반환한다.

        일반 Runtime 예외는 실행 실패로 정규화하지만, process spawn 자체가
        불가능한 ``RuntimeUnavailableError``는 표면화한다. attempt는 이미
        저장돼 있으므로 이 경우 ``DISPATCHED``로 남고, 그 상태가 곧
        "결과 불명"이다 (ADR-0024 §4, ADR-0057).
        """
        blueprint = (await self._cleared_blueprint(mission_id)).current
        state = await self._state(mission_id)

        criterion = next_criterion(blueprint=blueprint, state=state)
        if criterion is None:
            raise AllCriteriaExecutedError(
                mission_id=mission_id, blueprint_revision=blueprint.revision
            )
        return await self._dispatch(blueprint, criterion, state, previous_failure=None)

    async def dispatch_correction(
        self, *, mission_id: str, ac_key: str, previous_failure: PreviousFailure
    ) -> ExecuteState:
        """Recover의 교정 재시도 — 지정된 AC를 실패 증거와 함께 재실행한다.

        이미 ``EXECUTED_UNVERIFIED``인 AC도 대상이다(검증이 실패를 드러낸
        경우). 실패 증거 없는 교정은 없다 — ``previous_failure``가 필수인
        이유이며, 이 경로가 Guide §11 "같은 prompt를 반복하지 않는다"의
        구현이다 (ADR-0031 §5).
        """
        blueprint = (await self._cleared_blueprint(mission_id)).current
        criterion = next(
            (item for item in blueprint.acceptance_criteria if item.key == ac_key), None
        )
        if criterion is None:
            raise UnknownCriterionError(
                mission_id=mission_id, ac_key=ac_key, blueprint_revision=blueprint.revision
            )
        state = await self._state(mission_id)
        return await self._dispatch(blueprint, criterion, state, previous_failure=previous_failure)

    async def dispatch_stage(
        self, *, mission_id: str, max_workers: int | None = None
    ) -> ExecuteState:
        """immutable plan의 다음 ready stage를 bounded fan-out으로 실행한다."""
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers는 1 이상이어야 한다")
        blueprint = (await self._cleared_blueprint(mission_id)).current
        state = await self._state(mission_id)

        plan = state.plan_for(blueprint_revision=blueprint.revision)
        if plan is None:
            if self.analyzer is None:
                raise ParallelExecutionHoldError(
                    mission_id=mission_id, reason="dependency analyzer가 구성되지 않았다"
                )
            try:
                dependencies = await self.analyzer.analyze(
                    DependencyAnalysisRequest(
                        goal=blueprint.goal,
                        constraints=blueprint.constraints,
                        non_goals=blueprint.non_goals,
                        acceptance_criteria=blueprint.acceptance_criteria,
                    )
                )
                plan = build_parallel_plan(
                    blueprint=blueprint,
                    dependencies=dependencies,
                    analyzer_backend=self.analyzer.backend,
                )
            except MissionControlError as error:
                raise ParallelExecutionHoldError(
                    mission_id=mission_id, reason=str(error)
                ) from error
            state = state.add_plan(plan)
            await self.repository.save(state)

        active = state.latest_stage_run(plan_id=plan.plan_id)
        if active is not None:
            if active.status is StageRunStatus.WORKERS_DISPATCHED:
                if any(
                    attempt.status is AttemptStatus.DISPATCHED
                    for attempt in self._attempts_for(state, active)
                ):
                    raise ParallelExecutionHoldError(
                        mission_id=mission_id,
                        reason=(
                            f"{active.run_id}에 결과 불명 worker가 있다; 완료 worker와 "
                            "결과 불명 worker를 자동 재실행하지 않는다"
                        ),
                    )
                return await self._reconcile_stage(blueprint, state, active)
            if active.status is StageRunStatus.COORDINATOR_DISPATCHED:
                raise ParallelExecutionHoldError(
                    mission_id=mission_id,
                    reason=f"{active.run_id}의 Coordinator 결과가 불명이다; 자동 재호출하지 않는다",
                )
            if active.status is StageRunStatus.REVALIDATING:
                return await self._revalidate_and_finalize(blueprint, state, active)
            if active.status is StageRunStatus.HOLD:
                raise ParallelExecutionHoldError(
                    mission_id=mission_id, reason=active.error or f"{active.run_id}이 HOLD다"
                )

        readiness = plan_readiness(blueprint=blueprint, plan=plan, state=state)
        if not readiness.ready_ac_keys:
            if readiness.blocked_ac_keys:
                raise ParallelExecutionHoldError(
                    mission_id=mission_id,
                    reason=(
                        "실패 dependency 때문에 실행할 수 없는 AC가 있다: "
                        + ", ".join(readiness.blocked_ac_keys)
                    ),
                )
            raise AllCriteriaExecutedError(
                mission_id=mission_id, blueprint_revision=blueprint.revision
            )
        assert readiness.stage_index is not None

        criteria = tuple(
            criterion
            for key in readiness.ready_ac_keys
            if (criterion := blueprint.criterion_for(key)) is not None
        )
        requested = max_workers
        effective = min(max_workers or 1, len(criteria))
        if any(not item.is_mechanically_verifiable for item in criteria):
            effective = 1
        if effective > 1 and (self.coordinator is None or self.runner is None):
            raise ParallelExecutionHoldError(
                mission_id=mission_id,
                reason="병렬 fan-out에는 Coordinator와 settled revalidation runner가 필요하다",
            )

        state = state.dispatch_stage(
            plan=plan,
            stage_index=readiness.stage_index,
            ac_keys=readiness.ready_ac_keys,
            runtime_backend=self.runtime.backend,
            envelope=self.envelope,
            requested_workers=requested,
            effective_workers=effective,
        )
        await self.repository.save(state)
        run = state.stage_runs[-1]
        by_key = {item.key: item for item in criteria}
        semaphore = asyncio.Semaphore(effective)
        save_lock = asyncio.Lock()

        async def _worker(execution_id: str, ac_key: str) -> None:
            async with semaphore:
                outcome = None
                failure: str | None
                try:
                    returned = await self.runtime.execute(
                        self._request(blueprint, by_key[ac_key], previous_failure=None)
                    )
                except RuntimeUnavailableError:
                    raise
                except Exception as error:
                    failure = f"runtime raised before returning an outcome: {error}"
                else:
                    outcome = returned
                    failure = returned.error
                async with save_lock:
                    current = await self._state(mission_id)
                    resolved = current.record_result_for(
                        execution_id=execution_id,
                        succeeded=outcome.succeeded if outcome is not None else False,
                        native_session_id=(
                            outcome.native_session_id if outcome is not None else None
                        ),
                        result_summary=(outcome.result_summary if outcome is not None else None),
                        error=failure,
                        changed_files=(outcome.changed_files if outcome is not None else ()),
                        write_telemetry=(
                            outcome.write_telemetry
                            if outcome is not None
                            else WriteTelemetryStatus.INCOMPLETE
                        ),
                    )
                    await self.repository.save(resolved)
                if outcome is not None and not outcome.succeeded and _is_quota_failure(failure):
                    raise _QuotaPause(failure)

        quota_paused = False
        unavailable: RuntimeUnavailableError | None = None
        try:
            async with asyncio.TaskGroup() as group:
                for execution_id, ac_key in zip(
                    run.attempt_execution_ids, run.ac_keys, strict=True
                ):
                    group.create_task(_worker(execution_id, ac_key))
        except* RuntimeUnavailableError as errors:
            unavailable = next(
                error for error in errors.exceptions if isinstance(error, RuntimeUnavailableError)
            )
        except* _QuotaPause:
            quota_paused = True

        if unavailable is not None:
            raise unavailable

        state = await self._state(mission_id)
        if quota_paused:
            held = state.hold_stage(
                run_id=run.run_id,
                error="shared provider quota/rate-limit; incomplete stage를 재조정하지 않는다",
            )
            await self.repository.save(held)
            raise ParallelExecutionHoldError(
                mission_id=mission_id, reason=held.stage_run(run.run_id).error or "quota pause"
            )
        return await self._reconcile_stage(blueprint, state, state.stage_run(run.run_id))

    async def _dispatch(
        self,
        blueprint: Blueprint,
        criterion: AcceptanceCriterion,
        state: ExecuteState,
        *,
        previous_failure: PreviousFailure | None,
    ) -> ExecuteState:
        dispatched = state.dispatch(
            execution_id=f"exec-{state.mission_id}-{len(state.attempts) + 1:04d}",
            runtime_backend=self.runtime.backend,
            blueprint_revision=blueprint.revision,
            ac_key=criterion.key,
            envelope=self.envelope,
        )
        await self.repository.save(dispatched)

        try:
            outcome = await self.runtime.execute(
                self._request(blueprint, criterion, previous_failure=previous_failure)
            )
        except RuntimeUnavailableError:
            raise
        except Exception as error:
            failed = dispatched.record_result(
                succeeded=False, error=f"runtime raised before returning an outcome: {error}"
            )
            await self.repository.save(failed)
            return failed

        resolved = dispatched.record_result(
            succeeded=outcome.succeeded,
            native_session_id=outcome.native_session_id,
            result_summary=outcome.result_summary,
            error=outcome.error,
            changed_files=outcome.changed_files,
            write_telemetry=outcome.write_telemetry,
        )
        await self.repository.save(resolved)
        return resolved

    async def _reconcile_stage(
        self, blueprint: Blueprint, state: ExecuteState, run: StageRun
    ) -> ExecuteState:
        attempts = self._attempts_for(state, run)
        if any(item.status is AttemptStatus.DISPATCHED for item in attempts):
            raise ParallelExecutionHoldError(
                mission_id=state.mission_id, reason=f"{run.run_id}에 결과 불명 worker가 있다"
            )

        writers: dict[str, list[str]] = {}
        uncertain: list[str] = []
        for attempt in attempts:
            for path in attempt.changed_files:
                writers.setdefault(path, []).append(attempt.ac_key)
            if attempt.write_telemetry is not WriteTelemetryStatus.COMPLETE:
                uncertain.append(attempt.ac_key)
        conflicts = tuple(sorted(path for path, keys in writers.items() if len(set(keys)) > 1))

        needs_coordination = run.effective_workers > 1 and bool(conflicts or uncertain)
        if not needs_coordination:
            finalized = state.finalize_stage(run_id=run.run_id)
            await self.repository.save(finalized)
            return finalized
        if self.coordinator is None:
            finalized = state.finalize_stage(
                run_id=run.run_id, hold_error="Coordinator가 구성되지 않았다"
            )
            await self.repository.save(finalized)
            return finalized

        coordinating = state.begin_coordination(
            run_id=run.run_id,
            conflict_files=conflicts,
            uncertain_ac_keys=tuple(uncertain),
        )
        await self.repository.save(coordinating)
        current_run = coordinating.stage_run(run.run_id)
        outcome = None
        failure: str | None
        try:
            returned = await self.coordinator.coordinate(
                CoordinatorRequest(
                    goal=blueprint.goal,
                    constraints=blueprint.constraints,
                    non_goals=blueprint.non_goals,
                    acceptance_criteria=tuple(
                        item
                        for key in run.ac_keys
                        if (item := blueprint.criterion_for(key)) is not None
                    ),
                    worker_results=tuple(
                        WorkerExecutionSummary(
                            ac_key=item.ac_key,
                            succeeded=item.status is AttemptStatus.EXECUTED_UNVERIFIED,
                            result_summary=item.result_summary,
                            error=item.error,
                            changed_files=item.changed_files,
                            write_telemetry=item.write_telemetry,
                        )
                        for item in attempts
                    ),
                    conflict_files=conflicts,
                    uncertain_ac_keys=tuple(uncertain),
                    workspace=self.envelope.workspace,
                    allowed_tools=self.envelope.allowed_tools,
                )
            )
        except RuntimeUnavailableError:
            raise
        except Exception as error:
            failure = f"Coordinator runtime raised before returning an outcome: {error}"
        else:
            outcome = returned
            failure = returned.error
        resolved = coordinating.record_coordination_result(
            run_id=current_run.run_id,
            succeeded=outcome.succeeded if outcome is not None else False,
            native_session_id=outcome.native_session_id if outcome is not None else None,
            changed_files=outcome.changed_files if outcome is not None else (),
            error=failure,
        )
        await self.repository.save(resolved)
        if outcome is None or not outcome.succeeded:
            return resolved
        return await self._revalidate_and_finalize(
            blueprint, resolved, resolved.stage_run(run.run_id)
        )

    async def _revalidate_and_finalize(
        self, blueprint: Blueprint, state: ExecuteState, run: StageRun
    ) -> ExecuteState:
        if self.runner is None:
            finalized = state.finalize_stage(
                run_id=run.run_id, hold_error="settled revalidation runner가 구성되지 않았다"
            )
            await self.repository.save(finalized)
            return finalized

        successful_keys = {
            item.ac_key
            for item in self._attempts_for(state, run)
            if item.status is AttemptStatus.EXECUTED_UNVERIFIED
        }
        checks: list[SettledRevalidation] = []
        for key in run.ac_keys:
            if key not in successful_keys:
                continue
            criterion = blueprint.criterion_for(key)
            if criterion is None or not criterion.is_mechanically_verifiable:
                finalized = state.finalize_stage(
                    run_id=run.run_id,
                    hold_error=f"{key}에 settled revalidation success contract가 없다",
                )
                await self.repository.save(finalized)
                return finalized
            checks.append(await self._settled_check(criterion))

        finalized = state.finalize_stage(run_id=run.run_id, revalidations=tuple(checks))
        await self.repository.save(finalized)
        return finalized

    async def _settled_check(self, criterion: AcceptanceCriterion) -> SettledRevalidation:
        assert self.runner is not None
        missing = await self.runner.missing_artifacts(
            workspace=self.envelope.workspace, artifacts=criterion.expected_artifacts
        )
        if missing:
            return SettledRevalidation(
                ac_key=criterion.key, passed=False, missing_artifacts=missing
            )
        if criterion.verify_command is None:
            return SettledRevalidation(ac_key=criterion.key, passed=True)
        execution = await self.runner.run(
            command=criterion.verify_command,
            workspace=self.envelope.workspace,
            timeout_seconds=VERIFY_COMMAND_TIMEOUT_SECONDS,
        )
        asserted = criterion.output_assertion
        passed = (
            not execution.timed_out
            and execution.exit_code == 0
            and (asserted is None or asserted in execution.output)
        )
        return SettledRevalidation(
            ac_key=criterion.key,
            passed=passed,
            command=criterion.verify_command,
            exit_code=execution.exit_code,
            timed_out=execution.timed_out,
            output_tail=execution.output[-OUTPUT_TAIL_CHARS:],
        )

    @staticmethod
    def _attempts_for(state: ExecuteState, run: StageRun) -> tuple[ExecutionAttempt, ...]:
        attempt_ids = set(run.attempt_execution_ids)
        return tuple(item for item in state.attempts if item.execution_id in attempt_ids)

    async def decide_gate(self, *, mission_id: str) -> ExecuteGateDecision:
        """저장된 상태로 Verify 진입 Gate를 판정한다.

        진입 조건(Blueprint ``CLEAR``)을 먼저 확인한다 — Brief나 Blueprint가
        그 사이 바뀌었다면 실행 결과의 판정 이전에 진입 자체가 무효다.
        """
        blueprint = (await self._cleared_blueprint(mission_id)).current
        state = await self._state(mission_id)
        return evaluate_execute_gate(state=state, blueprint=blueprint)

    async def _state(self, mission_id: str) -> ExecuteState:
        stored = await self.repository.load(mission_id)
        return stored if stored is not None else ExecuteState.start(mission_id=mission_id)

    async def _cleared_blueprint(self, mission_id: str) -> BlueprintState:
        """Execute 진입 Gate를 확인하고 승인된 Blueprint 상태를 반환한다."""
        blueprint_state = await self.blueprints.load(mission_id)
        if blueprint_state is None:
            raise BlueprintNotFoundError(mission_id)
        brief = await self.briefs.load(mission_id)
        if brief is None:
            raise BriefNotFoundError(mission_id)

        decision = evaluate_blueprint_gate(state=blueprint_state, brief_revision=brief.revision)
        if decision.outcome != "CLEAR":
            raise BlueprintNotClearedError(mission_id=mission_id, reasons=decision.blocking_reasons)
        return blueprint_state

    def _request(
        self,
        blueprint: Blueprint,
        criterion: AcceptanceCriterion,
        *,
        previous_failure: PreviousFailure | None = None,
    ) -> ExecutionRequest:
        """Runtime에 전달할 bounded 입력을 구성한다.

        Blueprint의 방향 필드와 대상 AC 하나만 담는다. 다른 AC의 내용은
        전달하지 않는다 — 실행 범위는 이 AC이고, 전체를 주면 범위 밖 작업을
        유도한다.
        """
        return ExecutionRequest(
            goal=blueprint.goal,
            constraints=blueprint.constraints,
            non_goals=blueprint.non_goals,
            criterion=criterion,
            workspace=self.envelope.workspace,
            allowed_tools=self.envelope.allowed_tools,
            previous_failure=previous_failure,
        )
