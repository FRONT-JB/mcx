"""mcx CLI 표면 — 명령 목록, exit code, 오류 수렴 (ADR-0038 §1~§3)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_control.application.ports import RuntimeUnavailableError
from mission_control.cli import composition
from mission_control.cli.composition import default_adapters
from mission_control.cli.main import _load_draft, amain, build_parser
from mission_control.domain.execute.state import StageRunStatus

#: ADR-0038 §1의 명령 표면 전체. 여기 없는 명령이 생기거나 여기 있는 명령이
#: 사라지면 ADR 개정이 먼저다.
SURFACE: list[tuple[list[str], str, str]] = [
    (["brief", "start", "i"], "brief", "start"),
    (["brief", "ask"], "brief", "ask"),
    (["brief", "answer", "a"], "brief", "answer"),
    (["brief", "candidate", "--section", "goal", "--text", "t"], "brief", "candidate"),
    (["brief", "resolve", "--number", "1", "--resolution", "confirmed"], "brief", "resolve"),
    (["brief", "assess"], "brief", "assess"),
    (["brief", "audit"], "brief", "audit"),
    (["brief", "approve", "s"], "brief", "approve"),
    (["brief", "gate"], "brief", "gate"),
    (["brief", "handoff"], "brief", "handoff"),
    (["blueprint", "generate"], "blueprint", "generate"),
    (["blueprint", "qa"], "blueprint", "qa"),
    (["blueprint", "revise", "--draft-file", "d.json"], "blueprint", "revise"),
    (["blueprint", "approve", "s"], "blueprint", "approve"),
    (["blueprint", "gate"], "blueprint", "gate"),
    (["blueprint", "evolve"], "blueprint", "evolve"),
    (["execute", "next"], "execute", "next"),
    (["execute", "stage", "--max-workers", "2"], "execute", "stage"),
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


def test_blueprint_revision_draft_loads_a_complete_ontology(tmp_path: Path) -> None:
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(
        json.dumps(
            {
                "goal": "429 재시도 정책",
                "constraints": [],
                "non_goals": [],
                "acceptance_criteria": [{"description": "429만 재시도한다"}],
                "ontology": {
                    "name": "RetryPolicy",
                    "description": "재시도 입력과 결과 경계",
                    "fields": [
                        {
                            "name": "retry_after",
                            "field_type": "str | None",
                            "description": "Retry-After 입력",
                            "required": True,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    draft = _load_draft(draft_file)

    assert draft.ontology is not None
    assert draft.ontology.fields[0].name == "retry_after"


def test_shorthand_expands_to_brief_start() -> None:
    """`mcx brief \"프롬프트\"` 단축 — ADR-0038 개정 1 (upstream ooo init 정렬)."""
    from mission_control.cli.main import normalize_argv

    assert normalize_argv(["brief", "CSV 중복 제거 도구"]) == [
        "brief",
        "start",
        "CSV 중복 제거 도구",
    ]
    assert normalize_argv(["brief", "ask"]) == ["brief", "ask"]  # verb가 이긴다
    assert normalize_argv(["brief", "--help"]) == ["brief", "--help"]
    assert normalize_argv(["status"]) == ["status"]


async def test_missing_mission_without_any_started_exits_one(tmp_path: Path) -> None:
    """--mission 생략 + 시작된 mission 없음 → 오류 (개정 1)."""
    assert await amain(["brief", "gate", "--state-dir", str(tmp_path)], default_adapters()) == 1


async def test_omitted_mission_defaults_to_last_started(tmp_path: Path) -> None:
    """brief start가 id를 자동 생성하고 이후 명령이 그 mission을 쓴다 (개정 1)."""
    adapters = default_adapters()
    assert await amain(["brief", "작업 목표", "--state-dir", str(tmp_path)], adapters) == 0
    pointer = tmp_path / "state" / "current_mission"
    assert pointer.exists()
    assert pointer.read_text().strip().startswith("m-")
    # 같은 mission으로 이어진다 — gate는 fresh brief라 HOLD(2)
    assert await amain(["brief", "gate", "--state-dir", str(tmp_path)], adapters) == 2


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

    assert await amain(["brief", "start", "goal", *argv], adapters) == 0
    assert await amain(["brief", "gate", *argv], adapters) == 2


async def test_unknown_mission_exits_one(tmp_path: Path) -> None:
    argv = ["--mission", "nope", "--state-dir", str(tmp_path)]
    assert await amain(["brief", "gate", *argv], default_adapters()) == 1


async def test_execute_without_mission_record_exits_one(tmp_path: Path) -> None:
    """workspace는 mission record가 나른다 — record 없는 Execute는 오류다 (§5)."""
    argv = ["--mission", "m2", "--state-dir", str(tmp_path)]
    assert await amain(["execute", "next", *argv], default_adapters()) == 1


async def test_execute_next_runtime_unavailable_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class StubService:
        async def dispatch_next(self, *, mission_id: str) -> object:
            raise RuntimeUnavailableError(executable="codex")

    monkeypatch.setattr(
        composition, "execute_service", lambda layout, adapters, *, workspace: StubService()
    )
    argv = ["--mission", "spawn-missing", "--state-dir", str(tmp_path)]
    adapters = default_adapters()

    assert await amain(["brief", "start", "g", "--workspace", str(tmp_path), *argv], adapters) == 0

    assert await amain(["execute", "next", *argv], adapters) == 1
    assert "codex" in capsys.readouterr().err


async def test_gate_clear_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class StubService:
        async def decide_gate(self, *, mission_id: str) -> SimpleNamespace:
            return SimpleNamespace(outcome="CLEAR")

    monkeypatch.setattr(
        composition, "execute_service", lambda layout, adapters, *, workspace: StubService()
    )
    argv = ["--mission", "m3", "--state-dir", str(tmp_path)]
    adapters = default_adapters()
    assert await amain(["brief", "start", "g", *argv], adapters) == 0
    assert await amain(["execute", "gate", *argv], adapters) == 0


async def test_execute_stage_hold_exits_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class StubService:
        async def dispatch_stage(
            self, *, mission_id: str, max_workers: int | None
        ) -> SimpleNamespace:
            return SimpleNamespace(stage_runs=(SimpleNamespace(status=StageRunStatus.HOLD),))

    monkeypatch.setattr(
        composition, "execute_service", lambda layout, adapters, *, workspace: StubService()
    )
    argv = ["--mission", "stage-hold", "--state-dir", str(tmp_path)]
    adapters = default_adapters()
    assert (
        await amain(
            [
                "brief",
                "start",
                "g",
                "--workspace",
                str(tmp_path),
                *argv,
            ],
            adapters,
        )
        == 0
    )

    assert await amain(["execute", "stage", "--max-workers", "2", *argv], adapters) == 2


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
