"""Execute의 durable state — 승인된 AC에 대한 실행 attempt의 이력.

실행 단위는 별도 엔티티가 아니라 승인된 Blueprint의 AC key다. 이 모듈이
기록하는 것은 그 key에 대한 **시도(attempt)** 이며, AC는 계약이고 attempt는
시도라는 구분이 상태 이름에 그대로 박힌다 — ``EXECUTED_UNVERIFIED``는 Verify
통과가 아니다 (``docs/adr/0024-execute-v1-execution-model.md`` §1·§4).

이 모듈이 강제하는 핵심 불변 조건은 셋이다.

**열린 attempt는 하나다.** ``DISPATCHED`` attempt가 있는 동안 새 dispatch는
거부된다. 순차 실행의 상태 표현이자 중복 dispatch를 막는 최소 장치다 (§7).

**실행 실패는 후속을 막는다.** 같은 Blueprint revision에서 직전 attempt가
``EXECUTION_FAILED``면 다른 AC의 dispatch를 거부한다. 실패한 산출물 위에
쌓지 않기 위해서다. 같은 AC의 재시도는 막지 않는다 (§3).

**provenance는 선언 필드다.** 생성 경로, 실행 주체, lineage, 시도 번호가
없는 attempt는 만들어지지 않는다 (``docs/adr/0023-execute-entry-and-provenance.md``
§3). "무엇이 이 작업을 만들었는가"가 emitter의 성실함이 아니라 스키마로
보장된다.

계약: ``docs/07_EXECUTE.md`` §6, §7
결정: ``docs/adr/0024-execute-v1-execution-model.md``
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mission_control.domain.errors import MissionControlError
from mission_control.domain.execute.plan import ParallelExecutionPlan
from mission_control.security import redact_credentials


class OpenAttemptError(MissionControlError):
    """열린 attempt가 있는 상태에서 새 dispatch를 시도했다.

    동시에 두 attempt가 열리면 어느 쪽의 결과가 어느 dispatch의 것인지
    판정할 수 없다.
    """

    def __init__(self, *, mission_id: str, ac_key: str) -> None:
        super().__init__(
            f"mission {mission_id}에 {ac_key}의 dispatch된 시도가 이미 있다; "
            "다시 dispatch하기 전에 그 결과를 기록한다"
        )
        self.mission_id = mission_id
        self.ac_key = ac_key


class HaltedByFailedCriterionError(MissionControlError):
    """실행 실패가 해소되지 않은 채 다른 AC를 dispatch하려 했다.

    의존성을 모르는 v1에서 실패 뒤의 진행은 실패한 산출물 위에 쌓는 것이다.
    같은 AC의 재시도는 이 예외의 대상이 아니다 (ADR-0024 §3).
    """

    def __init__(self, *, mission_id: str, failed_ac_key: str, requested_ac_key: str) -> None:
        super().__init__(
            f"mission {mission_id}가 멈춰 있다: {failed_ac_key}가 실패해 "
            f"{requested_ac_key}의 dispatch를 막는다; 실패한 수용 기준을 재시도하거나 해소한다"
        )
        self.mission_id = mission_id
        self.failed_ac_key = failed_ac_key
        self.requested_ac_key = requested_ac_key


class NoOpenAttemptError(MissionControlError):
    """열린 attempt가 없는데 결과를 기록하려 했다.

    dispatch되지 않은 결과를 받아들이면 실행되지 않은 작업이 실행된 것으로
    기록된다.
    """

    def __init__(self, *, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}에 결과를 기다리는 dispatch된 시도가 없다")
        self.mission_id = mission_id


class AttemptStatus(StrEnum):
    """attempt의 상태. LOST를 따로 두지 않는다 — 결과를 받기 전에 프로세스가
    죽으면 ``DISPATCHED``로 남은 attempt 자체가 "결과 불명"이다 (ADR-0024 §4).
    """

    DISPATCHED = "dispatched"
    EXECUTED_UNVERIFIED = "executed_unverified"
    EXECUTION_FAILED = "execution_failed"


class WriteTelemetryStatus(StrEnum):
    """worker write attribution의 완전성.

    ``INCOMPLETE``는 write가 있었다는 뜻이 아니라, write가 없었다고 증명할 수
    없다는 뜻이다 (ADR-0053 §4).
    """

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class CapabilityEnvelope(BaseModel):
    """dispatch에 명시되는 실행 경계 (ADR-0024 §6).

    v1의 강제 범위는 계약의 전달과 기록까지다. 실제 차단은 concrete
    adapter(Phase 5)가 한다 — Brief의 tool-less port와 같은 강제 수준이다.
    """

    model_config = ConfigDict(frozen=True)

    workspace: str = Field(min_length=1)
    allowed_tools: tuple[str, ...] = ()


class ExecutionAttempt(BaseModel):
    """AC 하나에 대한 실행 시도 하나.

    provenance 네 항목(ADR-0023 §3)이 전부 필수 선언 필드다 — ``execution_id``
    (생성 경로), ``runtime_backend``(실행 주체), ``blueprint_revision``과
    ``ac_key``(lineage), ``number``(시도). ``native_session_id``만 선택인
    이유는 그것이 실행 주체가 아니라 실행 주체가 **돌려주는** 값이기
    때문이다 — dispatch 시점에는 존재하지 않는다.
    """

    model_config = ConfigDict(frozen=True)

    number: int = Field(ge=1)
    execution_id: str = Field(min_length=1)
    runtime_backend: str = Field(min_length=1)
    native_session_id: str | None = None
    blueprint_revision: int = Field(ge=1)
    ac_key: str = Field(min_length=1)
    envelope: CapabilityEnvelope

    status: AttemptStatus = AttemptStatus.DISPATCHED
    result_summary: str | None = None
    error: str | None = None
    changed_files: tuple[str, ...] = ()
    write_telemetry: WriteTelemetryStatus | None = None

    @field_validator("changed_files", mode="after")
    @classmethod
    def _changed_files_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("changed_files는 중복될 수 없다")
        if any(not item for item in value):
            raise ValueError("changed_files는 빈 경로를 담을 수 없다")
        return value

    @field_validator("error", "result_summary", mode="after")
    @classmethod
    def _mask_credentials(cls, value: str | None) -> str | None:
        """자격증명은 생성 시점에 가린다 (ADR-0040 §3).

        경로는 남긴다 — 이 발췌가 ``PreviousFailure.error_excerpt``로 worker에게
        전달되기 때문이다.
        """
        return value if value is None else redact_credentials(value)

    @model_validator(mode="after")
    def _result_matches_the_status(self) -> ExecutionAttempt:
        """상태와 결과 필드의 어긋남을 거부한다.

        실패인데 이유가 없으면 Verify와 Recover가 판정할 재료가 없고, 성공인데
        오류가 붙어 있으면 어느 쪽이 진실인지 알 수 없다. dispatch 시점의
        attempt는 아직 아무 결과도 가질 수 없다.
        """
        if self.status is AttemptStatus.DISPATCHED:
            if (
                self.result_summary is not None
                or self.error is not None
                or self.changed_files
                or self.write_telemetry is not None
            ):
                raise ValueError("dispatch된 시도는 아직 결과를 담을 수 없다")
        if self.status is AttemptStatus.EXECUTED_UNVERIFIED and self.error is not None:
            raise ValueError("실행에 성공한 시도는 오류를 담을 수 없다")
        if self.status is AttemptStatus.EXECUTION_FAILED and not self.error:
            raise ValueError("실패한 시도에는 오류가 필요하다")
        return self


class StageRunStatus(StrEnum):
    """parallel stage의 durable resume 경계."""

    WORKERS_DISPATCHED = "workers_dispatched"
    COORDINATOR_DISPATCHED = "coordinator_dispatched"
    REVALIDATING = "revalidating"
    EXECUTED_UNVERIFIED = "executed_unverified"
    EXECUTION_FAILED = "execution_failed"
    HOLD = "hold"


class SettledRevalidation(BaseModel):
    """Coordinator 뒤 settled workspace의 Execute 안전 검사."""

    model_config = ConfigDict(frozen=True)

    ac_key: str = Field(min_length=1)
    passed: bool
    command: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
    missing_artifacts: tuple[str, ...] = ()
    output_tail: str = ""

    @field_validator("output_tail", "command", mode="after")
    @classmethod
    def _mask_revalidation_output(cls, value: str | None) -> str | None:
        return value if value is None else redact_credentials(value)


class StageRun(BaseModel):
    """한 immutable plan stage의 grouped dispatch와 reconciliation lineage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    blueprint_revision: int = Field(ge=1)
    stage_index: int = Field(ge=0)
    ac_keys: tuple[str, ...] = Field(min_length=1)
    attempt_execution_ids: tuple[str, ...] = Field(min_length=1)
    requested_workers: int | None = Field(default=None, ge=1)
    effective_workers: int = Field(ge=1)
    status: StageRunStatus = StageRunStatus.WORKERS_DISPATCHED
    conflict_files: tuple[str, ...] = ()
    uncertain_ac_keys: tuple[str, ...] = ()
    coordinator_execution_id: str | None = None
    coordinator_native_session_id: str | None = None
    coordinator_changed_files: tuple[str, ...] = ()
    coordinator_error: str | None = None
    revalidations: tuple[SettledRevalidation, ...] = ()
    error: str | None = None

    @field_validator("coordinator_error", "error", mode="after")
    @classmethod
    def _mask_stage_errors(cls, value: str | None) -> str | None:
        return value if value is None else redact_credentials(value)

    @model_validator(mode="after")
    def _identity_sets_match(self) -> StageRun:
        if len(self.ac_keys) != len(set(self.ac_keys)):
            raise ValueError("stage run의 AC key가 중복된다")
        if len(self.attempt_execution_ids) != len(self.ac_keys):
            raise ValueError("stage run은 AC마다 attempt id 하나를 가져야 한다")
        if len(self.attempt_execution_ids) != len(set(self.attempt_execution_ids)):
            raise ValueError("stage run의 attempt id가 중복된다")
        if self.effective_workers > len(self.ac_keys):
            raise ValueError("effective_workers는 stage AC 수보다 클 수 없다")
        if self.status is StageRunStatus.COORDINATOR_DISPATCHED:
            if self.coordinator_execution_id is None:
                raise ValueError("dispatch된 Coordinator에는 execution id가 필요하다")
        return self


