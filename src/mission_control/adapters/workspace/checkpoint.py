"""입증된 변경만 커밋한다 — 검증 라운드 하나에 checkpoint 하나.

계약: ``docs/adr/0046-verified-checkpoint-commits.md``
근거: ``docs/research/CHECKPOINT_UPSTREAM_FINDINGS.md``
      (upstream ``auto/checkpoint_commits.py``)

**커밋 시점은 실행 뒤가 아니라 검증 뒤다** (findings §1). upstream도 호출
지점이 평가 이후 하나뿐이며 ``authoritative_pass``인 AC에만 커밋한다.
검증되지 않은 변경을 커밋하면 되돌릴 지점으로 믿을 수 없는 체크포인트가 쌓인다.

커밋 대상은 ADR-0045의 미션 전용 worktree다 — 사용자의 checkout에 커밋하는
경로가 구조적으로 없다.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess

from mission_control.domain.checkpoint import Checkpoint

#: 스테이징에서 제외하는 경로. upstream 정규식을 그대로 쓴다 (findings §3).
#: ADR-0040은 **내용**의 자격증명을 다루고 이것은 **경로**의 축이다.
SECRET_PATH = re.compile(r"(^|/)(\.env(?:\.|$)|.*secret.*|.*credential.*)", re.IGNORECASE)

_GIT_TIMEOUT_SECONDS = 30

#: 커밋 제목 상한과 AC 요약 상한. upstream과 같은 값이다.
_SUBJECT_LIMIT = 72
_SUMMARY_LIMIT = 48


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_SECONDS,
        check=False,
    )


def _output(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실행에 실패했다: {result.stderr.strip()}")
    return result.stdout.strip()


def changed_paths(workspace: Path) -> tuple[str, ...]:
    """작업 트리에서 바뀐 경로 전부. 추적되지 않은 파일도 포함한다.

    ``-z``로 읽는 이유는 공백이 든 경로 때문이다. rename/copy 항목은 원본
    경로가 한 칸 더 오므로 건너뛴다 (upstream 파싱과 같다).

    **출력을 ``strip``하지 않는다.** porcelain의 상태 두 글자는 ``" M"``처럼
    선행 공백을 가질 수 있고, 그것을 지우면 첫 항목만 경로가 한 글자 잘린다 —
    ``__pycache__`` → ``_pycache__``. 도그푸딩 0005가 실물로 관측했다: 첫
    checkpoint는 모든 파일이 ``??``(untracked)라 통과했고, **수정된 추적 파일이
    처음 나온 두 번째 라운드**에서 조용히 실패했다.
    """
    result = _git(workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if result.returncode != 0:
        raise RuntimeError(f"git status 실행에 실패했다: {result.stderr.strip()}")
    entries = result.stdout.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status, path = entry[:2], entry[3:]
        if path:
            paths.append(path)
        if status[0] in {"R", "C"} or status[1] in {"R", "C"}:
            index += 1
    return tuple(paths)


def _subject(mission_id: str, ac_keys: tuple[str, ...], summary: str) -> str:
    keys = ", ".join(ac_keys)
    text = " ".join(summary.split())
    if len(text) > _SUMMARY_LIMIT:
        text = text[: _SUMMARY_LIMIT - 3].rstrip() + "..."
    return f"mcx: {keys} 입증 — {text}".strip()[:_SUBJECT_LIMIT]


class GitCheckpointRecorder:
    """worktree에 checkpoint 커밋 하나를 남긴다.

    실패는 예외로 올리지 않는다 — 커밋을 못 남긴 것이 검증 결과를 무효로 만들지
    않는다 (upstream도 경고로 흘린다, findings §5). 대신 이유가 결과에 남는다.
    """

    def record(
        self,
        workspace: str,
        *,
        mission_id: str,
        blueprint_revision: int,
        ac_keys: tuple[str, ...],
        summary: str,
    ) -> Checkpoint:
        if not ac_keys:
            return Checkpoint(committed=False, skipped="입증된 수용 기준이 없다")
        repo = Path(workspace).expanduser().resolve()
        if not repo.is_dir():
            return Checkpoint(committed=False, skipped="workspace가 없다")
        try:
            return self._record(
                repo,
                mission_id=mission_id,
                blueprint_revision=blueprint_revision,
                ac_keys=ac_keys,
                summary=summary,
            )
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            return Checkpoint(committed=False, ac_keys=ac_keys, skipped=str(exc))

    def _record(
        self,
        repo: Path,
        *,
        mission_id: str,
        blueprint_revision: int,
        ac_keys: tuple[str, ...],
        summary: str,
    ) -> Checkpoint:
        if _git(repo, "rev-parse", "--is-inside-work-tree").returncode != 0:
            return Checkpoint(committed=False, ac_keys=ac_keys, skipped="git 저장소가 아니다")

        paths = changed_paths(repo)
        if not paths:
            return Checkpoint(committed=False, ac_keys=ac_keys, skipped="바뀐 파일이 없다")
        safe = tuple(path for path in paths if not SECRET_PATH.search(path))
        excluded = tuple(path for path in paths if SECRET_PATH.search(path))
        if not safe:
            return Checkpoint(
                committed=False,
                ac_keys=ac_keys,
                skipped="바뀐 파일이 전부 비밀 경로 규칙에 걸렸다",
                excluded=excluded,
            )

        _output(repo, "add", "--", *safe)
        # `git diff --cached --quiet`는 차이가 있을 때 1을 돌려준다.
        if _git(repo, "diff", "--cached", "--quiet", "--", *safe).returncode != 1:
            return Checkpoint(
                committed=False,
                ac_keys=ac_keys,
                skipped="스테이징된 변경이 없다",
                excluded=excluded,
            )

        message = "\n".join(
            [
                _subject(mission_id, ac_keys, summary),
                "",
                f"Mission: {mission_id}",
                f"Blueprint-Revision: {blueprint_revision}",
                f"Acceptance-Criteria: {', '.join(ac_keys)}",
            ]
        )
        # 경로를 명시해 커밋한다 — 걸러낸 파일이 우연히 실려 가지 않는다.
        _output(repo, "commit", "-m", message, "--", *safe)
        return Checkpoint(
            committed=True,
            commit=_output(repo, "rev-parse", "--short", "HEAD"),
            ac_keys=ac_keys,
            excluded=excluded,
        )
