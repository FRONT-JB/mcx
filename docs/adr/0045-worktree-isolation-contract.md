# ADR 0045 — worktree 격리 계약: 미션은 사용자의 checkout을 건드리지 않는다

- Status: **Accepted** (사용자 승인 2026-08-09 — 우회 플래그 없음 · 항상 격리 ·
  `mcx cleanup` 도입 · 자동 병합 미도입)
- Date: 2026-08-09
- Constitutional basis: [ADR-0004](./0004-stage-capability-boundaries.md)
  (Stage별 최소 capability), [ADR-0024](./0024-execute-v1-dispatch-contract.md) §6
  (`CapabilityEnvelope`), [ADR-0033](./0033-first-runtime-adapter-contract.md) §4
  (sandbox 경계)
- Upstream evidence: [WORKTREE findings](../research/WORKTREE_UPSTREAM_FINDINGS.md)
- 해소 대상: Phase 9의 *"worktree 격리 (upstream `core/worktree.py` 대조)"*
- 선행: [ADR-0029](./0029-verify-deliberate-divergences.md) `changed_files`,
  [ADR-0032](./0032-recover-deliberate-divergences.md) rollback, Phase 9의
  AC별 checkpoint 커밋 — 셋 다 **git 경계가 우리 것일 때만** 성립한다

## Context

지금 Execute는 사용자가 `--workspace`로 준 디렉토리에서 곧바로 `codex exec`를
돌린다. `CapabilityEnvelope.workspace`가 그대로 `-C`로 간다. 즉 **에이전트의
파일 변경이 사용자의 작업 사본에 직접 쌓인다.**

이것이 지금 당장 만드는 문제는 하나다 — 실패한 미션의 잔해가 사용자 코드에
남고, 되돌리는 수단이 `git checkout .`뿐이며 그것은 사용자 자신의 작업까지
지운다.

그리고 **Phase 9의 나머지 항목 셋이 전부 이것에 걸려 있다.** AC별 checkpoint
커밋은 커밋할 브랜치가 필요하고, rollback은 되돌릴 범위가 필요하고,
`changed_files` 수집은 *"무엇과 비교한 변경인가"* 의 기준점이 필요하다. 사용자의
브랜치에 checkpoint를 쌓으면 사용자의 히스토리를 오염시키고, 사용자의 커밋과
우리 커밋을 구분할 수 없어 rollback 범위가 정의되지 않는다.

**ADR-0044 §1과 같은 형태의 순서 제약이다** — 자리가 비어 있어 나중에 해도 될
것처럼 보이지만, 순서를 어기면 뒤의 셋이 각자 다른 기준점을 발명한다.

## Decision

### 1. 격리 단위는 **미션 하나**다 — AC가 아니다

upstream은 세션 하나에 worktree 하나이며, **병렬 AC 실행기가 있는데도 AC마다
만들지 않는다** (findings §1). 우리 mission이 그 세션의 대응물이다.

```
branch : mcx/<mission_id>
path   : <state-dir>/worktrees/<repo_name>/<mission_id>
```

브랜치 접두사만 upstream(`ooo/`)에서 우리 이름으로 바꾼다. 루트는 upstream이
`~/.ouroboros/worktrees` 고정 config인 자리를 **`--state-dir` 아래**로 옮긴다 —
우리에겐 이미 상태 루트가 하나 있고 (ADR-0038 §6), 별도 config 키를 만들 이유가
없다. 기본값은 `~/.mcx/worktrees/...`로 upstream과 같은 자리에 떨어진다.

브랜치 이름은 `git check-ref-format --branch`로 검증한다 — mission id가 git ref로
성립하지 않으면 오류다 (upstream `_managed_branch_name` 채택).

### 2. 경로는 **저장하지 않고 유도한다** — upstream보다 작은 구조

upstream은 `TaskWorkspace`(8필드)를 세션 progress에 직렬화하고 resume 때 복원한다.
우리는 하지 않는다. 경로가 `(state-dir, mission의 workspace, mission_id)`에서
**결정적으로 유도되기 때문**이다:

