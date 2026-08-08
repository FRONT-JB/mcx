# Recover Stage Guide

> User-facing stage: **Recover**<br>
> Internal/upstream correspondence: **Repair / resilience loop**

| 항목 | 값 |
|---|---|
| 문서 지위 | Draft implementation guide — Accepted canonical corrective Stage |
| 선행 문서 | [Constitution](./00_MISSION_CONTROL.md), [Lifecycle](./02_MISSION_LIFECYCLE.md), [Execute](./07_EXECUTE.md), [Verify](./08_VERIFY.md) |
| 계획된 canonical CLI 명령 | `mcx recover` — 아직 구현된 명령이 아님 |
| 진입 전제 | source `HOLD`, failure evidence, 진입 전에 저장된 RecoveryDirective |
| 성공 의미 | 교정 결과가 Verify에서 다시 검증될 준비가 됨 |
| 실패 의미 | bounded recovery로 해결할 수 없어 HOLD 유지 |

Recover는 Mission Lifecycle이 확정한 다섯 canonical Stage 중 하나이며 정상 성공
경로가 아닌 corrective Stage다. exact serialization과 아래에 명시한 정책 세부만 TBD다.

---

## 1. 목적

Recover는 실패한 미션 전체를 막연히 다시 시도하는 Stage가 아니다. 실패한 조건,
실제 관찰, 이전 시도와 허용 범위를 **새로운 제한적 교정 계약**으로 바꾸는
corrective path다.

```text
source HOLD decision
  → Recovery Policy classifies failure and owner Stage
  → persisted RecoveryDirective(destination = Recover)
  → enter Recover with smallest authorized scope
  → bounded repair assignment
  → new attempt
  → CLEAR — Clear for Verify
```

### Recover가 하지 않는 일

- 실패 원인을 지우고 처음부터 다시 시작하지 않는다.
- 같은 prompt를 무한 반복하지 않는다.
- 실패를 계기로 새로운 기능을 추가하지 않는다.
- 검증 기준을 낮춰 통과시키지 않는다.
- Seed를 조용히 수정하지 않는다.
- 제품 결정을 Flight Controller가 대신하지 않는다.
- 이전 Telemetry를 덮어쓰지 않는다.
- 성공 판정을 직접 선언하지 않는다.

---

## 2. Upstream correspondence

Mission Control의 Recover는 Ouroboros의 Repair와 resilience 철학에서 다음을
참고했다.

- 실패 evidence를 다음 시도의 입력으로 사용한다.
- 반복·진동·무진전 같은 stagnation을 관찰한다.
- 같은 전략의 무한 반복보다 문제 재분류 또는 관점 전환을 선호한다.
- retry는 bounded하다.
- 교정 결과는 다시 evaluation을 거친다.

Ouroboros의 persona rotation, checkpoint rollback, tier escalation, 자동 분해 전체를
v1에 그대로 넣지는 않는다. 먼저 실패 분류, attempt history, bounded repair,
re-verification의 핵심 루프를 검증한다.

---

## 3. Entry Contract

Recover에 진입하려면 다음이 필요하다.

- Mission을 식별할 수 있고 committed current Stage가 Recover다.
- source Stage의 `HOLD` GateDecision이 존재한다.
- HOLD 이유와 evidence reference가 있다.
- 실패한 Acceptance Criterion 또는 정책 조건을 식별할 수 있다.
- source Gate와 Execute/Verify attempt를 추적할 수 있다.
- 정확한 approved Blueprint/Seed revision이 고정되어 있다.
- Recover 전이 전에 저장된 RecoveryDirective가 source Gate/attempt, failure category,
  failed criterion, `destination = Recover`, 허용/금지 scope, capability, budget과
  verification plan을 지정한다.
- failure는 승인된 Blueprint를 바꾸지 않는 bounded implementation/verification
  defect로 분류되었다.

계획된 `mcx recover` command는 source `HOLD`에 대한 Recovery Policy 평가를 요청할
수 있지만 Recover Stage를 직접 강제하지 않는다. eligible한 경우 directive를 먼저
저장하고 전이를 commit한다. directive나 failure evidence가 없으면 source Stage의
`HOLD`를 유지하며 repair를 dispatch하지 않는다.

