# upstream worktree 격리 조사 — `core/worktree.py`

- 조사일: 2026-08-09
- Baseline: `~/.claude/plugins/marketplaces/ouroboros` @ `9486c78` (v0.50.8)
- Evidence level: **source-read** (실행 관측 아님). 실행으로만 알 수 있는 항목은
  그 자리에 표시했다.
- 소비처: [ADR-0045](../adr/0045-worktree-isolation-contract.md)

파일: `src/ouroboros/core/worktree.py` (755줄), `src/ouroboros/auto/worktree.py` (70줄).
docstring: *"Backend-agnostic git worktree management for mutating task workflows."*

---

## 1. 격리의 단위는 AC가 아니라 세션이다

worktree 하나는 **durable task 하나**에 대응하며, `durable_id`는 실제로 세션
식별자다 — `ooo run`은 `orch_<hex12>`, Auto는 `auto_<...>`를 넘긴다
(`cli/commands/run.py:704`, `auto/worktree.py:39`).

```
branch : ooo/<durable_id>
path   : <worktree_root>/<repo_name>/<durable_id>
lock   : <worktree_root>/.locks/<repo_name>/<durable_id>.json
```

`worktree_root` 기본값은 `~/.ouroboros/worktrees`이고 config로 바뀐다
(`OrchestratorConfig.worktree_root`). **AC마다 worktree를 만들지 않는다** —
병렬 AC 실행기가 있는데도 그렇다. 즉 격리 경계는 *"한 번의 미션 실행"* 이지
*"한 번의 작업 단위"* 가 아니다.

branch 이름은 `git check-ref-format --branch`로 검증한다 — `durable_id`가
git ref로 성립하지 않으면 `WorktreeError`다 (`_managed_branch_name`).

## 2. 진입 전제: 원본 checkout이 깨끗해야 한다

`prepare_task_workspace(..., allow_dirty=False)`가 기본이고,
`_ensure_clean_checkout`이 `git status --porcelain` 출력이 비어 있지 않으면
거부한다 — *"Cannot start task worktree from a dirty checkout"*.

**이유는 코드에 적혀 있지 않지만 구조가 말한다**: worktree는 HEAD에서
분기하므로, 사용자의 커밋되지 않은 변경은 worktree에 **들어가지 않는다**.
그대로 진행하면 에이전트가 사용자가 보는 것과 다른 트리에서 일하게 된다.

호출자별로 다르다:

| 호출자 | `allow_dirty` | 근거 |
|---|---|---|
| `ooo run` | `False` | `cli/commands/run.py:705` |
| Auto | `True` | `auto/worktree.py:43` |
| `execute_seed` (MCP) | 상속된 runtime handle이 있을 때만 `True` | `execution_handlers.py:1552` |

빈 저장소도 거부하며, 오류 메시지가 해결책을 직접 준다 —
*"Create an initial commit first (for example: `git commit --allow-empty -m ...`)"*.

## 3. 하위 디렉토리에서 불러도 상대 위치가 보존된다

```python
effective_cwd = worktree_path / _relative_subdir(repo_root, source_path)
```

`repo/packages/api`에서 실행하면 worktree의 같은 상대 경로로 들어간다.
저장소 루트로 끌어올리지 않는다. `source_path`가 repo 밖이면 `WorktreeError`다.

`TaskWorkspace`는 `original_cwd`(사용자가 부른 자리)와 `effective_cwd`(실제 작업
자리)를 **둘 다** 들고 있다 — 하나를 다른 하나로 덮어쓰지 않는다.

## 4. 되돌려 합치지 않는다

전 소스에서 `git merge`·PR 생성 경로가 **없다**. worktree의 `ooo/<id>` 브랜치가
산출물이고, 병합은 사용자의 몫이다. `ooo run`은 시작할 때 경로와 브랜치를
출력할 뿐이다 (`run.py:711`).

즉 upstream의 worktree는 *"작업을 격리해 두고 사람에게 넘긴다"* 이지
*"작업을 격리해 검증 후 자동 반영한다"* 가 아니다.

## 5. 정리(cleanup)는 실행 경로와 분리된 보수적 행위다

정책은 셋이다 (`OrchestratorConfig.worktree_cleanup`, 기본 `prune-merged`):

| 정책 | 동작 |
|---|---|
| `keep` | 아무것도 지우지 않는다 |
| `remove` | 깨끗한 worktree를 제거하고, 브랜치는 병합됐을 때만 삭제 |
| `prune-merged` (기본) | 브랜치가 병합됐고 checkout이 깨끗할 때만 제거 |

**설정 로드 실패 시 기본값을 상속하지 않는다.** 주석이 그 이유를 직접 적는다:

> *"Cleanup is destructive, so configuration failures must not inherit the model
> default. Other worktree settings can safely use `_orchestrator_config`'s
> defaults, but cleanup requires a positively loaded and validated operator
> policy."*

→ 실패하면 `"keep"`이다 (`_worktree_cleanup_policy`). 다른 worktree 설정은
`OrchestratorConfig()` 기본값으로 조용히 넘어가지만 정리만 다르게 취급한다.

같은 조심성이 호출 규약에도 있다. `release_task_workspace`의 docstring:

