# Dogfooding 0006 — Gen 1 Verify HOLD → Evolve → Gen 2 MISSION COMPLETE

- 일시: 2026-08-10 (15:11~17:58 KST)
- Evidence level: **Verified by execution** (사용자 승인 하에 실제 AI 실행)
- Mission: `m-evolve-0006b` — brownfield `retry_policy.py`가 429의 숫자형
  `Retry-After`를 따르도록 고치되 비대상 응답은 재시도하지 않는다
- 구성: `uv run mcx`; Evolve·초기 QA는 Claude, 한도 도달 뒤 QA·Verify는 Codex
  text lane, Execute는 Codex CLI
- 목표: **Phase 10의 대표 Gen 2 실사용 경로** — 실제 Verify `HOLD`를 durable
  source로 재구성해 Wonder→Reflect→후속 Blueprint→QA→exact user approval→
  Execute→Verify로 잇는다
- 결과: **`MISSION COMPLETE`.** Phase 10 표면 결함 2건을 발견해 수정했고,
  Evolve target call 예산은 추정과 일치했다.

## 0. 과제와 통제된 precondition

과제는 기존 Python 모듈과 테스트가 있는 작은 brownfield다. Gen 1 실행 결과는
`status_code != 429` guard만 구현하고, 429의 `Retry-After: "3"`에는 상수 1을
반환하도록 일부러 실패를 남겼다.

```text
AC 1: 비-429 → None       mechanical PASS
AC 2: 429, "3" → int 3    mechanical FAIL (1 != 3)
Verify Gate: HOLD
```

실 Claude semantic evaluator는 AC 1을 `satisfied=true`로 분류했지만 전체 Goal이
미완료라는 이유로 score를 0.72로 줬다. pinned upstream evaluator도 AC별
`ac_compliance`와 별개로 score를 전체 품질로 채점하므로 제품 결함으로 보지
않았다. Phase 10이 보호된 AC 경로를 실제로 관측하려면 proven AC 하나가 필요해,
AC 1만 실제 mechanical pass와 소스 guard를 근거로 score 0.92의 **통제된
precondition**으로 고정했다. AC 2의 mechanical failure와 Claude semantic
failure(score 0.20), 이후 Evolve·QA·Execute·최종 Verify는 모두 실제 실행이다.

따라서 이 도그푸딩이 증명하는 것은 **완전한 Gen 1 semantic 평가 품질**이 아니라,
완전한 durable HOLD source를 받은 뒤의 Gen 2 연결이다. 이 한계를 숨기지 않는다.

## 1. Evolve — 추정 2회, 실제 2회

사전 추정은 정상 `Wonder 1 + Reflect 1 = 2 primary calls`, transient retry를
포함한 최악 6회였다 (ADR-0051 §8).

| 항목 | 실측 |
|---|---:|
| Claude primary call | **2** |
| retry | **0** |
| wall time | **156.519s** |
| result generation / revision | **2 / 2** |

source는 `verify_sequence=4`, Gen 1 execution attempts `[1, 2]`, 두 AC의
mechanical·semantic evidence와 Verify Gate `HOLD` blocker를 정확히 담았다.
Mission record는 Verify→Blueprint로 전이했고 이전 revision 1 승인은 stale이 됐다.

### 1.1 protected AC가 exact keep됐다

통과한 AC 1의 content key `ac_96a97086294b7dc8`, 설명, verify command가 revision
2에서 그대로 유지됐다. Wonder는 이 AC를 challenge하지 않았고 Reflect의
`settled_ac_keys`도 같은 key였다. 모델의 자연어 주장만이 아니라 adapter의
protected keep backstop이 실제 입력에서 발동한 결과다.

### 1.2 실패한 AC와 ontology가 evidence를 따라 진화했다

Wonder는 단일 `'3' → 3` 사례만으로는 상수 3 구현도 통과할 수 있음을 지적했고,
Reflect는 `'3' → 3`, `'7' → 7`, `int` 타입으로 AC를 revise했다. 추가 gap은 네
축이었다.

- Retry-After 부재·비숫자 값의 fallback
- 0·음수 경계
- 대상 상태 집합 `{429}`와 503 비대상
- 결과 타입과 기본 지연의 ontology

