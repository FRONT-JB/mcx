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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mission_control.domain.errors import MissionControlError
from mission_control.security import redact_credentials


class OpenAttemptError(MissionControlError):
    """열린 attempt가 있는 상태에서 새 dispatch를 시도했다.

    동시에 두 attempt가 열리면 어느 쪽의 결과가 어느 dispatch의 것인지
    판정할 수 없다.
    """

    def __init__(self, *, mission_id: str, ac_key: str) -> None:
        super().__init__(
            f"mission {mission_id} already has a dispatched attempt for {ac_key}; "
            "record its result before dispatching again"
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
            f"mission {mission_id} halted: {failed_ac_key} failed and blocks "
            f"dispatching {requested_ac_key}; retry the failed criterion or resolve it"
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
        super().__init__(f"mission {mission_id} has no dispatched attempt awaiting a result")
        self.mission_id = mission_id


class AttemptStatus(StrEnum):
    """attempt의 상태. LOST를 따로 두지 않는다 — 결과를 받기 전에 프로세스가
    죽으면 ``DISPATCHED``로 남은 attempt 자체가 "결과 불명"이다 (ADR-0024 §4).
    """

    DISPATCHED = "dispatched"
    EXECUTED_UNVERIFIED = "executed_unverified"
    EXECUTION_FAILED = "execution_failed"


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
            if self.result_summary is not None or self.error is not None:
                raise ValueError("a dispatched attempt cannot carry a result yet")
        if self.status is AttemptStatus.EXECUTED_UNVERIFIED and self.error is not None:
            raise ValueError("an executed attempt cannot carry an error")
        if self.status is AttemptStatus.EXECUTION_FAILED and not self.error:
            raise ValueError("a failed attempt requires an error")
        return self


class ExecuteState(BaseModel):
    """하나의 Mission에 대한 Execute 상태."""

    model_config = ConfigDict(frozen=True)

    mission_id: str
    #: 쓰기 순서. 저장소는 이 값으로 덮어쓰기를 판정한다 (ADR-0014와 같은 축).
    sequence: int = 1
    attempts: tuple[ExecutionAttempt, ...] = ()

    @model_validator(mode="after")
    def _attempts_are_ordered_and_singly_open(self) -> ExecuteState:
        """attempt 번호의 연속성과 "열린 attempt는 마지막 하나"를 확인한다.

        번호에 빈틈이 있으면 provenance의 시도 번호가 검증 불가능해지고, 열린
        attempt가 중간에 있으면 그 뒤의 기록이 결과 없는 시도 위에 쌓인 것이
        된다.
        """
        for index, item in enumerate(self.attempts):
            if item.number != index + 1:
                raise ValueError(
                    f"attempt numbers must be contiguous from 1: "
                    f"position {index} holds number {item.number}"
                )
            if item.status is AttemptStatus.DISPATCHED and index != len(self.attempts) - 1:
                raise ValueError("only the last attempt may still be dispatched")
        return self

    @classmethod
    def start(cls, *, mission_id: str) -> ExecuteState:
        return cls(mission_id=mission_id)

    @property
    def open_attempt(self) -> ExecutionAttempt | None:
        """결과를 기다리는 attempt. 없으면 ``None``."""
        if self.attempts and self.attempts[-1].status is AttemptStatus.DISPATCHED:
            return self.attempts[-1]
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
