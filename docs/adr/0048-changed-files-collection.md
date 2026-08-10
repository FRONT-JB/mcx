# ADR 0048 — `changed_files` 수집: 마지막 입증 지점 이후 무엇을 손댔는가

- Status: **Accepted** (사용자 승인 2026-08-10)
- Date: 2026-08-09
- Constitutional basis: [ADR-0005](./0005-evidence-over-reasoning.md),
  [ADR-0028](./0028-verify-v1-mechanical-contract.md) §4 (증거 필드)
- Upstream evidence: [CHANGED_FILES findings](../research/CHANGED_FILES_UPSTREAM_FINDINGS.md)
- 해소 대상: [ADR-0029](./0029-verify-deliberate-divergences.md)의 `changed_files` 보류

## Context

ADR-0029가 *"`changed_files` 수집(git 기반)"* 을 보류로 등록한 뒤 두 Phase를
지나며 시한이 무처분 도과했다. 보류의 실질 이유는 **비교 기준점이 없었다**는
것이다 — 무엇과 견줘 "바뀌었다"고 할지가 정해지지 않았다.

[ADR-0046](./0046-verified-checkpoint-commits.md)과
[ADR-0047](./0047-rollback-to-the-last-proven-point.md)이 그것을 만들었다.
미션 브랜치의 HEAD가 **마지막 입증 지점**이고, rollback이 되돌리는 곳도 거기다.

## Decision

### 1. 기준선은 **HEAD**다 — 별도 지정을 두지 않는다

upstream과 같이 `git status --porcelain=v1 -z`를 쓴다. 기준 커밋을 인자로
받지 않는다.

우리 형태에서 이것이 곧 *"마지막 입증 지점 이후 바뀐 것"* 이다 — 브랜치의
커밋이 checkpoint뿐이기 때문이다. **rollback이 지우는 범위와 정확히 같은
집합**이며, 그래서 목록은 *"되돌리면 사라질 것"* 이기도 하다.

`--untracked-files=all`을 붙인다. 없으면 새 디렉토리가 한 줄로 뭉뚱그려져
그 안의 파일이 보이지 않는다.

### 2. **검증 명령을 돌리기 전에** 찍는다

upstream이 detector 실행 전에 캡처하는 이유와 같다 (findings §5) — 우리가 만든
파일이 에이전트의 산출물로 집계되면 안 된다. 우리 쪽 부작용은 검증 명령이다
(`pytest` 캐시, 커버리지 파일).

**그리고 우리에겐 함정이 하나 더 있다.** checkpoint가 커밋하면 트리가
깨끗해지므로, 수집을 뒤로 미루면 **언제나 빈 목록**이 된다. 순서는 고정이다:

```
verify mechanical  ── 수집 ─→ 명령 실행 → 증거 저장
verify semantic    → 판정 저장 → checkpoint(커밋)
```

### 3. rename은 **두 경로 모두** 싣는다

무엇이 사라지고 무엇이 생겼는지 둘 다 사실이다. upstream도 이 목적의 파서에서는
둘을 담는다.

**checkpoint의 파서와 다르다** — 그쪽은 스테이징 대상이라 새 경로만 담는다.
upstream도 같은 저장소에서 파서를 둘로 나눠 둔다 (findings §4). 목적이 다르면
파싱이 다르다.

### 4. **빈 목록과 수집 실패를 구분한다**

`changed_files: tuple[str, ...]`와 `changed_files_error: str | None`을 따로
둔다. 한 필드로 뭉치면 *"관찰하지 못했다"* 가 *"변경이 없었다"* 로 읽힌다 —
증거 계층에서 그 혼동은 판정을 뒤집을 수 있다.

**수집기가 조립되지 않은 경우도 사유다.** 조용히 빈 목록이 되지 않는다.

수집 실패는 예외가 아니다. 목록을 못 만든 것이 검증을 막지 않는다.

### 5. `git diff --stat`과 원문 보존은 **도입하지 않는다**

upstream은 세 명령을 캡처해 세 파일로 남긴다 (findings §3). 우리는
`--porcelain` 하나만 쓰고 파일로 남기지 않는다.

**근거**: upstream이 셋을 남기는 이유는 QA가 **작업 디렉토리를 관찰할 수 없기**
때문이다 — 렌더된 아티팩트가 QA가 가진 전부다. 우리 semantic 평가자는
`workspace`를 받아 직접 관찰한다 (ADR-0034 정정 — 그 필드가 없을 때 평가자가
엉뚱한 디렉토리를 검사함이 실물 스모크에서 관측됐다).

즉 우리에게 목록은 **판정의 대체재가 아니라 사용자를 위한 표시**다. 규모 요약과
원문 보존은 그 목적에 필요하지 않다.

**등록된 divergence.** 발동 조건은 *"목록만으로는 무엇이 일어났는지 알 수 없다는
것이 실사용에서 관측"* 이다.

### 6. 목록을 semantic 평가자에게 **넘기지 않는다** (지금은)

