"""LocalMechanicalRunner — 실제 subprocess로 실행 계약을 검증한다.

계약: docs/adr/0028-verify-v1-mechanical-contract.md §3
(upstream 대응: docs/research/VERIFY_UPSTREAM_FINDINGS.md §2)
"""

from pathlib import Path

import pytest

from mission_control.adapters.verification.local_mechanical_runner import (
    LocalMechanicalRunner,
)


@pytest.fixture
def runner() -> LocalMechanicalRunner:
    return LocalMechanicalRunner()


class TestRun:
    async def test_exit_zero_and_captured_output(
        self, runner: LocalMechanicalRunner, tmp_path: Path
    ) -> None:
        result = await runner.run(command="echo OK", workspace=str(tmp_path), timeout_seconds=10)
        assert result.exit_code == 0
        assert result.timed_out is False
        assert "OK" in result.output

    async def test_stderr_joins_stdout(self, runner: LocalMechanicalRunner, tmp_path: Path) -> None:
        result = await runner.run(
            command="echo boom 1>&2", workspace=str(tmp_path), timeout_seconds=10
        )
        assert result.exit_code == 0
        assert "boom" in result.output

    async def test_a_nonzero_exit_is_a_result_not_an_error(
        self, runner: LocalMechanicalRunner, tmp_path: Path
    ) -> None:
        result = await runner.run(command="exit 7", workspace=str(tmp_path), timeout_seconds=10)
        assert result.exit_code == 7

    async def test_the_command_runs_in_the_workspace(
        self, runner: LocalMechanicalRunner, tmp_path: Path
    ) -> None:
        (tmp_path / "marker.txt").write_text("here", encoding="utf-8")
        result = await runner.run(
            command="cat marker.txt", workspace=str(tmp_path), timeout_seconds=10
        )
        assert result.exit_code == 0
        assert "here" in result.output

    async def test_a_timeout_is_reported_and_the_process_is_gone(
        self, runner: LocalMechanicalRunner, tmp_path: Path
    ) -> None:
        result = await runner.run(command="sleep 30", workspace=str(tmp_path), timeout_seconds=1)
        assert result.timed_out is True
        assert result.exit_code is None


class TestMissingArtifacts:
    async def test_missing_entries_are_all_reported(
        self, runner: LocalMechanicalRunner, tmp_path: Path
    ) -> None:
        (tmp_path / "present.md").write_text("x", encoding="utf-8")
        missing = await runner.missing_artifacts(
            workspace=str(tmp_path),
            artifacts=("present.md", "absent.md", "also/absent.py"),
        )
        assert missing == ("absent.md", "also/absent.py")

    async def test_a_directory_counts_as_present(
        self, runner: LocalMechanicalRunner, tmp_path: Path
    ) -> None:
        (tmp_path / "docs").mkdir()
        missing = await runner.missing_artifacts(workspace=str(tmp_path), artifacts=("docs",))
        assert missing == ()
