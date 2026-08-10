"""MCP tool 표면 — ADR-0041 Verification 항목.

핵심은 둘이다: **HOLD는 오류가 아니다**(§2), 그리고 tool 목록이 CLI에서
파생되므로 어긋날 수 없다(§1).
"""

from pathlib import Path
from typing import Any

import pytest

from mission_control.cli.composition import default_adapters
from mission_control.cli.main import build_parser
from mission_control.mcp.protocol import ResultType
from mission_control.mcp.surface import (
    _CLI_ONLY,
    PREFIX,
    UnknownToolError,
    call_tool,
    tool_definitions,
)


def _names() -> set[str]:
    return {tool.name for tool in tool_definitions()}


def _cli_commands() -> set[str]:
    parser = build_parser()
    import argparse

    (stages,) = [
        action
        for action in parser._actions  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction)  # noqa: SLF001
    ]
    commands: set[str] = set()
    for stage, stage_parser in stages.choices.items():
        verbs = [
            action
            for action in stage_parser._actions  # noqa: SLF001
            if isinstance(action, argparse._SubParsersAction)  # noqa: SLF001
        ]
        if not verbs:
            commands.add(f"{PREFIX}{stage}")
            continue
        commands.update(f"{PREFIX}{stage}_{verb}" for verb in verbs[0].choices)
    return commands


class TestToolSurfaceIsDerived:
    def test_every_cli_command_has_exactly_one_tool(self) -> None:
        """목록을 손으로 적지 않으므로 어긋날 자리가 없다."""
        assert _names() == _cli_commands() - {f"{PREFIX}{stage}" for stage in _CLI_ONLY}

    def test_the_only_command_kept_off_the_surface_is_cleanup(self) -> None:
        """1:1의 예외는 하나이며 근거가 있다 (ADR-0045 §7).

        이 표면의 모든 tool은 ``mission``을 필수로 받는데 ``cleanup``에는 mission이
        없다. upstream도 ``ouroboros cleanup``을 tool로 내보내지 않는다. 예외가
        늘어나면 여기서 먼저 걸린다 — 조용히 하나 더 빠지지 않는다.
        """
        assert _CLI_ONLY == {"cleanup"}
        assert build_parser().parse_args(["cleanup"]).mission is None

    def test_the_prefix_is_global(self) -> None:
        assert all(name.startswith(PREFIX) for name in _names())

    def test_mission_is_required_even_though_the_cli_makes_it_optional(self) -> None:
        """서버는 '현재 mission'을 기억하지 않는다 (§3)."""
        for tool in tool_definitions():
            assert "mission" in tool.input_schema["required"], tool.name

    def test_the_state_dir_is_not_exposed(self) -> None:
        """상태 루트는 서버가 소유한다 — host가 고를 값이 아니다."""
        for tool in tool_definitions():
            assert "state_dir" not in tool.input_schema["properties"], tool.name

    def test_positional_and_required_arguments_are_declared(self) -> None:
        schema = next(t for t in tool_definitions() if t.name == "mcx_brief_start").input_schema

        assert "intent" in schema["required"]
        assert schema["properties"]["intent"]["type"] == "string"

    def test_choices_become_enums(self) -> None:
        schema = next(t for t in tool_definitions() if t.name == "mcx_brief_answer").input_schema

        assert schema["properties"]["authority"]["enum"] == ["decision", "observation"]

    def test_no_description_is_just_the_name_repeated(self) -> None:
        """host는 33개 중 무엇을 부를지 description만 보고 고른다.

        ``mcx brief ask``처럼 이름을 되풀이하면 정보가 0이다. Phase 8 종료
        검토가 잡아 CLI ``help=``를 원천으로 바꿨다.
        """
        bare = [
            tool.name
            for tool in tool_definitions()
            if tool.description.replace("_", " ") == tool.name.replace("mcx_", "mcx ").replace(
                "_", " "
            )
        ]

        assert bare == []

    def test_the_description_comes_from_the_cli_help(self) -> None:
        """원천이 하나다 — CLI ``--help``와 tool description이 같은 문장이다."""
        ask = next(t for t in tool_definitions() if t.name == "mcx_brief_ask")

        assert ask.description == "사용자에게 물을 질문 하나를 생성한다"

    def test_long_commands_say_so(self) -> None:
        """host가 `mcx_start_*` 짝을 언제 쓸지 판단할 근거."""
        long_running = {
            "mcx_blueprint_evolve",
            "mcx_execute_next",
            "mcx_execute_stage",
            "mcx_verify_semantic",
            "mcx_recover_dispatch",
        }
        described = {t.name: t.description for t in tool_definitions()}

        for name in long_running:
            assert "장기" in described[name], name

    def test_store_true_flags_become_booleans(self) -> None:
        schema = next(t for t in tool_definitions() if t.name == "mcx_status").input_schema

        assert schema["properties"]["full"]["type"] == "boolean"


