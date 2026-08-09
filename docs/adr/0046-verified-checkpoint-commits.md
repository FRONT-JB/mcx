# ADR 0046 — checkpoint 커밋: 입증된 것만 고정한다

- Status: **Proposed**
- Date: 2026-08-09
- Constitutional basis: [ADR-0005](./0005-evidence-over-reasoning.md)
  (Evidence over reasoning), [ADR-0045](./0045-worktree-isolation-contract.md)
  (미션 전용 worktree), [ADR-0040](./0040-secret-redaction-boundaries.md)
  (자격증명 경계)
- Upstream evidence: [CHECKPOINT findings](../research/CHECKPOINT_UPSTREAM_FINDINGS.md)
- 해소 대상: Phase 9의 *"AC별 checkpoint 커밋 (upstream `AutoCommitPolicy` 대조)"*

## Context

로드맵 항목의 이름은 *"AC별 checkpoint 커밋"* 이었고, 그 이름대로면 `execute
next` 뒤에 커밋을 붙이는 일이다. **조사에서 전제가 갈라졌다.**

upstream의 호출 지점은 **평가 이후 하나뿐**이며(`evolve_step`), 조건은
`authoritative_pass` — *"통과했고 그 판정이 권위 있다"* 이다 (findings §1).
모듈 docstring도 *"for verified auto acceptance criteria"* 다.

그리고 **"AC별"은 분할이 아니라 라벨이다** (findings §2). upstream은 AC의 파일
목록을 따로 계산하지 않고 그 시점의 작업 트리 변경 전체를 스테이징하므로, 한
라운드에서 AC 셋이 통과하면 첫 AC가 전부 가져가고 나머지는 건너뛴다.

## Decision

### 1. 커밋 시점은 **검증 뒤**다 — 실행 뒤가 아니다

`mcx verify semantic`이 판정을 저장한 **뒤** checkpoint를 남긴다. Execute
경로에는 커밋이 없다.

이것은 우리 표어를 그대로 코드에 놓는 것이다 — *"Executed is not verified."*
검증되지 않은 변경을 커밋하면 **되돌릴 지점으로 믿을 수 없는 체크포인트**가
쌓이고, rollback이 *"어느 커밋이 실제로 동작하는가"* 를 다시 판정해야 한다.

### 2. 무엇이 입증인가는 **Gate와 같은 함수**가 정한다

upstream `authoritative_pass`의 대응물로 `proven_criteria()`를 둔다. 새 판정
규칙을 쓰지 않는다 — Verify Gate의 AC별 판정을 `_criterion_blockers()`로 분리해
**Gate와 checkpoint가 그것 하나를 공유**한다.

```
_criterion_blockers(criterion, evidence, verdicts, policy) -> [blocker]
   ├─ evaluate_verify_gate : 전부 모아 CLEAR/HOLD
   └─ proven_criteria      : blocker가 없는 AC의 key
```

**두 벌로 쓰면 커밋된 것과 Gate가 인정한 것이 갈린다.** 그때 사용자는
"통과했다고 커밋된" 변경을 Gate가 거부하는 상태를 보게 되고, 어느 쪽이 진실인지
알 수 없다. 등가성을 테스트가 고정한다 — `CLEAR ⟺ 전부 입증`.

### 3. 단위는 **검증 라운드 하나**다 — AC별 분할이 아니다

upstream이 실제로 하는 일과 같다 (findings §2). 커밋 하나가 그 라운드에서
입증된 AC들을 **라벨로** 달고, 변경은 라운드 단위로 묶인다.

**우리 형태에서 이 차이가 upstream보다 두드러진다.** upstream은 세대를 돌며
매 세대의 delta를 커밋하지만, 우리는 `execute next`가 AC마다 돌고 `verify`가 한
번에 돈다 — 첫 라운드의 커밋 하나에 전체 AC의 변경이 들어간다. 두 번째 라운드
(Recover 뒤 재검증)부터 증분이 된다.

**AC별로 쪼개지 않는 이유**는 쪼갤 근거가 없기 때문이다. AC와 파일의 대응은
`expected_artifacts`뿐이고 그것은 산출물이지 변경 전체가 아니다. 없는 대응을
추측으로 만들면 *"AC-2의 커밋"* 이 실제로는 AC-2와 무관한 파일을 담는다.

**등록된 divergence**: 항목 이름이 *"AC별"* 이었으나 실제 단위는 라운드다.
upstream도 같으므로 upstream과의 차이는 아니고, **로드맵 이름의 정정**이다.

### 4. 비밀 경로는 스테이징에서 뺀다

upstream 정규식을 그대로 쓴다 — `.env`, `*secret*`, `*credential*`.

[ADR-0040](./0040-secret-redaction-boundaries.md)은 **내용**의 자격증명을 다루고
이것은 **경로**의 축이다. 새 축이므로 여기 명시한다.

- 걸러낸 뒤 남은 경로가 없으면 커밋하지 않는다.
- 커밋은 `git commit -- <safe_paths>`로 **경로를 명시**한다. `git commit -a`가
  아니므로 걸러낸 파일이 우연히 실려 가지 않는다.
- 제외된 파일은 결과에 남아 사용자에게 보인다 — 조용히 빠지지 않는다.

### 5. 멱등성은 **git에서 나온다** — 상태를 만들지 않는다

upstream은 `checkpoint_commits`와 `checkpoint_attempted_ac_ids`를 세션 상태에
쌓는다 (findings §4). 우리는 하지 않는다.

