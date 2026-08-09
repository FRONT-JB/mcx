"""mcx — coordinates AI coding missions. Executed is not verified.

명령 하나 = application service 메서드 하나. CLI는 Gate·retry·Recover를
결정하지 않고, 표면 파리티는 구현 공유로 얻는다 (ADR-0038 §1 — upstream
정렬). 모든 명령은 비대화형 단발이며 사용자 결정은 인자와 별도 명령으로만
들어온다 (§2).

exit code (§3): 0 성공/긍정 판정, 1 오류, 2 정상 수행된 판정이 부정
(gate ``HOLD``, QA 비PASS action).

mission record는 이 층만 쓴다 — Stage 진입 명령 성공 시 전이를 기록하고,
불법 전이는 명령을 실패시키지 않는 경고다 (Gate가 이긴다 — ADR-0037 §2).
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
import dataclasses
from datetime import UTC, datetime
from enum import Enum
import json
from pathlib import Path
import sys
import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from mission_control.adapters.workspace import worktree
from mission_control.cancellation import cancel_when
from mission_control.cli import backend_profile, composition, status_render, status_view
from mission_control.cli.calls import CallCounter
from mission_control.cli.composition import Adapters, StateLayout
from mission_control.cli.journal import MissionJournal
from mission_control.domain.blueprint.assembly import BlueprintDraft
from mission_control.domain.blueprint.qa import LoopAction
from mission_control.domain.blueprint.spec import AcceptanceCriterion
from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    ConfirmationAuthority,
    RequirementSection,
)
from mission_control.domain.mission import (
    InvalidStageTransitionError,
    MissionCompletedError,
    MissionRecord,
    MissionStatus,
)
from mission_control.domain.stage import Stage

DEFAULT_STATE_DIR = Path.home() / ".mcx"

#: Stage 진입 명령 → 기록할 destination (ADR-0038 §5). backward route는 v1에
#: 트리거가 없다 — 어긋남은 status가 표시한다.
_TRANSITION_TRIGGERS: dict[tuple[str, str], Stage] = {
    ("blueprint", "generate"): Stage.BLUEPRINT,
    ("execute", "next"): Stage.EXECUTE,
    ("verify", "mechanical"): Stage.VERIFY,
    ("verify", "semantic"): Stage.VERIFY,
    ("recover", "dispatch"): Stage.RECOVER,
}

BRIEF_VERBS = frozenset(
    {
        "start",
        "ask",
        "answer",
        "candidate",
        "resolve",
        "assess",
        "audit",
        "approve",
        "gate",
        "handoff",
    }
)


def normalize_argv(argv: list[str]) -> list[str]:
    """``mcx brief "<intent>"`` 단축을 ``brief start``로 편다 (개정 1).

    upstream ``ooo init "..."``의 default-subcommand fallback과 같은 규칙 —
    verb 자리의 토큰이 verb가 아니면 프롬프트다. 프롬프트가 verb와 같은
    단어면 verb로 해석되는 모호성도 upstream과 동일하다.
    """
    if len(argv) >= 2 and argv[0] == "brief":
        head = argv[1]
        if head not in BRIEF_VERBS and not head.startswith("-"):
            return ["brief", "start", *argv[1:]]
    return argv


def _now() -> str:
    return datetime.now(UTC).isoformat()


#: 출력 수집기. ``None``이면 터미널로 나간다. MCP가 같은 dispatch를 부르면서
#: 결과를 가로채는 유일한 지점이다 (ADR-0041 §1) — 두 벌의 핸들러를 만들지
#: 않기 위해서다. ContextVar라 동시 호출이 서로의 출력을 섞지 않는다.
_COLLECTED: ContextVar[list[tuple[str, object]] | None] = ContextVar("mcx_output", default=None)


@contextmanager
def collecting() -> Iterator[list[tuple[str, object]]]:
    """이 블록 안의 출력을 터미널 대신 목록으로 모은다.

    항목은 ``("data", payload)``(구조화 출력), ``("text", str)``(사람용 렌더),
    ``("note", str)``(stderr 안내)다.
    """
    sink: list[tuple[str, object]] = []
    token = _COLLECTED.set(sink)
    try:
        yield sink
    finally:
        _COLLECTED.reset(token)


def _note(message: str) -> None:
    sink = _COLLECTED.get()
    if sink is None:
        print(message, file=sys.stderr)
    else:
        sink.append(("note", message))


def _write(message: str) -> None:
    """사람이 읽는 렌더 한 덩어리."""
    sink = _COLLECTED.get()
    if sink is None:
        print(message)
    else:
        sink.append(("text", message))


def jsonable(value: object) -> Any:
    """판정·상태 객체를 JSON으로 렌더 가능한 형태로 바꾼다 (ADR-0038 §4)."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def show(value: object) -> None:
    """구조화 출력 한 덩어리. MCP는 이것을 ``structured_content``로 받는다."""
    payload = jsonable(value)
    sink = _COLLECTED.get()
    if sink is None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        sink.append(("data", payload))


