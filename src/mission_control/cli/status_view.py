"""``mcx status``가 렌더할 스냅샷을 저장 상태에서 조립한다 (ADR-0038 §6.1 c).

이 모듈은 **읽기만 한다**. Gate는 저장된 판정을 믿지 않고 다시 판정하지만
(ADR-0037 "Gate 재계산이 이긴다"), 다섯 ``decide_gate``는 저장 상태만 읽는
결정적 함수이며 AI를 부르지 않는다.

로우 상태 파생은 결정적이다 — 진행 중 > 저장 없음 > Gate 판정 순서이며,
그 밖의 판단을 넣지 않는다.
"""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from mission_control.adapters.persistence.file_blueprint_repository import (
    FileBlueprintRepository,
)
from mission_control.adapters.persistence.file_brief_repository import FileBriefRepository
from mission_control.adapters.persistence.file_execute_repository import FileExecuteRepository
from mission_control.adapters.persistence.file_verify_repository import FileVerifyRepository
from mission_control.adapters.workspace.worktree import BRANCH_PREFIX
from mission_control.cli import composition
from mission_control.cli.composition import Adapters, StateLayout
from mission_control.cli.journal import JournalEntry, MissionJournal, total_calls
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.brief.state import BriefState
from mission_control.domain.execute.state import ExecuteState
from mission_control.domain.mission import MissionRecord, MissionStatus
from mission_control.domain.stage import Stage
from mission_control.domain.verify.evidence import VerifyState

#: 표에 나오는 순서와 표시 이름. Recover는 진입한 적이 있을 때만 끼어든다.
STAGE_LABELS: dict[Stage, str] = {
    Stage.BRIEF: "Brief",
    Stage.BLUEPRINT: "Blueprint",
    Stage.EXECUTE: "Execute",
    Stage.RECOVER: "Recover",
    Stage.VERIFY: "Verify",
}

#: 진행 위치의 분자를 세는 순서. Recover는 교정 경로라 순번을 갖지 않으며,
#: 분모는 다섯 단계 전체다 (승인된 표기 ``Verify (4/5)``).
FORWARD_STAGES: tuple[Stage, ...] = (
    Stage.BRIEF,
    Stage.BLUEPRINT,
    Stage.EXECUTE,
    Stage.VERIFY,
)

#: CLEAR일 때 다음에 할 일. 표시이지 결정이 아니다 (ADR-0038 §1).
NEXT_WHEN_CLEAR: dict[Stage, str] = {
    Stage.BRIEF: "mcx blueprint generate",
    Stage.BLUEPRINT: "mcx execute stage --max-workers 2",
    Stage.EXECUTE: "mcx verify mechanical",
    Stage.RECOVER: "mcx verify mechanical",
    Stage.VERIFY: "mcx verify gate — CLEAR면 MISSION COMPLETE",
}

#: HOLD일 때 그 단계에서 쓸 수 있는 명령. 어느 것을 쓸지는 사용자가 정한다.
COMMANDS_WHEN_HOLD: dict[Stage, tuple[str, ...]] = {
    Stage.BRIEF: ("mcx brief ask", 'mcx brief answer "<답변>"', "mcx brief assess"),
    Stage.BLUEPRINT: (
        "mcx blueprint qa",
        "mcx blueprint revise --draft-file <파일>",
        'mcx blueprint approve "<문장>"',
    ),
    Stage.EXECUTE: (
        "mcx execute stage --max-workers 2",
        "mcx execute next",
        "mcx recover plan",
    ),
    Stage.VERIFY: (
        "mcx verify semantic",
        "mcx recover plan",
        "mcx blueprint evolve",
    ),
    Stage.RECOVER: ("mcx recover dispatch", "mcx recover gate"),
}


class RowState(StrEnum):
    """상태 어휘는 다섯 개로 닫힌다 (ADR-0038 §6.1 c)."""

    DONE = "done"
    RUNNING = "running"
    HOLD = "hold"
    WAITING = "waiting"
    RECOVERED = "recovered"


@dataclass(frozen=True)
class GateView:
    """한 단계의 Gate 재판정 결과. 판정 불가는 이유로 남는다."""

    outcome: str | None = None
    reasons: tuple[str, ...] = ()
    unavailable: str | None = None


@dataclass(frozen=True)
class IsolationView:
    """실행이 사용자의 workspace 밖에서 돌았을 때 그 자리와 브랜치."""

    workspace: str
    branch: str


@dataclass(frozen=True)
class StageRow:
    label: str
    summary: str
    state: RowState


@dataclass(frozen=True)
class BlockingBlock:
    """차단 블록 — 이유는 지어내지 않고 Gate와 감사 기록의 원문을 싣는다."""

    title: str
    quoted: tuple[str, ...]
    actions: tuple[str, ...]


