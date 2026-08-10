# Dogfooding 0005 — Phase 9 다섯 층 전부 실물 검증, `MISSION COMPLETE`. 결함 3건

- 일시: 2026-08-10 (09:05~10:30 KST)
- Evidence level: **Verified by execution** (사용자 승인 하에 실제 AI 실행)
- Mission: `m-b8f181` — `roman.py`: 정수 ↔ 로마 숫자 변환 모듈 (1~3999, 표준형,
  표준 라이브러리만, unittest 검증)
- 구성: `uv run mcx`, 텍스트·판정 claude 2.1.226, 실행 codex 0.147.0
- 목표: **Phase 9가 만든 다섯 층**의 실물 검증
- 결과: **다섯 층 전부 관측됨.** 결함 3건을 잡아 모두 처분하고
  **`MISSION COMPLETE`로 완주**했다 (§6).

## 0. 과제 선정이 0004의 원인이었음을 확인했다

0004는 인코딩·파일명 축 과제로 감사 **15라운드** 비수렴했다. 0005는 파일시스템·
인코딩·CLI 파싱을 전부 뺀 **순수 변환 모듈**로 잡았다.

| | 0004 | 0005 |
|---|---|---|
| `brief audit` | **15회 / 24분** | **4회 / 6분** |
| Brief Gate | 도달 못 함(중단) | **CLEAR** |
| Blueprint | 생성 실패 | **AC 7개 생성** |

도구가 아니라 **과제 축의 깊이**가 감사 라운드를 정한다는 것이 두 관측으로
고정됐다.

## 1. Phase 9 다섯 층 — 전부 관측

### 1.1 worktree 격리 (ADR-0045)

```
envelope.workspace = <state>/worktrees/workspace/m-b8f181
사용자 checkout:  ## main / README.md      ← 손대지 않음
worktree:         ## mcx/m-b8f181 / roman.py test_roman.py
```

### 1.2 진행 표시 + 정규화 (ADR-0049)

`execute next` 7회 전부에서 도구 호출이 실시간으로 나왔다.

```
→ command_execution /bin/zsh -lc 'python3 -m unittest -v'
→ command_execution /bin/zsh -lc 'git diff --check && git status --short'
```

진행 꼬리 `progress_m-b8f181_39.jsonl` (0600) 에 같은 줄이 남았다. 이전에는
89초 동안 화면이 비어 있었을 자리다.

### 1.3 `changed_files` 수집 (ADR-0048)

```
changed_files: ['__pycache__/roman.cpython-312.pyc', … , 'roman.py', 'test_roman.py']
changed_files_error: None
```

`__pycache__`가 목록에 있는 것은 **정상**이다 — worker가 Execute 중 테스트를
돌려 만든 것이고 수집은 검증 명령 실행 **전**이다 (§2 순서 계약). 이 저장소에
`.gitignore`가 없어 추적되지 않은 채로 보인다.

### 1.4 checkpoint 커밋 (ADR-0046)

```
6c9111c mcx: ac_71a54066b87634cb, ac_032d035b41f54959, …
Mission: m-b8f181
Blueprint-Revision: 2
Acceptance-Criteria: ac_71a…, ac_032…, ac_4e2…, ac_274…, ac_dda…, ac_a71…
```

AC 7개 중 **입증된 6개만** 라벨에 실렸다 — `proven_criteria`가 Gate와 같은
판정을 쓴다는 것이 실물로 확인된다 (§2). 커밋 후 트리는 깨끗했다.

### 1.5 rollback (ADR-0047)

```
rollback: 6c9111c로 되돌림
```

`recover dispatch`가 교정을 내보내기 **전에** 마지막 입증 지점으로 되돌렸다.

## 2. 결함 1 — 실사용에서 처음 관측된 **과잉 마스킹** (수정 완료)

진행 표시에 이렇게 찍혔다:

```
→ command_execution … python3 -c "import unittest,test_roman;
   n=[redacted](test_roman).countTestCases(); …"
```

`unittest.defaultTestLoader.loadTestsFromModule`이 통째로 지워졌다.

**원인**: 고신뢰 형태의 JWT 규칙
`[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}` 이 **세 조각 모두
8자 이상인 점 표기 식별자**를 잡는다.

