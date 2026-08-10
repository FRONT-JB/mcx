"""worktree 격리 — 실물 git 저장소로 검증한다 (ADR-0045 Verification).

fake git을 만들지 않는다. 이 adapter가 하는 일의 전부가 git의 실제 반응이므로,
흉내낸 것을 검증하면 아무것도 검증하지 않는 것이다.
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

from mission_control.adapters.workspace import worktree


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


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "state" / "worktrees"


class TestPreparation:
    def test_a_worktree_is_created_on_its_own_branch(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)

        assert isolation is not None
        assert isolation.branch == "mcx/m1"
        assert Path(isolation.worktree_path).is_dir()
        assert (Path(isolation.workspace) / "README.md").read_text() == "hello\n"

    def test_the_users_checkout_does_not_see_the_agents_changes(
        self, repo: Path, root: Path
    ) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None

        (Path(isolation.workspace) / "new.py").write_text("print()\n")

        assert not (repo / "new.py").exists()

    def test_the_second_call_reuses_the_same_worktree(self, repo: Path, root: Path) -> None:
        first = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert first is not None
        (Path(first.workspace) / "kept.py").write_text("x\n")

        second = worktree.prepare(str(repo), mission_id="m1", root=root)

        assert second == first
        assert (Path(second.workspace) / "kept.py").exists()

    def test_two_missions_get_two_worktrees(self, repo: Path, root: Path) -> None:
        one = worktree.prepare(str(repo), mission_id="m1", root=root)
        two = worktree.prepare(str(repo), mission_id="m2", root=root)

        assert one is not None and two is not None
        assert one.worktree_path != two.worktree_path
        assert one.branch != two.branch

    def test_a_subdirectory_workspace_keeps_its_relative_position(
        self, repo: Path, root: Path
    ) -> None:
        package = repo / "packages" / "api"
        package.mkdir(parents=True)
        (package / "main.py").write_text("x\n")
        git("add", ".", cwd=repo)
        git("commit", "-m", "sub", cwd=repo)

        isolation = worktree.prepare(str(package), mission_id="m1", root=root)

        assert isolation is not None
        assert isolation.workspace.endswith("/packages/api")
        assert (Path(isolation.workspace) / "main.py").exists()


class TestRefusals:
    def test_a_dirty_checkout_refuses_because_uncommitted_work_does_not_follow(
        self, repo: Path, root: Path
    ) -> None:
        (repo / "wip.py").write_text("unfinished\n")

        with pytest.raises(worktree.WorktreeError, match="격리 worktree를 시작할 수 없다"):
            worktree.prepare(str(repo), mission_id="m1", root=root)

    def test_a_dirty_checkout_does_not_block_an_existing_worktree(
        self, repo: Path, root: Path
    ) -> None:
        """전제는 **만들 때**의 것이다 — 이미 있으면 분기하지 않는다."""
        worktree.prepare(str(repo), mission_id="m1", root=root)
        (repo / "wip.py").write_text("unfinished\n")

        assert worktree.prepare(str(repo), mission_id="m1", root=root) is not None

    def test_an_empty_repository_says_how_to_fix_it(self, tmp_path: Path, root: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        git("init", "-b", "main", cwd=empty)

        with pytest.raises(worktree.WorktreeError, match="최초 커밋"):
            worktree.prepare(str(empty), mission_id="m1", root=root)

    def test_a_worktree_root_inside_the_repository_is_refused(self, repo: Path) -> None:
        with pytest.raises(worktree.WorktreeError, match="대상 저장소.*안에 있다"):
            worktree.prepare(str(repo), mission_id="m1", root=repo / ".mcx" / "worktrees")

    def test_a_mission_id_that_is_not_a_git_ref_is_refused(self, repo: Path, root: Path) -> None:
        with pytest.raises(worktree.WorktreeError, match="git 브랜치 이름으로 쓸 수 없다"):
            worktree.prepare(str(repo), mission_id="has space", root=root)

    def test_a_stray_directory_is_refused_rather_than_deleted(self, repo: Path, root: Path) -> None:
        stray = root / repo.name / "m1"
        stray.mkdir(parents=True)
        (stray / "someones-file.txt").write_text("do not delete me\n")

        with pytest.raises(worktree.WorktreeError, match="worktree로 알지 못한다"):
            worktree.prepare(str(repo), mission_id="m1", root=root)

        assert (stray / "someones-file.txt").exists()


class TestNonGitWorkspace:
    def test_a_plain_directory_runs_where_it_is(self, tmp_path: Path, root: Path) -> None:
        plain = tmp_path / "not-a-repo"
        plain.mkdir()

        assert worktree.prepare(str(plain), mission_id="m1", root=root) is None


class TestLock:
    def test_the_lock_is_released_when_the_command_ends(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None

        with worktree.hold(isolation):
            assert Path(isolation.lock_path).exists()

        assert not Path(isolation.lock_path).exists()

    def test_a_live_owner_blocks_a_second_dispatch(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None

        with worktree.hold(isolation):
            with pytest.raises(worktree.WorktreeError, match="이미 돌고 있다"):
                with worktree.hold(isolation):
                    pass

        assert not Path(isolation.lock_path).exists()

    def test_a_dead_owner_is_taken_over(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        lock = Path(isolation.lock_path)
        lock.parent.mkdir(parents=True, exist_ok=True)
        # 살아 있을 수 없는 pid — 프로세스가 죽으면서 남긴 lock의 모습이다.
        lock.write_text(json.dumps({"pid": 2**31 - 1, "host": os.uname().nodename}))

        with worktree.hold(isolation):
            assert json.loads(lock.read_text())["pid"] == os.getpid()

    def test_another_hosts_lock_is_not_stolen(self, repo: Path, root: Path) -> None:
        """판정할 수 없으면 살아 있는 것으로 본다 (ADR-0045 §6)."""
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        lock = Path(isolation.lock_path)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": 1, "host": "some-other-machine"}))

        with pytest.raises(worktree.WorktreeError, match="이미 돌고 있다"):
            with worktree.hold(isolation):
                pass

    def test_an_unreadable_lock_is_refused_not_overwritten(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        lock = Path(isolation.lock_path)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("{ truncated")

        with pytest.raises(worktree.WorktreeError, match="lock 파일을 읽을 수 없다"):
            with worktree.hold(isolation):
                pass

        assert lock.read_text() == "{ truncated"


def commit_in(worktree_path: Path, name: str) -> None:
    (worktree_path / name).write_text("done\n")
    git("add", ".", cwd=worktree_path)
    git("commit", "-m", f"add {name}", cwd=worktree_path)


class TestSweep:
    """정리는 사용자가 병합한 뒤 부르는 GC다 (ADR-0045 §7)."""

    def test_nothing_to_sweep_is_not_an_error(self, root: Path) -> None:
        result = worktree.sweep(root)

        assert result.removed == ()
        assert result.kept == ()

    def test_a_merged_mission_is_removed_with_its_branch(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        commit_in(Path(isolation.worktree_path), "feature.py")
        git("merge", "--no-edit", isolation.branch, cwd=repo)

        result = worktree.sweep(root)

        assert [item.branch for item in result.removed] == ["mcx/m1"]
        assert result.removed[0].branch_deleted is True
        assert not Path(isolation.worktree_path).exists()
        assert (repo / "feature.py").exists()

    def test_an_unmerged_mission_is_kept(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        commit_in(Path(isolation.worktree_path), "feature.py")

        result = worktree.sweep(root)

        assert result.removed == ()
        assert [item.reason for item in result.kept] == ["unmerged"]
        assert Path(isolation.worktree_path).exists()

    def test_force_removes_the_unmerged_worktree_but_keeps_the_branch(
        self, repo: Path, root: Path
    ) -> None:
        """작업이 사라지지 않는다 — 브랜치가 남으므로 나중에 꺼낼 수 있다."""
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        commit_in(Path(isolation.worktree_path), "feature.py")

        result = worktree.sweep(root, force=True)

        assert result.removed[0].branch_deleted is False
        assert not Path(isolation.worktree_path).exists()
        assert (
            "mcx/m1"
            in subprocess.run(
                ["git", "branch", "--list", "mcx/m1"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        )

    def test_uncommitted_work_is_never_swept_even_with_force(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        (Path(isolation.worktree_path) / "wip.py").write_text("half done\n")

        result = worktree.sweep(root, force=True)

        assert [item.reason for item in result.kept] == ["dirty"]
        assert (Path(isolation.worktree_path) / "wip.py").exists()

    def test_a_running_mission_is_never_swept(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        commit_in(Path(isolation.worktree_path), "feature.py")
        git("merge", "--no-edit", isolation.branch, cwd=repo)

        with worktree.hold(isolation):
            result = worktree.sweep(root, force=True)

        assert [item.reason for item in result.kept] == ["running"]
        assert Path(isolation.worktree_path).exists()

    def test_dry_run_reports_the_same_decision_without_touching_anything(
        self, repo: Path, root: Path
    ) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        commit_in(Path(isolation.worktree_path), "feature.py")
        git("merge", "--no-edit", isolation.branch, cwd=repo)

        planned = worktree.sweep(root, dry_run=True)
        assert Path(isolation.worktree_path).exists()

        actual = worktree.sweep(root)
        assert [item.worktree_path for item in planned.removed] == [
            item.worktree_path for item in actual.removed
        ]

    def test_a_dead_missions_leftover_lock_is_pruned(self, repo: Path, root: Path) -> None:
        isolation = worktree.prepare(str(repo), mission_id="m1", root=root)
        assert isolation is not None
        commit_in(Path(isolation.worktree_path), "feature.py")
        git("merge", "--no-edit", isolation.branch, cwd=repo)
        lock = Path(isolation.lock_path)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"pid": 2**31 - 1, "host": os.uname().nodename}))

        worktree.sweep(root)

        assert not lock.exists()

    def test_a_directory_that_is_not_our_worktree_is_left_alone(
        self, repo: Path, root: Path
    ) -> None:
        stray = root / "somewhere" / "not-a-worktree"
        stray.mkdir(parents=True)
        (stray / "file.txt").write_text("mine\n")

        result = worktree.sweep(root, force=True)

        assert result.removed == ()
        assert (stray / "file.txt").exists()