class TestEnvelope:
    async def test_success_is_complete_and_not_an_error(self, tmp_path: Path) -> None:
        result = await _start(tmp_path)

        assert result.is_error is False
        assert result.result_type is ResultType.COMPLETE
        assert result.structured_content["mission_id"] == "m"

    async def test_hold_is_not_an_error(self, tmp_path: Path) -> None:
        """exit 2를 is_error로 보내면 host가 무의미한 재시도를 건다 (§2)."""
        await _start(tmp_path)

        result = await call_tool(
            "mcx_brief_gate", {"mission": "m"}, state_dir=str(tmp_path), adapters=default_adapters()
        )

        assert result.result_type is ResultType.HOLD
        assert result.is_error is False
        assert result.meta["exit_code"] == 2

    async def test_a_missing_mission_is_refused(self, tmp_path: Path) -> None:
        result = await call_tool("mcx_brief_ask", {}, state_dir=str(tmp_path))

        assert result.is_error is True
        assert "mission" in result.text

    async def test_bad_arguments_do_not_kill_the_server(self, tmp_path: Path) -> None:
        """argparse는 검증 실패에 종료를 시도한다 — envelope으로 접어야 한다."""
        result = await call_tool(
            "mcx_brief_candidate",
            {"mission": "m", "section": "없는-섹션", "text": "x"},
            state_dir=str(tmp_path),
        )

        assert result.is_error is True
        assert result.result_type is ResultType.ERROR

    async def test_an_unknown_tool_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(UnknownToolError):
            await call_tool("mcx_not_a_tool", {"mission": "m"}, state_dir=str(tmp_path))

    async def test_the_human_render_rides_in_text(self, tmp_path: Path) -> None:
        await _start(tmp_path)

        result = await call_tool(
            "mcx_status", {"mission": "m"}, state_dir=str(tmp_path), adapters=default_adapters()
        )

        assert "단계별 현황:" in result.text

    async def test_local_paths_do_not_reach_the_host(self, tmp_path: Path) -> None:
        """host 프로필이 envelope 조립 지점에 걸린다 (ADR-0040 §5)."""
        result = await _start(tmp_path)

        assert str(tmp_path) not in str(result.structured_content)
        assert "[redacted path]" in str(result.structured_content)


class TestParityWithTheCli:
    async def test_the_tool_and_the_cli_reach_the_same_state(self, tmp_path: Path) -> None:
        """같은 dispatch를 지나므로 상태가 갈릴 수 없다 (§8)."""
        from mission_control.cli.main import amain

        await _start(tmp_path)
        assert (
            await amain(
                ["brief", "ask", "--mission", "m", "--state-dir", str(tmp_path)],
                default_adapters(),
            )
            != 999
        )

        result = await call_tool(
            "mcx_status", {"mission": "m"}, state_dir=str(tmp_path), adapters=default_adapters()
        )

        assert result.is_error is False

    async def test_a_tool_call_is_journalled_once(self, tmp_path: Path) -> None:
        from mission_control.cli.journal import MissionJournal

        await _start(tmp_path)

        entries = MissionJournal(root=tmp_path / "state", mission_id="m").entries()
        assert [entry.command for entry in entries] == ["brief start"]


async def _start(root: Path) -> Any:
    return await call_tool(
        "mcx_brief_start",
        {"mission": "m", "intent": "목표", "workspace": str(root)},
        state_dir=str(root),
        adapters=default_adapters(),
    )


class TestTheHostAlwaysGetsReadableText:
    async def test_a_json_only_command_carries_its_payload_as_text(self, tmp_path: Path) -> None:
        """CLI가 stdout에 찍는 것과 같은 것을 싣는다 — 빈 본문은 host가 못 읽는다."""
        await _start(tmp_path)

        result = await call_tool(
            "mcx_brief_gate", {"mission": "m"}, state_dir=str(tmp_path), adapters=default_adapters()
        )

        assert result.text.startswith("{")
        assert "HOLD" in result.text

    async def test_the_result_type_rides_in_meta_as_well(self, tmp_path: Path) -> None:
        """SDK가 필드를 떨어뜨려도 host가 판정을 읽을 수 있어야 한다."""
        await _start(tmp_path)

        result = await call_tool(
            "mcx_brief_gate", {"mission": "m"}, state_dir=str(tmp_path), adapters=default_adapters()
        )

        assert result.meta["result_type"] == "hold"
        assert result.meta["exit_code"] == 2
