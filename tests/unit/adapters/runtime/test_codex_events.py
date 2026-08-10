"""codex JSONL → 진행 한 줄 (ADR-0049 §1·§2).

이 파서가 답하는 질문은 *"지금 무엇을 하는가"* 하나다. 그래서 시작만 접고
완료는 접지 않는다 — 둘 다 실으면 마지막 줄이 "방금 끝난 것"이 되어 질문에
어긋난다.
"""

import json

from mission_control.adapters.runtime.codex_events import (
    activity,
    completed_command_observed,
    file_change,
    turn_completed,
)
from mission_control.progress import MAX_DETAIL


def event(item_type: str, **fields: object) -> str:
    return json.dumps({"type": "item.started", "item": {"type": item_type, **fields}})


class TestToolItems:
    def test_a_command_becomes_its_command_line(self) -> None:
        found = activity(event("command_execution", command="pytest tests/test_auth.py"))

        assert found is not None
        assert found.tool == "command_execution"
        assert found.detail == "pytest tests/test_auth.py"

    def test_a_command_given_as_a_list_is_joined(self) -> None:
        found = activity(event("command_execution", command=["git", "status", "--short"]))

        assert found is not None
        assert found.detail == "git status --short"

    def test_a_file_change_lists_its_paths(self) -> None:
        found = activity(event("file_change", changes=[{"path": "src/a.py"}, {"path": "src/b.py"}]))

        assert found is not None
        assert found.detail == "src/a.py src/b.py"

    def test_a_file_change_falls_back_to_a_single_path(self) -> None:
        found = activity(event("file_change", file_path="src/only.py"))

        assert found is not None
        assert found.detail == "src/only.py"

    def test_an_mcp_call_names_the_server_and_tool(self) -> None:
        found = activity(event("mcp_tool_call", server="context7", name="query-docs"))

        assert found is not None
        assert found.detail == "context7 query-docs"

    def test_a_web_search_carries_its_query(self) -> None:
        found = activity(event("web_search", query="python asyncio subprocess"))

        assert found is not None
        assert found.detail == "python asyncio subprocess"

    def test_an_unknown_item_type_is_not_progress(self) -> None:
        assert activity(event("agent_message", text="done")) is None


class TestWhatIsNotProjected:
    def test_completion_is_not_projected(self) -> None:
        """우리 질문은 "지금 무엇을 하는가"이고 그 답은 시작이다 (§2)."""
        line = json.dumps({"type": "item.completed", "item": {"type": "command_execution"}})

        assert activity(line) is None

    def test_the_thread_header_is_not_progress(self) -> None:
        assert activity(json.dumps({"type": "thread.started", "thread_id": "t-1"})) is None

    def test_a_broken_line_does_not_raise(self) -> None:
        """한 줄이 읽히지 않는다고 실행을 멈추지 않는다."""
        assert activity("{not json") is None
        assert activity("") is None

    def test_a_non_object_payload_is_ignored(self) -> None:
        assert activity("[1, 2, 3]") is None

    def test_an_item_that_is_not_an_object_is_ignored(self) -> None:
        assert activity(json.dumps({"type": "item.started", "item": "nope"})) is None


class TestWriteTelemetryProjection:
    def test_completed_file_change_keeps_identity_and_paths(self) -> None:
        line = json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "id": "item_7",
                    "type": "file_change",
                    "changes": [{"path": "/workspace/src/a.py"}],
                },
            }
        )
        found = file_change(line)

        assert found is not None
        assert found.phase == "completed"
        assert found.item_id == "item_7"
        assert found.paths == ("/workspace/src/a.py",)

    def test_command_and_terminal_events_are_distinguished(self) -> None:
        command = json.dumps({"type": "item.completed", "item": {"type": "command_execution"}})
        terminal = json.dumps({"type": "turn.completed"})

        assert completed_command_observed(command) is True
        assert turn_completed(command) is False
        assert turn_completed(terminal) is True


class TestTheStorageProfileIsAlreadyOn:
    """생성 시점에 걸린다 — 아무도 마스킹 함수를 부르지 않아도 (ADR-0049 §6)."""

    def test_a_credential_in_a_command_never_reaches_the_line(self) -> None:
        secret = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
        found = activity(event("command_execution", command=f"curl --api-key={secret} https://x"))

        assert found is not None
        assert secret not in found.detail
        assert secret not in found.line()

    def test_a_long_command_is_truncated(self) -> None:
        found = activity(event("command_execution", command="echo " + "x" * 500))

        assert found is not None
        assert len(found.detail) == MAX_DETAIL
