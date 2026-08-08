"""``mcx status``의 사람용 렌더 (ADR-0038 §6.1 c~e).

순수 함수만 둔다 — 입력은 :class:`StatusSnapshot` 하나이고 출력은 문자열
하나다. I/O가 없어야 레이아웃을 스냅샷 테스트로 고정할 수 있다 (upstream
``test_status_unified.py`` 정렬).

폭은 ``unicodedata.east_asian_width``로 센다. 다섯 상태 이모지는 EAW가
``Ambiguous``인 것(``⏸`` U+23F8)이 섞여 있어 폭 2로 명시 고정한다 — 터미널
추정에 레이아웃을 맡기지 않는다.
"""

from __future__ import annotations

from unicodedata import east_asian_width

from mission_control.cli.journal import JournalEntry
from mission_control.cli.status_view import STAGE_LABELS, RowState, StatusSnapshot

#: 상태 어휘 다섯 개 (ADR-0038 §6.1 c). ``⏸``만 EAW가 Ambiguous라 터미널마다
#: 폭이 갈리므로 VS16(U+FE0F)을 붙여 이모지 표현을 강제한다 — 다른 넷은 W다.
EMOJI: dict[RowState, str] = {
    RowState.DONE: "✅",
    RowState.RUNNING: "⏳",
    RowState.HOLD: "⛔",
    RowState.WAITING: "⏸️",
    RowState.RECOVERED: "🔁",
}

#: 이모지를 못 그리는 터미널용 ASCII 대체.
ASCII: dict[RowState, str] = {
    RowState.DONE: "[v]",
    RowState.RUNNING: "[~]",
    RowState.HOLD: "[!]",
    RowState.WAITING: "[ ]",
    RowState.RECOVERED: "[R]",
}

#: EAW가 Ambiguous라 폭을 고정해야 하는 글자. VS16은 앞 글자의 표현만 바꾸고
#: 자기 칸을 차지하지 않는다.
_FIXED_WIDTH = {"⏸": 2, "️": 0}

_BORDERS = {
    False: {
        "tl": "┌", "tm": "┬", "tr": "┐",
        "ml": "├", "mm": "┼", "mr": "┤",
        "bl": "└", "bm": "┴", "br": "┘",
        "h": "─", "v": "│",
        "rule": "─",
    },
    True: {
        "tl": "+", "tm": "+", "tr": "+",
        "ml": "+", "mm": "+", "mr": "+",
        "bl": "+", "bm": "+", "br": "+",
        "h": "-", "v": "|",
        "rule": "-",
    },
}


def display_width(text: str) -> int:
    """터미널에서 차지하는 칸 수. 한글·CJK는 2칸이다."""
    return sum(
        _FIXED_WIDTH.get(char, 2 if east_asian_width(char) in {"W", "F"} else 1) for char in text
    )


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def _center(text: str, width: int) -> str:
    slack = max(0, width - display_width(text))
    left = slack // 2
    return " " * left + text + " " * (slack - left)


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f}초"
    minutes, rest = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}분" if rest == 0 else f"{minutes}분 {rest}초"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}시간 {minutes}분"


def _table(rows: list[tuple[str, str, str]], *, plain: bool) -> list[str]:
    """모든 로우 사이에 구분선이 들어가는 테두리 표 (ADR-0038 §6.1 c)."""
    border = _BORDERS[plain]
    widths = [max(display_width(cell) for cell in column) + 2 for column in zip(*rows, strict=True)]

    def rule(left: str, middle: str, right: str) -> str:
        return left + middle.join(border["h"] * width for width in widths) + right

    def line(cells: tuple[str, str, str], *, center_last: bool) -> str:
        rendered = [
            _center(cell, widths[index] - 2)
            if center_last and index == len(cells) - 1
            else _pad(cell, widths[index] - 2)
            for index, cell in enumerate(cells)
        ]
        return border["v"] + border["v"].join(f" {cell} " for cell in rendered) + border["v"]

    out = [rule(border["tl"], border["tm"], border["tr"]), line(rows[0], center_last=True)]
    for row in rows[1:]:
        out.append(rule(border["ml"], border["mm"], border["mr"]))
        out.append(line(row, center_last=True))
    out.append(rule(border["bl"], border["bm"], border["br"]))
    return out


def _rule(width: int, *, plain: bool) -> str:
    return _BORDERS[plain]["rule"] * width


