"""tool 표면 — CLI 명령과 1:1이며 **파서에서 파생된다** (ADR-0041 §1).

tool 목록을 손으로 적지 않는다. ``build_parser()``를 훑어 만들기 때문에 CLI에
명령을 추가하면 tool이 따라오고, 인자 검증도 argparse가 그대로 한다. 두 표면이
어긋날 자리가 구조적으로 없다 — parity를 테스트로 쫓아다니지 않는 이유다.

호출도 같은 ``dispatch``를 지난다. 즉 mission record 전이·명령 원장·호출
계수·Stage 라우팅이 CLI와 같은 코드로 일어난다.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
import json
from typing import Any

from mission_control.cli import composition
from mission_control.cli.composition import Adapters
from mission_control.cli.main import build_parser, collecting, dispatch
from mission_control.mcp.protocol import ResultType, ToolDefinition, ToolResult, classify
from mission_control.security import redact_for_host

#: tool 이름 접두사. host의 도구 목록에서 출처가 이름만으로 구분된다
#: (upstream ``ouroboros_`` 정렬).
PREFIX = "mcx_"

#: 표면에서 제외하는 CLI 인자. 서버가 소유하거나(상태 루트) host가 알 필요가
#: 없는 것이다.
_SERVER_OWNED = frozenset({"--state-dir"})

#: tool로 내보내지 않는 CLI 명령. **1:1 규칙의 예외이므로 근거가 필요하다.**
#:
#: ``cleanup``은 mission 하나가 아니라 남은 것 전부를 훑는 운용 명령이다. 이
#: 표면의 모든 tool은 ``mission``을 필수로 요구하는데(서버가 현재 mission을
#: 기억하지 않으므로 — ADR-0041 §3), mission이 없는 명령은 그 계약에 자리가
#: 없다. upstream도 같다: ``ouroboros cleanup``은 CLI에만 있고 ``ouroboros_*``
#: tool 목록에 없다 (WORKTREE findings §5).
_CLI_ONLY = frozenset({"cleanup"})


def _stage_verb(tool_name: str) -> tuple[str, str] | None:
    if not tool_name.startswith(PREFIX):
        return None
    rest = tool_name[len(PREFIX) :]
    if rest == "status":
        return ("status", "show")
    stage, _, verb = rest.partition("_")
    return (stage, verb) if stage and verb else None


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:  # noqa: SLF001 — argparse가 공개 API를 주지 않는다
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            return dict(action.choices)
    return {}


def _helps(parser: argparse.ArgumentParser) -> dict[str, str]:
    """하위 명령의 ``help`` 문구. tool description의 원천이다.

    argparse는 ``add_parser(help=...)``를 부모의 pseudo-action에 담고 자식
    parser에는 남기지 않는다. 원천을 하나로 두려고(CLI ``--help``와 tool
    description이 같은 문장) 그 자리에서 읽는다.
    """
    for action in parser._actions:  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            return {
                choice.dest: choice.help
                for choice in action._choices_actions  # noqa: SLF001
                if choice.help
            }
    return {}


def _schema(parser: argparse.ArgumentParser) -> dict[str, Any]:
    """하나의 명령 파서를 JSON Schema로 옮긴다."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for action in parser._actions:  # noqa: SLF001
        if action.dest in {"help", "state_dir"}:
            continue
        if any(option in _SERVER_OWNED for option in action.option_strings):
            continue

        entry: dict[str, Any] = {"description": action.help or ""}
        if isinstance(action, argparse._StoreTrueAction):  # noqa: SLF001
            entry["type"] = "boolean"
        elif action.type is int:
            entry["type"] = "integer"
        else:
            entry["type"] = "string"
        if action.choices:
            entry["enum"] = [str(choice) for choice in action.choices]
        properties[action.dest] = entry

        positional = not action.option_strings
        if positional or action.required:
            required.append(action.dest)

    # CLI에서 `--mission`은 선택이다(`current_mission` 포인터가 있으므로). MCP에는
    # 그 포인터가 없으므로 필수다 (ADR-0041 §3) — 스키마가 그렇게 말해야 host가
    # 런타임 오류로 배우지 않는다.
    if "mission" in properties and "mission" not in required:
        required.append("mission")

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def tool_definitions() -> tuple[ToolDefinition, ...]:
    """CLI 명령 하나당 tool 하나. 순서는 파서 순서다."""
    parser = build_parser()
    stage_helps = _helps(parser)
    tools: list[ToolDefinition] = []
    for stage, stage_parser in _subparsers(parser).items():
        if stage in _CLI_ONLY:
            continue
        verbs = _subparsers(stage_parser)
        if not verbs:
            tools.append(
                ToolDefinition(
                    name=f"{PREFIX}{stage}",
                    description=(
                        stage_helps.get(stage) or stage_parser.description or stage
                    ).strip(),
                    input_schema=_schema(stage_parser),
                )
            )
            continue
        helps = _helps(stage_parser)
        for verb, verb_parser in verbs.items():
            # 이름의 반복은 description이 아니다 — host는 29개 중 무엇을 부를지
            # 이것만 보고 고른다. 원천은 CLI의 `help=`이며, 없으면 그 사실이
            # 드러나도록 이름으로 떨어진다(테스트가 그 상태를 거부한다).
            tools.append(
                ToolDefinition(
                    name=f"{PREFIX}{stage}_{verb}",
                    description=helps.get(verb, f"mcx {stage} {verb}"),
                    input_schema=_schema(verb_parser),
                )
            )
    return tuple(tools)


