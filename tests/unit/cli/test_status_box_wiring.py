"""원장 기록과 호출 계수의 배선 (ADR-0038 §6.1 a~b).

계수는 **명령 수 근사가 아니라 실측**이다 — 명령 하나가 호출 N번인 경우가
실재하므로, 그 경우 원장의 값이 N이어야 한다.
"""

from pathlib import Path
from typing import Any

from mission_control.cli.calls import CallCounter
from mission_control.cli.composition import Adapters, default_adapters
from mission_control.cli.journal import MissionJournal
from mission_control.cli.main import amain


def argv(mission: str, root: Path) -> list[str]:
    return ["--mission", mission, "--state-dir", str(root)]


def journal(root: Path, mission: str = "m") -> MissionJournal:
    return MissionJournal(root=root / "state", mission_id=mission)


class _FakeCompletion:
    backend = "fake_text"

    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(
        self, *, prompt: str, schema: dict[str, Any], workspace: str | None = None
    ) -> dict[str, Any]:
        self.calls += 1
        return {}


class _FakeRuntime:
    backend = "fake_exec"

    async def execute(self, request: object) -> object:
        return object()


async def test_a_command_writes_one_journal_entry(tmp_path: Path) -> None:
    adapters = default_adapters()
    assert await amain(["brief", "start", "목표", *argv("m", tmp_path)], adapters) == 0

    (entry,) = journal(tmp_path).entries()
    assert entry.command == "brief start"
    assert entry.exit_code == 0
    assert not entry.in_progress


async def test_status_does_not_grow_the_journal(tmp_path: Path) -> None:
    """읽기 명령이 원장을 늘리면 원장이 관측 행위를 작업으로 보고한다."""
    adapters = default_adapters()
    await amain(["brief", "start", "목표", *argv("m", tmp_path)], adapters)
    before = len(journal(tmp_path).entries())

    assert await amain(["status", *argv("m", tmp_path)], adapters) == 0
    assert await amain(["status", "--full", *argv("m", tmp_path)], adapters) == 0

    assert len(journal(tmp_path).entries()) == before


async def test_a_failing_command_is_still_closed(tmp_path: Path) -> None:
    """오류로 끝나도 end 줄은 쓰인다 — 진행 중으로 영원히 남지 않는다."""
    adapters = default_adapters()
    await amain(["brief", "start", "목표", *argv("m", tmp_path)], adapters)
    assert await amain(["blueprint", "generate", *argv("m", tmp_path)], adapters) == 1

    entries = journal(tmp_path).entries()
    assert entries[-1].command == "blueprint generate"
    assert entries[-1].exit_code == 1
    assert not entries[-1].in_progress


async def test_a_hold_verdict_is_journaled_as_exit_two(tmp_path: Path) -> None:
    adapters = default_adapters()
    await amain(["brief", "start", "목표", *argv("m", tmp_path)], adapters)
    assert await amain(["brief", "gate", *argv("m", tmp_path)], adapters) == 2

    assert journal(tmp_path).entries()[-1].exit_code == 2


async def test_the_counter_measures_calls_not_commands() -> None:
    """한 명령 안의 호출 N번이 N으로 세어진다 — 1로 접히지 않는다."""
    engine = _FakeCompletion()
    counter = CallCounter()
    wrapped = counter.wrap(
        Adapters(completion=engine, runtime=_FakeRuntime(), runner=object())  # type: ignore[arg-type]
    )

    for _ in range(9):
        await wrapped.completion.complete_json(prompt="p", schema={})

    assert counter.counts == {"fake_text": 9}
    assert engine.calls == 9


async def test_the_counter_keeps_backends_apart() -> None:
    counter = CallCounter()
    wrapped = counter.wrap(
        Adapters(completion=_FakeCompletion(), runtime=_FakeRuntime(), runner=object())  # type: ignore[arg-type]
    )

    await wrapped.completion.complete_json(prompt="p", schema={})
    await wrapped.runtime.execute(object())  # type: ignore[arg-type]

    assert counter.counts == {"fake_text": 1, "fake_exec": 1}


def test_the_real_engines_declare_their_backend_names() -> None:
    """원장의 계수 키는 실제 backend 이름이다 (ADR-0039가 쓰는 이름과 같다)."""
    from mission_control.adapters.runtime.codex_execution_runtime import CodexExecutionRuntime
    from mission_control.adapters.text.claude_completion import ClaudeCompletion
    from mission_control.adapters.text.codex_completion import CodexCompletion

    assert ClaudeCompletion().backend == "claude"
    assert CodexCompletion().backend == "codex"
    assert CodexExecutionRuntime().backend == "codex_cli"