def _summary_lines(snapshot: StatusSnapshot, *, plain: bool) -> list[str]:
    """한 줄 한 사실 (upstream ``_format_auto_status`` 정렬)."""
    mission = f"- Mission: {snapshot.mission_id}"
    if snapshot.intent:
        mission += f" — {snapshot.intent}"
    lines = ["Summary:", mission]

    facts = [_duration(snapshot.elapsed_seconds)]
    facts.extend(f"{backend} {count}콜" for backend, count in snapshot.calls)

    if snapshot.complete:
        stamp = f" · {snapshot.completed_at}" if snapshot.completed_at else ""
        mark = "MISSION COMPLETE" if plain else "✅ MISSION COMPLETE"
        lines.append(f"- {mark}{stamp} · 총 {' · '.join(facts)}")
        return lines

    label = STAGE_LABELS[snapshot.current_stage]
    position = (
        f"{label} ({snapshot.current_index}/{snapshot.total_stages})"
        if snapshot.current_index
        else label
    )
    lines.append(f"- 진행: {position} · 경과 {' · '.join(facts)}")
    if snapshot.running_command:
        lines.append(f"- 실행 중: mcx {snapshot.running_command}")
    if snapshot.blocking is not None:
        mark = ASCII[RowState.HOLD] if plain else EMOJI[RowState.HOLD]
        lines.append(f"- {mark} {snapshot.blocking.title} — 사용자 결정이 필요합니다")
    elif snapshot.next_action:
        lines.append(f"- 다음: {snapshot.next_action}")
    return lines


def _blocking_lines(snapshot: StatusSnapshot, width: int, *, plain: bool) -> list[str]:
    block = snapshot.blocking
    if block is None:
        return []
    head = block.title if plain else f"⛔ {block.title}"
    lines = ["", _rule(width, plain=plain), head, _rule(width, plain=plain)]
    if block.quoted:
        lines.extend(f'"{quote}"' for quote in block.quoted)
    else:
        lines.append("(기록된 차단 사유가 없다)")
    lines.append("")
    hint = "다음 행동:" if plain else "💡 다음 행동:"
    lines.append(hint)
    lines.extend(f"   {action}" for action in block.actions)
    return lines


def _usage_lines(snapshot: StatusSnapshot, width: int, *, plain: bool) -> list[str]:
    head = "이번 mission 사용 요약" if plain else "📊 이번 mission 사용 요약"
    lines = ["", _rule(width, plain=plain), head, _rule(width, plain=plain)]
    calls = " · ".join(f"{backend} {count}회" for backend, count in snapshot.calls) or "기록 없음"
    lines.append(f"{'호출:' if plain else '✅ 호출:'} {calls}")
    if snapshot.correction_count:
        mark = "Recover:" if plain else "🔁 Recover:"
        lines.append(f"{mark} {snapshot.correction_count}회 — 실패를 교정하고 재검증")
    artifacts = " · ".join(dict.fromkeys(snapshot.artifacts))
    mark = "산출물:" if plain else "💡 산출물:"
    lines.append(f"{mark} {artifacts or '선언된 artifact 없음'} ({snapshot.workspace})")
    return lines


def _journal_lines(entries: tuple[JournalEntry, ...], *, plain: bool) -> list[str]:
    if not entries:
        return ["", "명령 원장: 기록 없음"]
    rows: list[tuple[str, str, str]] = [("#", "명령", "소요 · exit")]
    for entry in entries:
        detail = (
            "진행 중"
            if entry.in_progress
            else f"{_duration(entry.duration_seconds)} · exit {entry.exit_code}"
        )
        rows.append((str(entry.sequence), f"mcx {entry.command}", detail))
    return ["", "명령 원장:", "", *_table(rows, plain=plain)]


def render(snapshot: StatusSnapshot, *, full: bool = False, plain: bool = False) -> str:
    """스냅샷 하나를 사람이 읽는 화면으로 만든다."""
    lines = _summary_lines(snapshot, plain=plain)
    lines.extend(["", "단계별 현황:", ""])

    marks = ASCII if plain else EMOJI
    table_rows: list[tuple[str, str, str]] = [("단계", "요약", "상태")]
    table_rows.extend((row.label, row.summary, marks[row.state]) for row in snapshot.rows)
    table = _table(table_rows, plain=plain)
    lines.extend(table)

    width = display_width(table[0])
    if snapshot.mismatch:
        lines.extend(["", f"경고: {snapshot.mismatch}"])
    if snapshot.complete:
        lines.extend(_usage_lines(snapshot, width, plain=plain))
    else:
        lines.extend(_blocking_lines(snapshot, width, plain=plain))
    if full:
        lines.extend(_journal_lines(snapshot.journal, plain=plain))
    else:
        lines.extend(["", "명령 단위 원장은 `mcx status --full`에 있다."])
    return "\n".join(lines) + "\n"
