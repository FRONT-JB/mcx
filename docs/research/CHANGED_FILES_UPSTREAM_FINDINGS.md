# upstream `changed_files` 조사 — `evaluation/verification_artifacts.py`

- 조사일: 2026-08-09
- Baseline: `~/.claude/plugins/marketplaces/ouroboros` @ `9486c78` (v0.50.8)
- Evidence level: **source-read**
- 소비처: [ADR-0048](../adr/0048-changed-files-collection.md)

## 1. `changed_files`는 **QA가 읽는 재료**다

`VerificationArtifacts`의 필드이며, `build_verification_artifacts`가 만들어
`## Repository Changes` 섹션으로 렌더한 뒤 **QA 핸들러의 `artifact` 입력**으로
들어간다 (`cli/commands/run.py:785`, `mcp/tools/execution_handlers.py:1848`).

즉 수집의 1차 목적이 기록이 아니라 **판정의 재료**다. upstream QA는 작업
디렉토리를 직접 관찰하지 않고 렌더된 아티팩트만 받기 때문이다.

## 2. 기준선은 커밋이 아니라 **작업 트리 상태**다

```python
("git", "status", "--porcelain=v1", "-z")
```

`HEAD` 대비 바뀐 것이다. 별도의 기준 커밋을 지정하지 않는다.

## 3. 세 가지를 캡처하고 **전부 파일로 보존**한다

| 명령 | 용도 | 저장 |
|---|---|---|
| `git status --short` | 사람용 렌더 | `git-status.txt` |
| `git status --porcelain=v1 -z` | 파싱 | `git-status-porcelain.txt` |
| `git diff --stat --find-renames` | 규모 요약 | `git-diff-stat.txt` |

## 4. rename/copy는 **두 경로 모두** 싣는다

```python
if "R" in status or "C" in status:
    new_path = entries[index + 1] if index + 1 < len(entries) else ""
    paths = [path, new_path]
    index += 1
```

중복은 `seen`으로 제거한다.

> **같은 저장소 안에 파서가 둘이다.** `auto/checkpoint_commits.py`의
> `_changed_paths`는 rename에서 **한쪽만** 담는다(스테이징 대상이므로). 목적이
> 다르면 파싱도 다르다는 것을 upstream이 코드로 보여 준다.

## 5. **순서가 계약이다** — 우리 도구의 부작용을 집계하지 않는다

```python
# Capture the execution's git diff BEFORE authoring the detector toml so
# ``changed_files`` reflects what the agent produced, not the side-effect
# of the detector writing ``.ouroboros/mechanical.toml``.
```

git 상태 캡처가 detector 실행보다 **먼저**다. 뒤로 밀면 우리가 만든 파일이
에이전트의 산출물로 집계된다.

## 6. 수집 실패는 예외가 아니고, **빈 목록과 구분된다**

`git_state_available: bool` + `git_state_error: str | None`을 따로 들고,
렌더가 세 갈래로 갈린다.

```
- (변경 목록)                    ← 목록이 있음
- (git state unavailable)        ← 수집 불가
- (no changed files detected)    ← 수집 성공, 변경 없음
```

**뭉치면 "관찰 못 함"이 "변경 없음"으로 읽힌다.**

---

## 우리 쪽 대응 지점 (조사 시점의 사실)

- 우리 대응물은 `VerificationEvidence`다 (ADR-0029가 예약해 둔 자리).
- 기준선이 **이미 맞는다** — 우리 worktree의 HEAD는 마지막 checkpoint이고
  (ADR-0046), 그것은 rollback이 되돌리는 지점과 같다 (ADR-0047). 따라서
  `git status` = *"마지막 입증 지점 이후 바뀐 것"* 이다.
- **§5의 함정이 우리 쪽에서 더 크다**: checkpoint가 커밋하면 트리가 깨끗해지므로
  그 뒤에 수집하면 **언제나 빈 목록**이다. 수집은 `verify mechanical`에서,
  검증 명령을 돌리기 전에 해야 한다.
- 우리 semantic 평가자는 `workspace`를 받아 **직접 관찰한다** (ADR-0034 정정).
  upstream QA가 목록을 필요로 하는 이유(관찰 불가)가 우리에겐 없다.