def _argv(stage: str, verb: str, arguments: dict[str, Any], *, state_dir: str) -> list[str]:
    """tool 인자를 CLI argv로 편다 — 검증은 argparse가 한다."""
    argv: list[str] = [stage] if stage == "status" else [stage, verb]
    parser = build_parser()
    stage_parser = _subparsers(parser)[stage]
    verbs = _subparsers(stage_parser)
    target = verbs[verb] if verbs else stage_parser

    for action in target._actions:  # noqa: SLF001
        if action.dest in {"help", "state_dir"} or action.dest not in arguments:
            continue
        value = arguments[action.dest]
        if value is None:
            continue
        if not action.option_strings:
            argv.append(str(value))
        elif isinstance(action, argparse._StoreTrueAction):  # noqa: SLF001
            if value:
                argv.append(action.option_strings[0])
        else:
            argv.extend([action.option_strings[0], str(value)])

    argv.extend(["--state-dir", state_dir])
    return argv


class UnknownToolError(Exception):
    """등록되지 않은 tool 이름."""


async def call_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    state_dir: str,
    adapters: Adapters | None = None,
    on_sequence: Callable[[int], None] | None = None,
) -> ToolResult:
    """tool 하나를 CLI와 **같은 dispatch**로 수행한다.

    ``mission_id``는 필수 인자다 — 서버는 "현재 mission"을 기억하지 않는다
    (ADR-0041 §3). host가 두 mission을 오가는 동안 서버가 기억하면 잘못된
    mission에 쓴다.
    """
    target = _stage_verb(name)
    if target is None or name not in {tool.name for tool in tool_definitions()}:
        raise UnknownToolError(name)
    stage, verb = target

    if not arguments.get("mission"):
        return ToolResult(
            text="mission 인자가 필요하다 — 서버는 현재 mission을 기억하지 않는다",
            is_error=True,
            result_type=ResultType.ERROR,
        )

    argv = _argv(stage, verb, arguments, state_dir=state_dir)
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse는 검증 실패에 종료를 시도한다
        return ToolResult(
            text=f"인자가 계약에 맞지 않는다: {' '.join(argv)}",
            is_error=True,
            result_type=ResultType.ERROR,
            meta={"argparse_code": exc.code},
        )

    resolved = adapters if adapters is not None else composition.default_adapters()
    with collecting() as sink:
        try:
            exit_code = await dispatch(args, resolved, on_sequence=on_sequence)
        except Exception as exc:  # noqa: BLE001 — 표면 경계: 예외는 envelope이 된다
            return ToolResult(
                text=f"{type(exc).__name__}: {exc}",
                is_error=True,
                result_type=ResultType.ERROR,
            )

    return _envelope(sink, exit_code)