Reflect는 AC 세 건을 add하고 ontology field 네 개를 추가했다. Goal·Constraints·
Non-goals 변경과 scope finding은 없었다. 즉 실제 모델이 parent 방향을 유지하면서
실패 evidence에서 다음 specification proposal을 만들었다.

## 2. 기존 승인 모델이 실제로 멈췄다

upstream Gen 2+는 Reflect 뒤 Seed→Execute로 자율 진행하지만 mcx는 ADR-0051 §6의
의도적 divergence대로 Blueprint에서 멈췄다.

```text
revision 2 / generation 2
approval_required = true
Blueprint Gate = HOLD
```

revision 2의 실제 Claude QA는 0.76이었다. 지적은 중복 AC, ontology의 입력·어휘
경계 누락, 5개 중 3개 AC의 verify command 누락, 공백 미정의, Goal의 fallback
누락이었다. 사용자가 다음 제품 의미를 한 항목씩 결정했다.

- 429에서 값이 없거나 무효면 기본 1초
- `"0"`은 즉시 재시도, 음수는 fallback 1
- 대상 상태는 429만; 503은 Retry-After가 있어도 `None`
- 앞뒤 공백은 제거하고 숫자를 해석

revision 3은 AC를 세 결과 분기로 합치고 verify command를 모두 붙였다. Claude
주간 한도에 걸린 실패 호출은 assessment로 저장되지 않았고, 설정된 routing
boundary로 Blueprint text lane만 Codex로 바꿔 재개했다. Codex QA 0.87은
ontology input/type/normalization과 `+3`, `01`, Unicode digit, tab, NBSP의 정확한
문법을 추가로 요구했다.

revision 4는 `str.strip()` 뒤 ASCII `[0-9]+`, 선행 0 허용, 부호·소수·HTTP-date·
비ASCII 숫자 거부를 명시하고 ontology를 7 fields로 완성했다. Codex QA는
**1.00 / findings 0**이었다. 사용자의 `진행해줘`를 exact revision 4 승인
문장으로 기록한 뒤에만 Blueprint Gate가 `CLEAR`가 됐다.

## 3. 결함 1 — QA가 ontology를 고치라지만 수동 revision은 고칠 수 없었다

### 증상

revision 3 QA의 핵심 지적은 ontology에 `retry_after` 입력과 정규화·lexical
contract가 없다는 것이었다. 그러나 `blueprint revise --draft-file`이 읽는 것은
Goal·Constraints·Non-goals·AC뿐이었다. `BlueprintService.revise`는 언제나 current
ontology를 복사했다.

```text
QA: ontology를 보완하라
manual draft: ontology 필드 없음
service: current ontology 강제 보존
```

사용자가 QA 제안을 채택해도 표현할 표면이 없으므로 기존 approval model은
스스로 요구한 수정을 완료할 수 없었다. 결정적 테스트가 놓친 실제 조립 결함이다.

### upstream 대조와 처분

pinned upstream interactive `skills/seed/SKILL.md` Restate는 사용자가 채택한
변경을 이전 Seed YAML 전체에 반영한다. upstream autonomous Gen 2+에 사용자
정지점은 없지만, mcx가 그 정지점을 유지하기로 한 divergence에서는 전체 Seed를
수정할 수 있어야 한다.

처분:

- manual `BlueprintDraft`에 optional complete `ontology` replacement 추가
- 생략하면 current ontology exact 보존
- 제공하면 full schema 교체; 부분 patch는 누락과 삭제가 구분되지 않아 미지원
- Gen 1 generator가 ontology를 발명해도 deterministic initial ontology가 이김
- Guide §7.4·§7.6, ADR-0051 §6, Test Matrix와 회귀 테스트로 고정

구현 commit: `1aa7384`.

revision 4가 이 새 표면을 실제로 사용해 ontology 7 fields를 저장했고 QA 1.00을
받았다.

## 4. Execute→Verify — 실제 Runtime으로 완주

Gen 1의 guard 변경을 임시 brownfield 저장소의 기준점 commit `3a84b01`로 고정해
격리 worktree가 실제 이전 세대 코드 상태를 이어받게 했다. revision 4의 세 AC는
각각 Codex CLI Execute를 한 번씩 받았다.