```
repo_root       = git rev-parse --show-toplevel  (mission workspace 기준)
worktree_path   = <state-dir>/worktrees/<repo_root.name>/<mission_id>
effective_cwd   = worktree_path / (mission workspace의 repo 내 상대 경로)
```

셋 다 이미 우리 손에 있는 값이다. upstream이 저장해야 하는 이유는 **worktree
루트가 config로 바뀔 수 있고, run이 하나의 긴 프로세스라 재개 지점을 복원해야
하기 때문**이다. 우리는 명령마다 새 프로세스이고 루트가 `--state-dir`에 묶여
있으므로, 매번 같은 값을 다시 계산한다. `--state-dir`가 바뀌면 상태 전체가
없어지므로 worktree만 따로 어긋나는 경우가 없다.

**역사적 기록은 이미 있다.** 각 `ExecutionAttempt`가 자기 `envelope.workspace`를
들고 있으므로 *"이 시도가 어디서 돌았는가"* 는 기록에 남는다 (ADR-0023 §3).
새 필드도, 새 파일도 추가하지 않는다.

> 이것은 **저장 방식**에 관한 되돌리기 비싼 결정이다 (AGENTS.md). upstream 대조
> 결과 *저장하지 않음*이 우리 구조에서 같은 성질을 준다고 판단했고, 근거를 이
> 절에 남긴다.

### 3. 진입 전제: **원본 checkout이 깨끗해야 한다**

worktree는 HEAD에서 분기하므로 커밋되지 않은 변경은 worktree에 들어가지 않는다.
그대로 진행하면 에이전트가 **사용자가 보는 것과 다른 트리**에서 일한다
(findings §2).

따라서 worktree를 새로 만들 때 `git status --porcelain`이 비어 있지 않으면
거부하고, 오류 메시지가 해결 방법을 직접 준다. **이미 있는 worktree를 재사용할
때는 검사하지 않는다** — upstream도 `prepare`에만 있고 `restore`에는 없다.

`--allow-dirty` 같은 우회 플래그는 만들지 않는다 (**사용자 결정 2026-08-09 —
거부**). upstream의 `allow_dirty=True` 호출자는 Auto와 resume이며 우리에겐 둘 다
없다 (resume은 Phase 9 미도입). 우회를 주면 *"AI가 내가 방금 쓴 코드를 못 본다"*
는 상황이 조용히 허용되고, 그 결과는 나중에 병합 충돌로만 드러난다.

빈 저장소도 거부한다 — 분기할 HEAD가 없다.

### 4. git 저장소가 아니면 **격리하지 않고 그대로 간다**

upstream `maybe_prepare_task_workspace`와 같다 — git 저장소가 아니면 `None`이고
호출자는 원래 디렉토리를 쓴다.

**켜고 끄는 설정 키는 만들지 않는다** (사용자 결정 2026-08-09 — 무조건 격리).
upstream에는 `use_worktrees`가 있지만 우리 `config.toml`은 라우팅만 받으며
(ADR-0039 §5), 격리 여부는 설정이 아니라 **사실에 대한 반응**이다. 스위치를 두면
같은 명령이 같은 저장소에서 다르게 동작하고, 사용자는 어느 쪽이었는지를 결과를
보고 역추적해야 한다.

### 5. 되돌려 합치지 않는다 — 대신 **어디에 있는지 반드시 보인다**

upstream에는 병합·PR 경로가 없다 (findings §4). 브랜치가 산출물이고 병합은
사용자의 결정이다. 우리도 같다.

**그래서 표시가 계약의 일부다.** 격리가 켜지면 사용자의 checkout에는 아무 일도
일어나지 않으므로, 어디서 일어났는지 보이지 않으면 *"아무것도 안 했다"* 로
읽힌다. 다음 둘을 강제한다:

- `mcx execute next`가 격리를 처음 켤 때 worktree 경로와 브랜치를 출력한다
  (upstream `run.py`가 같은 자리에서 같은 두 줄을 낸다)