#: 비동기 짝을 두는 명령. 짧은 명령까지 두 벌이 되면 host가 매번 어느 쪽을
#: 쓸지 판단해야 한다 (ADR-0041 §4 Rejected alternatives).
#:
#: ``recover dispatch``는 ``ExecuteService.dispatch_correction``을 거쳐 **같은
#: ``codex exec``** 를 돌린다 — ``execute next``와 길이가 같다. 초안이 둘로 적은
#: 것은 실행 경로를 따라가지 않은 오류였고, Phase 7 종료 검토가 잡았다
#: (progress 0007 §1.2).
LONG_RUNNING: frozenset[str] = frozenset(
    {"mcx_execute_next", "mcx_verify_semantic", "mcx_recover_dispatch"}
)


async def start_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    state_dir: str,
    adapters: Adapters | None = None,
) -> tuple[ToolResult, asyncio.Task[ToolResult]]:
    """작업을 시작하고 **접수증만** 돌려준다.

    job id를 추측하지 않는다 — 원장 구간이 열린 실제 sequence를 ``dispatch``의
    훅으로 받는다. 추측하면 동시 호출에서 다른 명령의 id를 돌려주게 된다.
    """
    if name not in LONG_RUNNING:
        raise UnknownToolError(name)

    loop = asyncio.get_running_loop()
    opened: asyncio.Future[int] = loop.create_future()

    def _seen(sequence: int) -> None:
        if not opened.done():
            opened.set_result(sequence)

    async def _run() -> ToolResult:
        return await call_tool(
            name, arguments, state_dir=state_dir, adapters=adapters, on_sequence=_seen
        )

    task = loop.create_task(_run())
    waiting: set[asyncio.Future[Any]] = {opened, task}
    done, _ = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
    if opened not in done:
        # 구간이 열리기 전에 끝났다 — 인자 오류처럼 dispatch 앞에서 실패한 것이다.
        return await task, task

    mission = str(arguments["mission"])
    job = f"{mission}#{opened.result()}"
    return (
        ToolResult(
            text=f"{job} 접수됨. mcx_job_status로 진행을 본다",
            result_type=ResultType.ACCEPTED,
            structured_content={"job": job, "state": "running"},
        ),
        task,
    )


def _envelope(sink: list[tuple[str, object]], exit_code: int) -> ToolResult:
    """수집된 출력과 exit code를 하나의 결과로 접는다.

    host로 나가기 전에 host 프로필 redaction을 건다 — ADR-0040 §5가 예약한
    자리이며 조립 지점은 여기 하나다.
    """
    is_error, result_type = classify(exit_code)
    data = [payload for kind, payload in sink if kind == "data"]
    lines = [str(payload) for kind, payload in sink if kind in {"text", "note"}]

    structured: Any = None
    if len(data) == 1:
        structured = data[0]
    elif data:
        structured = data

    # 사람용 렌더가 없는 명령은 CLI가 stdout에 JSON을 찍는다. 같은 것을 싣는다 —
    # host가 빈 본문을 받으면 결과를 못 읽는다. 파리티가 문자 그대로가 된다.
    if not lines and structured is not None:
        lines = [json.dumps(structured, indent=2, ensure_ascii=False)]

    return ToolResult(
        text=redact_for_host("\n".join(lines)),
        is_error=is_error,
        result_type=result_type,
        structured_content=redact_for_host(structured),
        meta={"exit_code": exit_code, "result_type": result_type.value},
    )