**upstream 대조**: 패턴은 upstream과 **자간까지 같다**
(`core/security.py:85`). 다른 것은 **거는 자리**다 — upstream은
`is_credential_shaped(value)`로 **필드 값**에 걸고, 우리는 산문을 훑는다.
[REDACTION_FIELD_TRIAL](./REDACTION_FIELD_TRIAL.md)과 같은 구조의 divergence다.

**수정**: 라벨 없는 층에서만 `eyJ` 접두사를 요구한다. 실제 JWT의 헤더는 언제나
JSON이므로 base64가 `eyJ`로 시작한다. **라벨이 붙은 JWT는 접두사와 무관하게**
`_LABEL`·`_BEARER`가 잡으므로 잃는 것이 없다. 957 tests (+5).

> REDACTION_FIELD_TRIAL §4의 *"과잉 마스킹 관측 0건"* 은 ruff·pytest·git 출력
> 위에서의 측정이었다. 그 출력에는 세 조각 점 표기가 없다. **측정 범위가
> 좁았던 것**이며, 실사용이 그것을 드러냈다.

## 3. 관측 — QA 예산은 `revise` 없이 소진된다

QA 궤적: `0.87 → 0.85 → 0.85 → 0.82 → 0.85(rev2)`.

**운영자 오류**: `qa`만 반복하면 점수가 오르지 않는다. 고치는 것은 `revise`이고,
`qa`는 채점만 한다. 예산 5회 중 3회를 재채점에 썼다.

지적 자체는 전부 실질이었다 — goal이 예외 계약을 한 겹으로만 말해 AC2와 모순,
공개 표면 검사가 `inspect.isfunction`이라 상수·`lru_cache` 래퍼에 대해 과소·
과대, 테스트 실질 확인이 부분 문자열이라 측정이 아님(`'iv'`가 `derive` 안에도
있다). 세 지적을 revision 2에 반영했다.

`action: continue`가 *"이제 revise할 차례"* 를 말하지 않는다. 표면 관측으로
기록한다 — upstream은 반복 카운트를 호출자가 넘기므로(§4) 대응물이 없다.

## 4. 결함 2 — 예산 소진 후 `revise`하면 **영원히 승인할 수 없다** (수정 완료)

```
blueprint revise   → revision 3 생성 (성공)
blueprint approve  → UnassessedRevisionError: revision 3에 QA 평가가 없다
blueprint qa       → QaBudgetExhaustedError: 예산이 소진됐다 (5회)
```

두 계약이 맞물려 출구가 없다:

- 예산은 **mission 단위 누적**이다 (ADR-0019 §6).
- 승인은 **현재 revision의 QA 평가**를 요구한다 (ADR-0019 §8).
- `--accept-below-threshold`는 **점수가 있는** revision에만 통한다.

즉 예산이 소진된 뒤 *"명세가 틀렸으니 고치자"* 는 자연스러운 대응을 하면 미션이
잠긴다. 도달 경로가 특수하지 않다 — 이번 미션이 정확히 그 길로 갔다.

**upstream에는 이 데드락이 없다.** upstream QA 도구는 `iteration`과
`iteration_history`를 **호출자가 넘기는 파라미터**로 받는다
(`mcp/tools/qa.py:358, :479`) — 예산이 저장된 상태가 아니고, 승인이 저장된
평가에 묶이지도 않는다. 우리가 둘 다 상태로 만들면서 생긴 조합이다.

**처분** ([ADR-0019 §6.1](../adr/0019-blueprint-qa-loop.md) 개정). 처음 떠올린
후보 셋((a) 예산 1회 허용 (b) revise 거부 (c) revision 단위 예산)은 **전부
발명이었다.** upstream 규칙이 답을 이미 갖고 있었다:

> `skills/seed/SKILL.md:113` — "If the user chooses **one final manual edit**,
> apply exactly that user-specified edit … and ask for **explicit
> below-threshold acceptance**; **do not start a sixth QA iteration, rerun QA**"

즉 **우리는 upstream 규칙의 절반만 이식했다.** upstream은 상한과 그 뒤의
탈출구를 한 문장에 함께 두는데, 우리는 상한을 skill이 아니라 코드로
옮기면서(§1, Constitution §6.5) 나머지 절반을 산문에 두고 왔다. upstream에서는
강제자가 에이전트라 지시 전체가 한 덩어리로 작동한다.