- `mcx status`가 mission의 worktree 경로와 브랜치를 표시한다 — upstream에는
  대응물이 없다(그쪽은 한 프로세스가 계속 떠 있어 시작 시 출력이면 충분하다).
  우리는 명령마다 프로세스가 끝나므로 **조회 지점이 있어야 한다**

### 6. 동시 실행은 lock으로 막는다 — 축소해서

`mcx execute next`를 같은 mission으로 두 번 동시에 돌리면 두 codex 프로세스가
같은 worktree를 쓴다. git은 이것을 막지 않고, `ExecuteState`의 낙관적 동시성은
**codex가 이미 파일을 바꾼 뒤에** 걸린다. 조용한 손상 경로다.

upstream의 lock에서 **받는 것**: 파일 하나에 `pid`·`host`를 적고, 같은 호스트면
pid 생존으로 stale을 판정한다. `PermissionError`는 살아 있음으로 본다. 남의
lock은 갱신하지도 해제하지도 않는다.

**버리는 것**: heartbeat와 시간 기반 staleness. upstream이 시간을 쓰는 자리는
**다른 호스트라 pid를 볼 수 없을 때**이고, 우리는 그 경우 stale로 판정하지 않고
**거부한다** — 임계값을 잘못 잡으면 살아 있는 실행의 worktree를 조용히 빼앗지만,
거부는 사용자가 lock 파일 경로를 보고 지우면 풀린다. 되돌릴 수 있는 쪽을 고른다.
heartbeat는 시간 판정을 버렸으므로 필요가 없다.

### 7. 정리는 **별도 명령** `mcx cleanup`이다 — 자동으로 지우지 않는다

> **개정 2026-08-09 (사용자 결정).** 초안은 *"아무것도 지우지 않는다"* 였고,
> 근거는 관측 부재였다. 사용자가 정리 도입을 결정했으므로 뒤집는다. 다만
> **자동 병합은 도입하지 않는다** — 그 결정도 같은 자리에서 내려졌고, §5의
> *"되돌려 합치지 않는다"* 는 그대로다.

upstream `ouroboros cleanup`과 같은 형태다. 자동 병합이 없으므로 이 명령은
**사용자가 병합한 뒤** 부르는 GC다 — 병합하지 않은 것은 남는다.

```sh
mcx cleanup             # 병합됐고 깨끗한 것만 치운다
mcx cleanup --dry-run   # 무엇이 지워질지만 보인다
mcx cleanup --force     # 병합되지 않은 것도 치우되 브랜치는 남긴다
```

**세 가지를 절대 건드리지 않는다:**

| 남기는 이유 | 판정 |
|---|---|
| `running` | lock의 소유자가 살아 있다 (§6과 같은 판정) |
| `dirty` | worktree에 커밋되지 않은 변경이 있다 — `--force`도 풀지 못한다 |
| `unmerged` | 브랜치가 HEAD에 들어가 있지 않다 — `--force`만 이것을 푼다 |

`--force`가 푸는 것은 마지막 하나뿐이고, **그때도 브랜치는 지우지 않는다.**
작업이 사라지지 않는다는 뜻이다 (upstream `--force`와 같은 의미). 브랜치 삭제는
언제나 `git branch -d`(안전 삭제)이며 `-D`로 가는 코드 경로가 없다.

worktree가 사라졌는데 남은 lock 파일도 같이 치운다. 살아 있는 lock은 남긴다.

**upstream보다 좁힌 것 하나**: upstream은 등록되지 않은 남은 디렉토리를
`shutil.rmtree`한다 (`_repair_managed_path`). 우리는 **거부한다** — 우리가 만든
것이 맞는지 확인할 수 없는 디렉토리를 지우지 않는다. 거부는 사용자가 되돌릴 수
있다.

**MCP 표면에는 올리지 않는다.** upstream도 `ouroboros_cleanup` tool이 없다
(findings §5). 우리 쪽 근거는 더 구조적이다 — 이 표면의 모든 tool은 `mission`을
필수로 받는데(서버가 현재 mission을 기억하지 않으므로, ADR-0041 §3) `cleanup`은
mission에 속하지 않는 운용 명령이라 그 계약에 자리가 없다. **ADR-0041 §1의
1:1 규칙에 대한 유일한 예외이며, 예외가 하나임을 테스트가 고정한다.**