**v1 확정 (2026-08-08)**: 위 초안의 "저장된 RecoveryDirective" 요구는 채택하지
않았다 — 실패 packet은 이미 durable한 기록(attempt·VerificationRun·verdict)에서
**결정적으로 파생**되며, 파생본을 따로 저장하면 두 진실이 생긴다
([ADR-0031](./adr/0031-recover-v1-failure-and-retry-contract.md) §1). 진입
근거는 Execute/Verify Gate의 `HOLD` 재평가이고, 근거 없는 교정 dispatch는
거부된다(`NothingToRecoverError`·`NoRetryableFailureError`). directive의 저장이
필요해지는 시점(장기 실행 job의 승인 기록 — Phase 7 MCP)에 재평가한다.

---

## 4. Failure taxonomy

Recovery Policy는 이 taxonomy를 Recover 진입 전에 적용한다. Recover 중 새 evidence로
분류가 바뀔 수 있지만, owner가 다른 실패를 Recover work로 계속 처리하지 않는다.

### 4.1 Specification gap

Goal, Constraint, Non-goal, Acceptance Criterion이 누락되거나 충돌한다.

예:

- 인증 정책을 결정하지 않아 구현이 갈린다.
- AC가 관찰할 수 없는 표현이다.
- 두 Constraint가 동시에 만족될 수 없다.

Specification gap은 Recover work가 아니다. source `HOLD`에서 Brief 또는 Blueprint를
destination으로 하는 RecoveryDirective를 저장하고 해당 owner Stage로 직접 route한다.

### 4.2 Implementation failure

명세는 충분하지만 구현이 요구 결과를 만들지 못했다.

예:

- 테스트 실패
- 잘못된 분기
- 누락된 오류 처리
- 기대 artifact 미생성

기본 routing: Recover에서 bounded correction을 수행한 뒤 → Verify.

### 4.3 Verification failure

구현이 아니라 검증 환경, 명령, observation이 잘못되거나 불충분하다.

예:

- 잘못된 working directory
- 필요한 test fixture 누락
- UI를 관찰하지 않고 diff만 사용
- command output이 손실됨

기본 routing: verification policy를 근거와 함께 보완하고 Verify. 코드 수정이
필요하지 않다면 Execute를 거치지 않는다.

### 4.4 Runtime/system failure

작업 내용과 무관하게 Runtime, process, network, resource가 실패한다.

예:

- executable 없음
- timeout
- session handle 손실
- adapter parse error
- disk full

기본 routing: 안전한 재개/재시도가 가능한지 판단하고, 불가능하면 HOLD.

### 4.5 Capability or authority failure

필요한 권한이 없거나 허용 범위를 넘어야만 작업할 수 있다.

기본 routing: 권한을 우회하지 않고 사용자 결정 또는 범위 재설계.

### 4.6 Scope drift or policy violation

Flight Controller가 Non-goal을 구현하거나 허용되지 않은 파일·외부 시스템을
변경했다.

기본 routing: 영향 격리, 변경 검토, 필요하면 복구 가능한 rollback, HOLD.

### 4.7 Stagnation

실패 유형은 달라 보이지만 실질적인 진전이 없다.

후보 패턴:

- 같은 오류 또는 동일 결과 반복
- A와 B 상태의 진동
- 변경은 있으나 실패 조건은 그대로
- 개선 폭이 계속 줄어듦

정확한 탐지 식과 threshold는 실행 이력을 수집한 뒤 ADR에서 결정한다.

**v1 확정 (2026-08-08)**: 첫 slice는 "같은 오류 반복"만 탐지한다 — 같은 AC의
연속 실패에서 오류 해시가 **3회** 동일하면 재시도를 중단하고 `HOLD`한다
(`upstream 관측` — SPINNING 임계 채택,
[REPAIR_UPSTREAM_FINDINGS §4](./research/REPAIR_UPSTREAM_FINDINGS.md)).
나머지 세 패턴(진동·무진전·수확 체감)은 실행 이력 축적 후 도입한다
([ADR-0031](./adr/0031-recover-v1-failure-and-retry-contract.md) §3,
[ADR-0032](./adr/0032-recover-deliberate-divergences.md) 보류).