물려받은 점수가 어느 revision의 것인지는 `qa_scored_revision`이 기록해 §8이
지키는 질문("통과한 것인가 봐준 것인가")을 보존한다.

## 5. 미션이 실패한 이유 — 운영자 저작 오류

AC7의 `output_assertion`을 `"OK / TESTS ENOUGH"` 로 썼는데 실제 출력은
`"Ran 11 tests…\n\nOK\nTESTS ENOUGH\n"` 다. 사람이 읽는 문구를 썼고 판정은
부분 문자열 일치다.

**QA가 revision 2를 채점하면서 이것을 잡지 못했다.** 같은 QA가 revision 1에서
*"부분 문자열 확인은 측정이 아니다"* 를 지적했던 것과 같은 축인데, 새로 들어온
assertion이 자기 명령의 출력과 맞는지는 보지 않았다. 관측으로 기록한다.

## 6. 결함 2 처분 후 재개 — `MISSION COMPLETE`

[ADR-0019 §6.1](../adr/0019-blueprint-qa-loop.md)로 데드락을 풀고 같은 미션을
그대로 이어 돌렸다.

```
approve --accept-below-threshold  →  approved_revision 3
blueprint gate                    →  CLEAR → execute
승인 기록: revision 3 / 점수가 나온 revision 1 / 0.87 / 미달수락 True
```

**최종 상태**: `✅ MISSION COMPLETE · 총 1시간 5분 · claude 41콜 · codex 15콜`
(Brief 5라운드 · Blueprint AC 7개 · mechanical 7/7 · semantic 7/7).

`revise`가 revision을 올리므로 **실행 lineage가 전부 무효가 됐다** — AC 하나의
문구를 고치는 데 AC 7개 재실행이 들었다. revision 단위 실행 lineage(ADR-0002)의
대가이며 최종 수정 경로의 것이 아니다. 관측으로 기록한다.

## 7. 결함 3 — checkpoint 경로 파서가 첫 항목을 한 글자 잘랐다 (수정 완료)

완주 직후 두 번째 checkpoint가 남지 않았다. 사유는 결과에 있었다 (ADR-0046 §6이
요구한 표시가 제 몫을 했다):

```
checkpoint 없음: git add -- _pycache__/test_roman.cpython-312.pyc … 실행에 실패했다
                            ↑ 밑줄 하나가 사라졌다
```

**원인**: `_output()`이 `result.stdout.strip()`을 한다. porcelain의 상태 두
글자는 수정된 추적 파일에서 `" M"`처럼 **선행 공백**을 갖고, strip이 그것을
지우면 첫 항목만 `entry[3:]`가 한 글자 밀린다.

**왜 지금까지 안 걸렸나**: 첫 checkpoint에서는 모든 파일이 `??`(untracked)라
선행 공백이 없었다. 그리고 `test_checkpoint.py`가 **untracked만** 덮고 있었다.
즉 ADR-0046 §3이 *"두 번째 라운드부터 증분"* 이라고 적은 바로 그 지점에서만
발동하는 결함이었고, 실사용이 아니면 드러나지 않았다.

`changes.py`의 파서(ADR-0048)는 `result.stdout`을 strip 없이 넘기므로 무사했다 —
같은 저장소에 파서가 둘이라는 ADR-0048 §3의 기술이 여기서 다행이 됐다.

**수정**: `changed_paths`가 strip하지 않는 경로로 git을 읽는다. 회귀 테스트 2건
추가(수정된 추적 파일, `__pycache__` 형태). 964 tests.

재확인:

```
checkpoint: b5f1ef6 (ac_71a…, ac_032…, ac_4e2…, ac_274…, ac_dda…, ac_a71…, ac_19d…)
b5f1ef6 mcx: …        ← 두 번째 라운드의 증분 checkpoint
6c9111c mcx: …
c5b1ef0 chore: 초기 커밋
```

## 8. 남은 것

없다. 관측 항목 셋은 등록만 한다 — 파생 후보의 굵기, `action: continue`가
revise 시점을 말하지 않는 것, revision 단위 실행 lineage의 재실행 비용.
