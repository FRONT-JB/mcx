"""server 층 — job tool과 SDK 경계 (ADR-0041 §1·§4·§5).

``serve()``만 SDK를 쓴다. 아래 전부가 SDK 없이 돈다는 것 자체가 §1의 검증이다.
"""

from pathlib import Path

from mission_control.cli.composition import default_adapters
from mission_control.cli.journal import MissionJournal
from mission_control.mcp import server
from mission_control.mcp.jobs import JobState, cancel_marker
from mission_control.mcp.protocol import ResultType


async def _start(root: Path) -> None:
    from mission_control.mcp.surface import call_tool

    await call_tool(
        "mcx_brief_start",
        {"mission": "m", "intent": "목표", "workspace": str(root)},
        state_dir=str(root),
        adapters=default_adapters(),
    )


class TestToolCatalogue:
    def test_only_job_and_start_tools_are_not_derived_from_the_cli(self) -> None:
        """CLI에 없는 tool은 셋뿐이다 — 나머지는 파서에서 파생된다 (§1)."""
        from mission_control.mcp.surface import tool_definitions

        derived = {tool.name for tool in tool_definitions()}
        extra = {tool.name for tool in server.definitions()} - derived

        assert extra == {
            "mcx_job_status",
            "mcx_cancel_job",
            "mcx_start_execute_next",
            "mcx_start_verify_semantic",
            "mcx_start_recover_dispatch",
        }

    def test_a_start_tool_mirrors_its_synchronous_schema(self) -> None:
        """두 벌의 인자 계약을 만들지 않는다."""
        by_name = {tool.name: tool for tool in server.definitions()}

        assert (
            by_name["mcx_start_execute_next"].input_schema
            == by_name["mcx_execute_next"].input_schema
        )

    def test_only_long_commands_get_a_start_pair(self) -> None:
        """짧은 명령까지 두 벌이면 host가 매번 어느 쪽을 쓸지 판단해야 한다."""
        starts = {t.name for t in server.definitions() if t.name.startswith("mcx_start_")}

        assert starts == {
            "mcx_start_execute_next",
            "mcx_start_verify_semantic",
            "mcx_start_recover_dispatch",
        }

    def test_every_command_that_drives_the_execution_runtime_has_a_start_pair(self) -> None:
        """길이는 명령 이름이 아니라 **실행 경로**가 정한다.

        ``recover dispatch``는 ``ExecuteService.dispatch_correction``을 거쳐
        ``execute next``와 같은 ``codex exec``를 돌린다. 짝이 없으면 host가
        900초까지 블로킹된 채 job id를 못 받아 취소할 수단도 없다 —
        Phase 7 종료 검토가 잡은 누락이다.
        """
        import inspect

        from mission_control.application import recover_service
        from mission_control.mcp.surface import LONG_RUNNING

        assert "self.execute.dispatch_correction" in inspect.getsource(recover_service)
        assert "mcx_recover_dispatch" in LONG_RUNNING

    def test_no_tool_name_repeats(self) -> None:
        names = [tool.name for tool in server.definitions()]

        assert len(names) == len(set(names))

    def test_every_schema_declares_its_shape(self) -> None:
        for tool in server.definitions():
            assert tool.input_schema["type"] == "object"
            assert tool.input_schema["additionalProperties"] is False


class TestJobStatus:
    async def test_a_finished_command_reports_its_exit(self, tmp_path: Path) -> None:
        await _start(tmp_path)

        result = await server.handle("mcx_job_status", {"job": "m#1"}, state_dir=tmp_path)

        assert result.is_error is False
        assert result.structured_content["state"] == JobState.COMPLETED.value
        assert result.structured_content["command"] == "brief start"

    async def test_an_unknown_job_is_an_error_not_a_silent_empty(self, tmp_path: Path) -> None:
        result = await server.handle("mcx_job_status", {"job": "m#9"}, state_dir=tmp_path)

        assert result.is_error is True
        assert result.result_type is ResultType.ERROR


class TestCancel:
    async def test_cancelling_a_running_job_writes_the_marker(self, tmp_path: Path) -> None:
        state = tmp_path / "state"
        MissionJournal(root=state, mission_id="m").open(
            command="execute next", at="2026-08-09T00:00:00+00:00"
        )

        result = await server.handle("mcx_cancel_job", {"job": "m#1"}, state_dir=tmp_path)

        assert result.result_type is ResultType.ACCEPTED
        assert cancel_marker(root=state, mission_id="m", sequence=1).exists()

    async def test_cancelling_a_finished_job_is_refused_without_a_marker(
        self, tmp_path: Path
    ) -> None:
        """이미 끝난 작업에 마커를 남기면 다음 같은 sequence가 오해한다."""
        await _start(tmp_path)

        result = await server.handle("mcx_cancel_job", {"job": "m#1"}, state_dir=tmp_path)

        assert "이미 끝났다" in result.text
        assert not cancel_marker(root=tmp_path / "state", mission_id="m", sequence=1).exists()

    async def test_a_malformed_job_id_does_not_touch_the_disk(self, tmp_path: Path) -> None:
        result = await server.handle("mcx_cancel_job", {"job": "../escape#1"}, state_dir=tmp_path)

        assert result.is_error is True
        assert not (tmp_path / "state").exists()


class TestTheSdkIsOptional:
    def test_the_surface_works_without_the_sdk(self) -> None:
        """이 파일이 통과한다는 것 자체가 검증이다 — SDK import는 serve() 안에만 있다."""
        import inspect

        source = inspect.getsource(server)
        head, _, tail = source.partition("def serve(")

        assert "import mcp" not in head
        assert "from mcp" not in head
        assert "from mcp.server.lowlevel import Server" in tail


class TestStartTools:
    async def test_a_receipt_carries_the_real_journal_sequence(self, tmp_path: Path) -> None:
        """job id를 추측하지 않는다 — 원장이 연 sequence를 받는다 (§4)."""
        await _start(tmp_path)  # sequence 1을 소비한다

        receipt = await server.handle(
            "mcx_start_verify_semantic", {"mission": "m"}, state_dir=tmp_path
        )

        assert receipt.result_type is ResultType.ACCEPTED
        assert receipt.structured_content["job"] == "m#2"

    async def test_the_recover_pair_routes_to_its_synchronous_tool(self, tmp_path: Path) -> None:
        """이름 되돌리기(``start_recover_dispatch`` → ``recover_dispatch``)가 도는지."""
        await _start(tmp_path)

        receipt = await server.handle(
            "mcx_start_recover_dispatch", {"mission": "m"}, state_dir=tmp_path
        )

        assert receipt.result_type is ResultType.ACCEPTED
        assert receipt.structured_content["job"] == "m#2"

    async def test_the_receipt_returns_before_the_work_finishes(self, tmp_path: Path) -> None:
        """접수증은 즉시다 — host가 결과를 기다리며 타임아웃하지 않게."""
        await _start(tmp_path)

        receipt = await server.handle(
            "mcx_start_execute_next", {"mission": "m"}, state_dir=tmp_path
        )

        assert receipt.structured_content["state"] == "running"
        assert receipt.is_error is False