@dataclass(frozen=True)
class StatusSnapshot:
    mission_id: str
    intent: str
    workspace: str
    #: 실행이 실제로 돈 자리 — 격리가 걸렸을 때만 채워진다 (ADR-0045 §5).
    isolation: IsolationView | None
    complete: bool
    completed_at: str | None
    current_stage: Stage
    current_index: int
    total_stages: int
    elapsed_seconds: float | None
    calls: tuple[tuple[str, int], ...]
    running_command: str | None
    rows: tuple[StageRow, ...]
    blocking: BlockingBlock | None
    next_action: str | None
    correction_count: int
    artifacts: tuple[str, ...]
    mismatch: str | None
    journal: tuple[JournalEntry, ...]


async def _decide(awaitable: Awaitable[object]) -> GateView:
    """Gate를 다시 판정한다. 진입 조건 위반은 예외이며 사유로 옮긴다."""
    try:
        decision = await awaitable
    except Exception as exc:  # noqa: BLE001 — status는 판정 실패로 죽지 않는다
        return GateView(unavailable=f"{type(exc).__name__}: {exc}")
    return GateView(
        outcome=str(getattr(decision, "outcome", "")),
        reasons=tuple(getattr(decision, "blocking_reasons", ())),
    )


def _parse(moment: str) -> datetime | None:
    try:
        return datetime.fromisoformat(moment)
    except ValueError:
        return None


def _elapsed_seconds(entries: tuple[JournalEntry, ...], now: str) -> float | None:
    if not entries:
        return None
    start = _parse(entries[0].started_at)
    if start is None:
        return None
    last = entries[-1]
    end = _parse(last.finished_at) if last.finished_at else _parse(now)
    if end is None:
        return None
    return max(0.0, (end - start).total_seconds())


def _stage_of(command: str) -> Stage | None:
    try:
        return Stage(command.split(" ", 1)[0])
    except ValueError:
        return None


def _correction_count(attempt_keys: tuple[tuple[int, str], ...]) -> int:
    """같은 revision·AC의 두 번째 이후 시도가 교정이다 — attempt에서 파생한다."""
    seen: set[tuple[int, str]] = set()
    corrections = 0
    for key in attempt_keys:
        if key in seen:
            corrections += 1
        else:
            seen.add(key)
    return corrections


def _isolation(record: MissionRecord, execute: ExecuteState | None) -> IsolationView | None:
    """실행이 사용자의 workspace 밖에서 돌았으면 그 자리를 돌려준다.

    유도하지 않고 **기록된 것**을 읽는다 — 각 시도의 envelope가 자기가 돈 자리를
    들고 있으므로 (ADR-0045 §2), status가 worktree를 다시 계산할 이유가 없다.
    """
    if execute is None or not execute.attempts:
        return None
    used = execute.attempts[-1].envelope.workspace
    if used == record.workspace:
        return None
    return IsolationView(workspace=used, branch=f"{BRANCH_PREFIX}/{record.mission_id}")


def _record_mismatch(
    *,
    stage: Stage,
    stored: bool,
    blueprint_revision: int | None,
    verify_blueprint_revision: int | None,
) -> str | None:
    """stored Stage와 artifact lineage가 어긋나는 표면 진단 (ADR-0037)."""
    if not stored:
        return (
            f"record는 {stage.value}라고 하는데 그 Stage 저장소가 비어 있다; Gate 재계산이 이긴다"
        )
    if (
        stage is Stage.VERIFY
        and blueprint_revision is not None
        and verify_blueprint_revision is not None
        and blueprint_revision != verify_blueprint_revision
    ):
        return (
            f"record는 verify지만 Verify evidence는 Blueprint revision "
            f"{verify_blueprint_revision}, current Blueprint는 {blueprint_revision}다; "
            "Gate 재계산이 이긴다"
        )
    return None