class ExecuteState(BaseModel):
    """하나의 Mission에 대한 Execute 상태."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mission_id: str
    schema_version: Literal[1] = 1
    #: 쓰기 순서. 저장소는 이 값으로 덮어쓰기를 판정한다 (ADR-0014와 같은 축).
    sequence: int = 1
    attempts: tuple[ExecutionAttempt, ...] = ()
    plans: tuple[ParallelExecutionPlan, ...] = ()
    stage_runs: tuple[StageRun, ...] = ()

    @model_validator(mode="after")
    def _attempts_are_ordered_and_owned_when_open(self) -> ExecuteState:
        """attempt 번호의 연속성과 복수 open의 durable stage ownership을 확인한다.

        번호에 빈틈이 있으면 provenance의 시도 번호가 검증 불가능해지고, 열린
        attempt가 중간에 있으면 그 뒤의 기록이 결과 없는 시도 위에 쌓인 것이
        된다.
        """
        open_ids: set[str] = set()
        for index, item in enumerate(self.attempts):
            if item.number != index + 1:
                raise ValueError(
                    f"시도 번호는 1부터 연속이어야 한다: {index}번 자리에 번호 {item.number}이 있다"
                )
            if item.status is AttemptStatus.DISPATCHED:
                open_ids.add(item.execution_id)

        if open_ids:
            owners = [
                run
                for run in self.stage_runs
                if run.status in {StageRunStatus.WORKERS_DISPATCHED, StageRunStatus.HOLD}
                and open_ids.issubset(set(run.attempt_execution_ids))
            ]
            only_last = len(open_ids) == 1 and self.attempts[-1].status is AttemptStatus.DISPATCHED
            if not only_last and len(owners) != 1:
                raise ValueError(
                    "dispatch 상태로 남을 수 있는 것은 마지막 시도뿐이거나 "
                    "하나의 active stage owner가 소유한 시도들뿐이다"
                )

        plan_ids = [item.plan_id for item in self.plans]
        if len(plan_ids) != len(set(plan_ids)):
            raise ValueError("parallel plan id가 중복된다")
        run_ids = [item.run_id for item in self.stage_runs]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("stage run id가 중복된다")
        return self

    @classmethod
    def start(cls, *, mission_id: str) -> ExecuteState:
        return cls(mission_id=mission_id)

    @property
    def open_attempt(self) -> ExecutionAttempt | None:
        """결과를 기다리는 attempt. 없으면 ``None``."""
        return self.open_attempts[-1] if self.open_attempts else None

    @property
    def open_attempts(self) -> tuple[ExecutionAttempt, ...]:
        return tuple(item for item in self.attempts if item.status is AttemptStatus.DISPATCHED)

    def plan_for(self, *, blueprint_revision: int) -> ParallelExecutionPlan | None:
        for item in reversed(self.plans):
            if item.blueprint_revision == blueprint_revision:
                return item
        return None

    def add_plan(self, plan: ParallelExecutionPlan) -> ExecuteState:
        existing = self.plan_for(blueprint_revision=plan.blueprint_revision)
        if existing is not None:
            if existing != plan:
                raise ValueError("같은 Blueprint revision의 parallel plan은 바꿀 수 없다")
            return self
        return ExecuteState.model_validate(
            self.model_copy(
                update={"sequence": self.sequence + 1, "plans": (*self.plans, plan)}
            ).model_dump()
        )

    def stage_run(self, run_id: str) -> StageRun:
        for item in self.stage_runs:
            if item.run_id == run_id:
                return item
        raise KeyError(run_id)

    def latest_stage_run(self, *, plan_id: str) -> StageRun | None:
        for item in reversed(self.stage_runs):
            if item.plan_id == plan_id:
                return item
        return None

    def latest_for(self, *, ac_key: str, blueprint_revision: int) -> ExecutionAttempt | None:
        """해당 AC·revision의 가장 최근 attempt. 없으면 ``None``.

        revision으로 거르는 이유는 새 revision이 승인되면 이전 revision의
        실행 결과를 자동 재사용하지 않기 때문이다 (``docs/06_BLUEPRINT.md`` §9
        Downstream invalidation).
        """
        for item in reversed(self.attempts):
            if item.ac_key == ac_key and item.blueprint_revision == blueprint_revision:
                return item
        return None

    def dispatch(
        self,
        *,
        execution_id: str,
        runtime_backend: str,
        blueprint_revision: int,
        ac_key: str,
        envelope: CapabilityEnvelope,
    ) -> ExecuteState:
        """새 attempt를 ``DISPATCHED``로 기록한다.

        호출자는 반환된 상태를 **저장한 뒤에** Runtime에 위임해야 한다
        (ADR-0024 §4 — 지속이 dispatch보다 먼저). 저장 전에 위임하면 결과를
        받기 전에 죽었을 때 시도했다는 사실 자체가 사라진다.
        """
        if self.open_attempt is not None:
            raise OpenAttemptError(mission_id=self.mission_id, ac_key=self.open_attempt.ac_key)

        latest = self.attempts[-1] if self.attempts else None
        if (
            latest is not None
            and latest.status is AttemptStatus.EXECUTION_FAILED
            and latest.blueprint_revision == blueprint_revision
            and latest.ac_key != ac_key
        ):
            raise HaltedByFailedCriterionError(
                mission_id=self.mission_id,
                failed_ac_key=latest.ac_key,
                requested_ac_key=ac_key,
            )

        attempt = ExecutionAttempt(
            number=len(self.attempts) + 1,
            execution_id=execution_id,
            runtime_backend=runtime_backend,
            blueprint_revision=blueprint_revision,
            ac_key=ac_key,
            envelope=envelope,
        )
        return self.model_copy(
            update={"sequence": self.sequence + 1, "attempts": (*self.attempts, attempt)}
        )

    def record_result(
        self,
        *,
        succeeded: bool,
        native_session_id: str | None = None,
        result_summary: str | None = None,
        error: str | None = None,
        changed_files: tuple[str, ...] = (),
        write_telemetry: WriteTelemetryStatus | None = None,
    ) -> ExecuteState:
        """열린 attempt의 결과를 기록한다.

        성공은 ``EXECUTED_UNVERIFIED``다 — 실행됐다는 뜻이지 AC가 충족됐다는
        뜻이 아니며, 그 판정은 Verify의 것이다.
        """
        open_attempt = self.open_attempt
        if open_attempt is None:
            raise NoOpenAttemptError(mission_id=self.mission_id)

        resolved = open_attempt.model_copy(
            update={
                "status": (
                    AttemptStatus.EXECUTED_UNVERIFIED
                    if succeeded
                    else AttemptStatus.EXECUTION_FAILED
                ),
                "native_session_id": native_session_id,
                "result_summary": result_summary,
                "error": error,
                "changed_files": changed_files,
                "write_telemetry": write_telemetry,
            }
        )
        # model_copy는 validator를 다시 돌리지 않으므로 상태-결과 일관성을
        # 명시적으로 재검증한다. 이것이 없으면 실패인데 이유 없는 기록이
        # 이 경로로만 만들어질 수 있다.
        resolved = ExecutionAttempt.model_validate(resolved.model_dump())
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "attempts": (*self.attempts[:-1], resolved),
            }
        )

    def dispatch_stage(
        self,
        *,
        plan: ParallelExecutionPlan,
        stage_index: int,
        ac_keys: tuple[str, ...],
        runtime_backend: str,
        envelope: CapabilityEnvelope,
        requested_workers: int | None,
        effective_workers: int,
    ) -> ExecuteState:
        """한 stage의 attempt 전체와 owner를 한 상태 전이로 연다."""
        if self.open_attempts:
            raise OpenAttemptError(mission_id=self.mission_id, ac_key=self.open_attempts[-1].ac_key)
        if not ac_keys:
            raise ValueError("빈 stage는 dispatch할 수 없다")
        if plan not in self.plans:
            raise ValueError("durable하게 저장되지 않은 plan으로 stage를 열 수 없다")
        if stage_index >= len(plan.stages) or not set(ac_keys).issubset(
            set(plan.stages[stage_index])
        ):
            raise ValueError("stage AC가 plan과 일치하지 않는다")

        start = len(self.attempts) + 1
        attempts = tuple(
            ExecutionAttempt(
                number=start + offset,
                execution_id=f"exec-{self.mission_id}-{start + offset:04d}",
                runtime_backend=runtime_backend,
                blueprint_revision=plan.blueprint_revision,
                ac_key=ac_key,
                envelope=envelope,
            )
            for offset, ac_key in enumerate(ac_keys)
        )
        run_number = len(self.stage_runs) + 1
        run = StageRun(
            run_id=f"stage-{self.mission_id}-{run_number:04d}",
            plan_id=plan.plan_id,
            blueprint_revision=plan.blueprint_revision,
            stage_index=stage_index,
            ac_keys=ac_keys,
            attempt_execution_ids=tuple(item.execution_id for item in attempts),
            requested_workers=requested_workers,
            effective_workers=effective_workers,
        )
        return ExecuteState.model_validate(
            self.model_copy(
                update={
                    "sequence": self.sequence + 1,
                    "attempts": (*self.attempts, *attempts),
                    "stage_runs": (*self.stage_runs, run),
                }
            ).model_dump()
        )

    def record_result_for(
        self,
        *,
        execution_id: str,
        succeeded: bool,
        native_session_id: str | None = None,
        result_summary: str | None = None,
        error: str | None = None,
        changed_files: tuple[str, ...] = (),
        write_telemetry: WriteTelemetryStatus | None = None,
    ) -> ExecuteState:
        """완료 순서와 무관하게 exact execution id의 worker 결과를 닫는다."""
        index = next(
            (
                offset
                for offset, item in enumerate(self.attempts)
                if item.execution_id == execution_id
            ),
            None,
        )
        if index is None or self.attempts[index].status is not AttemptStatus.DISPATCHED:
            raise NoOpenAttemptError(mission_id=self.mission_id)
        current = self.attempts[index]
        resolved = ExecutionAttempt.model_validate(
            current.model_copy(
                update={
                    "status": (
                        AttemptStatus.EXECUTED_UNVERIFIED
                        if succeeded
                        else AttemptStatus.EXECUTION_FAILED
                    ),
                    "native_session_id": native_session_id,
                    "result_summary": result_summary,
                    "error": error,
                    "changed_files": changed_files,
                    "write_telemetry": write_telemetry,
                }
            ).model_dump()
        )
        attempts = list(self.attempts)
        attempts[index] = resolved
        return ExecuteState.model_validate(
            self.model_copy(
                update={"sequence": self.sequence + 1, "attempts": tuple(attempts)}
            ).model_dump()
        )

    def begin_coordination(
        self,
        *,
        run_id: str,
        conflict_files: tuple[str, ...],
        uncertain_ac_keys: tuple[str, ...],
    ) -> ExecuteState:
        run = self.stage_run(run_id)
        if run.status is not StageRunStatus.WORKERS_DISPATCHED:
            raise ValueError("worker 수집 단계에서만 Coordinator를 시작할 수 있다")
        if any(
            item.status is AttemptStatus.DISPATCHED
            for item in self.attempts
            if item.execution_id in run.attempt_execution_ids
        ):
            raise ValueError("모든 worker 결과가 닫히기 전에는 Coordinator를 시작할 수 없다")
        execution_id = f"coord-{run.run_id}"
        updated = StageRun.model_validate(
            run.model_copy(
                update={
                    "status": StageRunStatus.COORDINATOR_DISPATCHED,
                    "conflict_files": conflict_files,
                    "uncertain_ac_keys": uncertain_ac_keys,
                    "coordinator_execution_id": execution_id,
                }
            ).model_dump()
        )
        return self._replace_stage_run(updated)

    def record_coordination_result(
        self,
        *,
        run_id: str,
        succeeded: bool,
        native_session_id: str | None = None,
        changed_files: tuple[str, ...] = (),
        error: str | None = None,
    ) -> ExecuteState:
        run = self.stage_run(run_id)
        if run.status is not StageRunStatus.COORDINATOR_DISPATCHED:
            raise ValueError("dispatch된 Coordinator가 없다")
        updated = StageRun.model_validate(
            run.model_copy(
                update={
                    "status": (StageRunStatus.REVALIDATING if succeeded else StageRunStatus.HOLD),
                    "coordinator_native_session_id": native_session_id,
                    "coordinator_changed_files": changed_files,
                    "coordinator_error": error,
                    "error": error,
                }
            ).model_dump()
        )
        return self._replace_stage_run(updated)

    def finalize_stage(
        self,
        *,
        run_id: str,
        revalidations: tuple[SettledRevalidation, ...] = (),
        hold_error: str | None = None,
    ) -> ExecuteState:
        run = self.stage_run(run_id)
        attempts = tuple(
            item for item in self.attempts if item.execution_id in run.attempt_execution_ids
        )
        if any(item.status is AttemptStatus.DISPATCHED for item in attempts):
            raise ValueError("열린 worker가 있는 stage는 닫을 수 없다")
        if hold_error is not None or any(not item.passed for item in revalidations):
            status = StageRunStatus.HOLD
        elif any(item.status is AttemptStatus.EXECUTION_FAILED for item in attempts):
            status = StageRunStatus.EXECUTION_FAILED
        else:
            status = StageRunStatus.EXECUTED_UNVERIFIED
        updated = StageRun.model_validate(
            run.model_copy(
                update={
                    "status": status,
                    "revalidations": revalidations,
                    "error": hold_error,
                }
            ).model_dump()
        )
        return self._replace_stage_run(updated)

    def hold_stage(self, *, run_id: str, error: str) -> ExecuteState:
        """quota·shared runtime 실패로 incomplete stage를 durable HOLD한다."""
        run = self.stage_run(run_id)
        updated = StageRun.model_validate(
            run.model_copy(update={"status": StageRunStatus.HOLD, "error": error}).model_dump()
        )
        return self._replace_stage_run(updated)

    def _replace_stage_run(self, updated: StageRun) -> ExecuteState:
        runs = tuple(updated if item.run_id == updated.run_id else item for item in self.stage_runs)
        return ExecuteState.model_validate(
            self.model_copy(update={"sequence": self.sequence + 1, "stage_runs": runs}).model_dump()
        )
