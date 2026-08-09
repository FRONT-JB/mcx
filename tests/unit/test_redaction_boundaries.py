"""redaction이 **경계에서** 강제되는지 (ADR-0040 §2·§3).

핵심은 "함수가 올바른가"가 아니라 **안 부르는 경로가 없는가**다. 부르면 되는
함수로 두면 새 호출자가 조용히 빠뜨린다 — upstream이 raw append를 예외로 막은
이유와 같다.
"""

from pathlib import Path

import pytest

from mission_control.cli.journal import MissionJournal
from mission_control.domain.execute.state import (
    AttemptStatus,
    CapabilityEnvelope,
    ExecutionAttempt,
)
from mission_control.domain.verify.evidence import VerificationRun
from mission_control.security import REDACTED, RedactionError

_ENVELOPE = CapabilityEnvelope(workspace="/w", allowed_tools=("shell",))


def _attempt(error: str) -> ExecutionAttempt:
    return ExecutionAttempt(
        number=1,
        execution_id="exec-1",
        runtime_backend="codex_cli",
        blueprint_revision=1,
        ac_key="ac1",
        envelope=_ENVELOPE,
        status=AttemptStatus.EXECUTION_FAILED,
        error=error,
    )


class TestStateDocumentsMaskOnConstruction:
    def test_an_attempt_error_is_masked_without_anyone_asking(self) -> None:
        attempt = _attempt("auth failed: Bearer ghp_abcdefghijklmnopqrstuvwxyz0123")

        assert "ghp_" not in (attempt.error or "")
        assert REDACTED in (attempt.error or "")

    def test_the_attempt_error_keeps_its_path(self) -> None:
        """Recover가 이 발췌를 worker에게 넘긴다 — 경로가 없으면 같은 실패를 반복한다."""
        attempt = _attempt("FileNotFoundError: /Users/jb/project/src/app.py")

        assert "/Users/jb/project/src/app.py" in (attempt.error or "")

    def test_a_verification_run_masks_its_output_tail(self) -> None:
        run = VerificationRun(
            ac_key="ac1",
            command="pytest -q",
            exit_code=1,
            passed=False,
            output_tail="env dump: AWS_SECRET_ACCESS_KEY=s3cr3tvalue",
        )

        assert "s3cr3tvalue" not in run.output_tail

    def test_a_verification_run_masks_its_command(self) -> None:
        """verify_command 자체에 토큰이 실려 있을 수 있다."""
        run = VerificationRun(
            ac_key="ac1",
            command="curl --api-key=hunter2 https://example.com",
            exit_code=0,
            passed=True,
        )

        assert "hunter2" not in (run.command or "")


class TestJournalRefusesRatherThanMasks:
    def test_a_replay_unsafe_key_is_refused_at_write(self, tmp_path: Path) -> None:
        """마스킹으로 구제하지 않는다 — 그 자리에 있으면 안 되는 값이다."""
        journal = MissionJournal(root=tmp_path, mission_id="m")

        with pytest.raises(RedactionError):
            journal._append({"event": "end", "sequence": 1, "stdout": "..."})

    def test_the_guard_sits_at_the_single_write_path(self, tmp_path: Path) -> None:
        """open/close 둘 다 _append를 지난다 — 새 필드를 붙여도 가드를 우회할 수 없다."""
        journal = MissionJournal(root=tmp_path, mission_id="m")
        sequence = journal.open(command="brief start", at="2026-08-09T00:00:00+00:00")
        journal.close(
            sequence=sequence,
            at="2026-08-09T00:00:01+00:00",
            duration_seconds=1.0,
            exit_code=0,
            calls={"claude": 1},
        )

        assert len(journal.entries()) == 1

    def test_a_backend_named_like_a_secret_is_refused(self, tmp_path: Path) -> None:
        """calls의 키는 backend 이름이다 — 그 자리를 비밀 이름으로 쓸 수 없다."""
        journal = MissionJournal(root=tmp_path, mission_id="m")
        sequence = journal.open(command="brief start", at="2026-08-09T00:00:00+00:00")

        with pytest.raises(RedactionError):
            journal.close(
                sequence=sequence,
                at="2026-08-09T00:00:01+00:00",
                duration_seconds=1.0,
                exit_code=0,
                calls={"api_key": 1},
            )


def test_the_state_pointer_is_owner_only(tmp_path: Path) -> None:
    """조사에서 이 파일만 0644였다 — 나머지 상태 파일과 같은 권한이어야 한다."""
    import asyncio

    from mission_control.cli.composition import default_adapters
    from mission_control.cli.main import amain

    assert (
        asyncio.run(
            amain(
                ["brief", "start", "목표", "--mission", "m", "--state-dir", str(tmp_path)],
                default_adapters(),
            )
        )
        == 0
    )

    pointer = tmp_path / "state" / "current_mission"
    assert pointer.stat().st_mode & 0o777 == 0o600
