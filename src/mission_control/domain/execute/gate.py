"""Execute Gate — Verify로 넘길 수 있는지에 대한 판정.

``CLEAR — Clear for Verify``는 AC가 충족되었다는 보장이 아니다. 실행이
끝났고 결과가 관찰 가능하며 Verify가 독립적으로 판정할 입력이 있다는 뜻이다
(``docs/07_EXECUTE.md`` §10).

v1의 결정적 판정 조건: 현재 Blueprint revision의 모든 AC에 대해 가장 최근
attempt가 ``EXECUTED_UNVERIFIED``이고, 결과를 알 수 없는(``DISPATCHED``)
attempt가 남아 있지 않다. provenance와 결과-상태 일관성은 Gate가 아니라
attempt 스키마가 생성 시점에 강제하므로 여기서 재검사하지 않는다
(ADR-0023 §3 — Brief·Blueprint Gate와 같은 배치).

Execute → Verify 전이 helper는 Verify Stage(Phase 4)와 함께 만든다. 전이의
반대편이 없는 지금은 검증할 수 없는 코드다.

계약: ``docs/07_EXECUTE.md`` §10
결정: ``docs/adr/0024-execute-v1-execution-model.md``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mission_control.domain.blueprint.spec import Blueprint
from mission_control.domain.brief.gate import GateOutcome
from mission_control.domain.execute.state import (
    AttemptStatus,
    ExecuteState,
    StageRunStatus,
)
from mission_control.domain.stage import Stage


class ExecuteGateBlockingCondition(StrEnum):
    """Verify로의 진행을 막은 조건."""

    ATTEMPT_OPEN = "attempt_open"
    CRITERION_UNEXECUTED = "criterion_unexecuted"
    CRITERION_FAILED = "criterion_failed"
    STAGE_UNSETTLED = "stage_unsettled"


@dataclass(frozen=True, slots=True)
class ExecuteGateBlocker:
    condition: ExecuteGateBlockingCondition
    detail: str


@dataclass(frozen=True, slots=True)
class ExecuteGateDecision:
    """한 Blueprint revision에 대한 Execute Gate 판정과 그 근거."""

    outcome: GateOutcome
    blueprint_revision: int
    gate_blockers: tuple[ExecuteGateBlocker, ...]
    next_destination: Stage | None

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        """사람이 읽을 수 있는 이유 목록. 표시용이며 판정 근거는 원본 blocker다."""
        return tuple(blocker.detail for blocker in self.gate_blockers)


def evaluate_execute_gate(*, state: ExecuteState, blueprint: Blueprint) -> ExecuteGateDecision:
    """실행 결과가 Verify로 넘어갈 준비가 되었는지 판정한다.

    이 함수는 순수 함수다. 상태를 바꾸지 않으며 저장도 하지 않는다. Blueprint
    Gate가 여전히 ``CLEAR``인지(Brief가 그 사이 바뀌지 않았는지)는 호출하는
    application 계층이 이 판정 **전에** 확인한다 — 진입 조건과 진행 조건을
    한 판정에 섞으면 어느 쪽이 막았는지 알 수 없다.
    """
    gate_blockers: list[ExecuteGateBlocker] = []

    open_attempt = state.open_attempt
    if open_attempt is not None:
        gate_blockers.append(
            ExecuteGateBlocker(
                condition=ExecuteGateBlockingCondition.ATTEMPT_OPEN,
                detail=(
                    f"{open_attempt.ac_key}의 시도 {open_attempt.number}에 기록된 결과가 "
                    "없다; 결과를 알 수 없다"
                ),
            )
        )

    for run in state.stage_runs:
        if run.blueprint_revision != blueprint.revision:
            continue
        if run.status in {
            StageRunStatus.WORKERS_DISPATCHED,
            StageRunStatus.COORDINATOR_DISPATCHED,
            StageRunStatus.REVALIDATING,
            StageRunStatus.HOLD,
        }:
            gate_blockers.append(
                ExecuteGateBlocker(
                    condition=ExecuteGateBlockingCondition.STAGE_UNSETTLED,
                    detail=(
                        f"{run.run_id}이 settled되지 않았다: {run.status.value}"
                        + (f" — {run.error}" if run.error else "")
                    ),
                )
            )

    for criterion in blueprint.acceptance_criteria:
        latest = state.latest_for(ac_key=criterion.key, blueprint_revision=blueprint.revision)
        if latest is None:
            gate_blockers.append(
                ExecuteGateBlocker(
                    condition=ExecuteGateBlockingCondition.CRITERION_UNEXECUTED,
                    detail=f"{criterion.key}가 아직 실행되지 않았다",
                )
            )
        elif latest.status is AttemptStatus.EXECUTION_FAILED:
            gate_blockers.append(
                ExecuteGateBlocker(
                    condition=ExecuteGateBlockingCondition.CRITERION_FAILED,
                    detail=(f"{criterion.key}가 시도 {latest.number}에서 실패했다: {latest.error}"),
                )
            )

    cleared = not gate_blockers
    return ExecuteGateDecision(
        outcome="CLEAR" if cleared else "HOLD",
        blueprint_revision=blueprint.revision,
        gate_blockers=tuple(gate_blockers),
        next_destination=Stage.VERIFY if cleared else None,
    )