async def build_snapshot(
    *,
    layout: StateLayout,
    adapters: Adapters,
    record: MissionRecord,
    now: str,
) -> StatusSnapshot:
    """저장된 모든 것을 한 번 읽어 스냅샷을 만든다."""
    mission_id = record.mission_id

    brief = await FileBriefRepository(root=layout.state).load(mission_id)
    blueprint = await FileBlueprintRepository(root=layout.state).load(mission_id)
    execute = await FileExecuteRepository(root=layout.state).load(mission_id)
    verify = await FileVerifyRepository(root=layout.state).load(mission_id)
    entries = MissionJournal(root=layout.state, mission_id=mission_id).entries()

    entered_recover = any(
        transition.destination is Stage.RECOVER for transition in record.transitions
    )
    stored: dict[Stage, bool] = {
        Stage.BRIEF: brief is not None,
        Stage.BLUEPRINT: blueprint is not None,
        Stage.EXECUTE: execute is not None and bool(execute.attempts),
        Stage.VERIFY: verify is not None,
        Stage.RECOVER: entered_recover,
    }

    gates: dict[Stage, GateView] = {}
    if stored[Stage.BRIEF]:
        gates[Stage.BRIEF] = await _decide(
            composition.brief_service(layout, adapters).decide_gate(mission_id=mission_id)
        )
    if stored[Stage.BLUEPRINT]:
        gates[Stage.BLUEPRINT] = await _decide(
            composition.blueprint_service(layout, adapters).decide_gate(mission_id=mission_id)
        )
    if stored[Stage.EXECUTE]:
        gates[Stage.EXECUTE] = await _decide(
            composition.execute_service(layout, adapters, workspace=record.workspace).decide_gate(
                mission_id=mission_id
            )
        )
    if stored[Stage.VERIFY]:
        gates[Stage.VERIFY] = await _decide(
            composition.verify_service(layout, adapters).decide_gate(mission_id=mission_id)
        )
    if stored[Stage.RECOVER]:
        gates[Stage.RECOVER] = await _decide(
            composition.recover_service(layout, adapters, workspace=record.workspace).decide_gate(
                mission_id=mission_id
            )
        )

    running = next((entry for entry in reversed(entries) if entry.in_progress), None)
    running_stage = _stage_of(running.command) if running is not None else None

    corrections = _correction_count(
        tuple((attempt.blueprint_revision, attempt.ac_key) for attempt in execute.attempts)
        if execute
        else ()
    )
    summaries = _summaries(
        brief=brief,
        blueprint=blueprint,
        execute=execute,
        verify=verify,
        corrections=corrections,
        stored=stored,
        gates=gates,
    )

    rows = tuple(
        StageRow(
            label=label,
            summary=summaries[stage],
            state=_row_state(
                stage=stage,
                stored=stored[stage],
                gate=gates.get(stage, GateView()),
                running=running_stage is stage,
                corrections=corrections,
            ),
        )
        for stage, label in STAGE_LABELS.items()
        if stage is not Stage.RECOVER or stored[Stage.RECOVER]
    )

    complete = record.status is MissionStatus.COMPLETE
    current_gate = gates.get(record.current_stage, GateView())
    blocked = not complete and (
        current_gate.outcome == "HOLD" or current_gate.unavailable is not None
    )

    return StatusSnapshot(
        mission_id=mission_id,
        intent=brief.initial_intent if brief is not None else "",
        workspace=record.workspace,
        isolation=_isolation(record, execute),
        complete=complete,
        completed_at=record.completed_at,
        current_stage=record.current_stage,
        current_index=(
            FORWARD_STAGES.index(record.current_stage) + 1
            if record.current_stage in FORWARD_STAGES
            else 0
        ),
        total_stages=len(STAGE_LABELS),
        elapsed_seconds=_elapsed_seconds(entries, now),
        calls=tuple(total_calls(entries).items()),
        running_command=running.command if running is not None else None,
        rows=rows,
        blocking=(
            _blocking_block(stage=record.current_stage, gate=current_gate, brief=brief)
            if blocked
            else None
        ),
        next_action=(
            NEXT_WHEN_CLEAR.get(record.current_stage)
            if not complete and current_gate.outcome == "CLEAR"
            else None
        ),
        correction_count=corrections,
        artifacts=(
            tuple(
                artifact
                for criterion in blueprint.current.acceptance_criteria
                for artifact in criterion.expected_artifacts
            )
            if blueprint is not None
            else ()
        ),
        mismatch=_record_mismatch(
            stage=record.current_stage,
            stored=stored[record.current_stage],
            blueprint_revision=blueprint.revision if blueprint is not None else None,
            verify_blueprint_revision=(
                verify.evidence.blueprint_revision
                if verify is not None and verify.evidence is not None
                else None
            ),
        ),
        journal=entries,
    )


def _row_state(
    *,
    stage: Stage,
    stored: bool,
    gate: GateView,
    running: bool,
    corrections: int,
) -> RowState:
    """진행 중 > 저장 없음 > Gate 판정. 이 순서 밖의 판단은 넣지 않는다."""
    if running:
        return RowState.RUNNING
    if not stored:
        return RowState.WAITING
    if gate.unavailable is not None:
        # 증거는 있는데 진입이 무효다 — "대기"로 표시하면 그 사실이 사라진다.
        return RowState.HOLD
    if gate.outcome != "CLEAR":
        return RowState.HOLD
    if stage is Stage.RECOVER and corrections:
        return RowState.RECOVERED
    return RowState.DONE


