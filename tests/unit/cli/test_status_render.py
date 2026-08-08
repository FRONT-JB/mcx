"""status 박스 레이아웃 — 스냅샷으로 고정한다 (ADR-0038 §6.1 c~e).

렌더는 순수 함수이므로 손으로 만든 스냅샷에서 직접 검증한다. 세 화면(진행
중·HOLD·MISSION COMPLETE)의 레이아웃이 여기서 깨지면 ADR 개정이 먼저다.
"""

from mission_control.cli.journal import JournalEntry
from mission_control.cli.status_render import ASCII, EMOJI, display_width, render
from mission_control.cli.status_view import (
    BlockingBlock,
    RowState,
    StageRow,
    StatusSnapshot,
)
from mission_control.domain.stage import Stage

MISSION = "m-b99bbe"
INTENT = "마크다운 목차(TOC) 생성 CLI 도구 mdtoc.py"


def _snapshot(**overrides: object) -> StatusSnapshot:
    base = {
        "mission_id": MISSION,
        "intent": INTENT,
        "workspace": "/tmp/dogfood3/workspace",
        "complete": False,
        "completed_at": None,
        "current_stage": Stage.VERIFY,
        "current_index": 4,
        "total_stages": 5,
        "elapsed_seconds": 68 * 60,
        "calls": (("claude", 41), ("codex_cli", 10)),
        "running_command": "verify semantic",
        "rows": (
            StageRow("Brief", "질문 6 + 감사 7라운드 · 명확도 0.95/0.92/0.95", RowState.DONE),
            StageRow("Blueprint", "AC 9개 · QA 0.75→0.89 · rev 5", RowState.DONE),
            StageRow("Execute", "AC 9개 실행 · 시도 10회 — 검증 전", RowState.DONE),
            StageRow("Recover", "교정 1회 · 재검증 준비됨", RowState.RECOVERED),
            StageRow("Verify", "mechanical 9/9 · semantic 미판정", RowState.RUNNING),
        ),
        "blocking": None,
        "next_action": None,
        "correction_count": 1,
        "artifacts": ("mdtoc.py", "test_mdtoc.py"),
        "mismatch": None,
        "journal": (),
    }
    base.update(overrides)
    return StatusSnapshot(**base)  # type: ignore[arg-type]


def _table_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith(("┌", "├", "└", "│"))]


def test_every_row_is_separated_by_a_rule() -> None:
    """사용자 확정 스타일 — 모든 로우 사이에 구분선이 들어간다."""
    lines = _table_lines(render(_snapshot()))
    assert lines[0].startswith("┌") and lines[-1].startswith("└")
    # 헤더 + 5개 로우 = 6줄, 그 사이 구분선 5줄, 위아래 테두리 2줄
    assert sum(1 for line in lines if line.startswith("├")) == 5
    assert sum(1 for line in lines if line.startswith("│")) == 6


def test_the_border_never_breaks_on_cjk_width() -> None:
    """한글이 섞여도 모든 테두리 줄의 표시 폭이 같다."""
    for output in (render(_snapshot()), render(_snapshot(), plain=True)):
        widths = {display_width(line) for line in output.splitlines() if line.strip()}
        table = _table_lines(output) or [
            line for line in output.splitlines() if line.startswith(("+", "|"))
        ]
        assert len({display_width(line) for line in table}) == 1
        assert widths  # 렌더가 비어 있지 않다


def test_the_running_screen_shows_position_elapsed_and_calls() -> None:
    output = render(_snapshot())
    assert f"- Mission: {MISSION} — {INTENT}" in output
    assert "- 진행: Verify (4/5) · 경과 1시간 8분 · claude 41콜 · codex_cli 10콜" in output
    assert "- 실행 중: mcx verify semantic" in output
    assert EMOJI[RowState.RUNNING] in output


def test_the_hold_screen_quotes_the_blocking_question_verbatim() -> None:
    """차단 이유는 지어내지 않는다 — 저장된 원문 그대로다."""
    question = "슬러그 생성 시 한글 등 비-ASCII 문자를 GitHub처럼 보존하나요?"
    output = render(
        _snapshot(
            current_stage=Stage.BRIEF,
            current_index=1,
            running_command=None,
            rows=(
                StageRow("Brief", "질문 6라운드 · 명확도 0.95/0.85/0.80", RowState.HOLD),
                StageRow("Blueprint", "Brief CLEAR 대기", RowState.WAITING),
            ),
            blocking=BlockingBlock(
                title="차단 질문 (closure 감사)",
                quoted=(question,),
                actions=('mcx brief answer "<답변>" --question "<질문>"', "mcx brief audit"),
            ),
        )
    )
    assert f'"{question}"' in output
    assert "⛔ 차단 질문 (closure 감사) — 사용자 결정이 필요합니다" in output
    assert '💡 다음 행동:' in output
    assert 'mcx brief answer "<답변>" --question "<질문>"' in output


def test_the_complete_screen_shows_the_usage_block() -> None:
    output = render(
        _snapshot(
            complete=True,
            completed_at="2026-08-09T02:03:00+00:00",
            running_command=None,
            elapsed_seconds=82 * 60,
        )
    )
    assert "✅ MISSION COMPLETE · 2026-08-09T02:03:00+00:00 · 총 1시간 22분" in output
    assert "📊 이번 mission 사용 요약" in output
    assert "✅ 호출: claude 41회 · codex_cli 10회" in output
    assert "🔁 Recover: 1회" in output
    assert "mdtoc.py · test_mdtoc.py" in output
    assert "차단" not in output


def test_recover_row_is_absent_when_never_entered() -> None:
    output = render(
        _snapshot(
            rows=(
                StageRow("Brief", "질문 6라운드", RowState.DONE),
                StageRow("Blueprint", "AC 9개", RowState.DONE),
            )
        )
    )
    assert "Recover" not in output


def test_the_state_vocabulary_is_closed_at_five() -> None:
    """여섯 번째 상태가 생기면 ADR 개정이 먼저다."""
    assert set(EMOJI) == set(RowState) == set(ASCII)
    assert len(EMOJI) == 5
    assert all(display_width(mark) == 2 for mark in EMOJI.values())


def test_plain_mode_uses_ascii_only() -> None:
    output = render(_snapshot(), plain=True)
    assert output.isascii() is False  # 한글 요약은 그대로다
    assert not any(mark in output for mark in EMOJI.values())
    assert ASCII[RowState.RUNNING] in output
    assert "┌" not in output and "+" in output


def test_full_mode_appends_the_command_ledger() -> None:
    entries = (
        JournalEntry(
            sequence=1,
            command="brief start",
            started_at="2026-08-09T00:00:00+00:00",
            finished_at="2026-08-09T00:00:03+00:00",
            duration_seconds=3.0,
            exit_code=0,
            calls={"claude": 1},
        ),
        JournalEntry(
            sequence=2, command="verify semantic", started_at="2026-08-09T00:05:00+00:00"
        ),
    )
    output = render(_snapshot(journal=entries), full=True)
    assert "명령 원장:" in output
    assert "mcx brief start" in output
    assert "3초 · exit 0" in output
    assert "진행 중" in output

    assert "명령 원장:" not in render(_snapshot(journal=entries))