---

## 5. Recovery routing

다음 표는 v1 baseline이다. 정확한 state enum과 자동 전이는
[Mission Lifecycle](./02_MISSION_LIFECYCLE.md)이 소유한다.

| 진단 | 정책 또는 Recover action | destination |
|---|---|---|
| 사용자 제품 결정 누락 | Recover 진입 금지, source `HOLD`에서 사용자 결정 요청 | Brief |
| Seed/AC 모순 | Recover 진입 금지, 새 Blueprint revision 요구 | Blueprint |
| 구현 결함 | 최소 수정 범위의 repair assignment를 Recover에서 실행 | Verify |
| mechanical failure | 재현 명령과 오류를 repair assignment에 포함해 교정 | Verify |
| semantic AC failure | observed/expected 차이를 포함해 교정 | Verify |
| Execute/Recover 결과·Telemetry 누락 | 필요한 evidence를 생산할 owner Stage로 직접 route | Execute 또는 Recover |
| Verify observation/check evidence 누락 | 코드 repair 없이 evidence-only attempt | Verify |
| Runtime transient failure | 부작용 안전성을 확인한 뒤 해당 attempt owner에서 새 attempt | Execute 또는 Recover |
| capability 부족 | 자동 권한 확대 금지, compatible Runtime 또는 사용자 결정 요청 | source/current Stage `HOLD` |
| scope drift | 변경 격리 및 승인된 범위 회복 | Verify |
| stagnation | 문제를 재분류하거나 더 작은 범위/다른 전략 제안 | 정책 판정 후 해당 Stage |

Recover는 자신에게 배정된 bounded correction만 수행한다. owner가 Brief, Blueprint,
Execute 또는 Verify인 항목은 source `HOLD`와 persisted directive로 직접 route하며,
Recover가 자동으로 Blueprint를 변경하지 않는다.

---

## 6. Recovery packet

Recover가 Flight Controller에 전달하는 정보는 “다시 해라”보다 구체적이어야 한다.

**v1 확정 (2026-08-08)**: packet의 축은 lineage(mission·revision·AC), 실패
원천 4종(실행 실패/mechanical 실패/semantic 불충족/escalation 대기), 결정적
분류(`BLOCKED`·`STALL`·미분류), 오류 발췌, 증거 참조, 소진 시도 수다
([ADR-0031](./adr/0031-recover-v1-failure-and-retry-contract.md) §1~§3 —
upstream 6종 분류 중 verifier 증거 계약이 필요한 것들은
[ADR-0032](./adr/0032-recover-deliberate-divergences.md) 보류). 아래 목록의
정확한 필드 이름은 구현 slice에서 이 목록과 대조해 확정한다.

```text
mission identity
approved seed revision
recovery directive identity
source HOLD decision
source attempt identities
failed criterion or gate condition
expected behavior
observed behavior
reproduction steps
mechanical error output
evidence references
previous attempt summaries
allowed files and tools
forbidden scope
repair objective
required re-verification
attempt budget
```

### 예시

```text
Repair objective:
  AC-04 "작성 실패 시 오류가 표시된다"를 만족시킨다.

Observed:
  API 오류 뒤 error state는 설정되지만 UI에 렌더링되지 않는다.

Evidence:
  TEST-17 failed: expected alert text, received none.

Allowed scope:
  CommentForm component and its tests.

Forbidden:
  API contract 변경, 새 상태관리 라이브러리, 다른 기능 리팩터링.

Re-verify:
  TEST-17, related CommentForm tests, AC-04 semantic observation.
```

---

## 7. Capability Contract

Recover의 capability는 실패 원인과 최소 수정 범위에서 파생한다.

### 기본 원칙

- 이전 Execute보다 넓은 권한을 자동 상속하지 않는다.
- 실패와 관련된 파일 범위만 write scope로 연다.
- reproduction과 re-verification에 필요한 명령만 허용한다.
- Git push, 배포, 외부 메시지 등은 별도 승인 없이는 금지한다.
- Mission state와 Seed 파일을 worker가 직접 변경하지 못하게 한다.
- Mission Control 재귀 호출을 금지한다.

Specification gap은 파일 수정 capability로 해결하지 않는다. 사용자 또는
Blueprint 결정이 먼저다.

