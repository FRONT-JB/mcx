# Progress 0004 — Verify·Recover Vertical Slice

- Status: COMPLETE
- Started: 2026-08-08
- Completed: 2026-08-08
- Scope owner: Verify·Recover Stage core implementation

## Goal

승인된 실행 위에서 증거로 판정하고(`CLEAR — MISSION COMPLETE`는 Verify Gate만),
실패를 bounded correction으로 회복해 다섯 Stage의 순환을 완성한다.

## Inputs

- [Verify Guide](../08_VERIFY.md), [Recover Guide](../09_RECOVER.md)
- [EVALUATE](../research/EVALUATE_UPSTREAM_FINDINGS.md)·[VERIFY](../research/VERIFY_UPSTREAM_FINDINGS.md)·[REPAIR](../research/REPAIR_UPSTREAM_FINDINGS.md) upstream findings
- ADR-0026(진입 lineage), 0027(telemetry 층), 0028(mechanical 계약),
  0029(Verify 등록부), 0030(semantic verdict), 0031(실패·재시도), 0032(Recover 등록부)

## In scope

- Verify domain: evidence(run·묶음·판정불가 구분), verdict(정책 0.8/0.3/0.7),
  gate(MISSION COMPLETE 네 조건)
- Recover domain: 실패 packet의 결정적 파생(원천 4종 + BLOCKED·STALL), 예산,
  gate(Clear for Verify)
- Application: VerifyService(mechanical 실행·semantic 판정·Gate),
  RecoverService(plan·교정 dispatch·Gate),
  ExecuteService.dispatch_correction + `ExecutionRequest.previous_failure`
- Adapters: LocalMechanicalRunner(실제 subprocess), FileVerifyRepository +
  출력 보존소
- deterministic fake(runtime·semantic 평가자) + 실제 명령의 통합 test suite

## Out of scope

- 실제 LLM semantic 평가자, capability 차단, timeout/cancel/resume (Phase 5)
- repo 수준 명령 층(mechanical.toml 대응), workspace mutation guard,
  coverage (ADR-0029 보류)
- consensus escalation, lateral 전환, 세밀 실패 분류, rollback (ADR-0029·0032 보류)
- `mcx verify`·`mcx recover` CLI (Phase 6)

## Deliverables

- [x] `domain/verify/evidence.py` — VerificationRun/Evidence, judge_run,
  VerifyState(재검증이 verdicts 무효화)
- [x] `domain/verify/verdict.py` — CriterionVerdict, SemanticAssessment,
  SemanticPolicy(upstream 임계)
- [x] `domain/verify/gate.py` — `CLEAR — MISSION COMPLETE` 네 조건,
  escalation 대기·veto blocker
- [x] `domain/recover/packet.py` — 파생·분류·예산, `domain/recover/gate.py`
- [x] `application/verify_service.py`, `application/recover_service.py`,
  ExecuteService 교정 진입점
- [x] `adapters/verification/local_mechanical_runner.py`,
  `adapters/persistence/file_verify_repository.py`(+출력 보존소)
- [x] unit + integration test suite (95건 — 실제 subprocess 포함)

## Exit criteria

- [x] 승인된 실행 위에서만 검증이 시작된다 — 기록 없는 작업은 진입 불가
  (ADR-0026, `test_verify_service.py` Entry).
- [x] 실행되는 명령은 승인된 Blueprint의 `verify_command`뿐이고, 증거는
  파일 보존 + 참조로 남는다 (ADR-0028).
- [x] worker의 성공 주장이 어느 증거 경로에도 등장하지 않는다 — mechanical은
  직접 실행, semantic 입력에도 `result_summary` 없음.
- [x] mechanical과 semantic이 서로의 실패를 뒤집지 못하고, 불확신은 실패가
  아니라 escalation 대기 `HOLD`다 (ADR-0030).
- [x] 두 층 전부 통과 시 `CLEAR — MISSION COMPLETE` — v1 첫 도달, Verify
  Gate만 선언.
- [x] 실패 → 실패 증거를 실은 교정 → 재검증 → MISSION COMPLETE의 전체 순환이
  실제 명령으로 돈다 (`test_recover_flow.py`).