같은 이유로 명령 원장에도 기록하지 않는다 — `status`와 같은 취급이다.

## Consequences

### Positive

- 실패한 미션이 사용자 코드에 잔해를 남기지 않는다. 되돌리기가
  *"브랜치를 안 쓴다"* 로 끝난다.
- Phase 9 나머지 셋(checkpoint 커밋·rollback 범위·`changed_files`)이 **같은
  기준점** 위에 놓인다. 각자 발명하지 않는다.
- Verify가 자동으로 따라온다 — `verify_service`가 이미
  `attempts[-1].envelope.workspace`를 읽으므로(findings 말미) 배선이 한 곳이다.
  upstream이 `verification_working_dir`로 명시하는 것을 우리는 기록된 envelope로
  얻는다.

### Cost

- **사용자의 checkout이 깨끗해야 Execute가 시작된다.** 실사용에서 가장 자주
  부딪힐 마찰이며, 우회 플래그를 두지 않았으므로 커밋 아니면 stash다.
- 미션 결과가 사용자 눈앞에 없다. §5의 표시가 이 대가를 갚는 유일한 수단이다.
- **병합하지 않은 미션의 worktree는 계속 쌓인다.** `mcx cleanup`이 치우는 것은
  사용자가 이미 병합한 것뿐이고, 실패해서 버린 미션은 `--force`를 눌러야 사라진다
  (§7). 자동 병합이 없는 이상 이 대가는 남는다.
- git 저장소 여부에 따라 동작이 갈린다 — 같은 명령이 어떤 workspace에서는
  격리되고 어떤 곳에서는 안 된다. 표시로만 구분된다.

## Rejected alternatives

- **AC마다 worktree** — upstream은 병렬 실행기를 가지고도 하지 않는다. AC 간
  변경이 서로 보이지 않으면 뒤 AC가 앞 AC의 결과 위에 쌓을 수 없다.
- **`TaskWorkspace`를 mission record에 저장** — 유도 가능한 값을 저장하면 두
  진실의 원천이 생기고, 저장 스키마 변경은 되돌리기 비싼 축이다 (§2).
- **격리 on/off 설정 키** — upstream의 `use_worktrees`는 config 계층이 이미 큰
  쪽의 습관이다. 우리 `config.toml`은 라우팅만 받는다 (ADR-0039 §5). git 저장소가
  아니라는 **사실**에 반응하는 것으로 충분하다 (§4).
- **완료 시 자동 병합** — **사용자 결정으로 기각 (2026-08-09).** upstream에
  대응물이 없고, `MISSION COMPLETE`는 Verify Gate의 판정이지 사용자의 수용이
  아니다 (ADR-0042 §5 User Adoption Gate는 skill 소유). 자동 병합은 그 경계를
  넘는다.
- **정리를 하지 않고 사용자에게 git 명령을 안내** — 초안의 결정이었고 사용자
  결정으로 뒤집혔다 (§7). 안내는 명령이 아니라 문서였으므로 실사용에서 잔여물이
  쌓이는 것을 막지 못한다.
- **정리를 실행 경로에 붙이기** (미션 완료 시 자동 제거) — 병합이 없으므로
  완료 시점에 제거 가능한 것이 없다. 그리고 파괴적 행위를 사용자가 부르지 않은
  자리에 두게 된다.

## Verification

- worktree가 없으면 만들고, 있으면 재사용한다 (같은 mission을 두 번 dispatch해도
  worktree가 하나다).
- dirty checkout에서 **새로** 만들려 하면 거부한다. 이미 있으면 거부하지 않는다.
- git 저장소가 아닌 workspace는 격리 없이 원래 경로로 실행한다.
- 실행에 쓰인 경로가 `ExecutionAttempt.envelope.workspace`에 남고, Verify가 같은
  경로에서 명령을 돈다.
