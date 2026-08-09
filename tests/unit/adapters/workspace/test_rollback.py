"""마지막 입증 지점으로 되돌리기 — 실물 git으로 검증한다 (ADR-0047)."""

from pathlib import Path
import subprocess

import pytest

from mission_control.adapters.workspace.checkpoint import GitCheckpointRecorder
from mission_control.adapters.workspace.rollback import GitRollback


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    root.mkdir()
    git("init", "-b", "main", cwd=root)
    git("config", "user.email", "t@example.com", cwd=root)
    git("config", "user.name", "t", cwd=root)
    (root / "README.md").write_text("hello\n")
    git("add", ".", cwd=root)
    git("commit", "-m", "init", cwd=root)
    return root


def checkpoint(repo: Path) -> None:
    GitCheckpointRecorder().record(
        str(repo), mission_id="m-1", blueprint_revision=1, ac_keys=("AC-1",), summary="목차 도구"
    )


def rollback(repo: Path, mission_id: str = "m-1"):
    return GitRollback().to_last_proven(str(repo), mission_id=mission_id)


class TestReverting:
    def test_unproven_changes_are_discarded(self, repo: Path) -> None:
        (repo / "proven.py").write_text("좋다\n")
        checkpoint(repo)
        (repo / "proven.py").write_text("실패한 시도가 망쳐 놓음\n")
        (repo / "garbage.py").write_text("실패한 시도의 잔해\n")

        result = rollback(repo)

        assert result.reverted
        assert (repo / "proven.py").read_text() == "좋다\n"
        assert not (repo / "garbage.py").exists()

    def test_the_commit_history_survives(self, repo: Path) -> None:
        """`reset --hard`가 아니다 — 입증된 것은 커밋으로 남는다."""
        (repo / "proven.py").write_text("좋다\n")
        checkpoint(repo)
        before = git("log", "--format=%h", cwd=repo)
        (repo / "garbage.py").write_text("잔해\n")

        rollback(repo)

        assert git("log", "--format=%h", cwd=repo) == before

    def test_staged_leftovers_are_unstaged_too(self, repo: Path) -> None:
        (repo / "proven.py").write_text("좋다\n")
        checkpoint(repo)
        (repo / "half.py").write_text("반쯤 만든 것\n")
        git("add", "half.py", cwd=repo)

        rollback(repo)

        assert git("status", "--porcelain", cwd=repo).strip() == ""

    def test_ignored_files_are_left_alone(self, repo: Path) -> None:
        """`clean -x`가 아니다 — 가상환경·빌드 산출물은 되돌리기 대상이 아니다."""
        (repo / ".gitignore").write_text("build/\n")
        (repo / "proven.py").write_text("좋다\n")
        checkpoint(repo)
        (repo / "build").mkdir()
        (repo / "build" / "artifact.bin").write_text("비싼 것\n")

        rollback(repo)

        assert (repo / "build" / "artifact.bin").exists()


class TestRefusals:
    def test_nothing_proven_yet_means_no_rollback(self, repo: Path) -> None:
        """upstream: "No previous generation to rollback to" — 시작점으로는 안 간다."""
        (repo / "first_try.py").write_text("첫 시도\n")

        result = rollback(repo)

        assert not result.reverted
        assert result.skipped == "되돌릴 입증 지점이 아직 없다"
        assert (repo / "first_try.py").exists()

    def test_another_missions_checkpoint_is_not_a_target(self, repo: Path) -> None:
        (repo / "proven.py").write_text("좋다\n")
        checkpoint(repo)
        (repo / "garbage.py").write_text("잔해\n")

        result = rollback(repo, mission_id="m-2")

        assert not result.reverted
        assert (repo / "garbage.py").exists()

    def test_a_non_git_directory_is_reported_not_raised(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()

        result = GitRollback().to_last_proven(str(plain), mission_id="m-1")

        assert not result.reverted
        assert result.skipped is not None


class TestWithCheckpoint:
    def test_the_round_trip_leaves_only_proven_work(self, repo: Path) -> None:
        """checkpoint → 실패 → rollback → checkpoint가 남긴 것만 남는다."""
        (repo / "ac1.py").write_text("AC-1 입증\n")
        checkpoint(repo)
        (repo / "ac2_attempt.py").write_text("AC-2 실패한 시도\n")

        rollback(repo)

        assert (repo / "ac1.py").exists()
        assert not (repo / "ac2_attempt.py").exists()
        assert git("status", "--porcelain", cwd=repo).strip() == ""