> *"Callers must positively establish that no delegated or resumable work is
> still using the workspace before passing `cleanup=True`."*

브랜치 삭제는 언제나 `git branch -d`(안전 삭제)이며 `-D`는 없다. dirty checkout은
어떤 정책에서도 제거하지 않는다.

별도 CLI 명령 `ouroboros cleanup`이 남은 잔여물을 GC한다 — 살아 있는 lock을 가진
worktree는 건드리지 않고, `auto_*` durable_id만 대상으로 하며, `--dry-run`이 있다.

## 6. lock은 디렉토리가 아니라 *소유권*을 지킨다

lock 파일에 `pid`·`host`·`created_at`·`updated_at`을 담는다. 살아 있는 lock 위에
다시 잡으려 하면 `"Task already active"`다.

staleness 판정이 두 갈래다 (`_is_lock_stale`):

- **같은 호스트**면 pid 생존으로 판정한다 (`os.kill(pid, 0)`).
  `PermissionError`는 *"살아 있음"* 이다 — 프로세스는 있는데 신호 권한이 없는
  경우다.
- **다른 호스트**면 판정할 수 없으므로 시간으로 넘어간다 —
  `worktree_lock_stale_after_minutes` (기본 60) 초과면 stale.

장기 실행 중에는 `heartbeat_lock`이 `updated_at`을 갱신하며, 자기 pid·host가
아닌 lock은 갱신하지 않는다. 해제도 같다 — 남의 lock은 지우지 않는다.
파일 자체의 원자성은 `core/file_lock.py`가 따로 맡는다.

## 7. worktree는 증거의 앵커이기도 하다

격리 이상의 역할이 둘 있다.

- `orchestrator/evidence/claims.py`가 `task_cwd`(worktree 루트)와
  `effective_cwd`를 받아 에이전트가 주장한 파일 경로를 실물 `st_dev`/`st_ino`와
  대조한다 — 실행 시점에 기록된 파일 정체성이 지금 파일과 같은지 확인한다.
- `orchestrator/session.py::_resolve_managed_publication_identity`가
  `Path(project_workspace).samefile(task_workspace.effective_cwd)`로
  *"발행 직전에 작업 디렉토리가 바뀌지 않았음"* 을 증명한다. 다르면
  `"managed execution workspace changed before publication"`이다.

즉 `TaskWorkspace`는 실행 편의 객체가 아니라 **증거 계층이 참조하는 고정점**이다.

## 8. 기본값이 진입점마다 반대다

| 진입점 | 기본 | 근거 |
|---|---|---|
| `ooo run` | **격리** (`use_worktrees=True`) | `config/models.py:685` |
| `ouroboros_execute_seed` (MCP) | **격리** (`use_worktree` 기본 `True`) | `execution_handlers.py:1442` |
| Auto | **사용자 checkout** (`AutoWorktreePolicy.CURRENT`) | `auto/state.py:579` |

Auto의 `AUTO` 정책은 *coding 도메인 프로파일일 때만* 격리한다
(`auto/worktree.py:23-28`) — docstring이 *"AUTO is intentionally coding-only"*.
`ALWAYS`인데 git 저장소가 아니면 오류이고, `AUTO`면 조용히 격리를 포기한다.

**왜 전체 파이프라인(Auto)이 단발 실행(run)보다 덜 격리하는지는 소스로 알 수
없다.** `upstream 미확인`으로 남긴다.

## 9. resume은 저장된 workspace가 권위다

세션 progress에 `TaskWorkspace.to_progress_dict()`가 실린다. 재개 시
`restore_task_workspace`가 그것을 복원하고 lock을 **다시 잡는다**.
`execution_handlers.py:1509-1517`의 주석이 함정을 적어 둔다:

> *"A persisted task workspace is authoritative for resume, even when the caller
> omits `use_worktree`. That flag controls provisioning of a *new* workspace; it
> must not bypass reacquisition of the lock for a retained runner."*

디스크에서 worktree가 사라졌으면 브랜치로부터 다시 만든다.

## 10. 고아 복구가 있다

- `_repair_managed_path` — 경로는 있는데 `git worktree list`에 없으면 남은
  디렉토리를 지우고 다시 만든다.
- `discover_managed_workspaces` — worktree 루트를 훑어 `TaskWorkspace`를
  재구성한다. 부모 저장소가 사라진 것은 건너뛴다.
- 브랜치가 **다른** worktree에 이미 checkout돼 있으면 오류다 —
  *"Task branch already checked out in another worktree"*.

---

## 우리 쪽 대응 지점 (조사 시점의 사실)

- `CapabilityEnvelope.workspace`가 실행 경계이고 `codex exec -C <workspace>`로
  간다 (`adapters/runtime/codex_execution_runtime.py:148`).
- **Verify는 Execute가 쓴 workspace를 따라간다** —
  `verify_service.py:103`이 `execute_state.attempts[-1].envelope.workspace`를
  읽는다. 따라서 envelope의 workspace가 worktree를 가리키면 검증도 같은 트리에서
  돈다. upstream이 `verification_working_dir = workspace.effective_cwd`로 명시하는
  것을 우리는 기록된 envelope로 얻는다.
- worktree 관련 코드는 현재 **없다**. mission record의 `workspace`가 그대로
  실행 경계다.