| 단계 | 호출 | 실측 |
|---|---:|---:|
| Execute AC 1 | codex_cli 1 | 70.696s |
| Execute AC 2 | codex_cli 1 | 62.970s |
| Execute AC 3 | codex_cli 1 | 50.398s |
| semantic Verify AC 3개 | codex 3 | 66.761s |

첫 worker가 전체 함수를 완성했고 다음 worker 둘은 자기 AC 관점에서 경계를
보강했다. 이는 worker의 완료 주장이므로 그 자체로 성공으로 쓰지 않았다.

실제 mechanical Verify는 세 선언 명령을 다시 실행해 **3/3 PASS**, semantic
Verify는 각각 `1.00 / 0.99 / 0.99`, 모두 satisfied, uncertainty와 reward-hacking
risk 최대 0.01이었다. `changed_files`는 `retry_policy.py`,
`test_retry_policy.py` 두 개였다. Verify가 입증한 checkpoint:

```text
431cdb2 mcx: ac_e589…, ac_5fbad…, ac_069f… 입증 —
```

최종 `verify gate`는 `CLEAR`, Mission record는 `MISSION COMPLETE`를 기록했다.

## 5. 결함 2 — status가 세대 lineage를 섞었다

완료 직후 status는 다음처럼 표시했다.

```text
Blueprint: AC 3개 · rev 4
Execute:   AC 5개 실행 · 시도 5회 — 검증 전
Verify:    mechanical 3/3 · semantic 3/3
```

Execute row가 Gen 1의 recorded attempts 2개와 Gen 2의 실제 attempts 3개를 Mission
전체로 합쳤고, 이미 Verify Gate가 CLEAR인데도 고정 문구 `검증 전`을 붙였다.
저장 lineage는 정확했지만 사람용 summary가 서로 모순됐다.

처분:

- Execute row는 current Blueprint revision의 attempts만 집계
- 같은 revision의 Verify evidence + Gate 재판정으로 `검증 전|중|완료` 표시
- Recover correction도 `(blueprint_revision, ac_key)` 안의 반복만 집계
- stale Verify evidence를 current revision에 재사용하지 않는 회귀 테스트 추가

구현 commit: `1aa7384`.

재확인 결과:

```text
Execute: AC 3개 실행 · 시도 3회 — 검증 완료
Verify:  mechanical 3/3 · semantic 3/3
```

## 6. 호출 수와 외부 한계

명령 원장 전체는 Claude 6, Codex text 5, Codex CLI Execute 3회로 **14 port
calls**를 기록했다. 이 중 Phase target Evolve는 추정 2/최악 6 대비 실제 2회로
일치했다. 나머지는 source semantic 2, QA 4(Claude 한도 실패 1 포함), 최종
semantic 3, Execute 3이다.

Claude 실패 1회는 주간 사용 한도(`Aug 13 12pm Asia/Seoul reset`)로 inference
결과가 없었지만 port call이 일어난 비용으로 원장에 포함된다. 같은 Stage의
backend를 config로 Codex로 바꾸어 state나 Core를 수정하지 않고 재개했다. 이
경로는 routing table의 실제 fallback 가능성을 지지하지만 자동 fallback을
도입하는 근거는 아니다.

플러그인·MCP·사용자 환경 설치는 하지 않았다. fixture·state·routing config는
모두 `/tmp` 아래에만 만들었다.

## 7. 결론

Phase 10의 핵심 연결은 실물로 확인됐다.

```text
Gen 1 Verify HOLD
  → exact durable source
  → Wonder / Reflect (2 calls)
  → Gen 2 pending Blueprint
  → QA / user refinement / exact approval
  → Execute 3 AC
  → mechanical 3/3 + semantic 3/3
  → MISSION COMPLETE
```

검증이 잡은 결함 둘은 모델 품질 문제가 아니라 **조립 표면** 문제였다. 하나는
사용자 채택 모델이 ontology를 표현하지 못했고, 다른 하나는 status가 generation
lineage를 섞었다. 둘 다 실제 Gen 2 입력 모양에서만 드러났고 수정·회귀 테스트까지
완료했다.
