"""Mission record — 합성 계층이 소유하는 current Stage의 durable 기록.

Stage service는 이 모듈을 알지 못한다. 기록의 소비자는 표시(status)·resume·
stall 진단이며, Stage 진입의 실질 보증은 각 진입의 Gate 재계산이다 — 저장된
Stage와 Gate가 어긋나면 Gate가 이긴다 (``docs/adr/0037``).

합법 전이는 Lifecycle §9 표에서 도출한다. ``MISSION COMPLETE``는 Stage
전이가 아니라 mission status이며 Verify Gate의 ``CLEAR``만 선언할 수 있다
(``docs/00_MISSION_CONTROL.md``).

시각은 호출자가 주입한다 — upstream도 전이 시각을 호출부에서 스탬프한다
(``auto/state.py`` ``transition()``, ADR-0037 §3).

계약: ``docs/02_MISSION_LIFECYCLE.md`` §3.1, §9
결정: ``docs/adr/0037-mission-record-and-canonical-stage.md``,
``docs/adr/0038-mcx-cli-surface-contract.md`` §5
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from mission_control.domain.errors import MissionControlError
from mission_control.domain.stage import Stage


class InvalidStageTransitionError(MissionControlError):
    """Lifecycle §9에 없는 Stage 전이를 기록하려 했다."""

    def __init__(self, *, mission_id: str, source: Stage, destination: Stage) -> None:
        super().__init__(
            f"mission {mission_id}: {source.value} -> {destination.value} 전이는 "
            "Lifecycle §9 표에 없다"
        )
        self.mission_id = mission_id
        self.source = source
        self.destination = destination


class CompletionNotFromVerifyError(MissionControlError):
    """Verify가 아닌 Stage에서 MISSION COMPLETE를 기록하려 했다 (§9.1)."""

    def __init__(self, *, mission_id: str, source: Stage) -> None:
        super().__init__(
            f"mission {mission_id}: MISSION COMPLETE는 verify에서만 기록할 수 있다 — "
            f"{source.value}에서는 안 된다"
        )
        self.mission_id = mission_id
        self.source = source


class MissionCompletedError(MissionControlError):
    """완료된 mission의 record를 다시 바꾸려 했다."""

    def __init__(self, *, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}는 이미 완료됐다")
        self.mission_id = mission_id


class MissionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETE = "complete"


#: Lifecycle §9 표의 Stage 전이만 담는다. 같은 Stage에 머무는 HOLD 행은
#: 전이가 아니고(§10.2), Verify → COMPLETE는 status 전이라 여기 없다.
ALLOWED_TRANSITIONS: Final[dict[Stage, frozenset[Stage]]] = {
    Stage.BRIEF: frozenset({Stage.BLUEPRINT}),
    Stage.BLUEPRINT: frozenset({Stage.EXECUTE}),
    Stage.EXECUTE: frozenset({Stage.VERIFY, Stage.RECOVER, Stage.BRIEF, Stage.BLUEPRINT}),
    Stage.VERIFY: frozenset({Stage.RECOVER, Stage.BRIEF, Stage.BLUEPRINT}),
    Stage.RECOVER: frozenset({Stage.VERIFY, Stage.EXECUTE, Stage.BRIEF, Stage.BLUEPRINT}),
}


class StageTransition(BaseModel):
    """한 번의 Stage 전이 — 시각과 사유를 함께 남긴다 (ADR-0037 §3)."""

    model_config = ConfigDict(frozen=True)

    source: Stage
    destination: Stage
    at: str
    reason: str


class MissionRecord(BaseModel):
    """합성 계층이 소유하는 mission 단위 기록.

    Lifecycle §3.1의 나머지 항목(input revisions, attempt lineage, Gate·
    Telemetry reference)은 여기 복제하지 않는다 — 각 Stage 저장소가 소유하고
    status 표시가 조합한다 (ADR-0038 §5).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mission_id: str
    schema_version: Literal[1] = 1
    workspace: str
    current_stage: Stage = Stage.BRIEF
    status: MissionStatus = MissionStatus.ACTIVE
    completed_at: str | None = None
    #: 쓰기 순서. 저장소는 이 값으로 덮어쓰기를 판정한다 (ADR-0014와 같은 축).
    sequence: int = 1
    transitions: tuple[StageTransition, ...] = ()

    @classmethod
    def create(cls, *, mission_id: str, workspace: str) -> MissionRecord:
        """Lifecycle §9 첫 행 — Mission created → Brief."""
        return cls(mission_id=mission_id, workspace=workspace)

    def transit(self, *, destination: Stage, at: str, reason: str) -> MissionRecord:
        """합법 전이면 새 record를, 같은 Stage면 자기 자신을 돌려준다."""
        if self.status is MissionStatus.COMPLETE:
            raise MissionCompletedError(mission_id=self.mission_id)
        if destination is self.current_stage:
            return self
        if destination not in ALLOWED_TRANSITIONS[self.current_stage]:
            raise InvalidStageTransitionError(
                mission_id=self.mission_id,
                source=self.current_stage,
                destination=destination,
            )
        transition = StageTransition(
            source=self.current_stage, destination=destination, at=at, reason=reason
        )
        return self.model_copy(
            update={
                "current_stage": destination,
                "sequence": self.sequence + 1,
                "transitions": (*self.transitions, transition),
            }
        )

    def complete(self, *, at: str) -> MissionRecord:
        """MISSION COMPLETE — 호출 자격은 Verify Gate ``CLEAR``뿐이다.

        자격 검사(실제 Gate 판정)는 호출자(합성)의 책임이다. 이 메서드는
        Verify가 아닌 Stage에서의 완료 선언만 구조로 막는다 (Lifecycle §9.1 —
        Execute·Recover는 COMPLETE로 갈 수 없다).
        """
        if self.status is MissionStatus.COMPLETE:
            raise MissionCompletedError(mission_id=self.mission_id)
        if self.current_stage is not Stage.VERIFY:
            raise CompletionNotFromVerifyError(
                mission_id=self.mission_id, source=self.current_stage
            )
        return self.model_copy(
            update={
                "status": MissionStatus.COMPLETE,
                "completed_at": at,
                "sequence": self.sequence + 1,
            }
        )