def build_parser() -> argparse.ArgumentParser:
    """명령 표면을 구성하는 순수 함수 — conformance 테스트가 고정한다."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--mission",
        default=None,
        help="mission id (생략: brief start는 자동 생성, 그 외는 마지막 시작 mission)",
    )
    common.add_argument(
        "--state-dir",
        type=Path,
        default=DEFAULT_STATE_DIR,
        help=f"상태 루트 (기본 {DEFAULT_STATE_DIR})",
    )

    parser = argparse.ArgumentParser(
        prog="mcx",
        description="mcx — coordinates AI coding missions. Executed is not verified.",
    )
    stage_sub = parser.add_subparsers(dest="stage", required=True)

    brief = stage_sub.add_parser("brief", help="Brief — 모호함 제거").add_subparsers(
        dest="verb", required=True
    )
    p = brief.add_parser("start", parents=[common], help="새 mission을 열고 초기 의도를 기록한다")
    p.add_argument("intent", help="mission의 초기 의도")
    p.add_argument("--workspace", default=None, help="실행 workspace (기본: 현재 디렉터리)")
    brief.add_parser("ask", parents=[common], help="사용자에게 물을 질문 하나를 생성한다")
    p = brief.add_parser("answer", parents=[common], help="열린 질문에 대한 답을 기록한다")
    p.add_argument("answer", help="질문에 대한 답변")
    p.add_argument("--authority", default="decision", choices=["decision", "observation"])
    p.add_argument(
        "--question", default=None, help="닫힌 질문 밖에서 온 질문(예: closure 차단 질문)"
    )
    p = brief.add_parser(
        "candidate", parents=[common], help="질문 답변 밖에서 온 요구사항 후보를 기록한다"
    )
    p.add_argument("--section", required=True, choices=[s.value for s in RequirementSection])
    p.add_argument("--text", required=True)
    p.add_argument(
        "--source", default="user_stated", choices=[s.value for s in CandidateContentSource]
    )
    p.add_argument(
        "--resolution",
        default="needs_confirmation",
        choices=[r.value for r in CandidateResolution],
    )
    p.add_argument("--authority", default="none", choices=[a.value for a in ConfirmationAuthority])
    p.add_argument("--required", action="store_true")
    p = brief.add_parser("resolve", parents=[common], help="미해결 후보의 처리를 확정한다")
    p.add_argument("--number", type=int, required=True)
    p.add_argument("--resolution", required=True, choices=[r.value for r in CandidateResolution])
    p.add_argument("--authority", default="none", choices=[a.value for a in ConfirmationAuthority])
    brief.add_parser("assess", parents=[common], help="명확도를 채점하고 종료 조건 충족을 본다")
    brief.add_parser("audit", parents=[common], help="종료 감사 3-lane을 돌려 차단 질문을 받는다")
    p = brief.add_parser("approve", parents=[common], help="사용자 승인을 현재 revision에 기록한다")
    p.add_argument("statement", help="승인 문장")
    brief.add_parser("gate", parents=[common], help="Blueprint 진입 가능 여부를 판정한다")
    brief.add_parser("handoff", parents=[common], help="승인된 Brief를 Blueprint 입력으로 투영한다")

    blueprint = stage_sub.add_parser(
        "blueprint", help="Blueprint — 승인 가능한 불변 명세"
    ).add_subparsers(dest="verb", required=True)
    blueprint.add_parser(
        "generate", parents=[common], help="Brief handoff에서 명세 초안을 만든다 (revision 1)"
    )
    blueprint.add_parser("qa", parents=[common], help="명세를 채점하고 루프의 다음 동작을 반환한다")
    p = blueprint.add_parser(
        "revise", parents=[common], help="사용자가 채택한 수정을 새 revision으로 적용한다"
    )
    p.add_argument("--draft-file", required=True, type=Path)
    p = blueprint.add_parser(
        "approve", parents=[common], help="사용자 승인을 채점된 현재 revision에 기록한다"
    )
    p.add_argument("statement", help="승인 문장")
    p.add_argument("--accept-below-threshold", action="store_true")
    blueprint.add_parser("gate", parents=[common], help="Execute 진입 가능 여부를 판정한다")

    execute = stage_sub.add_parser("execute", help="Execute — bounded work").add_subparsers(
        dest="verb", required=True
    )
    execute.add_parser(
        "next", parents=[common], help="다음 미실행 수용 기준 하나를 실행한다 (장기 — 침묵 900초)"
    )
    execute.add_parser("gate", parents=[common], help="Verify 진입 가능 여부를 판정한다")

    verify = stage_sub.add_parser("verify", help="Verify — evidence로 판정").add_subparsers(
        dest="verb", required=True
    )
    verify.add_parser(
        "mechanical", parents=[common], help="승인된 확인 명령을 실제로 실행하고 증거를 보존한다"
    )
    verify.add_parser(
        "semantic", parents=[common], help="증거 위에서 수용 기준별 판정을 기록한다 (장기)"
    )
    verify.add_parser("gate", parents=[common], help="MISSION COMPLETE 선언 가능 여부를 판정한다")

    recover = stage_sub.add_parser("recover", help="Recover — 제한적 교정").add_subparsers(
        dest="verb", required=True
    )
    recover.add_parser("plan", parents=[common], help="저장된 기록에서 실패 packet을 파생한다")
    recover.add_parser(
        "dispatch", parents=[common], help="실패 증거를 실어 교정을 재실행한다 (장기)"
    )
    recover.add_parser("gate", parents=[common], help="교정을 계속할 수 있는지 판정한다")

    status = stage_sub.add_parser("status", parents=[common], help="mission record와 Stage 요약")
    status.set_defaults(verb="show")
    status.add_argument("--full", action="store_true", help="명령 단위 원장까지 보인다")
    status.add_argument("--json", action="store_true", help="구조화 출력 (개정 2 이전과 동일)")
    status.add_argument("--plain", action="store_true", help="테두리·상태를 ASCII로 그린다")

    # 정리는 mission 하나가 아니라 남은 것 전부를 훑는다 — ``--mission``이 없는
    # 유일한 명령이다 (ADR-0045 §7).
    cleanup = stage_sub.add_parser(
        "cleanup", help="끝난 mission의 worktree와 브랜치를 치운다 (병합된 것만)"
    )
    cleanup.set_defaults(verb="sweep", mission=None)
    cleanup.add_argument(
        "--state-dir",
        type=Path,
        default=DEFAULT_STATE_DIR,
        help=f"상태 루트 (기본 {DEFAULT_STATE_DIR})",
    )
    cleanup.add_argument("--dry-run", action="store_true", help="무엇이 지워질지만 보인다")
    cleanup.add_argument(
        "--force",
        action="store_true",
        help="병합되지 않은 worktree도 치운다 (브랜치는 남는다)",
    )

    return parser


def _current_mission_pointer(layout: StateLayout) -> Path:
    return layout.state / "current_mission"


def _resolve_mission(args: argparse.Namespace, layout: StateLayout) -> str:
    """생략된 ``--mission``을 채운다 (ADR-0038 개정 1).

    brief start는 새 id를 만들고, 그 외 명령은 마지막으로 시작한 mission을
    쓴다. 최근 mission 추론은 upstream CLI에 없는 등록된 divergence다 —
    병행 mission에서는 ``--mission`` 명시가 안전 경계다.
    """
    if args.mission:
        return str(args.mission)
    if args.stage == "brief" and args.verb == "start":
        return f"m-{uuid4().hex[:6]}"
    pointer = _current_mission_pointer(layout)
    if pointer.exists():
        value = pointer.read_text(encoding="utf-8").strip()
        if value:
            return value
    raise LookupError(
        'no mission specified and none started yet; run `mcx brief "<intent>"` first'
    )


async def _load_record(layout: StateLayout, mission_id: str) -> MissionRecord | None:
    return await composition.mission_repository(layout).load(mission_id)


async def _require_workspace(layout: StateLayout, mission_id: str) -> str:
    record = await _load_record(layout, mission_id)
    if record is None:
        raise LookupError(
            f"mission record not found for {mission_id}; run `mcx brief start` first"
        )
    return record.workspace


@contextmanager
def _isolated(layout: StateLayout, mission_id: str, workspace: str) -> Iterator[str]:
    """변경을 만드는 명령의 실행 자리를 미션 전용 worktree로 옮긴다 (ADR-0045).

    git 저장소가 아니면 원래 workspace가 그대로 나온다. 격리가 걸렸을 때는
    **반드시 알린다** — 사용자의 checkout에는 아무 일도 일어나지 않으므로,
    어디서 일어났는지 보이지 않으면 아무것도 안 한 것으로 읽힌다 (§5).
    """
    isolation = worktree.prepare(workspace, mission_id=mission_id, root=layout.worktrees)
    if isolation is None:
        yield workspace
        return
    _note(f"worktree: {isolation.workspace}")
    _note(f"branch:   {isolation.branch} — 병합은 사용자가 결정한다")
    with worktree.hold(isolation):
        yield isolation.workspace


async def _record_transition(
    layout: StateLayout, mission_id: str, *, stage: str, verb: str
) -> None:
    """진입 명령 성공 후 전이를 기록한다 — 실패는 경고이지 명령 실패가 아니다."""
    destination = _TRANSITION_TRIGGERS.get((stage, verb))
    if destination is None:
        return
    repository = composition.mission_repository(layout)
    record = await repository.load(mission_id)
    if record is None:
        _note(f"warning: no mission record for {mission_id}; transition not recorded")
        return
    try:
        moved = record.transit(destination=destination, at=_now(), reason=f"mcx {stage} {verb}")
    except (InvalidStageTransitionError, MissionCompletedError) as exc:
        _note(f"warning: transition not recorded ({exc}); gate recomputation wins")
        return
    if moved is not record:
        await repository.save(moved)


async def _record_completion(layout: StateLayout, mission_id: str) -> None:
    repository = composition.mission_repository(layout)
    record = await repository.load(mission_id)
    if record is None:
        _note(f"warning: no mission record for {mission_id}; MISSION COMPLETE not recorded")
        return
    if record.status is MissionStatus.COMPLETE:
        return
    try:
        await repository.save(record.complete(at=_now()))
    except Exception as exc:  # noqa: BLE001 — 기록 실패는 판정을 뒤집지 않는다
        _note(f"warning: MISSION COMPLETE not recorded ({exc}); gate recomputation wins")


def _load_draft(path: Path) -> BlueprintDraft:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return BlueprintDraft(
        goal=raw["goal"],
        constraints=tuple(raw["constraints"]),
        non_goals=tuple(raw["non_goals"]),
        acceptance_criteria=tuple(
            AcceptanceCriterion(
                description=item["description"],
                verify_command=item.get("verify_command"),
                expected_artifacts=tuple(item.get("expected_artifacts", ())),
                output_assertion=item.get("output_assertion"),
            )
            for item in raw["acceptance_criteria"]
        ),
    )


async def _status(
    args: argparse.Namespace, layout: StateLayout, adapters: Adapters, mission_id: str
) -> int:
    """읽기 전용 요약. 원장을 늘리지 않는다 (ADR-0038 §6.1 a)."""
    record = await _load_record(layout, mission_id)
    if record is None:
        _note(f"error: mission record not found for {mission_id}")
        return 1

    if args.json:
        return await _status_json(layout, record, mission_id)

    snapshot = await status_view.build_snapshot(
        layout=layout, adapters=adapters, record=record, now=_now()
    )
    _write(status_render.render(snapshot, full=args.full, plain=args.plain))
    return 0


async def _status_json(layout: StateLayout, record: MissionRecord, mission_id: str) -> int:
    """개정 2 이전과 같은 구조화 출력 — 기계 소비자의 계약은 바뀌지 않는다."""
    from mission_control.adapters.persistence.file_blueprint_repository import (
        FileBlueprintRepository,
    )
    from mission_control.adapters.persistence.file_brief_repository import FileBriefRepository
    from mission_control.adapters.persistence.file_execute_repository import (
        FileExecuteRepository,
    )
    from mission_control.adapters.persistence.file_verify_repository import FileVerifyRepository

    brief = await FileBriefRepository(root=layout.state).load(mission_id)
    blueprint = await FileBlueprintRepository(root=layout.state).load(mission_id)
    execute = await FileExecuteRepository(root=layout.state).load(mission_id)
    verify = await FileVerifyRepository(root=layout.state).load(mission_id)

    stage_evidence: dict[Stage, bool] = {
        Stage.BRIEF: brief is not None,
        Stage.BLUEPRINT: blueprint is not None,
        Stage.EXECUTE: execute is not None,
        Stage.VERIFY: verify is not None,
        Stage.RECOVER: execute is not None,
    }
    mismatch = None
    if not stage_evidence[record.current_stage]:
        mismatch = (
            f"record says {record.current_stage.value} but its stage store is empty; "
            "gate recomputation wins"
        )

    show(
        {
            "record": jsonable(record),
            "stages": {
                "brief": None if brief is None else {"revision": brief.revision},
                "blueprint": None if blueprint is None else {"revision": blueprint.revision},
                "execute": None if execute is None else {"attempts": len(execute.attempts)},
                "verify": verify is not None,
            },
            "mismatch": mismatch,
            "journal": [jsonable(entry) for entry in MissionJournal(
                root=layout.state, mission_id=mission_id
            ).entries()],
        }
    )
    return 0


async def _dispatch_brief(
    args: argparse.Namespace, layout: StateLayout, adapters: Adapters
) -> int:
    service = composition.brief_service(layout, adapters)
    mission: str = args.mission
    verb: str = args.verb

    if verb == "start":
        workspace = args.workspace or str(Path.cwd())
        state = await service.start(mission_id=mission, initial_intent=args.intent)
        record = MissionRecord.create(mission_id=mission, workspace=workspace)
        await composition.mission_repository(layout).save(record)
        pointer = _current_mission_pointer(layout)
        pointer.write_text(f"{mission}\n", encoding="utf-8")
        # 다른 상태 파일과 같은 권한으로 맞춘다 — 이 하나만 0644였다
        # (ADR-0040 조사에서 실측 발견).
        pointer.chmod(0o600)
        show({"mission_id": state.mission_id, "revision": state.revision, "workspace": workspace})
    elif verb == "ask":
        show(await service.ask_next_question(mission_id=mission))
    elif verb == "answer":
        state = await service.record_answer(
            mission_id=mission,
            answer=args.answer,
            authority=args.authority,
            question=args.question,
        )
        show({"rounds": len(state.rounds), "revision": state.revision})
    elif verb == "candidate":
        state = await service.record_candidate(
            mission_id=mission,
            section=RequirementSection(args.section),
            text=args.text,
            content_source=CandidateContentSource(args.source),
            resolution=CandidateResolution(args.resolution),
            confirmation_authority=ConfirmationAuthority(args.authority),
            required=args.required,
        )
        show({"candidates": len(state.candidates), "revision": state.revision})
    elif verb == "resolve":
        state = await service.resolve_candidate(
            mission_id=mission,
            number=args.number,
            resolution=CandidateResolution(args.resolution),
            confirmation_authority=ConfirmationAuthority(args.authority),
        )
        show({"number": args.number, "revision": state.revision})
    elif verb == "assess":
        state = await service.assess_clarity(mission_id=mission)
        show(
            {
                "assessment": jsonable(state.assessment),
                "stability_signal": state.stability_signal,
            }
        )
    elif verb == "audit":
        state = await service.audit_closure(mission_id=mission)
        audit_record = state.closure_audit
        assert audit_record is not None
        show(audit_record.audit)
    elif verb == "approve":
        state = await service.approve(mission_id=mission, statement=args.statement)
        show({"approved_revision": state.revision})
    elif verb == "gate":
        decision = await service.decide_gate(mission_id=mission)
        show(decision)
        return 0 if decision.outcome == "CLEAR" else 2
    elif verb == "handoff":
        show(await service.build_handoff(mission_id=mission))
    return 0


async def _dispatch_blueprint(
    args: argparse.Namespace, layout: StateLayout, adapters: Adapters
) -> int:
    mission: str = args.mission
    verb: str = args.verb
    # 생성만 workspace를 필요로 한다 — 확인 명령 검출의 대상이다 (ADR-0044 §3).
    # 나머지 verb에서 요구하면 workspace 없는 mission의 채점·승인이 막힌다.
    workspace = await _require_workspace(layout, mission) if verb == "generate" else None
    service = composition.blueprint_service(layout, adapters, workspace=workspace)

    if verb == "generate":
        state = await service.generate(mission_id=mission)
        show(state.current)
    elif verb == "qa":
        state = await service.assess_qa(mission_id=mission)
        qa_record = state.qa_records[-1]
        action = state.loop(policy=composition.QA_POLICY).action
        show(
            {
                "iteration": len(state.qa_records),
                "revision": qa_record.revision,
                "assessment": jsonable(qa_record.assessment),
                "action": action.value,
            }
        )
        if action is LoopAction.EXHAUSTED:
            _note(
                "QA exhausted: 반복 상한에 도달했고 통과 점수가 없다. 결정은 사용자 "
                "몫이다 — `mcx blueprint revise`로 고치거나 `mcx blueprint approve "
                "--accept-below-threshold`로 현재 최선을 수락한다 (Lifecycle §10.4)."
            )
        elif action is LoopAction.ESCALATE:
            _note(
                "QA escalate: 명세 수준의 결함이다 — Brief를 재개해 요구사항을 고친 뒤 "
                "다시 생성한다."
            )
        return 0 if action is LoopAction.DONE else 2
    elif verb == "revise":
        state = await service.revise(mission_id=mission, draft=_load_draft(args.draft_file))
        show(state.current)
    elif verb == "approve":
        state = await service.approve(
            mission_id=mission,
            statement=args.statement,
            accept_below_threshold=args.accept_below_threshold,
        )
        show({"approved_revision": state.revision})
    elif verb == "gate":
        decision = await service.decide_gate(mission_id=mission)
        show(decision)
        return 0 if decision.outcome == "CLEAR" else 2
    return 0


async def _dispatch_execute(
    args: argparse.Namespace, layout: StateLayout, adapters: Adapters
) -> int:
    workspace = await _require_workspace(layout, args.mission)
    if args.verb == "next":
        with _isolated(layout, args.mission, workspace) as effective:
            service = composition.execute_service(layout, adapters, workspace=effective)
            state = await service.dispatch_next(mission_id=args.mission)
        show(state.attempts[-1])
    elif args.verb == "gate":
        service = composition.execute_service(layout, adapters, workspace=workspace)
        decision = await service.decide_gate(mission_id=args.mission)
        show(decision)
        return 0 if decision.outcome == "CLEAR" else 2
    return 0


async def _dispatch_verify(
    args: argparse.Namespace, layout: StateLayout, adapters: Adapters
) -> int:
    service = composition.verify_service(layout, adapters)
    mission: str = args.mission

    if args.verb == "mechanical":
        state = await service.run_mechanical(mission_id=mission)
        assert state.evidence is not None
        show(state.evidence.runs)
    elif args.verb == "semantic":
        state = await service.assess_semantics(mission_id=mission)
        assert state.verdicts is not None
        show(state.verdicts.verdicts)
    elif args.verb == "gate":
        decision = await service.decide_gate(mission_id=mission)
        show(decision)
        if decision.outcome == "CLEAR":
            await _record_completion(layout, mission)
            return 0
        return 2
    return 0


async def _dispatch_recover(
    args: argparse.Namespace, layout: StateLayout, adapters: Adapters
) -> int:
    workspace = await _require_workspace(layout, args.mission)
    if args.verb == "dispatch":
        # 교정도 변경을 만든다 — Execute와 같은 worktree를 재사용한다.
        with _isolated(layout, args.mission, workspace) as effective:
            service = composition.recover_service(layout, adapters, workspace=effective)
            state = await service.dispatch_correction(mission_id=args.mission)
        show(state.attempts[-1])
        return 0
    service = composition.recover_service(layout, adapters, workspace=workspace)
    if args.verb == "plan":
        show(await service.plan(mission_id=args.mission))
    elif args.verb == "gate":
        decision = await service.decide_gate(mission_id=args.mission)
        show(decision)
        return 0 if decision.outcome == "CLEAR" else 2
    return 0


async def dispatch(
    args: argparse.Namespace,
    adapters: Adapters,
    *,
    on_sequence: Callable[[int], None] | None = None,
) -> int:
    """파싱된 명령을 service 호출로 위임하고 exit code를 돌려준다.

    명령마다 원장 구간을 열고 닫는다 (ADR-0038 §6.1 a) — 예외로 끝나도
    ``end`` 줄은 쓰인다. ``status``만 예외다: 읽기 명령이 원장을 늘리면
    원장이 관측 행위를 작업으로 보고한다.
    """
    layout = StateLayout.under(args.state_dir)
    # 실행 진입점만 seeding 원천을 넘긴다 — 모델이 설정에 없으면 사용자가 지금
    # 쓰는 값을 읽어 채택하고 **기록한다** (ADR-0042 §6, 사용자 결정 2026-08-09).
    adapters = composition.routed_adapters(
        layout.root, adapters, codex_config=backend_profile.CODEX_CONFIG
    )
    if args.stage == "cleanup":
        # mission에 속하지 않는 운용 명령이다 — mission을 해석하지도, 원장을
        # 늘리지도 않는다 (ADR-0045 §7).
        show(
            worktree.sweep(layout.worktrees, force=args.force, dry_run=args.dry_run)
        )
        return 0

    args.mission = _resolve_mission(args, layout)

    if args.stage == "status":
        return await _status(args, layout, adapters, args.mission)

    handlers = {
        "brief": _dispatch_brief,
        "blueprint": _dispatch_blueprint,
        "execute": _dispatch_execute,
        "verify": _dispatch_verify,
        "recover": _dispatch_recover,
    }

    counter = CallCounter()
    journal = MissionJournal(root=layout.state, mission_id=args.mission)
    started = time.monotonic()
    sequence = journal.open(command=f"{args.stage} {args.verb}", at=_now())
    if on_sequence is not None:
        # 원장 구간이 열린 직후다 — 비동기 접수증이 job id를 추측하지 않고
        # 실제 sequence를 받는다 (ADR-0041 §4).
        on_sequence(sequence)
    exit_code = 1
    marker = layout.state / f"cancel_{args.mission}_{sequence}"
    try:
        # 이 명령의 취소 마커를 실행 adapter가 관측하게 한다 (ADR-0041 §5).
        # 마커를 놓는 것만으로는 아무것도 멈추지 않는다 — 관측이 있어야 한다.
        with cancel_when(marker.exists):
            exit_code = await handlers[args.stage](args, layout, counter.wrap(adapters))
    finally:
        marker.unlink(missing_ok=True)
        journal.close(
            sequence=sequence,
            at=_now(),
            duration_seconds=time.monotonic() - started,
            exit_code=exit_code,
            calls=counter.counts,
        )

    if exit_code == 0:
        await _record_transition(layout, args.mission, stage=args.stage, verb=args.verb)
    return exit_code


async def amain(argv: list[str] | None = None, adapters: Adapters | None = None) -> int:
    args = build_parser().parse_args(normalize_argv(argv if argv is not None else sys.argv[1:]))
    try:
        return await dispatch(args, adapters or composition.default_adapters())
    except Exception as exc:  # noqa: BLE001 — 표면 경계: 오류는 exit 1로 수렴한다
        _note(f"error: {type(exc).__name__}: {exc}")
        cause = exc.__cause__
        while cause is not None:
            _note(f"  caused by: {type(cause).__name__}: {cause}")
            cause = cause.__cause__
        return 1


def run() -> None:
    sys.exit(asyncio.run(amain()))


if __name__ == "__main__":
    run()