---

## 8. Attempt and budget model

각 Recover 실행은 새 attempt다.

```text
failure_id
  ├─ source_execute_attempt
  ├─ source_verify_attempt
  └─ recover_attempts
       ├─ R1
       ├─ R2
       └─ ... bounded
```

### MUST rules

- attempt 번호와 부모 실패를 기록한다.
- 이전 attempt의 input, output, evidence를 보존한다.
- 새로운 attempt가 무엇을 다르게 하는지 기록한다.
- retry budget을 무한대로 두지 않는다.
- budget 소진 전에 progress를 평가한다.
- 소진되면 `HOLD`하고 필요한 사용자 결정을 제시한다.

**v1 확정 (2026-08-08)**: 예산은 **AC당 교정 재시도 2회**(`upstream 관측` —
`ac_retry_attempts` 기본값,
[VERIFY_UPSTREAM_FINDINGS §2](./research/VERIFY_UPSTREAM_FINDINGS.md))이고,
새 Blueprint revision이 승인되면 리셋된다. 재시도 요청에는 실패 분류와
마지막 오류 tail이 실리며 **마지막 시도에는 접근 전환 지시**가 붙는다
(`upstream 관측` — 재시도 프롬프트 3요소,
[REPAIR_UPSTREAM_FINDINGS §3](./research/REPAIR_UPSTREAM_FINDINGS.md)).
계약은 [ADR-0031](./adr/0031-recover-v1-failure-and-retry-contract.md)
§4~§5가 고정한다.

### Progress signal 후보

- 실패 테스트 수 감소
- 충족된 AC 수 증가
- 동일 오류 signature 제거
- drift 감소
- 관찰 불가능 상태가 관찰 가능 상태로 변함
- 수정 범위 축소

파일 변경량 자체는 progress가 아니다.

---

## 9. Strategy change

동일 실패가 반복되면 더 강하게 같은 지시를 하는 대신 전략을 바꾼다.

가능한 방향:

- **Simplify**: 실패한 조건을 더 작은 재현으로 축소
- **Research**: 누락된 저장소 사실이나 외부 계약 조사
- **Reframe**: failure taxonomy가 잘못되었는지 재분류
- **Architectural check**: 국소 수정으로 해결할 수 없는 구조 문제 확인
- **Contradiction check**: Seed의 충돌 또는 잘못된 가정 확인

이것은 새로운 기능을 발명하는 persona parade가 아니다. 실패와 직접 연결된 하나의
관점만 선택하고, 선택 이유와 기대 progress signal을 기록한다.

---

## 10. Normal sequence

```mermaid
sequenceDiagram
    participant MC as Mission Control
    participant ST as Mission State
    participant RA as Runtime Adapter
    participant FC as Flight Controller

    MC->>ST: Read source HOLD + evidence + attempts
    MC->>MC: Classify failure and identify owner Stage
    alt owner is Brief/Blueprint/evidence producer
        MC->>ST: Persist directive and route directly; do not enter Recover
    else bounded correction is eligible
        MC->>ST: Persist directive(destination=Recover), then enter Recover
        MC->>ST: Re-read and validate directive + approved revision
        MC->>MC: Build recovery packet from directive
        MC->>RA: Dispatch new recover attempt
        RA->>FC: Invoke bounded corrective work
        FC-->>RA: Result + Telemetry
        RA-->>MC: Normalized events
        MC->>ST: Persist attempt and progress signals
        MC->>ST: CLEAR to Verify or HOLD with a new directive
    end
```

### Detailed steps

1. source HOLD, failure evidence와 attempt history를 읽는다.
2. Recovery Policy가 failure owner와 Recover eligibility를 판정한다.
3. owner가 Brief/Blueprint/evidence producer면 directive를 저장하고 직접 route한다.
4. Recover가 eligible하면 `destination = Recover` directive를 먼저 저장하고 전이한다.
5. Recover entry에서 directive, approved revision, capability와 budget을 다시 검증한다.
6. recovery packet을 만들고 새 attempt를 지속한 뒤 dispatch한다.
7. 결과와 Telemetry를 보존하고 progress signal을 평가한다.
8. Verify 가능한 결과면 `CLEAR — Clear for Verify`를 기록한다.
9. 그렇지 않으면 Recover `HOLD`와 필요한 새 RecoveryDirective를 기록한다.