커밋하고 나면 작업 트리가 깨끗하므로 **다시 불러도 `바뀐 파일이 없다`로 끝난다.**
upstream이 목록으로 얻는 성질을 우리는 git의 상태에서 얻는다. ADR-0045 §2와 같은
판단이다 — 유도되는 것을 저장하지 않는다.

**대신 upstream의 한 성질을 잃는다**: upstream은 커밋에 *실패한* AC를 기억해
다시 시도하지 않는다. 우리는 다음 `verify semantic`에서 다시 시도한다. 실패가
사용자에게 보이고 재시도가 값싸므로(git 호출 몇 번) 기억할 이유가 없다고
판단했다. **등록된 divergence.**

### 6. 실패는 미션을 죽이지 않는다

커밋을 남기지 못한 것이 검증 결과를 무효로 만들지 않는다. 그래서 checkpoint는
**저장 경로와 분리된 별도 단계**다 (`VerifyService.checkpoint`) — `verify
semantic`의 저장이 끝난 뒤에 불린다.

건너뛴 이유는 결과에 실려 CLI가 표시한다. *"커밋됐겠지"* 로 읽고 지나가면
되돌릴 지점이 없다는 것을 되돌려야 할 때 알게 된다.

### 7. 정책 스위치를 만들지 않는다

upstream은 셋을 가졌다 — `ac_checkpoint` · `final_only` · `none`. 기본값이
coding에서만 `ac_checkpoint`이고 그 외에는 `none`인데, 그 이유가 주석에 있다:

> *"never auto-commit or relocate the caller's checkout by default … rather than
> a silent side effect."*

**그 위험이 우리에겐 없다.** ADR-0045로 우리는 **항상** 미션 전용 worktree에서
실행하므로, 커밋은 언제나 우리 브랜치에 간다 — 사용자의 checkout에 커밋하는
코드 경로가 존재하지 않는다. 즉 upstream이 `none` 기본값으로 막는 것을 우리는
구조로 막았고, 남은 것은 켤지 말지가 아니라 **켜져 있는 것뿐**이다.

git 저장소가 아니면 격리도 커밋도 일어나지 않는다 (ADR-0045 §4와 같은 규칙).

## Consequences

### Positive

- **rollback 범위(ADR-0032)의 답이 따라 나온다** — 입증된 AC가 이미 커밋돼
  있으므로, 실패한 것을 되돌릴 때 통과한 작업을 건드리지 않는다.
- **`changed_files` 수집(ADR-0029)의 기준점이 정해진다** — 마지막 checkpoint가
  비교 대상이다.
- 커밋 히스토리가 곧 *"증거가 지지한 진행"* 의 기록이 된다. `MISSION COMPLETE`가
  아니라도 어디까지 믿을 수 있는지가 브랜치에 남는다.

### Cost

- **첫 라운드의 커밋 하나가 굵다** (§3). AC별 되돌리기는 두 번째 라운드부터
  의미를 갖는다.
- 커밋에 실패해도 미션은 계속 간다 — 되돌릴 지점 없이 진행할 수 있다는 뜻이다.
  표시가 이 대가를 갚는 유일한 수단이다 (§6).
- 비밀 경로 정규식은 이름 기반이라 완전하지 않다. `config.yaml`에 든 토큰은
  걸러지지 않는다 — 그 축은 ADR-0040의 내용 경계가 담당한다.

## Rejected alternatives

- **Execute 뒤에 AC별로 커밋** — 로드맵 이름이 그렇게 읽히지만 upstream은
  하지 않으며, 검증 안 된 커밋은 되돌릴 지점이 될 수 없다 (§1).
- **AC별로 파일을 나눠 커밋** — AC↔파일 대응이 `expected_artifacts`뿐이라
  추측이 된다 (§3).
- **checkpoint를 `assess_semantics` 안에 넣기** — 커밋 실패가 판정 저장에
  얽힌다. upstream도 평가 이후의 별도 단계로 둔다 (§6).
- **`proven_criteria`를 새로 판정** — Gate와 갈릴 자리를 만든다 (§2).
- **정책 셋(`ac_checkpoint`/`final_only`/`none`)을 그대로 도입** — 그 정책이
  막는 위험(사용자 checkout 오염)을 ADR-0045가 구조로 이미 막았다 (§7).

## Verification

- `verify semantic` 뒤에만 커밋이 생긴다. `execute next`는 커밋을 만들지 않는다.
- 커밋되는 AC 집합은 Gate가 막지 않는 AC 집합과 **같다** (`CLEAR ⟺ 전부 입증`).
- 실패한 AC는 커밋 라벨에 없고, 같은 라운드의 통과한 AC는 있다.
- 비밀 경로 파일은 커밋에도 스테이징에도 남지 않는다. 변경이 전부 비밀 경로면
  커밋 자체가 없다.
- 두 번 연속 실행해도 빈 커밋이 생기지 않는다.
- git 저장소가 아니면 예외 없이 사유와 함께 건너뛴다.
- 커밋 제목은 72자 이내이고, 본문에 mission·Blueprint revision·AC가 남는다.

## 미결로 남기는 것

- **첫 라운드 커밋의 굵기** (§3의 Cost). 실사용에서 이것이 rollback을 무용하게
  만드는지는 관측이 있어야 안다. 답이 필요해지면 후보는 *"AC별 파일 분할"* 이
  아니라 **Execute 중 임시 커밋 후 검증 시 squash**일 수 있다.
  **시한 Phase 9 종료 검토.**
- **실패한 checkpoint의 재시도** (§5의 divergence). upstream은 기억하고 우리는
  다시 시도한다. 재시도가 매번 실패하는 상황(권한 없는 저장소 등)이 관측되면
  재고한다. **시한 Phase 9 종료 검토.**
