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
import dataclasses
from datetime import UTC, datetime
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from mission_control.cli import composition
from mission_control.cli.composition import Adapters, StateLayout
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


def _note(message: str) -> None:
    print(message, file=sys.stderr)


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
    print(json.dumps(jsonable(value), indent=2, ensure_ascii=False))


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
    p = brief.add_parser("start", parents=[common])
    p.add_argument("intent", help="mission의 초기 의도")
    p.add_argument("--workspace", default=None, help="실행 workspace (기본: 현재 디렉터리)")
    brief.add_parser("ask", parents=[common])
    p = brief.add_parser("answer", parents=[common])
    p.add_argument("answer", help="질문에 대한 답변")
    p.add_argument("--authority", default="decision", choices=["decision", "observation"])
    p.add_argument(
        "--question", default=None, help="닫힌 질문 밖에서 온 질문(예: closure 차단 질문)"
    )
    p = brief.add_parser("candidate", parents=[common])
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
    p = brief.add_parser("resolve", parents=[common])
    p.add_argument("--number", type=int, required=True)
    p.add_argument("--resolution", required=True, choices=[r.value for r in CandidateResolution])
    p.add_argument("--authority", default="none", choices=[a.value for a in ConfirmationAuthority])
    brief.add_parser("assess", parents=[common])
    brief.add_parser("audit", parents=[common])
    p = brief.add_parser("approve", parents=[common])
    p.add_argument("statement", help="승인 문장")
    brief.add_parser("gate", parents=[common])
    brief.add_parser("handoff", parents=[common])

    blueprint = stage_sub.add_parser(
        "blueprint", help="Blueprint — 승인 가능한 불변 명세"
    ).add_subparsers(dest="verb", required=True)
    blueprint.add_parser("generate", parents=[common])
    blueprint.add_parser("qa", parents=[common])
    p = blueprint.add_parser("revise", parents=[common])
    p.add_argument("--draft-file", required=True, type=Path)
    p = blueprint.add_parser("approve", parents=[common])
    p.add_argument("statement", help="승인 문장")
    p.add_argument("--accept-below-threshold", action="store_true")
    blueprint.add_parser("gate", parents=[common])

    execute = stage_sub.add_parser("execute", help="Execute — bounded work").add_subparsers(
        dest="verb", required=True
    )
    execute.add_parser("next", parents=[common])
    execute.add_parser("gate", parents=[common])

    verify = stage_sub.add_parser("verify", help="Verify — evidence로 판정").add_subparsers(
        dest="verb", required=True
    )
    verify.add_parser("mechanical", parents=[common])
    verify.add_parser("semantic", parents=[common])
    verify.add_parser("gate", parents=[common])

    recover = stage_sub.add_parser("recover", help="Recover — 제한적 교정").add_subparsers(
        dest="verb", required=True
    )
    recover.add_parser("plan", parents=[common])
    recover.add_parser("dispatch", parents=[common])
    recover.add_parser("gate", parents=[common])

    status = stage_sub.add_parser("status", parents=[common], help="mission record와 Stage 요약")
    status.set_defaults(verb="show")

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


async def _status(layout: StateLayout, mission_id: str) -> int:
    record = await _load_record(layout, mission_id)
    if record is None:
        _note(f"error: mission record not found for {mission_id}")
        return 1

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
        _current_mission_pointer(layout).write_text(f"{mission}\n", encoding="utf-8")
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
    service = composition.blueprint_service(layout, adapters)
    mission: str = args.mission
    verb: str = args.verb

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
    service = composition.execute_service(layout, adapters, workspace=workspace)
    if args.verb == "next":
        state = await service.dispatch_next(mission_id=args.mission)
        show(state.attempts[-1])
    elif args.verb == "gate":
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
    service = composition.recover_service(layout, adapters, workspace=workspace)
    if args.verb == "plan":
        show(await service.plan(mission_id=args.mission))
    elif args.verb == "dispatch":
        state = await service.dispatch_correction(mission_id=args.mission)
        show(state.attempts[-1])
    elif args.verb == "gate":
        decision = await service.decide_gate(mission_id=args.mission)
        show(decision)
        return 0 if decision.outcome == "CLEAR" else 2
    return 0


async def dispatch(args: argparse.Namespace, adapters: Adapters) -> int:
    """파싱된 명령을 service 호출로 위임하고 exit code를 돌려준다."""
    layout = StateLayout.under(args.state_dir)
    args.mission = _resolve_mission(args, layout)

    if args.stage == "status":
        return await _status(layout, args.mission)

    handlers = {
        "brief": _dispatch_brief,
        "blueprint": _dispatch_blueprint,
        "execute": _dispatch_execute,
        "verify": _dispatch_verify,
        "recover": _dispatch_recover,
    }
    exit_code = await handlers[args.stage](args, layout, adapters)

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