---

## 11. Recover Gate semantics

Recover 자체는 `MISSION COMPLETE`를 선언하지 않는다.

### `CLEAR`의 의미

Recover의 `CLEAR`는 교정 작업이 성공했다고 최종 승인하는 것이 아니다. 다음
Stage가 검증할 수 있는 결과와 evidence가 준비되었다는 뜻이다.

허용되는 표현:

```text
CLEAR — Clear for Verify
```

Recover `CLEAR`는 항상 Verify로 진행한다. 교정 과정에서 실행을 새로 구성하거나
Brief/Blueprint 결정이 필요해졌다면 `CLEAR`로 우회하지 않고, source `HOLD`와
RecoveryDirective를 가진 corrective routing을 기록한다.

### `HOLD`

다음 중 하나면 HOLD를 유지한다.

- failure evidence가 불충분하다.
- 사용자 제품 결정이 필요하다.
- Seed revision이 필요하다.
- capability 또는 권한이 부족하다.
- retry budget이 소진되었다.
- 동일 실패가 반복되고 progress가 없다.
- 교정 범위가 원래 Mission 범위를 넘어간다.
- 안전하게 rollback하거나 재현할 수 없다.

HOLD는 반드시 지금까지 시도한 것, 실패가 반복된 이유, 남은 선택지와 영향을
보여준다.

---

## 12. Telemetry

Recover attempt는 최소한 다음을 기록한다.

- source HOLD decision
- source failure and evidence references
- failure classification
- selected routing and reason
- parent attempts
- retry budget before/after
- repair objective and scope
- capabilities granted
- Runtime/session handle
- changed artifacts and command results
- progress signals
- newly introduced failures
- next recommended Stage

요약은 원본 evidence를 대체하지 않는다.

---

## 13. CLI experience

```text
$ mcx recover

Mission: <mission id>
Stage: RECOVER
Failure: <failed criterion or gate condition>
Classification: <failure class>
Attempt: <current>/<budget>

Preparing bounded corrective work...
Allowed scope: <scope summary>
Re-verification: <required checks>

CLEAR — Clear for Verify
Next: mcx verify
```

사용자 결정이 필요한 예시:

```text
HOLD — Product decision required

Conflict:
  The approved Blueprint does not define who may delete a comment.

Why recovery stopped:
  A Flight Controller cannot choose product policy.

Next action:
  Return to Brief and record the decision.
```

확정된 command 외의 옵션은 정의하지 않는다.

---

## 14. Test matrix

| 영역 | 시나리오 | 기대 결과 |
|---|---|---|
| Entry | persisted RecoveryDirective 없음 | Recover 진입·repair dispatch 금지, source HOLD 유지 |
| Entry | directive destination이 Recover가 아님 | 지정 owner Stage로 직접 route |
| Classification | 제품 결정 누락 | Recover 진입 없이 Brief routing |
| Classification | AC 모순 | Recover 진입 없이 Blueprint revision 요구 |
| Implementation | 단일 실패 테스트 | 해당 scope의 repair packet 생성 |
| Scope | worker가 관련 없는 파일 변경 | policy violation과 HOLD |
| Evidence | observed/expected 차이 누락 | recovery 시작 금지 |
| Attempts | 새 retry | 이전 attempt 보존, 새 ID 생성 |
| Budget | budget 소진 | 추가 dispatch 없이 HOLD |
| Progress | 동일 오류 반복 | strategy change 또는 HOLD |
| Progress | 실패 수 감소 | progress 기록 후 재검증 |
| Runtime | transient timeout 후 resume 가능 | 새 중복 작업보다 resume 정책 사용 |
| Evidence | Execute/Recover 결과 누락 | evidence owner Stage로 route |
| Verification | Verify-owned evidence만 누락 | 코드 수정 없이 Verify observation 재실행 |
| Seed | worker가 Seed 수정 시도 | 차단하고 revision workflow 요구 |
| Completion | repair 성공 보고 | MISSION COMPLETE 금지, Verify 필요 |
| Recursion | worker가 Mission Control 호출 | 차단하고 policy violation 기록 |

