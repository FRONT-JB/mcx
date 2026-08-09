"""실패한 시도의 잔해를 지우고 마지막 입증 지점에서 다시 시작한다.

계약: ``docs/adr/0047-rollback-to-the-last-proven-point.md``
근거: ``docs/research/ROLLBACK_UPSTREAM_FINDINGS.md``
      (upstream ``scripts/ralph.sh`` ``rollback_to_previous``)

**파괴적 연산을 쓰지 않는다.** upstream과 같은 세 걸음이며 ``reset --hard``가
아니다 — 트리와 인덱스만 되감고 커밋 이력은 남는다.

``clean``에 ``-x``를 붙이지 않는 것도 upstream과 같다: ``.gitignore``된 것
(가상환경·빌드 산출물)은 되돌리기의 대상이 아니다.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

from mission_control.domain.checkpoint import Rollback

_GIT_TIMEOUT_SECONDS = 30

#: checkpoint 커밋이 남기는 trailer. 되돌릴 지점이 **우리가 입증해서 만든 것**
#: 인지 판정하는 표식이다 (ADR-0047 §5) — upstream이 태그 존재로 판정하는 자리.
_MISSION_TRAILER = "Mission: "


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_SECONDS,
        check=False,
    )


def _require(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실행에 실패했다: {result.stderr.strip()}")
    return result.stdout.strip()


class GitRollback:
    """미션 브랜치의 HEAD로 작업 트리를 되돌린다.

    태그를 쓰지 않는다 — 이 브랜치의 커밋은 checkpoint뿐이고 checkpoint는
    입증된 것만 담으므로(ADR-0046), **HEAD가 곧 upstream의 "직전 성공 세대
    태그"** 다 (ADR-0047 §2).
    """

    def to_last_proven(self, workspace: str, *, mission_id: str) -> Rollback:
        repo = Path(workspace).expanduser().resolve()
        if not repo.is_dir():
            return Rollback(reverted=False, skipped="workspace가 없다")
        try:
            return self._revert(repo, mission_id=mission_id)
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            return Rollback(reverted=False, skipped=str(exc))

    def _revert(self, repo: Path, *, mission_id: str) -> Rollback:
        if _git(repo, "rev-parse", "--is-inside-work-tree").returncode != 0:
            return Rollback(reverted=False, skipped="git 저장소가 아니다")

        head = _git(repo, "log", "-1", "--format=%B")
        if head.returncode != 0 or f"{_MISSION_TRAILER}{mission_id}" not in head.stdout:
            # upstream: "No previous generation to rollback to". 미션 시작
            # 지점으로는 되돌리지 않는다 — 입증된 것이 하나도 없다는 뜻이다.
            return Rollback(reverted=False, skipped="되돌릴 입증 지점이 아직 없다")

        # upstream `rollback_to_previous`와 같은 세 걸음.
        _require(repo, "checkout", "HEAD", "--", ".")
        _git(repo, "reset", "HEAD")
        _require(repo, "clean", "-fd")
        return Rollback(reverted=True, commit=_require(repo, "rev-parse", "--short", "HEAD"))
