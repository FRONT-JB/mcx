"""SDK 바인딩 — **이 파일만 SDK를 안다** (ADR-0041 §1).

``protocol``·``surface``·``jobs``는 SDK 없이 서고 테스트된다. SDK는 optional
extra이며(``pip install mission-control[mcp]``) import는 여기서 지연된다 —
설치하지 않은 환경에서 ``mcx`` CLI가 그대로 동작해야 하기 때문이다.

transport는 stdio 하나다 (§7). 원격을 열면 인증이 선행 조건이며 그때
upstream의 ``AuthMethod``/``Permission`` 축과 대조한다.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from mission_control.mcp import jobs
from mission_control.mcp.protocol import ResultType, ToolDefinition, ToolResult
from mission_control.mcp.surface import (
    LONG_RUNNING,
    PREFIX,
    call_tool,
    start_tool,
    tool_definitions,
)

#: 백그라운드 task의 강한 참조. 놓으면 GC가 실행 중인 작업을 거둘 수 있다.
_BACKGROUND: set[Any] = set()

SERVER_NAME = "mcx"

#: CLI와 같은 기본 상태 루트. 두 표면이 같은 mission을 본다.
DEFAULT_STATE_DIR = Path.home() / ".mcx"

#: job 조회·제어 tool. CLI 명령에서 파생되지 않는 유일한 tool이며, MCP에만
#: 존재하는 이유는 CLI가 한 프로세스 안에서 끝나기 때문이다 (§4).
JOB_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name=f"{PREFIX}job_status",
        description="명령 하나의 진행 상태 — 원장에서 유도한다",
        input_schema={
            "type": "object",
            "properties": {"job": {"type": "string", "description": "<mission_id>#<sequence>"}},
            "required": ["job"],
            "additionalProperties": False,
        },
    ),
    ToolDefinition(
        name=f"{PREFIX}cancel_job",
        description="취소를 요청한다. 실행 중인 작업이 관측해야 실제로 멈춘다",
        input_schema={
            "type": "object",
            "properties": {"job": {"type": "string", "description": "<mission_id>#<sequence>"}},
            "required": ["job"],
            "additionalProperties": False,
        },
    ),
)


def _start_definitions() -> tuple[ToolDefinition, ...]:
    """장기 명령의 비동기 짝. 동기 tool의 스키마를 그대로 쓴다 (§4)."""
    by_name = {tool.name: tool for tool in tool_definitions()}
    return tuple(
        ToolDefinition(
            name=f"{PREFIX}start_{name[len(PREFIX) :]}",
            description=f"{by_name[name].description} — 접수증만 돌려주고 백그라운드로 돈다",
            input_schema=by_name[name].input_schema,
        )
        for name in sorted(LONG_RUNNING)
        if name in by_name
    )


def definitions() -> tuple[ToolDefinition, ...]:
    return (*tool_definitions(), *_start_definitions(), *JOB_TOOLS)


async def handle(name: str, arguments: dict[str, Any], *, state_dir: Path) -> ToolResult:
    """tool 하나를 처리한다. job tool만 여기서 갈라지고 나머지는 CLI dispatch다."""
    state = state_dir / "state"
    if name == f"{PREFIX}job_status":
        return _job_status(str(arguments.get("job", "")), state=state)
    if name == f"{PREFIX}cancel_job":
        return _cancel(str(arguments.get("job", "")), state=state)
    if name.startswith(f"{PREFIX}start_"):
        target = f"{PREFIX}{name[len(PREFIX) + len('start_') :]}"
        receipt, task = await start_tool(target, arguments, state_dir=str(state_dir))
        _BACKGROUND.add(task)
        task.add_done_callback(_BACKGROUND.discard)
        return receipt
    return await call_tool(name, arguments, state_dir=str(state_dir))


def _job_status(job: str, *, state: Path) -> ToolResult:
    try:
        view = jobs.job_view(root=state, job=job)
    except jobs.UnknownJobError as exc:
        return ToolResult(text=str(exc), is_error=True, result_type=ResultType.ERROR)
    return ToolResult(
        text=f"{view.job_id} · mcx {view.command} · {view.state.value}",
        structured_content={
            "job": view.job_id,
            "command": view.command,
            "state": view.state.value,
            "started_at": view.started_at,
            "finished_at": view.finished_at,
            "duration_seconds": view.duration_seconds,
            "exit_code": view.exit_code,
        },
    )


def _cancel(job: str, *, state: Path) -> ToolResult:
    try:
        mission_id, sequence = jobs.parse_job_id(job)
        view = jobs.job_view(root=state, job=job)
    except jobs.UnknownJobError as exc:
        return ToolResult(text=str(exc), is_error=True, result_type=ResultType.ERROR)

    if view.state not in {jobs.JobState.RUNNING, jobs.JobState.CANCEL_REQUESTED}:
        return ToolResult(
            text=f"{job}는 이미 끝났다 ({view.state.value}) — 취소할 것이 없다",
            structured_content={"job": job, "state": view.state.value},
        )

    jobs.request_cancel(root=state, mission_id=mission_id, sequence=sequence)
    return ToolResult(
        text=f"{job} 취소를 요청했다. 실행 중인 작업이 관측하면 멈춘다",
        result_type=ResultType.ACCEPTED,
        structured_content={"job": job, "state": jobs.JobState.CANCEL_REQUESTED.value},
    )


def serve(state_dir: Path) -> None:  # pragma: no cover — SDK 실물이 필요하다
    """stdio MCP 서버를 띄운다. SDK가 없으면 설치 방법을 알리고 끝낸다.

    SDK v2의 lowlevel ``Server``에 ``tools/list``·``tools/call`` 핸들러를 직접
    건다. 상위 ``MCPServer``의 함수 기반 tool 등록은 스키마를 파이썬 시그니처
    에서 뽑는데, 우리 스키마는 ``build_parser()``에서 파생되므로 맞지 않는다.
    """
    try:
        import anyio
        from mcp.server.lowlevel import Server
        from mcp.server.stdio import stdio_server
        import mcp.types as types
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"MCP SDK가 없다. `uv pip install 'mission-control[mcp]'`로 설치한다 (누락: {exc.name})"
        ) from exc

    server: Any = Server(SERVER_NAME)

    async def _on_list(_context: Any, _params: Any) -> Any:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                )
                for tool in definitions()
            ]
        )

    async def _on_call(_context: Any, params: Any) -> Any:
        result = await handle(params.name, dict(params.arguments or {}), state_dir=state_dir)
        structured = (
            result.structured_content if isinstance(result.structured_content, dict) else None
        )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result.text or "")],
            structured_content=structured,
            is_error=result.is_error,
            # SDK는 `complete`/`input_required` 외의 문자열도 받는다 — HOLD를
            # 오류로 접지 않고 그대로 실어 보낸다 (ADR-0041 §2). SDK가 이 필드를
            # 직렬화에서 떨어뜨려도 host가 읽을 수 있게 meta에도 싣는다.
            result_type=result.result_type.value,
            _meta={"result_type": result.result_type.value, **result.meta},
        )

    server.add_request_handler("tools/list", types.PaginatedRequestParams, _on_list)
    server.add_request_handler("tools/call", types.CallToolRequestParams, _on_call)

    async def _run() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(_run)


def main() -> int:
    """``mcx-mcp`` 진입점.

    CLI(``mcx``)에 붙이지 않는 이유는 순환이다 — MCP가 CLI의 ``dispatch``를
    부르므로(ADR-0041 §1) 반대 방향 import가 생기면 두 표면이 서로를 물게 된다.
    host 설정은 어차피 실행할 명령 하나를 가리킨다.
    """
    parser = argparse.ArgumentParser(prog="mcx-mcp", description="mcx MCP control surface (stdio)")
    parser.add_argument("action", nargs="?", default="serve", choices=["serve", "tools"])
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    args = parser.parse_args()

    if args.action == "tools":
        for tool in definitions():
            print(f"{tool.name}\t{tool.description}")
        return 0
    serve(args.state_dir)
    return 0