### Pattern tests

- 같은 오류 signature가 연속 반복됨
- A/B 접근이 번갈아 같은 실패로 돌아옴
- 파일은 계속 바뀌지만 AC verdict는 동일함
- 하나의 AC 수정이 이미 통과한 AC를 깨뜨림
- 잘못된 failure classification을 evidence로 재분류함

---

## 15. Implementation slices

### Slice 1 — Failure packet

- Verify fixture에서 failure packet을 생성한다.
- evidence가 없으면 생성이 실패하는지 테스트한다.

### Slice 2 — Deterministic classifier

- Recovery Policy에서 specification, implementation, verification, runtime, authority
  분류와 owner Stage routing을 구현한다.
- 모호한 경우 자동 수정보다 HOLD를 선택한다.

### Slice 3 — Attempt history and budget

- 부모 attempt와 새 recover attempt를 연결한다.
- budget 소진과 no-progress를 테스트한다.

### Slice 4 — Fake repair runtime

- 수정 성공, 동일 실패, 새 실패를 재현한다.
- progress signal과 routing을 테스트한다.

### Slice 5 — `mcx recover`

- Core application boundary를 호출한다.
- failure, scope, attempt, next action을 표시한다.
- CLI 자체에서 prompt나 retry를 관리하지 않는다.

---

## 16. Implementation checklist

- [ ] failure taxonomy를 정의했다.
- [ ] HOLD decision을 recovery input으로 연결했다.
- [ ] Recover 진입 전에 RecoveryDirective를 durable하게 저장한다.
- [ ] directive destination이 Recover가 아니면 repair를 dispatch하지 않는다.
- [ ] 제품 결정 누락을 코드 수정으로 해결하지 않는다.
- [ ] Seed revision 필요성을 감지한다.
- [ ] recovery packet schema를 정의했다.
- [ ] 최소 capability와 file scope를 계산한다.
- [ ] parent/child attempt를 보존한다.
- [ ] retry budget을 정의했다.
- [ ] progress signal을 정의했다.
- [ ] 동일 실패와 진동을 탐지할 수 있다.
- [ ] strategy change가 failure evidence와 연결된다.
- [ ] Runtime/system failure와 AC failure를 분리했다.
- [ ] Recover가 MISSION COMPLETE를 선언하지 않는다.
- [ ] 재검증 routing을 테스트했다.
- [ ] recursion guard를 테스트했다.
- [ ] upstream 관찰을 research 문서에 기록했다.
- [ ] 의도적 차이를 Stage의 divergence ADR에 등록했다. 확인하지 못한
      항목은 미확인으로 같은 곳에 적었다.

---

## 17. Learning questions

1. 왜 실패는 버릴 로그가 아니라 다음 시도의 입력인가?
2. “다시 잘해”와 bounded recovery packet의 차이는 무엇인가?
3. 제품 결정 누락을 코드 수정으로 처리하면 어떤 drift가 생기는가?
4. 파일 변경량이 progress가 아닌 이유는 무엇인가?
5. 동일 실패 반복과 A/B 진동은 어떻게 다른가?
6. retry budget이 없으면 시스템이 왜 안전하지 않은가?
7. Runtime timeout과 semantic AC failure는 왜 다른 routing을 가져야 하는가?
8. Recover가 직접 MISSION COMPLETE를 선언하면 어떤 책임 경계가 깨지는가?

---

## 18. Open decisions

- accepted Recover Stage와 RecoveryDirective의 exact serialization/storage schema
- failure taxonomy의 canonical enum과 classifier schema
- retry/no-progress budget의 단위, 기본값과 progress threshold

Recover가 canonical corrective Stage라는 결정과 Recover `CLEAR`가 항상 Verify로
간다는 의미는 확정되었다. 위 세부사항은 실제 failure fixture와 Lifecycle transition
tests를 근거로 확정한다.

---

## Exit statement

Recover의 성공은 실패가 사라졌다는 자기 보고가 아니다.

> **The failure has been converted into the smallest authorized corrective
> action. A CLEAR result is durable and ready for Verify; otherwise HOLD names
> the explicit human or policy decision still required.**
