# ADR 0047 — 되돌리기: 마지막 입증 지점에서 다시 시작한다

- Status: **Accepted** (사용자 승인 2026-08-10 — 태그 미도입·upstream 구조 반영)
- Date: 2026-08-09
- Constitutional basis: [ADR-0008](./0008-bounded-recovery.md) (bounded recovery),
  [ADR-0045](./0045-worktree-isolation-contract.md) (미션 전용 worktree),
  [ADR-0046](./0046-verified-checkpoint-commits.md) (입증된 것만 커밋)
- Upstream evidence: [ROLLBACK findings](../research/ROLLBACK_UPSTREAM_FINDINGS.md)
- 해소 대상: [ADR-0032](./0032-recover-deliberate-divergences.md)의 rollback 보류
- 사용자 지시 2026-08-09: **태그 미도입 · upstream 구조 최대한 반영**

## Context

[ADR-0032](./0032-recover-deliberate-divergences.md)는 rollback의 upstream 근거를
`core/worktree.py`로 적어 두었다. **전수 확인 결과 그 파일에는 되돌리기가
없다** — 되돌리기는 두 곳에 나뉘어 있고 성격이 다르다 (findings §0~§2).

| 층 | 무엇을 | 어디 |
|---|---|---|
| lineage rewind | 세대 이력(스펙 계보) | Python Core |
| **파일 되돌리기** | 작업 트리 | **`scripts/ralph.sh`** |

그리고 지금 우리 Recover는 **실패한 시도의 잔해 위에서 재시도한다.** 실패한
worker가 반쯤 만들어 놓은 파일이 그대로 남고, 다음 worker는 그것을 물려받는다.
그 상태에서 또 실패하면 원인이 새 시도의 것인지 이전 찌꺼기인지 구분할 수 없다.

## Decision

### 1. 되돌리기는 **재투입보다 먼저**다

`mcx recover dispatch`는 교정을 내보내기 **전에** 작업 트리를 마지막 입증
지점으로 되돌린다. upstream의 순서와 같다 — 세대 실패 → 직전 성공 세대로 트리
복원 → 다음 세대 (findings §2).

순서를 정하는 자리는 **조율 계층(CLI)** 이다. upstream도 되돌리기를 Core가
아니라 루프 스크립트가 부른다. 그래서 `RecoverService.rewind()`와
`dispatch_correction()`은 별개 단계이며, 둘을 잇는 것은 호출자다.

**대가**: 실패한 시도가 만든 *부분적으로 쓸모 있는* 변경도 사라진다. upstream이
감수하는 대가이고 우리도 감수한다 — 입증되지 않은 것을 남겨 두면 그것이
무엇인지 아무도 모른다.

### 2. 되돌릴 지점은 **태그가 아니라 HEAD**다 (사용자 결정)

우리 미션 브랜치의 커밋은 checkpoint뿐이고, checkpoint는 **입증된 것만**
담는다 (ADR-0046). 따라서 **HEAD가 곧 upstream의 "직전 성공 세대 태그"** 다.

upstream이 태그를 쓰는 이유는 **임의 세대를 지정할 수 있어야 하기 때문**이다 —
rewind가 세대를 고르고, `rollback_to_previous`는 `gen_{N-1}`을 이름으로 찾는다.
**우리 v1에는 세대가 없다.** 지점을 고르는 표면이 없으므로 이름표도 필요 없다.

세대(Evolve)는 Phase 10이다. 그때 지점 선택이 생기면 이름표가 필요해지므로
**§2를 다시 본다** (미결).

### 3. 파괴적 연산을 쓰지 않는다 — upstream 세 걸음 그대로

```sh
git checkout HEAD -- .     # 트리·인덱스를 마지막 입증 지점으로
git reset HEAD             # 인덱스 정리
git clean -fd              # 추적되지 않은 잔해 제거
```

`reset --hard`가 **아니다.** 커밋 이력은 남는다. upstream 전 소스에서 유일한
`reset --hard`는 PM 스냅샷 갱신이며 미션과 무관하다 (findings §3).

`clean`에 **`-x`를 붙이지 않는 것도 upstream과 같다** — `.gitignore`된 것
(가상환경·빌드 산출물·의존성)은 되돌리기의 대상이 아니다. 붙이면 재시도마다
환경을 다시 만들어야 한다.

### 4. **dirty 가드는 옮기지 않는다** — 옮기면 의미가 뒤집힌다

upstream은 rewind의 git 부분에서 `git status --porcelain`을 보고 dirty면
건너뛴다 (findings §4). 그대로 옮기면 **우리 rollback은 영원히 발동하지
않는다** — 실패한 시도 뒤의 worktree는 언제나 dirty이고, 그 dirty가 바로
되돌릴 대상이기 때문이다.

가드가 지키려던 것은 *"사용자의 미커밋 변경을 덮지 않는다"* 이고, 우리는 그것을
**두 겹으로 이미 지킨다**:

- **격리** (ADR-0045) — 되돌리는 곳은 미션 전용 worktree다. 사용자의 checkout이
  아니며, 사용자 코드에 닿는 경로가 구조적으로 없다.
- **checkpoint** (ADR-0046) — 지워지는 것은 **입증되지 않은 변경**뿐이다.
  입증된 것은 이미 커밋돼 있다.

**등록된 divergence**: upstream에 있는 검사를 도입하지 않는다. 근거는 그 검사가
막으려는 상황이 우리 구조에서 발생할 수 없다는 것이며, 두 선행 ADR이 그것을
만든다. **둘 중 하나라도 무너지면 이 divergence의 근거가 사라진다.**

