"""변경 수집 — 실물 git으로 검증한다 (ADR-0048)."""

from pathlib import Path
import subprocess

import pytest

from mission_control.adapters.workspace.changes import GitWorkspaceChanges, parse_porcelain


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
    (root / "old_name.py").write_text("x\n")
    git("add", ".", cwd=root)
    git("commit", "-m", "init", cwd=root)
    return root


class TestCollecting:
    def test_a_clean_tree_reports_no_changes_and_no_error(self, repo: Path) -> None:
        result = GitWorkspaceChanges().collect(str(repo))

        assert result.paths == ()
        assert result.error is None

    def test_modified_and_new_files_are_both_listed(self, repo: Path) -> None:
        (repo / "README.md").write_text("바뀜\n")
        (repo / "brand_new.py").write_text("새것\n")

        result = GitWorkspaceChanges().collect(str(repo))

        assert set(result.paths) == {"README.md", "brand_new.py"}

    def test_a_rename_lists_both_paths(self, repo: Path) -> None:
        """무엇이 사라지고 무엇이 생겼는지 둘 다 사실이다."""
        git("mv", "old_name.py", "new_name.py", cwd=repo)

        result = GitWorkspaceChanges().collect(str(repo))

        assert set(result.paths) == {"old_name.py", "new_name.py"}

    def test_files_in_new_directories_are_listed_individually(self, repo: Path) -> None:
        """``--untracked-files=all``이 없으면 디렉토리 하나로 뭉뚱그려진다."""
        (repo / "pkg").mkdir()
        (repo / "pkg" / "a.py").write_text("a\n")
        (repo / "pkg" / "b.py").write_text("b\n")

        result = GitWorkspaceChanges().collect(str(repo))

        assert set(result.paths) == {"pkg/a.py", "pkg/b.py"}

    def test_paths_with_spaces_survive(self, repo: Path) -> None:
        (repo / "이름에 공백.md").write_text("x\n")

        assert "이름에 공백.md" in GitWorkspaceChanges().collect(str(repo)).paths


class TestUnavailable:
    def test_a_non_git_directory_reports_an_error_not_an_empty_list(
        self, tmp_path: Path
    ) -> None:
        """빈 목록과 수집 실패는 다르다 — 뭉치면 '변경 없음'으로 읽힌다."""
        plain = tmp_path / "plain"
        plain.mkdir()

        result = GitWorkspaceChanges().collect(str(plain))

        assert result.paths == ()
        assert result.error is not None

    def test_a_missing_workspace_reports_an_error(self, tmp_path: Path) -> None:
        result = GitWorkspaceChanges().collect(str(tmp_path / "없음"))

        assert result.error == "workspace가 없다"


class TestParsing:
    def test_short_and_empty_entries_are_ignored(self) -> None:
        assert parse_porcelain("\0\0 M\0") == ()

    def test_duplicates_collapse(self) -> None:
        assert parse_porcelain(" M a.py\0 M a.py\0") == ("a.py",)