같은 근거다 (§5) — 평가자가 workspace를 직접 본다. 목록을 프롬프트에 넣으면
토큰이 늘고 판정이 *"목록에 있는 것"* 에 갇힐 수 있다.

**미결로 등록한다** (§미결). 실사용에서 평가자가 변경 범위를 놓치는 것이
관측되면 그때 넣는다.

## Consequences

### Positive

- 사용자가 *"이 미션이 무엇을 손댔는가"* 를 증거에서 본다. 지금은 worktree에
  들어가 `git status`를 쳐야 안다.
- 목록이 **rollback이 지울 것**과 같은 집합이라, 되돌리기 전에 무엇이 사라질지
  볼 수 있다 (§1).
- ADR-0029의 두 Phase 묵은 보류가 닫힌다.

### Cost

- 목록이 **규모를 말하지 않는다** (§5). 한 줄 고친 파일과 새로 쓴 파일이
  같은 항목으로 보인다.
- 평가자는 여전히 목록을 보지 않는다 (§6) — 판정 품질에 기여하지 않는다.
- git 호출이 검증마다 한 번 는다. 비용은 무시할 수준이지만 `verify mechanical`이
  git 저장소가 아닌 workspace에서도 한 번 시도한다(실패는 사유로 남는다).

## Rejected alternatives

- **기준 커밋을 인자로 받기** — 고를 지점이 없다. HEAD가 유일한 입증 지점이다
  (ADR-0047 §2와 같은 근거).
- **`git diff --stat`과 원문 파일 보존** — QA가 관찰할 수 없는 upstream의
  사정에서 나온 것이며 우리에겐 그 사정이 없다 (§5).
- **checkpoint 뒤에 수집** — 트리가 깨끗해져 언제나 빈 목록이 된다 (§2).
- **`available` bool과 `error`를 함께 두기** — error의 유무가 곧 availability다.
  두 필드가 어긋날 자리를 만들지 않는다.
- **checkpoint의 파서를 재사용** — rename을 한쪽만 담는다. 목적이 다르다 (§3).

## Verification

- 수집은 검증 명령 **실행 전에** 일어난다.
- 수정·추가·삭제·rename이 전부 목록에 오르고, rename은 두 경로 모두 오른다.
- 새 디렉토리 안의 파일이 개별로 오른다.
- 공백이 든 경로가 온전히 온다 (`-z` 파싱).
- 깨끗한 트리는 빈 목록 + 사유 없음이다.
- git 저장소가 아니면 빈 목록 + **사유**다. 수집기가 없어도 사유가 남는다.
- 수집 실패가 검증을 막지 않는다.
- **목록이 사용자에게 표시된다** — §5가 이 목록의 존재 이유로 적은 것이며,
  2026-08-10까지 표시 경로가 없었다 (Phase 9 종료 검토 §2.1). 빈 목록은
  아무 말도 하지 않고, 수집 실패는 사유와 함께 나온다.

## 미결로 남기는 것

- ~~**평가자에게 목록을 넘길 것인가**~~ → **닫음: 넣지 않는다** ([Phase 9 종료 검토](../progress/0009_RECOVERY_LAYERS.md) §3-9,
  2026-08-10). 도그푸딩 0005 semantic 판정의 evidence에
  `Glob of the worktree: only roman.py, test_roman.py, README.md, .git and
  __pycache__` 가 있다 — **평가자가 workspace를 직접 관찰했고 변경 범위를
  놓치지 않았다.** §6의 근거가 실물로 지지됐다.
- ~~**규모 정보의 필요**~~ → **닫음: 이 미결의 전제가 틀렸다** ([Phase 9 종료 검토](../progress/0009_RECOVERY_LAYERS.md) §3-10,
  2026-08-10). 도그푸딩 0005에서 목록만으로 부족한지 판단할 수 없었는데,
  이유는 **목록이 표시되지 않았기 때문**이다 — §5가 "사용자를 위한 표시"라고
  적은 것이 CLI 어디에도 없었다. 간극은 규모 정보가 아니라 표시였고 그것을
  고쳤다 (0009 §2.1). `--stat` divergence는 유지한다.
- **되돌리기가 지운 것의 표시** — ADR-0047의 같은 항목과 함께 본다.
  **Phase 10 종료 처분 (2026-08-10):** Recover가 발동하지 않아 미관측이며,
  ADR-0047과 함께 **Phase 11 종료 전 targeted dirty-rollback fixture**로
  재지정한다. 자연 발동이 없어도 실행해 닫는다
  ([progress 0010](../progress/0010_REFLECT_EVOLVE.md) §2.7).
  **최종 처분 (2026-08-10): 필요성이 실물로 확인되어 도입한다.** fixture에서
  수집된 `proven.py`, `failed_attempt.py`, `nested/trace.txt` 세 경로가 rollback
  뒤 사라졌지만 기존 CLI는 commit만 표시했다. rollback 직전 같은 porcelain
  수집기를 사용해 결과와 CLI에 이 exact 목록을 남긴다. 별도 `--stat`이나 원문
  보존은 여전히 필요하지 않다.
