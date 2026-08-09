"""checkpoint 커밋 — 실물 git 저장소로 검증한다 (ADR-0046 Verification)."""

from pathlib import Path
import subprocess

import pytest

from mission_control.adapters.workspace.checkpoint import GitCheckpointRecorder


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


def record(repo: Path, *, ac_keys: tuple[str, ...] = ("AC-1",), summary: str = "목차 도구"):
    return GitCheckpointRecorder().record(
        str(repo), mission_id="m-1", blueprint_revision=2, ac_keys=ac_keys, summary=summary
    )


class TestCommitting:
    def test_proven_changes_become_one_commit(self, repo: Path) -> None:
        (repo / "mdtoc.py").write_text("print()\n")

        result = record(repo)

        assert result.committed
        assert result.commit
        assert "mdtoc.py" in git("show", "--name-only", "--format=", "HEAD", cwd=repo)

    def test_the_message_carries_the_mission_lineage(self, repo: Path) -> None:
        (repo / "mdtoc.py").write_text("print()\n")

        record(repo, ac_keys=("AC-1", "AC-3"))

        message = git("log", "-1", "--format=%B", cwd=repo)
        assert "AC-1, AC-3" in message
        assert "Mission: m-1" in message
        assert "Blueprint-Revision: 2" in message

    def test_the_subject_stays_within_the_git_convention(self, repo: Path) -> None:
        (repo / "mdtoc.py").write_text("print()\n")

        record(repo, summary="아주 긴 목표 문장을 " * 20)

        subject = git("log", "-1", "--format=%s", cwd=repo).strip()
        assert len(subject) <= 72

    def test_untracked_files_are_included(self, repo: Path) -> None:
        (repo / "brand_new.py").write_text("x\n")

        assert record(repo).committed
        assert "brand_new.py" in git("show", "--name-only", "--format=", "HEAD", cwd=repo)


class TestRefusals:
    def test_nothing_proven_means_nothing_committed(self, repo: Path) -> None:
        (repo / "mdtoc.py").write_text("print()\n")

        result = record(repo, ac_keys=())

        assert not result.committed
        assert result.skipped == "입증된 수용 기준이 없다"

    def test_a_clean_tree_leaves_no_commit(self, repo: Path) -> None:
        before = git("rev-parse", "HEAD", cwd=repo)

        result = record(repo)

        assert not result.committed
        assert result.skipped == "바뀐 파일이 없다"
        assert git("rev-parse", "HEAD", cwd=repo) == before

    def test_running_twice_does_not_make_an_empty_second_commit(self, repo: Path) -> None:
        """저장하고 나면 트리가 깨끗하다 — 멱등성이 git에서 나온다 (ADR-0046 §5)."""
        (repo / "mdtoc.py").write_text("print()\n")
        first = record(repo)

        second = record(repo)

        assert first.committed and not second.committed
        assert len(git("log", "--format=%h", cwd=repo).split()) == 2

    def test_a_non_git_directory_is_reported_not_raised(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()

        result = GitCheckpointRecorder().record(
            str(plain), mission_id="m-1", blueprint_revision=1, ac_keys=("AC-1",), summary="x"
        )

        assert not result.committed
        assert result.skipped is not None


class TestSecretPaths:
    def test_secret_paths_never_reach_the_commit(self, repo: Path) -> None:
        (repo / "mdtoc.py").write_text("print()\n")
        (repo / ".env").write_text("TOKEN=sk-live-1234\n")
        (repo / "aws_credentials.json").write_text("{}\n")

        result = record(repo)

        committed = git("show", "--name-only", "--format=", "HEAD", cwd=repo)
        assert "mdtoc.py" in committed
        assert ".env" not in committed
        assert "aws_credentials.json" not in committed
        assert set(result.excluded) == {".env", "aws_credentials.json"}

    def test_only_secret_changes_means_no_commit_at_all(self, repo: Path) -> None:
        (repo / ".env").write_text("TOKEN=sk-live-1234\n")
        before = git("rev-parse", "HEAD", cwd=repo)

        result = record(repo)

        assert not result.committed
        assert result.excluded == (".env",)
        assert git("rev-parse", "HEAD", cwd=repo) == before

    def test_the_excluded_file_is_not_left_staged(self, repo: Path) -> None:
        """스테이징에만 남아도 다음 커밋에 섞여 들어간다."""
        (repo / "mdtoc.py").write_text("print()\n")
        (repo / ".env").write_text("TOKEN=sk-live-1234\n")

        record(repo)

        assert ".env" not in git("diff", "--cached", "--name-only", cwd=repo)
