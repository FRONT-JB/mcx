"""작업 트리에서 무엇이 바뀌었는가 — 마지막 입증 지점 대비.

계약: ``docs/adr/0048-changed-files-collection.md``
근거: ``docs/research/CHANGED_FILES_UPSTREAM_FINDINGS.md``
      (upstream ``evaluation/verification_artifacts.py``)

기준선은 HEAD다. 우리 브랜치의 커밋은 checkpoint뿐이므로(ADR-0046) 이것은 곧
**마지막 입증 지점 이후 바뀐 것**이다 — rollback이 되돌리는 범위와 같은 축이다
(ADR-0047).

rename/copy는 **옛 경로와 새 경로를 둘 다** 싣는다. 무엇이 사라지고 무엇이
생겼는지 둘 다 사실이기 때문이며, staging 목적의 파싱(checkpoint)과 다른
지점이다 — upstream도 두 파서를 따로 둔다.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

from mission_control.domain.workspace import WorkspaceChanges

_GIT_TIMEOUT_SECONDS = 30


def parse_porcelain(raw: str) -> tuple[str, ...]:
    """``git status --porcelain=v1 -z`` 출력에서 경로를 뽑는다 (순수 함수)."""
    entries = raw.split("\0")
    seen: set[str] = set()
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        candidates = [path]
        if "R" in status or "C" in status:
            # 옛 경로가 다음 항목으로 온다. 둘 다 사실이므로 둘 다 싣는다.
            candidates.append(entries[index] if index < len(entries) else "")
            index += 1
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                paths.append(candidate)
    return tuple(paths)


class GitWorkspaceChanges:
    """git으로 변경 목록을 수집한다. 실패는 예외가 아니라 ``error``다."""

    def collect(self, workspace: str) -> WorkspaceChanges:
        repo = Path(workspace).expanduser().resolve()
        if not repo.is_dir():
            return WorkspaceChanges(error="workspace가 없다")
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return WorkspaceChanges(error=str(exc))
        if result.returncode != 0:
            return WorkspaceChanges(error=result.stderr.strip() or "git status 실행에 실패했다")
        return WorkspaceChanges(paths=parse_porcelain(result.stdout))