### 5. 입증 지점이 없으면 되돌리지 않는다

upstream: `prev_gen < 1` → *"No previous generation to rollback to"* → 아무것도
하지 않는다. **시작 지점으로는 되돌리지 않는다.**

우리도 같다. 판정은 HEAD 커밋이 **이 미션의 checkpoint인가**로 한다 —
checkpoint가 남기는 `Mission: <mission_id>` trailer를 본다. upstream이 태그
존재로 판정하는 자리이며, 우리는 태그를 두지 않기로 했으므로 커밋 자신이 표식이
된다.

이것이 첫 라운드 실패를 보호한다: 아직 입증된 것이 없으면 되돌려 봐야 미션
시작 상태로 가고, 그것은 *"지금까지 한 일을 전부 버린다"* 이지 *"실패한 시도만
버린다"* 가 아니다.

### 6. 실패해도 미션을 죽이지 않는다

되돌리지 못한 것이 교정 재시도를 막지 않는다. 이유는 결과에 실려 CLI가
표시한다. upstream도 `|| { log WARNING; return 0; }`으로 흘린다 (findings §2).

### 7. 임의 지점으로 가는 명령을 만들지 않는다

upstream에서 자동 되돌리기는 **세대 실패 한 경우뿐**이고, 그 밖의 되돌리기는
사용자가 rewind에서 **세대를 고를 때** 일어난다. 우리에겐 세대가 없으므로
(§2) 고를 것이 없다 — 그래서 `mcx rollback` 같은 명령을 만들지 않는다.

사용자가 직접 되돌리고 싶으면 브랜치가 이미 손 안에 있다 (`mcx status`가 경로와
브랜치를 표시한다, ADR-0045 §5).

### 8. 입증된 AC의 재작업 제외는 **이미 있다**

upstream은 `frozen_ac_indices`로 `authoritative_pass`인 AC를 다음 세대의 작업
집합에서 뺀다 (findings §5). 우리 `derive_failure_packets`는 **실패한 AC에서만**
packet을 만들므로 같은 성질을 **파생으로** 얻는다 — 저장하는 필드가 없다.

ADR-0045 §2·ADR-0046 §5와 같은 판단이다: 유도되는 것을 저장하지 않는다.

## Consequences

### Positive

- 재시도가 **깨끗한 지점에서 출발**한다. 실패 원인이 새 시도의 것인지 이전
  찌꺼기인지 섞이지 않는다.
- `ADR-0031`의 재시도 프롬프트(`previous_failure` + `change_approach`)와 맞물려
  *"같은 지점에서 다른 접근"* 이 문자 그대로 성립한다.
- ADR-0032의 잘못된 근거 포인터가 정정된다.

### Cost

- **실패한 시도의 쓸 만한 부분도 사라진다** (§1). 입증되지 않았으므로 무엇이
  쓸 만한지 우리는 모른다.
- 되돌리기가 조용히 건너뛰어질 수 있다 (§5, §6). 표시가 이 대가를 갚는 유일한
  수단이다.
- **§4의 divergence는 두 ADR에 얹혀 있다.** 격리나 checkpoint가 약해지면
  사용자 코드를 지우는 경로가 열린다.

## Rejected alternatives

- **세대 태그 도입** — 사용자 결정으로 기각 (§2). 지점을 고르는 표면이 없는데
  이름표만 만들면 같은 사실의 두 번째 표현이 된다.
- **`git reset --hard`** — 커밋 이력이 사라진다. upstream도 되돌리기에 쓰지
  않는다 (§3).
- **`git clean -fdx`** — 의존성·빌드 산출물까지 지워 재시도가 비싸진다.
  upstream도 `-x`를 쓰지 않는다.
- **dirty 가드 이식** — 우리 형태에서는 rollback이 영원히 발동하지 않는다 (§4).
- **`dispatch_correction` 안에서 되돌리기** — upstream은 Core가 아니라 루프
  스크립트가 순서를 정한다. 안에 넣으면 되돌리기 실패가 재투입에 얽힌다 (§1).
- **`mcx rollback` 명령 추가** — 고를 지점이 없다 (§7).

## Verification

- `recover dispatch`는 되돌린 **뒤** 교정을 내보낸다.
- 되돌리기는 입증되지 않은 변경만 지운다 — checkpoint된 파일은 그 내용으로
  복원되고, 추적되지 않은 잔해는 사라진다.
- 커밋 이력이 보존된다 (`git log`가 되돌리기 전후로 같다).
- `.gitignore`된 파일은 남는다.
- 스테이징에 남은 잔해도 풀린다.
- 이 미션의 checkpoint가 HEAD가 아니면 되돌리지 않는다 (첫 라운드, 다른 미션의
  커밋).
- git 저장소가 아니면 예외 없이 사유와 함께 건너뛴다.
- 되돌리기 실패가 교정 재시도를 막지 않는다.

## 미결로 남기는 것

- **세대가 생기면 지점 이름이 필요한가** (§2). Phase 10 Evolve에서 세대와
  지점 선택이 들어오면 태그 결정을 다시 본다. **시한 Phase 10 진입 시.**
- **되돌리기가 지운 것을 사용자가 볼 수 없다** — 무엇이 사라졌는지 목록이
  남지 않는다. `changed_files` 수집(ADR-0029)이 그 재료를 만들므로 그 항목과
  함께 본다. **시한 Phase 9 종료 검토.**
- **§4 divergence의 근거 유지 여부** — 격리(ADR-0045)나 checkpoint(ADR-0046)의
  전제가 바뀌면 dirty 가드가 다시 필요해진다. 두 ADR을 고칠 때 이 절을 함께
  본다.