- [x] 재시도 예산(AC당 2회, revision 리셋)·동일 오류 3회 중단·BLOCKED 인식이
  재시도를 멈춘다 (ADR-0031).
- [x] mypy, ruff, ruff-format이 통과한다.

## Verification evidence

```text
Commits: 72280c5 (ADR-0026·0027) → 6407600 (ADR-0028·0029) → d663c7b (mechanical)
         → 90b9cac (ADR-0030) → 153f8d7 (semantic) → 1276118 (ADR-0031·0032)
         → 9424b4e (recover) → 0186450 (종료 검토 수정: revision 예산 리셋)
Tests: 483 passed (Phase 4 신규 95)
  domain/verify: evidence 19, verdict 12, gate 8
  domain/recover: packet 11, gate 6
  adapters: file_verify 7, local_mechanical_runner 7 (실제 subprocess)
  application: verify_service 13, recover_service 6
  integration: verify_flow 4, recover_flow 2 (다섯 Stage 순환)
mypy: Success (44 source files)
ruff check / ruff format --check: 통과
Verify·Recover 구현: 1,518 lines
```

## Phase 종료 검토

[progress README](./README.md)의 여섯 질문에 대한 답이다.

### 1. 구조 검사 — 각 방어가 막는 결함

| 방어 | 막는 결함 | 위치 |
|---|---|---|
| 진입 재확인(Blueprint+Execute Gate) | 기록 없는 작업의 검증 — upstream §12.3 사고의 재현 | `verify_service._cleared_pipeline` |
| VerificationRun 필드 일관성 validator | 통과인데 누락 artifacts·timeout·비0 exit가 공존하는 증거 | `evidence.py` |
| 판정 불가 구분(run 없음 + Gate blocker 아님) | 검사 안 한 AC가 통과로 집계 | `evidence.py`·`verdict 요구` |
| verdict의 evidence 바인딩(`record_verdicts`) | 증거 없는 판정 — semantic이 mechanical을 대체하는 문 | `evidence.py` `VerdictWithoutEvidenceError` |
| 재검증의 verdicts 무효화 | 옛 증거 위의 판정이 새 증거를 지지 | `evidence.py` `record` |
| verdict 귀속 검증 | A의 판정이 B의 완료 근거가 됨 | `verify_service` `VerdictMismatchError` |
| escalation 대기 blocker (실패 아님) | 확신 있는 오판과 불확실한 정판의 혼동 | `verify/gate.py` |
| reward-hacking veto (독립 검사) | 평가자를 속인 산출물의 통과 | `verify/gate.py` |
| revision 스코프(evidence·verdicts) | 이전 revision 결과의 자동 재사용 | `verify/gate.py`, `recover/packet.py` |
| 실패 packet의 파생(저장 없음) | 원본 기록과 파생본의 두 진실 | `recover/packet.py` |
| BLOCKED·STALL 결정적 인식 | 권한 문제·동일 실패를 재시도로 문지르는 낭비 | `recover/packet.py` |
| 재시도 예산 + revision 리셋 | 같은 AC의 무한 교정 | `recover/packet.py`, **리셋 테스트는 이 검토에서 추가 (0186450)** |
| `previous_failure` 필수의 교정 진입점 | 실패 증거 없는 "같은 prompt 반복" | `execute_service.dispatch_correction` |
| 교정 후 stale 실패의 재검증 대기 판정 | 오래된 실패 증거로 교정을 다시 교정 | `recover/packet.py` (attempt 번호 ∉ 검증 번호) |
| `NothingToRecover`·`NoRetryableFailure` | 근거 없는 회복·조용한 no-op | `recover_service.py` |

산문·프롬프트로만 막는 계약: `previous_failure`의 프롬프트 렌더링(전환 지시
문구 포함)은 Phase 5 adapter 소관 — v1은 구조화 필드의 전달까지. Guide §9
(Strategy change)의 관점 선택은 전부 미구현(보류 등록). Gate 조건 대조는
아래 특별 항목.

