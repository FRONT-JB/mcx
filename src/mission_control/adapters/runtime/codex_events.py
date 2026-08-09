"""codex ``--json`` 스트림을 진행 한 줄로 접는다 (ADR-0049 §1·§2).

순수 함수다 — 파일도 프로세스도 모른다. 실행 adapter가 읽는 매 줄에 이것을
걸고, 결과가 있으면 :func:`mission_control.progress.record`로 보낸다.

upstream 봉투 형태 채택: ``{"type": "item.started", "item": {"type": …}}``
(``codex_cli_runtime.py:3393-3400``). 도구 lifecycle item type 넷도 upstream
목록 그대로다 (``:182-184``).

``item.completed``는 접지 않는다 — upstream은 deliver gate가 도구 완료를
증명해야 해서 쌍이 필요하지만, 우리 질문은 *"지금 무엇을 하는가"* 이고 그
답은 시작이다 (ADR-0049 §2).
"""

from __future__ import annotations

import json
from typing import Any

from mission_control.progress import RuntimeActivity

#: 도구 lifecycle로 보는 codex item type (upstream ``_TOOL_LIFECYCLE_ITEM_TYPES``).
TOOL_ITEM_TYPES = frozenset({"command_execution", "mcp_tool_call", "file_change", "web_search"})

#: 명령 원문이 실릴 수 있는 자리 (upstream ``_extract_command``).
_COMMAND_KEYS = ("command", "cmd", "command_line")

#: 대상 경로가 실릴 수 있는 자리 (upstream ``_extract_tool_input``).
_PATH_KEYS = ("path", "file_path", "target_file")


def activity(line: str) -> RuntimeActivity | None:
    """JSONL 한 줄을 진행 한 줄로. 해당 없으면 ``None``.

    깨진 줄은 조용히 넘긴다 — 한 줄이 읽히지 않는다고 실행을 멈추지 않는다.
    """
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict) or event.get("type") != "item.started":
        return None
    item = event.get("item")
    if not isinstance(item, dict):
        return None
    item_type = item.get("type")
    if not isinstance(item_type, str) or item_type not in TOOL_ITEM_TYPES:
        return None
    return RuntimeActivity(kind="tool", tool=item_type, detail=_detail(item_type, item))


def _detail(item_type: str, item: dict[str, Any]) -> str:
    if item_type == "command_execution":
        return _first_command(item)
    if item_type == "file_change":
        return _changed_paths(item)
    if item_type == "mcp_tool_call":
        server = item.get("server")
        name = item.get("name")
        return " ".join(str(part) for part in (server, name) if isinstance(part, str) and part)
    if item_type == "web_search":
        query = item.get("query")
        return query if isinstance(query, str) else ""
    return ""


def _first_command(item: dict[str, Any]) -> str:
    for key in _COMMAND_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            parts = [str(part) for part in value if isinstance(part, (str, int))]
            if parts:
                return " ".join(parts)
    return ""


def _changed_paths(item: dict[str, Any]) -> str:
    changes = item.get("changes")
    paths: list[str] = []
    if isinstance(changes, list):
        for change in changes:
            if isinstance(change, str):
                paths.append(change)
            elif isinstance(change, dict):
                paths.extend(
                    str(change[key]) for key in _PATH_KEYS if isinstance(change.get(key), str)
                )
    if not paths:
        paths = [str(item[key]) for key in _PATH_KEYS if isinstance(item.get(key), str)]
    return " ".join(paths)
