"""mcx CLI 표면 — 명령 목록, exit code, 오류 수렴 (ADR-0038 §1~§3)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_control.cli import composition
from mission_control.cli.composition import default_adapters
from mission_control.cli.main import amain, build_parser

#: ADR-0038 §1의 명령 표면 전체. 여기 없는 명령이 생기거나 여기 있는 명령이
#: 사라지면 ADR 개정이 먼저다.
SURFACE: list[tuple[list[str], str, str]] = [
    (["brief", "start", "--intent", "i"], "brief", "start"),
    (["brief", "ask"], "brief", "ask"),
    (["brief", "answer", "--answer", "a"], "brief", "answer"),
    (["brief", "candidate", "--section", "goal", "--text", "t"], "brief", "candidate"),
    (["brief", "resolve", "--number", "1", "--resolution", "confirmed"], "brief", "resolve"),
    (["brief", "assess"], "brief", "assess"),
    (["brief", "audit"], "brief", "audit"),
    (["brief", "approve", "--statement", "s"], "brief", "approve"),
    (["brief", "gate"], "brief", "gate"),
    (["brief", "handoff"], "brief", "handoff"),
    (["blueprint", "generate"], "blueprint", "generate"),
    (["blueprint", "qa"], "blueprint", "qa"),
    (["blueprint", "revise", "--draft-file", "d.json"], "blueprint", "revise"),
    (["blueprint", "approve", "--statement", "s"], "blueprint", "approve"),
    (["blueprint", "gate"], "blueprint", "gate"),
    (["execute", "next"], "execute", "next"),
    (["execute", "gate"], "execute", "gate"),
    (["verify", "mechanical"], "verify", "mechanical"),
    (["verify", "semantic"], "verify", "semantic"),
    (["verify", "gate"], "verify", "gate"),
    (["recover", "plan"], "recover", "plan"),
    (["recover", "dispatch"], "recover", "dispatch"),
    (["recover", "gate"], "recover", "gate"),
    (["status"], "status", "show"),
]

_COMMON = ["--mission", "m", "--state-dir", "/tmp/x"]


@pytest.mark.parametrize(("argv", "stage", "verb"), SURFACE)
def test_surface_is_fixed(argv: list[str], stage: str, verb: str) -> None:
    args = build_parser().parse_args([*argv, *_COMMON])
    assert args.stage == stage
    assert args.verb == verb


def test_mission_is_required() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["brief", "gate", "--state-dir", "/tmp/x"])


def test_every_domain_section_is_accepted_by_the_parser() -> None:
    """CLI choices가 도메인 enum에서 파생된다 — 손으로 쓴 목록이 아니다."""
    from mission_control.domain.brief.requirement import RequirementSection

    for section in RequirementSection:
        args = build_parser().parse_args(
            ["brief", "candidate", "--section", section.value, "--text", "t", *_COMMON]
        )
        assert args.section == section.value


async def test_brief_start_exits_zero_and_gate_hold_exits_two(tmp_path: Path) -> None:
    """LLM 없이 도는 실경로: start(0) → gate HOLD(2). 오류는 1 (§3)."""
    argv = ["--mission", "m1", "--state-dir", str(tmp_path)]
    adapters = default_adapters()

    assert await amain(["brief", "start", "--intent", "goal", *argv], adapters) == 0
    assert await amain(["brief", "gate", *argv], adapters) == 2


async def test_unknown_mission_exits_one(tmp_path: Path) -> None:
    argv = ["--mission", "nope", "--state-dir", str(tmp_path)]
    assert await amain(["brief", "gate", *argv], default_adapters()) == 1


async def test_execute_without_mission_record_exits_one(tmp_path: Path) -> None:
    """workspace는 mission record가 나른다 — record 없는 Execute는 오류다 (§5)."""
    argv = ["--mission", "m2", "--state-dir", str(tmp_path)]
    assert await amain(["execute", "next", *argv], default_adapters()) == 1


async def test_gate_clear_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class StubService:
        async def decide_gate(self, *, mission_id: str) -> SimpleNamespace:
            return SimpleNamespace(outcome="CLEAR")

    monkeypatch.setattr(
        composition, "execute_service", lambda layout, adapters, *, workspace: StubService()
    )
    argv = ["--mission", "m3", "--state-dir", str(tmp_path)]
    adapters = default_adapters()
    assert await amain(["brief", "start", "--intent", "g", *argv], adapters) == 0
    assert await amain(["execute", "gate", *argv], adapters) == 0


def test_default_adapters_are_claude_text_and_codex_execution() -> None:
    """기본 조립은 사용자 확정 구조다 (ADR-0036 §1, ADR-0038 §6)."""
    from mission_control.adapters.runtime.codex_execution_runtime import CodexExecutionRuntime
    from mission_control.adapters.text.claude_completion import ClaudeCompletion
    from mission_control.adapters.verification.local_mechanical_runner import (
        LocalMechanicalRunner,
    )

    adapters = default_adapters()
    assert isinstance(adapters.completion, ClaudeCompletion)
    assert isinstance(adapters.runtime, CodexExecutionRuntime)
    assert isinstance(adapters.runner, LocalMechanicalRunner)