### 2. 부품/단계 구분

end-to-end로 돈다 — `test_recover_flow.py`가 다섯 Stage의 전체 순환(실패 →
교정 → 재검증 → MISSION COMPLETE)을 실제 명령·파일 저장소로 잇는다. "돈다"의
기준: Runtime과 semantic 평가자는 결정적 fake, **검증 명령은 진짜다**. Phase 4
checklist 5항목 전부 `[x]`이며 각각 test·commit이 연결되어 있다. Guide slice
기준 08 §13의 Slice 5(observation adapter)와 09 §15의 lateral류는 보류로
등록된 미착수다 — 완료로 기록하지 않았다.

### 3. 미등록 이탈

검토에서 하나 발견: **Guide 09 §3 초안의 "저장된 RecoveryDirective" 요구와
ADR-0031의 "파생하고 저장하지 않는다"가 충돌**하고 있었다 — 진실의 원천
우선순위(ADR > Stage Guide 초안)에 따라 가이드에 v1 확정 표시를 추가해
해소했다(재평가 시점: Phase 7 장기 실행 job의 승인 기록). 그 외 이탈(STALL
처방 HOLD, 분류 축소, 검증 시점 통합, lineage 요구)은 ADR-0029·0032에 기등록.

### 4. 표시 없는 보류

두 건 발견, 처분했다.

1. **`exit_conditions` 유예의 시한 도래** — ADR-0017이 "대응 필요 시점은
   Verify(Phase 4)"로 유예했는데 Phase 4가 그것 없이 완성됐다. 재평가를
   수행해 기록했다: 핵심 조건은 Gate의 AC 전수 요구가 덮고, 잔여는 repo 명령
   층·Phase 6·7 surface에 종속 — 시한을 그 도입 시점으로 이동 (ADR-0017
   dated note + ADR-0029 보류 등록).
2. **canonical Stage 저장의 부재** — Phase 1이 "Phase 2에서 다룬다"고 했으나
   재론되지 않았고, 그 결과 모든 Entry Contract의 "현재 Stage가 X다" 조건이
   전 Stage에서 미강제다. 실질 보증은 각 진입의 Gate 재계산이 대신하고 있다.
   progress README 알려진 한계에 추가했다 — 처분은 Lifecycle 소유 결정으로
   Phase 6(CLI가 mission 상태를 표시·조작) 전.

### 5. 계약 문장 원문 여부

Phase 4 신규 코드에 문장이 곧 계약인 지점은 없다 — 임계값·순서·분류는 전부
결정적 코드다. upstream의 영어 지시문("Do not repeat the failed path" 등)은
가져오지 않았고, 그 대응물(`change_approach`)은 bool 신호다 — 프롬프트 문구가
필요해지는 Phase 5 adapter에서 이 질문을 다시 적용한다.

### 6. 관측 대조

runtime 도그푸딩 전사와 모순되는 규칙 없음. 이번 Phase의 upstream 대조는 전부
소스 수준(EVALUATE·VERIFY·REPAIR findings)이었고, 실행 관측이 필요한 지점
(semantic 평가 품질, consensus 발동)은 Phase 5에서 실제 adapter와 함께 온다.

## 특별 항목 — Gate 조건·Test Matrix 전수 대조

### Verify Gate (08 §9) — CLEAR 조건 9개 중 검사되는 것

검사됨: 필수 mechanical 통과, 모든 AC의 verdict 충족(+ 불확신·게이밍 조건).
**검사되지 않는 것 6건은 progress README "Verify Gate CLEAR 조건 중 강제되지
않는 것" 표로 옮겼다** — 검사 생략의 정책 근거, Exit Conditions(유예 재평가),
Constraint 위반, Non-goal 구현, workspace revision 추적, unresolved risk 근거.
Constraint·Non-goal 대조는 semantic 평가자의 입력에 있으나(§ 프롬프트 계약)
결정적 검사가 아니다.

### 08 §12 Test Matrix