- 하위 디렉토리를 workspace로 준 미션은 worktree의 **같은 상대 경로**에서 돈다.
- 살아 있는 lock 위에서 두 번째 dispatch는 실행 전에 거부된다.
- `mcx cleanup`은 병합됐고 깨끗한 worktree만 제거하며, 브랜치는 병합됐을 때만
  지운다. `running`·`dirty`는 `--force`로도 제거되지 않고, `--force`가 제거한
  `unmerged` worktree의 브랜치는 남는다.
- `mcx cleanup`은 mission 없이 실행되고 명령 원장을 늘리지 않는다.
- `cleanup`은 MCP tool 목록에 없으며, 1:1 규칙의 예외가 그것 하나임을 테스트가
  고정한다.
- `--state-dir`가 대상 저장소 **안**이면 거부한다 — worktree가 저장소 내부에
  생기면 그 저장소가 영구히 dirty가 되어 §3이 이후 모든 미션을 막는다.
  (upstream 대응물 없음: upstream에는 `--state-dir`가 없어 발생하지 않는다.)

## 미결로 남기는 것

- ~~**정리 정책**~~ → **해소 (2026-08-09 사용자 결정).** `mcx cleanup` 도입,
  자동 병합은 미도입 (§7).
- **버려진 미션의 잔여물** — 자동 병합이 없으므로 실패한 미션의 worktree는
  사용자가 `--force`를 부를 때까지 남는다 (Cost). 이것이 실사용에서 실제로
  방해가 되는지, 된다면 미션 실패 시점에 무엇을 물어야 하는지는 관측이 있어야
  한다. → **닫음** ([Phase 9 종료 검토](../progress/0009_RECOVERY_LAYERS.md) §3-3, 2026-08-10). 완주 미션의 worktree 52K가 남았고
  방해가 관측되지 않았다. `mcx cleanup`이 이미 답이며 그 계약("작업이 사라지지
  않는다")이 자동 삭제보다 낫다. **발동 조건**: 미션 수가 늘어 사용자가 정리를
  잊는 것이 관측되면 미션 실패 시점의 안내를 본다.
- **Auto가 run보다 덜 격리하는 이유** — upstream에서 전체 파이프라인의 기본은
  사용자 checkout이고 단발 실행의 기본은 격리다 (findings §8). 소스로는 이유를
  알 수 없어 `upstream 미확인`이다. **우리는 항상 격리로 확정했고**(사용자 결정
  2026-08-09) 이것이 upstream Auto의 반대편이라는 사실은 남는다 — 실사용에서
  마찰이 관측되면 그때 이 미확인을 먼저 푼다. → **닫음** ([Phase 9 종료 검토](../progress/0009_RECOVERY_LAYERS.md) §3-4, 2026-08-10):
  미션 2회에서 마찰 0회이므로 미확인을 풀 필요가 없다. `upstream 미확인` 표시는
  그대로 남는다.
- **깨끗한 checkout 요구의 마찰** — 우회 플래그를 두지 않기로 확정했으므로
  (§3, 사용자 결정) 사용자는 매번 커밋하거나 stash한다. 이것이 실사용에서
  얼마나 자주 걸리는지는 관측 대상이며, 잦다면 답은 플래그가 아니라 **명령이
  stash를 제안하는 것**일 수 있다. → **닫음** ([Phase 9 종료 검토](../progress/0009_RECOVERY_LAYERS.md) §3-5, 2026-08-10): 미션 2회
  모두 걸리지 않았다. **다만 둘 다 새로 만든 저장소에서 시작했으므로 표본이
  실사용을 대표하지 않는다** — 그 한계를 적고 닫는다. **발동 조건**: 기존
  저장소에서 시작할 때 걸리면 그때 stash 제안을 본다.
- **resume과의 관계** — [ADR-0033](./0033-first-runtime-adapter-contract.md) §6
  resume이 Phase 9로 재지정돼 있고, upstream은 저장된 workspace를 resume의
  권위로 삼는다 (findings §9). 우리는 유도하므로 같은 값이 나오지만, resume을
  도입할 때 §2의 판단을 다시 본다.
