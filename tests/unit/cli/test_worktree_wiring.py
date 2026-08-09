"""격리가 실제로 실행 경계를 바꾸는지 — CLI 배선 (ADR-0045 §5, Verification).

adapter 자체는 ``tests/unit/adapters/workspace/test_worktree.py``가 검증한다.
여기서 보는 것은 *"어느 명령이 격리를 쓰고, 그 사실이 사용자에게 보이는가"* 다.
"""

from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from mission_control.cli import composition
from mission_control.cli.composition import default_adapters
from mission_control.cli.main import amain
from mission_control.cli.status_view import _isolation
from mission_control.domain.execute.state import CapabilityEnvelope, ExecutionAttempt
from mission_control.domain.mission import MissionRecord


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    git("init", "-b", "main", cwd=root)
    git("config", "user.email", "t@example.com", cwd=root)
    git("config", "user.name", "t", cwd=root)
    (root / "README.md").write_text("hello\n")
    git("add", ".", cwd=root)
    git("commit", "-m", "init", cwd=root)
    return root


class StubExecute:
    async def dispatch_next(self, *, mission_id: str) -> SimpleNamespace:
        return SimpleNamespace(attempts=[SimpleNamespace(number=1)])

    async def decide_gate(self, *, mission_id: str) -> SimpleNamespace:
        return SimpleNamespace(outcome="CLEAR")


def _capture(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def factory(layout: object, adapters: object, *, workspace: str, **_: object) -> StubExecute:
        seen.append(workspace)
        return StubExecute()

    monkeypatch.setattr(composition, "execute_service", factory)
    return seen


async def _mission(tmp_path: Path, repo: Path) -> list[str]:
    argv = ["--mission", "m", "--state-dir", str(tmp_path / "state")]
    adapters = default_adapters()
    assert await amain(["brief", "start", "g", "--workspace", str(repo), *argv], adapters) == 0
    return argv


async def test_execute_next_runs_in_the_worktree_not_the_users_checkout(
    tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _capture(monkeypatch)
    argv = await _mission(tmp_path, repo)

    assert await amain(["execute", "next", *argv], default_adapters()) == 0

    assert len(seen) == 1
    assert seen[0] != str(repo)
    assert seen[0].endswith("/worktrees/project/m")


async def test_the_isolated_location_and_branch_are_announced(
    tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """사용자의 checkout에는 아무 일도 없다 — 보이지 않으면 안 한 것으로 읽힌다."""
    _capture(monkeypatch)
    argv = await _mission(tmp_path, repo)
    capsys.readouterr()

    assert await amain(["execute", "next", *argv], default_adapters()) == 0

    error = capsys.readouterr().err
    assert "worktree:" in error
    assert "branch:   mcx/m" in error


async def test_execute_gate_does_not_provision_a_worktree(
    tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """판정은 변경을 만들지 않는다 — 격리할 것이 없다."""
    seen = _capture(monkeypatch)
    argv = await _mission(tmp_path, repo)

    assert await amain(["execute", "gate", *argv], default_adapters()) == 0

    assert seen == [str(repo)]
    assert not (tmp_path / "state" / "worktrees").exists()


async def test_a_non_git_workspace_runs_where_it_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    seen = _capture(monkeypatch)
    argv = ["--mission", "m", "--state-dir", str(tmp_path / "state")]
    adapters = default_adapters()
    assert await amain(["brief", "start", "g", "--workspace", str(plain), *argv], adapters) == 0

    assert await amain(["execute", "next", *argv], adapters) == 0

    assert seen == [str(plain)]


async def test_a_dirty_checkout_fails_the_command_rather_than_running_elsewhere(
    tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _capture(monkeypatch)
    argv = await _mission(tmp_path, repo)
    (repo / "wip.py").write_text("unfinished\n")

    assert await amain(["execute", "next", *argv], default_adapters()) == 1

    assert seen == []


class TestCleanupCommand:
    """정리는 mission에 속하지 않는 운용 명령이다 (ADR-0045 §7)."""

    async def test_it_runs_without_a_mission_and_without_any_state(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """mission을 한 번도 시작하지 않은 상태에서도 오류가 아니다."""
        code = await amain(["cleanup", "--state-dir", str(tmp_path)], default_adapters())

        assert code == 0
        assert '"removed": []' in capsys.readouterr().out

    async def test_it_does_not_open_a_ledger_entry(self, tmp_path: Path, repo: Path) -> None:
        """관측·운용 명령이 원장을 늘리면 원장이 작업을 잘못 보고한다."""
        argv = ["--mission", "m", "--state-dir", str(tmp_path / "state")]
        adapters = default_adapters()
        assert await amain(["brief", "start", "g", "--workspace", str(repo), *argv], adapters) == 0
        before = (tmp_path / "state" / "state" / "journal_m.jsonl").read_text()

        assert await amain(["cleanup", "--state-dir", str(tmp_path / "state")], adapters) == 0

        assert (tmp_path / "state" / "state" / "journal_m.jsonl").read_text() == before


def _attempt(workspace: str) -> ExecutionAttempt:
    return ExecutionAttempt(
        number=1,
        execution_id="e1",
        runtime_backend="codex_cli",
        blueprint_revision=1,
        ac_key="AC-1",
        envelope=CapabilityEnvelope(workspace=workspace),
    )


class TestStatusDisplay:
    """status는 worktree를 다시 계산하지 않고 기록된 envelope를 읽는다 (§2)."""

    def test_isolation_is_reported_when_the_attempt_ran_elsewhere(self) -> None:
        record = MissionRecord.create(mission_id="m", workspace="/ws")
        state = SimpleNamespace(attempts=[_attempt("/state/worktrees/project/m")])

        view = _isolation(record, state)  # type: ignore[arg-type]

        assert view is not None
        assert view.workspace == "/state/worktrees/project/m"
        assert view.branch == "mcx/m"

    def test_nothing_is_reported_when_the_attempt_ran_in_place(self) -> None:
        record = MissionRecord.create(mission_id="m", workspace="/ws")
        state = SimpleNamespace(attempts=[_attempt("/ws")])

        assert _isolation(record, state) is None  # type: ignore[arg-type]

    def test_nothing_is_reported_before_the_first_attempt(self) -> None:
        record = MissionRecord.create(mission_id="m", workspace="/ws")

        assert _isolation(record, None) is None