| 상태 | 행 |
|---|---|
| 덮음 | Entry 4행, Mechanical 6행(허용 위반 행은 v1 대상 없음 표시 기존), Semantic 5행(미충족·score·veto·stale·모든 AC), Uncertainty, Evidence(worker claim만 — 구조적), Parser(구조화 port — 대상 없음에 가깝지만 verdict 귀속 검증이 인접 결함을 덮음), Completion |
| 부분 | Independence(실행 주체와 평가자가 다른 fake이나 vendor 개념 없음 — Phase 5) |
| 대상 없음 (v1) | Identity(workspace revision — §5 미결정), Observation(not_observed — 보류), Regression 5행(회귀 시나리오 — repo 검사 층·이력 축적 후) |

### Recover 진입(09 §3)·Gate(09 §11)

진입 조건 중 검사됨: Blueprint 유효(재확인), 실패 근거(Gate HOLD 재평가),
lineage 고정(revision 스코프). 검사되지 않음: committed Stage(위 질문 4),
저장된 directive(파생으로 대체 — v1 확정 표시), HOLD decision의 **저장본**
참조(재계산 대체 — Gate decision 미저장은 기존 알려진 한계). §11 HOLD 조건은
8개 중 6개가 blocker로 검사되고, "교정 범위 초과"·"rollback 불가"는 대상
없음(scope drift 탐지·rollback 보류).

### 09 §14 Test Matrix

| 상태 | 행 |
|---|---|
| 덮음 | Implementation(repair packet), Attempts(이전 보존·새 ID), Budget(소진 HOLD), Progress(동일 오류 → HOLD), Verification(Verify-owned 누락 → 코드 수정 없이 재검증), Completion(MISSION COMPLETE 금지 — 구조적), Evidence(차이 누락 — packet은 기록에서만 파생) |
| 부분 | Progress(실패 수 감소 기록 — progress 기록 없음, 재검증 경로만), Evidence(Execute 결과 누락 — Execute Gate blocker로 우회 덮음) |
| 대상 없음 (v1) | Entry 2행(directive — 파생 대체 확정), Classification 2행(spec-gap 분류 미도입 — 사용자가 Brief/Blueprint 경로 사용), Scope, Runtime(resume), Seed 수정 차단, Recursion — 전부 Phase 5·7 보류 |
| Pattern tests | SPINNING만 덮음 — 나머지 4패턴은 ADR-0032 보류 |

### ADR Verification 항목 대조 (0026·0028·0030·0031)

전 항목을 assertion과 대조했다. 이 검토가 잡은 것: ADR-0031 "새 revision이
예산을 리셋"에 테스트가 없었다 → 추가 (0186450). 부분 충족 1건: ADR-0028
"timeout 시 프로세스가 정리된다"는 timed_out 기록까지만 assertion이 있다 —
process group 정리는 코드 경로로만 확인된다(간접 증거: sleep 30이 1초에
반환됨).

## 미완료 항목의 처분

- **observation adapter·not_observed, consensus, lateral, rollback, 세밀
  분류** — ADR-0029·0032 등록 보류 (각 도입 시점 명시).
- **실제 semantic 평가자·runtime adapter** — Phase 5. 판정의 품질은 그때
  처음 검증된다.
- **workspace snapshot/revision 검증** — OPEN_QUESTIONS §5 미결정 유지.
- **canonical Stage 저장** — Phase 6 전 Lifecycle 결정 (질문 4 처분).

## 이번 검토가 잡은 것

1. **ADR-0031 revision 예산 리셋의 테스트 부재** — 추가 (0186450).
2. **Guide 09 §3 directive 저장 요구와 ADR-0031의 충돌 미표시** — 가이드에
   v1 확정 표시로 해소.
3. **exit_conditions 유예 시한(Phase 4) 도래, 처분 없음** — 재평가 수행,
   시한 이동 등록 (ADR-0017 note + ADR-0029).
4. **canonical Stage 저장 부재가 전 Stage의 Entry 조건을 미강제로 만듦,
   미표시** — 알려진 한계 등록 + Phase 6 전 처분 지정.
5. **Verify Gate CLEAR 조건 6건 미검사 미표시** — README 강제되지 않는 것
   표 신설.
