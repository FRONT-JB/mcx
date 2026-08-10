"""미션 하나에 git worktree 하나 — 변경이 사용자의 checkout에 쌓이지 않게 한다.

계약: ``docs/adr/0045-worktree-isolation-contract.md``
근거: ``docs/research/WORKTREE_UPSTREAM_FINDINGS.md`` (upstream ``core/worktree.py``)

경로는 **저장하지 않고 유도한다** (ADR-0045 §2) — ``(worktree 루트, mission의
workspace, mission_id)``에서 결정적으로 나오므로 upstream ``TaskWorkspace``의
직렬화·복원 계층이 우리에겐 없다. 역사적 기록은 각 ``ExecutionAttempt``의
``envelope.workspace``가 이미 들고 있다.

git 호출은 동기다. 한 CLI 명령 안에서 다른 일이 동시에 돌지 않고 호출이
수백 ms로 끝나므로, 비동기로 감싸면 계약만 복잡해지고 얻는 것이 없다.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import socket
import subprocess

#: 관리 브랜치 접두사. upstream ``ooo/``의 자리다.
BRANCH_PREFIX = "mcx"

#: git 호출 상한. upstream과 같은 값이다.
_GIT_TIMEOUT_SECONDS = 30


class WorktreeError(RuntimeError):
    """격리를 성립시킬 수 없다 — 실행을 시작하지 않는다."""


@dataclass(frozen=True)
class Isolation:
    """준비된 격리 자리. ``workspace``가 실행이 실제로 도는 곳이다."""

    workspace: str
    worktree_path: str
    branch: str
    lock_path: str


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorktreeError(f"git {' '.join(args)} 실행에 실패했다: {exc}") from exc


def _git_output(args: list[str], cwd: Path) -> str:
    result = _git(args, cwd)
    if result.returncode != 0:
        raise WorktreeError(f"git {' '.join(args)} 실행에 실패했다: {result.stderr.strip()}")
    return result.stdout.strip()


def repo_root(workspace: str | Path) -> Path | None:
    """workspace를 담고 있는 저장소 루트. git 저장소가 아니면 ``None``이다."""
    path = Path(workspace).expanduser().resolve()
    probe = path if path.is_dir() else path.parent
    if not probe.is_dir():
        return None
    result = _git(["rev-parse", "--show-toplevel"], probe)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def _branch_name(root: Path, mission_id: str) -> str:
    branch = f"{BRANCH_PREFIX}/{mission_id}"
    if _git(["check-ref-format", "--branch", branch], root).returncode != 0:
        raise WorktreeError(f"mission id {mission_id!r}는 git 브랜치 이름으로 쓸 수 없다")
    return branch


def _registered(root: Path) -> set[str]:
    """``git worktree list``가 아는 경로들."""
    output = _git_output(["worktree", "list", "--porcelain"], root)
    return {line.split(" ", 1)[1] for line in output.splitlines() if line.startswith("worktree ")}


def _require_clean(root: Path) -> None:
    """worktree는 HEAD에서 분기하므로 커밋되지 않은 변경은 따라오지 않는다."""
    if _git_output(["status", "--porcelain"], root):
        raise WorktreeError(
            f"커밋되지 않은 변경이 있어 격리 worktree를 시작할 수 없다 ({root}); "
            "먼저 커밋하거나 stash한다 — 커밋되지 않은 작업은 worktree로 따라오지 않는다"
        )


def _head(root: Path) -> str:
    result = _git(["rev-parse", "--verify", "HEAD"], root)
    if result.returncode != 0:
        raise WorktreeError(
            f"빈 저장소에서는 분기할 수 없다 ({root}); 먼저 최초 커밋을 만든다 "
            '(예: git commit --allow-empty -m "chore: initialize")'
        )
    return result.stdout.strip()


def _create(root: Path, worktree_path: Path, branch: str) -> None:
    _require_clean(root)
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    if _git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], root).returncode == 0:
        _git_output(["worktree", "add", str(worktree_path), branch], root)
        return
    _git_output(["worktree", "add", "-b", branch, str(worktree_path), _head(root)], root)


def prepare(workspace: str, *, mission_id: str, root: Path) -> Isolation | None:
    """미션의 worktree를 만들거나 재사용한다. git 저장소가 아니면 ``None``이다.

    ``None``은 설정이 아니라 **사실에 대한 반응**이다 (ADR-0045 §4) — 호출자는
    원래 workspace를 그대로 쓴다.
    """
    source = Path(workspace).expanduser().resolve()
    repository = repo_root(source)
    if repository is None:
        return None

    branch = _branch_name(repository, mission_id)
    worktree_path = (root / repository.name / mission_id).resolve()
    if worktree_path.is_relative_to(repository):
        # 저장소 안에 worktree가 생기면 그 저장소가 영구히 dirty가 되어
        # 이후 모든 미션이 clean checkout 전제에서 막힌다 (ADR-0045 Verification).
        raise WorktreeError(
            f"worktree 루트 {root}가 대상 저장소 {repository} 안에 있다; "
            "--state-dir를 저장소 밖으로 지정한다"
        )

    if str(worktree_path) not in _registered(repository):
        if worktree_path.exists():
            # upstream은 이 경우 남은 디렉토리를 rmtree하고 다시 만든다. 우리는
            # 지우지 않는다 (ADR-0045 §7) — 거부는 사용자가 되돌릴 수 있다.
            raise WorktreeError(
                f"{worktree_path}가 있는데 git은 이것을 worktree로 알지 못한다; "
                "그 디렉토리를 지우거나 `git worktree prune`을 실행한 뒤 다시 시도한다"
            )
        _create(repository, worktree_path, branch)

    relative = source.relative_to(repository) if source != repository else Path()
    return Isolation(
        workspace=str(worktree_path / relative),
        worktree_path=str(worktree_path),
        branch=branch,
        lock_path=str(root / ".locks" / repository.name / f"{mission_id}.json"),
    )


def _owner_is_live(owner: dict[str, object]) -> bool:
    """다른 호스트의 lock은 판정할 수 없으므로 **살아 있는 것으로 본다**.

    upstream은 이 자리에서 시간 임계값으로 넘어가지만, 임계값을 잘못 잡으면
    살아 있는 실행의 worktree를 조용히 빼앗는다. 거부는 사용자가 lock 경로를
    보고 지우면 풀린다 (ADR-0045 §6).
    """
    if owner.get("host") != socket.gethostname():
        return True
    pid = owner.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # 프로세스는 있는데 신호 권한이 없다 — 살아 있다.
        return True
    return True


def _read_owner(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and payload else None


@contextmanager
def hold(isolation: Isolation) -> Iterator[None]:
    """이 명령이 끝날 때까지 미션의 worktree 소유권을 잡는다 (ADR-0045 §6).

    같은 미션을 동시에 dispatch하면 두 실행이 같은 worktree에 쓴다. git은 그것을
    막지 않고, 상태 저장소의 낙관적 동시성은 파일이 이미 바뀐 뒤에 걸린다.
    """
    path = Path(isolation.lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _acquire(path, isolation)
    try:
        yield
    finally:
        _release(path)


def _acquire(path: Path, isolation: Isolation) -> None:
    for _ in range(2):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            owner = _read_owner(path)
            if owner is None:
                raise WorktreeError(
                    f"lock 파일을 읽을 수 없다: {path}; 돌고 있는 mission이 없으면 그 파일을 지운다"
                ) from None
            if _owner_is_live(owner):
                raise WorktreeError(
                    f"{isolation.worktree_path}에서 mission이 이미 돌고 있다 "
                    f"(pid {owner.get('pid')}, host {owner.get('host')}); "
                    f"끝날 때까지 기다리거나, 돌고 있지 않다면 {path}를 지운다"
                ) from None
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": os.getpid(),
                    "host": socket.gethostname(),
                    "branch": isolation.branch,
                    "worktree_path": isolation.worktree_path,
                    "acquired_at": datetime.now(UTC).isoformat(),
                },
                handle,
                indent=2,
                sort_keys=True,
            )
        return
    raise WorktreeError(f"{path}를 잡을 수 없다")


def _release(path: Path) -> None:
    """자기 것만 푼다 — 남의 lock을 지우지 않는다."""
    owner = _read_owner(path)
    if owner is None:
        return
    if owner.get("pid") == os.getpid() and owner.get("host") == socket.gethostname():
        path.unlink(missing_ok=True)


# --- 정리 (ADR-0045 §7, 사용자 결정 2026-08-09) -------------------------------
#
# 실행 경로와 분리된 별도 명령이다. upstream ``ouroboros cleanup``과 같은 형태이며,
# 자동 병합이 없으므로 **사용자가 병합한 뒤** 부르는 GC다.


@dataclass(frozen=True)
class Removed:
    worktree_path: str
    branch: str
    branch_deleted: bool


@dataclass(frozen=True)
class Kept:
    worktree_path: str
    branch: str
    reason: str


@dataclass(frozen=True)
class Sweep:
    """정리 한 번의 결과. ``dry_run``이면 아무것도 바뀌지 않았다."""

    dry_run: bool
    removed: tuple[Removed, ...]
    kept: tuple[Kept, ...]
    locks_removed: tuple[str, ...]


def _common_repo_root(worktree_path: Path) -> Path | None:
    """linked worktree가 가리키는 원본 저장소."""
    result = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"], worktree_path)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve().parent


def _is_merged(repository: Path, branch: str) -> bool:
    """브랜치가 저장소의 HEAD에 이미 들어가 있는가."""
    exists = _git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], repository)
    if exists.returncode != 0:
        return True  # 브랜치가 없으면 남길 것도 없다
    result = _git(["merge-base", "--is-ancestor", branch, "HEAD"], repository)
    if result.returncode in (0, 1):
        return result.returncode == 0
    raise WorktreeError(f"{branch}가 병합됐는지 판정할 수 없다: {result.stderr.strip()}")


def sweep(root: Path, *, force: bool = False, dry_run: bool = False) -> Sweep:
    """정리 가능한 worktree를 훑어 제거한다.

    **살아 있는 미션, 커밋되지 않은 변경, 병합되지 않은 브랜치는 건드리지
    않는다.** ``force``는 셋 중 마지막 하나만 푼다 — 깨끗하지만 병합되지 않은
    worktree를 치우되 **브랜치는 남긴다**. 작업이 사라지지 않는다는 뜻이며,
    upstream ``--force``와 같은 의미다.
    """
    removed: list[Removed] = []
    kept: list[Kept] = []
    for worktree_path, mission_id, repository in _managed(root):
        branch = f"{BRANCH_PREFIX}/{mission_id}"
        reason = _keep_reason(root, worktree_path, repository, branch, mission_id, force=force)
        if reason is not None:
            kept.append(Kept(str(worktree_path), branch, reason))
            continue
        merged = _is_merged(repository, branch)
        if not dry_run:
            _git_output(["worktree", "remove", str(worktree_path)], repository)
            if merged:
                _git_output(["branch", "-d", branch], repository)
            _lock_for(root, repository.name, mission_id).unlink(missing_ok=True)
        removed.append(Removed(str(worktree_path), branch, branch_deleted=merged))
    return Sweep(
        dry_run=dry_run,
        removed=tuple(removed),
        kept=tuple(kept),
        locks_removed=tuple(_prune_locks(root, dry_run=dry_run)),
    )


def _keep_reason(
    root: Path,
    worktree_path: Path,
    repository: Path,
    branch: str,
    mission_id: str,
    *,
    force: bool,
) -> str | None:
    """지우지 **않는** 이유. ``None``이면 지워도 된다."""
    lock = _lock_for(root, repository.name, mission_id)
    owner = _read_owner(lock) if lock.exists() else None
    if owner is not None and _owner_is_live(owner):
        return "running"
    if _git_output(["status", "--porcelain"], worktree_path):
        return "dirty"
    if not force and not _is_merged(repository, branch):
        return "unmerged"
    return None


def _lock_for(root: Path, repo_name: str, mission_id: str) -> Path:
    return root / ".locks" / repo_name / f"{mission_id}.json"


def _managed(root: Path) -> Iterator[tuple[Path, str, Path]]:
    """``<root>/<repo>/<mission>`` 중 실제 linked worktree인 것만 내놓는다."""
    if not root.is_dir():
        return
    for repo_dir in sorted(root.iterdir()):
        if not repo_dir.is_dir() or repo_dir.name == ".locks":
            continue
        for worktree_path in sorted(repo_dir.iterdir()):
            if not worktree_path.is_dir():
                continue
            repository = _common_repo_root(worktree_path)
            if repository is None or repository == worktree_path.resolve():
                # 원본 저장소가 사라졌거나 linked worktree가 아니다 — 우리 것이
                # 맞는지 알 수 없으므로 지우지 않는다.
                continue
            yield worktree_path, worktree_path.name, repository


def _prune_locks(root: Path, *, dry_run: bool) -> list[str]:
    """worktree가 사라졌는데 남은 lock 파일. 살아 있는 것은 건드리지 않는다."""
    pruned: list[str] = []
    locks = root / ".locks"
    if not locks.is_dir():
        return pruned
    for repo_dir in sorted(locks.iterdir()):
        if not repo_dir.is_dir():
            continue
        for lock in sorted(repo_dir.glob("*.json")):
            if (root / repo_dir.name / lock.stem).exists():
                continue
            owner = _read_owner(lock)
            if owner is not None and _owner_is_live(owner):
                continue
            if not dry_run:
                lock.unlink(missing_ok=True)
            pruned.append(str(lock))
    return pruned