def _summaries(
    *,
    brief: BriefState | None,
    blueprint: BlueprintState | None,
    execute: ExecuteState | None,
    verify: VerifyState | None,
    corrections: int,
    stored: dict[Stage, bool],
    gates: dict[Stage, GateView],
) -> dict[Stage, str]:
    """각 로우의 한 줄 요약 — 저장된 사실만 적는다."""
    lines: dict[Stage, str] = dict.fromkeys(STAGE_LABELS, "—")

    if brief is not None:
        scores = (
            "/".join(f"{score.clarity:.2f}" for score in brief.assessment.scores)
            if brief.assessment is not None
            else "미평가"
        )
        approved = " · 승인됨" if brief.has_current_approval else ""
        lines[Stage.BRIEF] = (
            f"질문 {len(brief.rounds)}라운드 · 명확도 {scores} · rev {brief.revision}{approved}"
        )

    if blueprint is not None:
        qa = blueprint.qa_records
        trail = (
            f" · QA {qa[0].assessment.score:.2f}→{qa[-1].assessment.score:.2f}"
            if qa
            else " · QA 미실시"
        )
        approved = " · 승인됨" if blueprint.has_current_approval else ""
        lines[Stage.BLUEPRINT] = (
            f"AC {len(blueprint.current.acceptance_criteria)}개{trail}"
            f" · rev {blueprint.revision}{approved}"
        )
    else:
        lines[Stage.BLUEPRINT] = "Brief CLEAR 대기"

    if execute is not None and execute.attempts:
        current_revision = blueprint.revision if blueprint is not None else None
        attempts = tuple(
            attempt
            for attempt in execute.attempts
            if current_revision is None or attempt.blueprint_revision == current_revision
        )
        if attempts:
            distinct = len({attempt.ac_key for attempt in attempts})
            failed = sum(1 for attempt in attempts if attempt.error)
            detail = f" · 실패 {failed}건" if failed else ""
            evidence_is_current = (
                verify is not None
                and verify.evidence is not None
                and verify.evidence.blueprint_revision == current_revision
            )
            verify_outcome = gates.get(Stage.VERIFY, GateView()).outcome
            verification = (
                "검증 완료"
                if evidence_is_current and verify_outcome == "CLEAR"
                else "검증 중"
                if evidence_is_current
                else "검증 전"
            )
            lines[Stage.EXECUTE] = (
                f"AC {distinct}개 실행 · 시도 {len(attempts)}회{detail} — {verification}"
            )
        else:
            lines[Stage.EXECUTE] = f"Blueprint rev {current_revision} 실행 대기"
    else:
        lines[Stage.EXECUTE] = "Blueprint 승인 대기"

    if corrections:
        ready = gates.get(Stage.RECOVER, GateView()).outcome == "CLEAR"
        lines[Stage.RECOVER] = f"교정 {corrections}회" + (
            " · 재검증 준비됨" if ready else " · 진행 중"
        )
    elif stored[Stage.RECOVER]:
        lines[Stage.RECOVER] = "진입 · 교정 없음"

    if verify is not None:
        mechanical = (
            f"mechanical {sum(1 for run in verify.evidence.runs if run.passed)}"
            f"/{len(verify.evidence.runs)}"
            if verify.evidence is not None
            else "mechanical 미실시"
        )
        semantic = (
            f"semantic {sum(1 for item in verify.verdicts.verdicts if item.satisfied)}"
            f"/{len(verify.verdicts.verdicts)}"
            if verify.verdicts is not None
            else "semantic 미판정"
        )
        lines[Stage.VERIFY] = f"{mechanical} · {semantic}"
    else:
        lines[Stage.VERIFY] = "Execute CLEAR 대기"

    return lines


def _blocking_block(*, stage: Stage, gate: GateView, brief: BriefState | None) -> BlockingBlock:
    """차단 블록을 만든다 — 인용문은 저장된 원문이거나 Gate의 이유다."""
    if gate.unavailable is not None:
        return BlockingBlock(
            title=f"{STAGE_LABELS[stage]} 진입 무효",
            quoted=(gate.unavailable,),
            actions=COMMANDS_WHEN_HOLD[stage],
        )

    if stage is Stage.BRIEF and brief is not None and brief.closure_audit is not None:
        questions = brief.closure_audit.audit.decision.blocking_questions
        if questions:
            return BlockingBlock(
                title="차단 질문 (closure 감사)",
                quoted=questions,
                actions=('mcx brief answer "<답변>" --question "<질문>"', "mcx brief audit"),
            )

    return BlockingBlock(
        title=f"{STAGE_LABELS[stage]} Gate HOLD",
        quoted=gate.reasons,
        actions=COMMANDS_WHEN_HOLD[stage],
    )
