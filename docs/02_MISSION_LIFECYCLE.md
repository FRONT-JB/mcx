# Mission Lifecycle and Gate Policy

> **Model proposes. Workflow constrains. Telemetry proves. Gate decides.**

| 항목 | 값 |
|---|---|
| 문서 지위 | Active Draft — v1 최소 상태 머신 기준 |
| 상위 규범 | [`00_MISSION_CONTROL.md`](./00_MISSION_CONTROL.md) |
| 아키텍처 | [`01_ARCHITECTURE.md`](./01_ARCHITECTURE.md) |
| Stage Guide | [`05_BRIEF.md`](./05_BRIEF.md), [`06_BLUEPRINT.md`](./06_BLUEPRINT.md), [`07_EXECUTE.md`](./07_EXECUTE.md), [`08_VERIFY.md`](./08_VERIFY.md), [`09_RECOVER.md`](./09_RECOVER.md) |
| 적용 범위 | 한 Mission의 생성부터 `MISSION COMPLETE`까지 |
| 최종 갱신일 | 2026-08-07 |

이 문서는 Mission Control의 canonical Stage, Gate 의미, attempt lineage, 정상 전이와
policy-directed Recover routing을 정의한다. 각 Stage의 prompt, tool allowlist,
quality threshold와 구체 schema는 Stage Guide가 소유한다.

---

## 1. 결정 상태 표기

| 표기 | 의미 |
|---|---|
| **NORMATIVE** | v1 구현과 테스트가 지켜야 하는 생명주기 규칙 |
| **PROPOSED** | 의미는 유용하지만 구현 전 ADR/검증이 필요한 제안 |
| **TBD** | 수치, enum, UX 등 아직 결정할 근거가 부족한 항목 |
| **EXAMPLE** | 계약 설명용 예시; 실제 schema나 문구를 고정하지 않음 |

Constitution과 충돌하는 전이는 이 문서에 있더라도 무효다. 반대로 구현이 이
문서와 다르면 구현을 정답으로 간주하지 않고 문서 또는 구현을 명시적으로
교정한다.

---

## 2. Lifecycle이 답해야 하는 질문

이 상태 머신은 매 순간 다음 질문에 답할 수 있어야 한다.

- 현재 Mission의 Stage는 무엇인가?
- 현재 Stage에 들어올 때 사용한 입력 revision은 무엇인가?
- 어떤 attempt가 실행 중이거나 닫혔는가?
- 마지막 Gate는 왜 `CLEAR` 또는 `HOLD`였는가?
- 그 결정은 어떤 Telemetry와 policy version을 사용했는가?
- 진행을 막는 질문, 실패, 권한 또는 evidence gap은 무엇인가?
- Recover 중이라면 어떤 실패를 어떤 범위에서 교정하는가?
- 다음으로 허용된 행동과 금지된 행동은 무엇인가?
- 새 host/session이 이어받아도 같은 결정을 설명할 수 있는가?

답이 대화 memory나 Runtime session에만 있으면 canonical lifecycle로 간주하지 않는다.

---

## 3. Canonical Concepts

### 3.1 Mission — NORMATIVE

Mission은 하나의 승인 가능한 Goal을 Brief부터 최종 검증까지 추적하는 단위다.
Mission은 최소한 identity, current Stage, state version, active input revisions,
attempt lineage, GateDecision과 Telemetry reference를 가진다.

> **구현 시점 (2026-08-08,
> [ADR-0037](adr/0037-mission-record-and-canonical-stage.md)).** current
> Stage를 포함한 Mission record는 합성 계층(Phase 6 CLI) 소유로 도입한다.
> 저장된 Stage는 표시·resume·stall 탐지용이며, Stage 진입의 실질 보증은 각
> 진입의 Gate 재계산이다 — 둘이 어긋나면 Gate가 이긴다 (upstream 정렬:
> [CLI_UPSTREAM_FINDINGS §4](research/CLI_UPSTREAM_FINDINGS.md)).

### 3.2 Stage — NORMATIVE

Stage는 책임, 입력, 종료 조건과 capability가 분리된 구간이다.

| 사용자 용어 | 내부 대응 | canonical 역할 |
|---|---|---|
| Brief | Interview | 목표·제약·비범위·성공 조건의 모호함 제거 |
| Blueprint | Seed | 승인 가능한 불변 실행 명세 생성 |
| Execute | Run | 승인된 명세에 대한 bounded work 수행 |
| Verify | Evaluate | 결과를 기준과 evidence로 판정 |
| Recover | Repair | 실패 evidence 기반의 제한적 교정 |

`MISSION COMPLETE`는 Stage가 아니라 Verify Gate가 선언하는 terminal mission
status다.

### 3.3 GateDecision — NORMATIVE

GateDecision은 한 Stage가 진행 조건을 만족하는지 평가한 durable policy record다.
결과 값은 오직 `CLEAR`와 `HOLD`다.

- `CLEAR`: 현재 Stage의 Exit Contract를 충족해 지정된 목적지로 진행 가능
- `HOLD`: 현재 evidence와 권한으로는 진행 불가; 보완이나 control decision 필요

Gate는 attempt의 process exit code나 모델의 자연어 판단과 다르다.

### 3.4 Attempt — NORMATIVE

Attempt는 **고정된 입력 snapshot과 bounded scope로 수행한 하나의 식별 가능한
시도**다. 같은 지시를 다시 실행해도 새 attempt다. 닫힌 attempt의 입력, 결과,
Telemetry를 덮어쓰지 않는다.

### 3.5 RecoveryDirective — NORMATIVE concept

RecoveryDirective는 `HOLD`의 실패 evidence를 다음 corrective action으로 변환하는
정책 record다. `HOLD` 자체가 목적지를 선택하지 않는다. Recover 진입, 같은 Stage의
새 attempt, 이전 Stage로의 specification correction은 별도 directive가 권한을
부여한다.

이 분리는 다음 두 사실을 동시에 지킨다.

1. `HOLD`는 forward progression의 승인이 아니다.
2. `HOLD`에서 아무 행동도 못 하는 것이 아니라, 기록된 정책으로 교정 경로를
   선택할 수 있다.

### 3.6 Stage activation — PROPOSED representation

한 Stage에 들어와 `CLEAR`로 나가거나 corrective route로 떠날 때까지의 점유 구간을
Stage activation으로 표현할 수 있다. 같은 Mission이 Blueprint 또는 Verify에 다시
돌아오면 새 activation이다. 이 개념은 이력 설명에 유용하지만 정확한 타입명과
저장 schema는 TBD다.

---

## 4. State Dimensions

하나의 거대한 상태 enum으로 모든 경우를 표현하지 않는다. 다음 축을 분리하는
것이 의미상 기준이다.

### 4.1 Current Stage — NORMATIVE

```text
BRIEF | BLUEPRINT | EXECUTE | VERIFY | RECOVER
```

문서의 대문자 값은 개념 값이다. Python enum 이름을 확정하는 것은 아니다.

### 4.2 Mission status — NORMATIVE minimum

```text
ACTIVE | COMPLETE
```

- `ACTIVE`: 어떤 Stage에 있으며 아직 최종 완료되지 않음
- `COMPLETE`: Verify Gate가 `MISSION COMPLETE`를 선언한 terminal 상태

`FAILED`, `CANCELLED`, `ARCHIVED` 같은 terminal status는 아직 정의하지 않는다.
회복 불가능하거나 사용자 결정을 기다리는 경우도 근거 없이 `FAILED`로 끝내지 않고
현재 Stage에서 `HOLD`한다.

### 4.3 Pause overlay — PROPOSED

운영 중단과 품질 판정을 구분하기 위해 `PAUSED`를 Stage나 Gate 결과가 아닌 control
overlay로 두는 안을 권장한다. 자세한 의미는 [12. Pause and Resume](#12-pause-and-resume--proposed)를
따른다. v1 필수 포함 여부는 TBD다.

### 4.4 Attempt outcome과 Gate result의 분리 — NORMATIVE

Attempt는 성공적으로 process를 종료해도 Gate가 `HOLD`일 수 있다. 반대로 한 attempt가
실패했어도 이전/후속 evidence를 종합한 Stage Gate가 나중에 `CLEAR`일 수 있다.

```text
attempt outcome ≠ GateDecision ≠ mission status
```

구체 attempt outcome enum은 TBD지만 최소한 정상 결과, 실패, 중단/취소, 결과 불명
상태를 구분할 수 있어야 한다.

---

## 5. Success Path

모든 성공 Mission의 전진 경로는 다음과 같다.

```mermaid
flowchart LR
    C["Mission Created"] --> B["Brief / Interview"]
    B -->|"CLEAR — Clear for Blueprint"| P["Blueprint / Seed"]
    P -->|"CLEAR — Clear for Execute"| E["Execute / Run"]
    E -->|"CLEAR — Clear for Verify"| V["Verify / Evaluate"]
    V -->|"CLEAR — MISSION COMPLETE"| D["COMPLETE"]
```

Recover는 위 직선 경로의 마지막 Stage가 아니다. `HOLD`와 failure evidence가 있고
정책이 bounded correction이 가능하다고 판단할 때만 진입하는 corrective path다.

### 5.1 Mission creation — NORMATIVE

Mission creation은 이전 Stage에서의 전이가 아니라 lifecycle 시작 event다. 생성 시
current Stage는 Brief이며, 초기 user intent와 provenance가 durable하게 연결되어야
한다. 생성만으로 Brief Gate가 평가되거나 `CLEAR`되지 않는다.

### 5.2 Forward progression — NORMATIVE

정상 방향의 Stage 변경은 source Stage의 `CLEAR`가 있어야 한다. `HOLD`, runtime
success, 사용자 침묵, 모델 확신은 forward progression을 허가하지 않는다.

### 5.3 Completion — NORMATIVE

오직 Verify Gate만 `CLEAR — MISSION COMPLETE`를 기록할 수 있다. Execute 또는 Recover
결과가 완벽해 보이더라도 먼저 Verify entry/exit contract를 충족해야 한다.

---

## 6. Stage Entry and Exit Contracts

이 절은 최소 계약을 정한다. 세부 질문 전략과 tool restriction은 해당 Stage Guide가
구체화하되 이 계약을 약화할 수 없다.

### 6.1 Brief (Interview)

#### Entry — NORMATIVE

- user intent 또는 문제 설명이 존재한다.
- 조사 가능한 대상과 현재 권한의 provenance를 알고 있다.
- 이전 Stage는 없다. 요구사항 교정으로 복귀한 경우에는 복귀를 유발한 failure와
  downstream invalidation 정보가 있다.

#### Permitted work

- 목표, 제약, Non-goal, 성공 조건, unresolved decision을 식별한다.
- 필요한 최소 질문을 생성하고 사용자 답변/관찰/가정을 출처와 함께 축적한다.
- clarity/ambiguity를 평가하되 구현을 시작하지 않는다.

#### Exit evidence — NORMATIVE

- Goal
- Constraints
- Non-goals
- 검증 가능한 성공 조건
- unresolved decisions가 없거나 명시적으로 blocker가 아님을 설명한 기록
- 중요한 사실과 제품 결정의 provenance
- **사용자의 진행 승인**

#### Gate

- `CLEAR` → Blueprint
- `HOLD` → Brief 유지; 부족한 질문, 충돌 또는 승인 조건을 제시

질문 횟수, 토큰 사용량, 모델의 “충분하다”는 의견만으로 `CLEAR`할 수 없다.

### 6.2 Blueprint (Seed)

#### Entry — NORMATIVE

- Brief Gate의 `CLEAR`와 해당 evidence reference가 있다.
- 입력 Brief revision/snapshot이 고정되어 있다.
- 해결되지 않은 제품 결정을 몰래 구현 선택으로 바꾸지 않았다.

#### Permitted work

- Goal, Constraints, Non-goals, Acceptance Criteria, Exit Conditions를 하나의
  reviewable specification으로 구성한다.
- QA, 모순 검사, 검증 가능성 검사를 수행한다.
- 승인 전 revision을 보완한다.

#### Exit evidence — NORMATIVE

- immutable Blueprint revision identifier
- Brief input revision과 추적 관계
- 각 Acceptance Criterion의 관찰/검증 방법
- Constraints와 Non-goals의 검사 방법
- QA 결과와 남은 위험
- 정확한 revision에 대한 사용자의 명시적 승인

#### Gate

- `CLEAR` → Execute, 승인된 revision을 active execution baseline으로 고정
- `HOLD` → Blueprint 유지; 수정/QA/승인 계속

승인 후 내용이 바뀌면 새 revision과 재승인이 필요하다.

### 6.3 Execute (Run)

#### Entry — NORMATIVE

- `CLEAR`된 정확한 Blueprint revision이 있다.
- dispatch가 하나 이상의 Acceptance Criterion과 추적된다.
- scope, allowed files/tools/external actions, budget, Telemetry contract가 명시되었다.
- Runtime이 필수 capability restriction을 실제로 지원하는지 확인했다.
- Recover 후 재실행이면 failure evidence와 허용 교정 범위가 연결되어 있다.

#### Permitted work

- 승인된 Goal과 Constraints 안에서 bounded work를 수행한다.
- 필요한 명령과 변경을 실행하고 원본/정규화 Telemetry를 반환한다.
- 범위 밖 제안은 실행하지 않고 별도 observation으로 남긴다.

#### Exit evidence — NORMATIVE

- dispatch와 attempt identity
- 사용한 Blueprint revision과 capability envelope
- 실제 수행/변경/실패 내역
- 처리되지 않은 runtime 또는 command error
- Verify가 검사할 결과/artifact와 필수 Telemetry
- Acceptance Criterion과 결과의 추적 관계

#### Gate

- `CLEAR` → Verify
- `HOLD` → 현재 근거로 Verify 진입 불가; 정책이 retry, Recover, specification
  correction 또는 operator action을 선택

Execute `CLEAR`는 구현의 최종 적합성을 보증하지 않는다.

### 6.4 Verify (Evaluate)

#### Entry — NORMATIVE

- Execute 또는 Recover Gate의 `CLEAR — Clear for Verify`가 있다.
- source GateDecision과 그 결정이 참조한 Execute/Recover attempt가 식별된다.
- 검증 대상 Blueprint revision과 source attempt 결과가 정확히 연결된다.
- 검증에 필요한 workspace/artifact 상태를 식별할 수 있다.
- 평가 주체가 작업 수행 주체와 동일하더라도 자기 보고를 독립 evidence로 사용하지
  않는 분리된 Gate policy가 있다.

#### Permitted work

1. mechanical verification: lint, typecheck, build, test, 실행 관찰
2. semantic verification: Goal, AC, Constraints, Non-goals와 대조
3. risk-based escalation: ambiguity나 위험이 실제로 있을 때만 추가 평가

#### Exit evidence — NORMATIVE

- 각 필수 Acceptance Criterion의 pass/fail/insufficient-evidence 판정
- 각 판정과 원본 evidence reference의 연결
- mechanical check의 실제 명령/결과 또는 실행하지 못한 이유
- Constraints/Non-goals의 위반 여부
- scope drift, 미해결 위험, evidence gap
- 실패 시 Recovery Policy가 사용할 구조화된 failure report

#### Gate

- 모든 필수 조건 충족: `CLEAR — MISSION COMPLETE`
- 하나라도 실패/불충분: `HOLD`; 완료 금지, corrective routing 평가

### 6.5 Recover (Repair)

#### Entry — NORMATIVE

- source Stage의 `HOLD` GateDecision이 있다.
- 실패 category와 원본 Telemetry가 있다.
- current Stage를 Recover로 바꾸기 전에 durable하게 저장된 RecoveryDirective가
  source attempt, 목표 criterion, 허용 수정 범위, budget과 `destination = Recover`를
  지정한다.
- specification correction이 필요한 상황을 구현 결함으로 위장하지 않는다.

source failure가 이미 specification gap으로 분류되었다면 Recover를 활성화하지 않고
RecoveryDirective를 통해 Brief 또는 Blueprint로 직접 route한다.

#### Permitted work

- 실패와 직접 관련된 bounded correction
- directive가 요구한 mechanical check와 Telemetry 수집
- 새롭게 발견한 specification/security blocker 보고

#### Exit evidence — NORMATIVE

- recovery attempt와 source failure/attempt의 lineage
- 실제 교정 내용과 변경 범위
- directive 범위 준수 여부
- 재검증해야 할 criteria와 실행한 사전 검사
- 새 실패 또는 unresolved blocker

#### Gate

- 교정 결과가 Verify 가능한 상태: `CLEAR — Clear for Verify` → Verify
- 교정 자체가 실패/불충분: `HOLD` → Recovery Policy 재평가

Recover `CLEAR`는 failure가 해결되었다는 최종 판정이 아니다. 반드시 Verify가 같은
Blueprint revision을 기준으로 다시 확인한다.

---

## 7. Gate Semantics

### 7.1 Gate evaluation order — NORMATIVE

Gate는 최소한 다음 순서로 fail closed 평가한다.

1. **Identity and freshness**: mission, Stage, state version, input revision이 현재와 일치
2. **Entry contract**: source Stage가 합법적으로 시작되었는지 확인
3. **Evidence integrity**: 필수 Telemetry가 존재하고 읽히며 provenance가 유효
4. **Exit contract**: Stage별 필수 산출물과 조건 평가
5. **Scope/security**: 범위 이탈, 권한 위반, secret/security blocker 평가
6. **Approval**: 필요한 사용자/정책 승인이 정확한 revision에 연결됨
7. **Decision**: 이유, evidence refs, policy version, 목적지를 durable하게 기록

상위 단계에서 `HOLD`가 확정되면 후속 의미 평가가 이를 `CLEAR`로 뒤집지 않는다.
추가 evidence로 재평가하려면 새 GateDecision을 만든다.

### 7.2 `CLEAR` contract — NORMATIVE

모든 `CLEAR`는 최소한 다음 정보를 가져야 한다.

```text
mission_id
source_stage
source_activation_or_attempt_refs
decision = CLEAR
reason
evidence_refs
policy_or_schema_version
decided_at
destination
expected_mission_version
```

정확한 field 이름은 TBD다. destination은 source Stage의 허용 전이 중 하나여야 한다.

### 7.3 `HOLD` contract — NORMATIVE

모든 `HOLD`는 최소한 다음을 설명한다.

- 현재 Stage와 관련 attempt
- 진행 불가 이유와 failure category
- 실패, 누락, 충돌하는 evidence reference
- 사용자 결정이 필요한지 여부
- 충족해야 하는 condition 또는 질문
- 권장 next action
- 적용한 policy/schema version

`HOLD`는 terminal failure도, 자동 retry 명령도, 사용자 책임 전가도 아니다.

### 7.4 Gate history — NORMATIVE

새 evidence로 같은 Stage를 재평가할 때 이전 `HOLD`를 수정하지 않는다. 새
GateDecision이 이전 decision을 참조하거나 supersede한다. 과거 시점에서 왜 진행하지
못했는지 계속 설명할 수 있어야 한다.

### 7.5 Gate actor separation — NORMATIVE

Flight Controller의 result에 포함된 `success`, `approved`, `done` 필드는 evidence의
한 부분일 뿐 GateDecision이 아니다. Gate policy는 Mission Control 경계에서 별도로
실행된다. 작업 주체와 동일 모델을 평가에 재사용하더라도 독립 도구 권한, 입력,
policy를 갖는 별도 역할이어야 하며 자기 보고만으로 `CLEAR`할 수 없다.

---

## 8. Attempt Model

### 8.1 Attempt input snapshot — NORMATIVE

Attempt는 시작 시 다음 의미를 고정한다.

- mission과 current Stage/state version
- Stage activation 또는 trigger GateDecision
- Brief/Blueprint 등 적용되는 input revision
- 목표 criterion과 bounded scope
- capability envelope와 budget
- 제공한 prior evidence/failure context
- backend/runtime adapter identity와 지원 capability
- 적용한 policy/prompt/schema version

입력 중 하나가 의미 있게 바뀌면 동일 attempt를 계속하는 대신 새 attempt를 만든다.

### 8.2 Attempt lifecycle — NORMATIVE semantics, enum TBD

Attempt는 최소한 다음 상황을 구분한다.

```text
created → started → result recorded
                    ├─ normal outcome
                    ├─ failed outcome
                    ├─ cancelled/interrupted outcome
                    └─ unknown/partial outcome
```

정확한 상태 이름은 TBD다. process가 사라졌다는 이유만으로 `failed` 또는 `success`를
추정하지 않는다. 결과를 알 수 없으면 partial/unknown과 확보된 Telemetry를 보존한다.

### 8.3 Attempt lineage — NORMATIVE

재시도와 Recover attempt는 최소한 다음 관계를 추적한다.

- 어떤 attempt/Gate/failure가 새 시도를 촉발했는가?
- 같은 input revision을 사용하는가?
- 무엇이 달라졌는가: 지시, scope, runtime, 권한, strategy?
- 이전 실패 중 어떤 것을 해결하려는가?

global ordinal 하나만으로 lineage를 대체하지 않는다. 사용자 표시를 위해 `attempt 3`
같은 번호를 제공할 수 있지만 stable ID와 parent/trigger reference가 기준이다.

### 8.4 Retry semantics — NORMATIVE

- 부작용 가능한 work를 다시 실행하면 항상 새 attempt다.
- 이전 attempt의 Telemetry를 덮어쓰지 않는다.
- 같은 failure fingerprint와 같은 strategy의 반복을 감지할 수 있어야 한다.
- retry budget은 Runtime 내부가 아니라 Recovery Policy가 소유한다.
- adapter는 정책이 모르는 무한 retry를 수행하지 않는다.

adapter가 외부 부작용이 발생하지 않았음을 증명할 수 있는 transport failure만 같은
attempt 안의 retry event로 기록할 수 있다. 부작용이 발생했거나 발생 여부가
불명확하면 같은 attempt에서 재실행하지 않고 partial/unknown 결과를 보존한 뒤 새
attempt 또는 reconciliation 대상으로 취급한다. 허용 횟수와 backoff 값은 TBD다.

### 8.5 Gate와 attempt의 cardinality — NORMATIVE

- 한 Stage Gate는 여러 attempt와 evidence를 참조할 수 있다.
- 한 attempt 결과가 자동으로 하나의 `CLEAR`를 만들지 않는다.
- 한 `HOLD` 이후 evidence-only attempt를 수행하고 같은 Stage를 다시 평가할 수 있다.
- 과거 Blueprint revision의 attempt를 새 revision의 Gate evidence로 재사용하려면
  적용 가능성을 명시적으로 증명해야 하며 기본값은 재사용 금지다.

---

## 9. Transition Table

아래 표는 v1의 canonical transition semantics다. `RecoveryDirective`가 있는 행은
forward progression이 아니라 `HOLD`에서 시작하는 corrective route다.

| Source | Trigger | 추가 조건 | Destination | 의미 |
|---|---|---|---|---|
| — | Mission created | 초기 intent와 provenance 저장 | Brief | lifecycle 시작 |
| Brief | `CLEAR` | clarity contract + user approval | Blueprint | Clear for Blueprint |
| Brief | `HOLD` | 질문/충돌/승인 부족 | Brief | 보완 계속 |
| Blueprint | `CLEAR` | QA + exact revision user approval | Execute | Clear for Execute |
| Blueprint | `HOLD` | 명세/QA/승인 부족 | Blueprint | revision 보완 |
| Execute | `CLEAR` | 결과와 필수 Telemetry 준비 | Verify | Clear for Verify |
| Execute | `HOLD` | Execute-owned evidence 누락 + directive | Execute | evidence-only attempt |
| Execute | `HOLD` | retryable execution failure + directive | Execute | 새 attempt, 동일 baseline |
| Execute | `HOLD` | bounded correction 필요 + directive | Recover | corrective route |
| Execute | `HOLD` | specification gap + directive | Brief 또는 Blueprint | 요구사항/명세 교정 |
| Execute | `HOLD` | 권한·security·budget blocker | Execute | operator action 대기 |
| Verify | `CLEAR` | 모든 필수 AC/Exit 충족 | `COMPLETE` | MISSION COMPLETE |
| Verify | `HOLD` | evidence만 부족 + directive | Verify | 추가 검증 attempt |
| Verify | `HOLD` | 구현 결함 교정 가능 + directive | Recover | bounded correction |
| Verify | `HOLD` | Goal/AC 자체의 gap + directive | Brief 또는 Blueprint | spec correction |
| Verify | `HOLD` | 권한·risk·budget blocker | Verify | operator action 대기 |
| Recover | `CLEAR` | 교정 결과와 Telemetry 준비 | Verify | 반드시 재검증 |
| Recover | `HOLD` | Recover-owned evidence 누락 + directive | Recover | evidence-only attempt |
| Recover | `HOLD` | strategy 변경 여지 + directive | Recover | 새 bounded attempt |
| Recover | `HOLD` | execution을 다시 구성해야 함 + directive | Execute | 새 execution attempt |
| Recover | `HOLD` | specification gap 발견 + directive | Brief 또는 Blueprint | spec correction |
| Recover | `HOLD` | budget/no-progress/security blocker | Recover | operator action 대기 |

### 9.1 금지된 전이 — NORMATIVE

- Brief → Execute 또는 Verify
- Blueprint → Verify
- Execute → `COMPLETE`
- Recover → `COMPLETE`
- `HOLD`만 기록하고 directive 없이 다른 Stage로 이동
- 승인되지 않은 Blueprint revision을 기준으로 Execute/Recover/Verify
- 과거 state version을 기준으로 현재 Stage 덮어쓰기
- Runtime/LLM result가 destination을 직접 commit

### 9.2 Backward route의 선택 기준 — NORMATIVE

Brief와 Blueprint 중 어디로 돌아갈지는 문제의 소유자가 결정한다.

- 사용자 Goal, 제약, Non-goal, 성공 의미가 불명확/변경됨 → **Brief**
- 의미는 명확하지만 실행 명세, AC, 검증 방법, 작업 분해가 잘못됨 → **Blueprint**
- 승인된 명세는 유효하고 구현/검증 결과만 잘못됨 → **Recover** 또는 동일 Stage retry

더 앞 Stage로 보내는 것이 안전하다는 이유만으로 매번 Brief부터 다시 시작하지
않는다. 반대로 specification gap을 코드 수정으로 덮지 않는다.

---

## 10. HOLD Semantics

### 10.1 HOLD는 상태를 숨기지 않는다 — NORMATIVE

`HOLD` 응답은 사용자가 다음 질문에 답할 수 있게 해야 한다.

```text
어디에서 멈췄는가?
왜 진행할 수 없는가?
이미 확인된 것은 무엇인가?
무엇이 부족한가?
누가 어떤 결정을 하거나 어떤 작업을 해야 하는가?
자동 교정이 가능하다면 범위와 남은 budget은 무엇인가?
```

단순한 `something went wrong`, stack trace만 있는 응답, 모델의 긴 추론은 충분한
`HOLD` 설명이 아니다.

### 10.2 HOLD와 current Stage — NORMATIVE

GateDecision 자체는 source Stage를 유지한다. 이어서 다음 중 하나가 발생한다.

1. 사용자가 답변/승인/evidence를 제공해 같은 Stage를 재평가한다.
2. Recovery Policy가 동일 Stage의 새 attempt를 지시한다.
3. RecoveryDirective가 corrective Stage transition을 기록한다.
4. operator action을 기다리며 아무 외부 work도 시작하지 않는다.

따라서 `HOLD`를 기록한 순간과 corrective route를 commit한 순간을 구분할 수 있어야
한다.

### 10.3 HOLD는 실패 횟수와 다르다 — NORMATIVE

질문 하나가 부족해도 `HOLD`일 수 있고, 여러 attempt가 실패해도 새 evidence가
필요해 `HOLD`일 수 있다. Gate 횟수, attempt 횟수, recovery budget을 하나의 counter로
합치지 않는다.

### 10.4 사용자 결정이 필요한 HOLD — NORMATIVE

Goal 또는 권한 같은 사용자 소유 결정을 모델이 대신 선택하지 않는다. 이 경우
recommended options와 영향은 제시할 수 있지만 자동 route나 retry를 시작하지 않는다.
사용자 답변은 provenance와 함께 현재 Brief/Blueprint revision에 반영한다.

---

## 11. Policy-directed Recover Routing

### 11.1 Recover eligibility — NORMATIVE

다음을 모두 만족할 때만 Recover dispatch를 만든다.

- source `HOLD`와 구체 failure evidence가 있다.
- 승인된 Goal/Blueprint를 바꾸지 않고 해결 가능한 실행/검증 결함이다.
- 수정 범위를 실패와 직접 관련된 부분으로 제한할 수 있다.
- 필요한 capability가 승인되어 있고 실제로 강제 가능하다.
- 정책 budget이 남아 있다.
- 같은 전략의 반복이 무진전으로 판정되지 않았다.
- 수정 결과를 다시 Verify할 방법이 있다.

하나라도 충족하지 않으면 Recover를 자동 실행하지 않는다.
특히 specification gap은 Recover work가 아니다. failure owner가 Brief 또는 Blueprint면
source `HOLD`에서 해당 Stage로 직접 route하는 RecoveryDirective를 저장한다.

### 11.2 Routing algorithm — NORMATIVE semantics

```text
1. Validate source HOLD and evidence freshness
2. Classify failure
3. Identify the stage that owns the missing decision or defect
4. Determine whether automatic bounded action is authorized
5. Check capability, security, attempt and progress budgets
6. Create a RecoveryDirective with exact scope and destination
7. Persist the directive before committing any corrective Stage transition
8. If destination is Recover, enter Recover and run a new attempt
9. Record result and re-enter the appropriate Gate
```

분류 confidence가 낮아 목적지가 달라질 수 있으면 안전한 질문/evidence 수집으로
`HOLD`한다. 임의로 가장 강한 Runtime을 호출하지 않는다.

### 11.3 RecoveryDirective minimum meaning — NORMATIVE

정확한 schema는 TBD지만 의미상 다음이 필요하다.

```text
mission_id
source_stage
source_gate_decision
source_attempts_and_evidence
failure_category
failed_criteria
destination_stage
allowed_scope
prohibited_scope
capability_envelope
verification_plan
strategy_identifier
budget_snapshot
policy_version
```

### 11.4 Recover output routing — NORMATIVE

- 정상적인 코드/구성 교정 결과 → Verify
- 작업 분해 또는 실행 자체를 다시 해야 함 → Execute
- AC/Exit Condition의 문제 → Blueprint
- Goal/제약/성공 의미의 문제 → Brief
- 새 권한, security decision, budget 초과 → 현재 Stage `HOLD`, operator action

Recover가 이전보다 많은 기능을 구현했다는 이유로 성공하지 않는다. directive 범위를
벗어나면 scope drift로 `HOLD`한다.

### 11.5 No-progress and oscillation — NORMATIVE

Mission Control은 최소한 다음 징후를 감지할 수 있어야 한다.

- 동일 failure category/criterion/error fingerprint 반복
- 동일 strategy와 동일 scope가 같은 결과를 반환
- A 수정 후 B 실패, B 수정 후 A 실패가 반복되는 진동
- 변경이 없는데 “다시 시도”만 반복
- evidence 양만 늘고 Gate blocker가 줄지 않음

징후가 정책 한계에 도달하면 자동 Recover를 중단하고 `HOLD`한다. 정확한 fingerprint,
진전 점수, 횟수와 시간 budget은 **TBD**이며 upstream 조사와 ADR이 필요하다.

### 11.6 Retry budget — NORMATIVE ownership, value TBD

- budget은 Recovery Policy가 소유한다.
- Runtime/Adapter가 임의로 초기화하거나 숨기지 않는다.
- Stage, failure category, strategy별로 다를 수 있다.
- budget 변경은 사용자 승인 또는 정책 version 변경으로 추적한다.
- 수치를 정하지 않았다는 이유로 무제한 재시도를 허용하지 않는다. 자동 실행을
  시작하기 전 명시적 유한 policy가 필요하다.

---

## 12. Pause and Resume — PROPOSED

이 절 전체는 채택 전 제안이며 v1 규범 계약이 아니다.

Pause는 품질 부족을 뜻하는 `HOLD`와 다른 운영 제어다. 긴 Runtime 작업, host 연결
종료, 사용자 요청에 안전하게 대응하려면 별도 control overlay가 유용하다.

### 12.1 Proposed semantics — PROPOSED

- `pause`는 current Stage와 마지막 GateDecision을 변경하지 않는다.
- pause가 durable하게 기록된 뒤 새 external work/attempt를 시작하지 않는다.
- active Runtime에는 best-effort cancellation을 요청한다.
- cancellation 결과가 불명확하면 attempt를 unknown/partial로 닫고 Telemetry를
  수집한다. 완료나 rollback을 추정하지 않는다.
- `resume`는 persisted state, workspace/artifact 상태, input revision과 capability를
  다시 검증한다.
- 닫힌/불명 attempt를 같은 ID로 이어 쓰지 않고 필요한 경우 새 attempt를 만든다.
- pause 기간 중 Blueprint나 workspace가 바뀌었다면 stale input으로 자동 재개하지
  않는다.

### 12.2 Why not model pause as a Stage — PROPOSED rationale

Pause에는 독립적인 Goal, capability, Gate가 없다. Brief/Execute/Verify 어느 곳에서든
발생할 수 있는 control condition이므로 Stage로 만들면 허용 전이 수만 늘고 의미가
흐려진다.

### 12.3 Why not model pause as HOLD — PROPOSED rationale

`HOLD`는 Stage Exit Contract가 충족되지 않았다는 evidence-backed 판단이다. 사용자가
점심시간 동안 중지한 것은 품질 판정이 아니다. 둘을 합치면 Gate history와 운영
상태가 섞인다.

### 12.4 Decisions required before adoption — TBD

- pause acknowledgement 전에 Runtime cancel 완료를 기다릴지
- pause 요청과 attempt 완료가 경합할 때 commit 순서
- resume 시 workspace drift 검사 방식
- MCP/CLI에서 누가 pause/resume 권한을 갖는지
- `PAUSED`를 mission status enum에 넣을지 별도 control flag/event로 둘지

이 제안이 채택되기 전까지 v1은 안전한 중단을 `HOLD` + operator action으로 표현할
수 있지만, 품질 HOLD와 운영 중단이 섞였음을 문서에 명시해야 한다.

---

## 13. Blueprint Revision and Downstream Invalidation

### 13.1 Revision binding — NORMATIVE

Execute, Verify, Recover attempt는 모두 하나의 정확한 approved Blueprint revision에
연결된다. `latest blueprint` 같은 동적 참조를 사용하지 않는다.

### 13.2 변경 시 규칙 — NORMATIVE

승인된 Blueprint의 의미가 바뀌면 다음 순서를 따른다.

```text
new Brief decision when needed
  → new Blueprint revision
  → QA and approval
  → new Execute attempt
  → Verify
```

과거 실행/검증 evidence는 삭제하지 않지만 새 revision의 완료 증거로 자동 승격하지
않는다.

### 13.3 Editorial vs semantic change — TBD

오탈자나 링크 수정처럼 실행 의미를 바꾸지 않는 변경까지 재실행을 요구할지는
revision policy에서 정한다. 기본 안전값은 **승인 이후 content hash가 바뀌면 새
revision으로 취급**하는 것이다. semantic equivalence 최적화는 근거와 테스트가
있을 때만 추가한다.

### 13.4 Requirement change during Execute/Verify — NORMATIVE

사용자가 요구사항을 바꾸면 현재 attempt를 새 요구사항에 맞춰 몰래 계속하지 않는다.
현재 결과를 보존하고 `HOLD`, 변경 provenance, owner Stage로의 corrective route를
기록한다. 새 승인 revision 없이 다시 Execute하지 않는다.

---

## 14. Failure Categories and Default Routing

정확한 enum 이름은 TBD지만 다음 의미 구분은 NORMATIVE다.

| Failure category | 설명 | 기본 owner/route | 자동 행동 조건 |
|---|---|---|---|
| Specification gap | Goal, 제약, Non-goal, 성공 의미 미정/충돌 | Brief | 사용자 결정 전 자동 수정 금지 |
| Blueprint defect | AC 모순, 검증 불가, 작업 기준 누락 | Blueprint | 새 revision QA/승인 필요 |
| Approval stale/missing | 다른 revision 승인, 승인 provenance 없음 | Blueprint | 자동 승인 금지 |
| Runtime/adapter unavailable | timeout, protocol error, binary/service 없음 | Execute/Recover 동일 Stage | 유한 retry와 무부작용 확인 시만 |
| Unsupported capability | sandbox/path/tool 제한을 Runtime이 강제 못함 | 현재 Stage `HOLD` | 대안 adapter 또는 사용자 risk 결정 |
| Mechanical failure | build/test/command 실패 | Recover | 실패 범위가 제한되고 검증 가능할 때 |
| Acceptance failure | 결과가 AC 미충족 | Recover 또는 Blueprint | AC가 유효하면 Recover |
| Scope drift | Non-goal/허용 path 밖 변경 | Recover 또는 operator action | 안전한 되돌림 권한과 범위 필요 |
| Evidence missing | 필수 결과 없음/읽을 수 없음 | 증거 생산 owner Stage | evidence-only attempt가 가능할 때 |
| Semantic uncertainty | 평가 근거가 충돌하거나 불충분 | Verify 또는 user decision | 조건부 추가 평가만 |
| Permission/security | 권한 부족, secret 노출, injection, 파괴적 행동 | 현재 Stage `HOLD` | 자동 권한 상승 금지 |
| Persistence/conflict | 저장 실패, stale writer, corruption | 현재 Stage 불변 | reconcile 전 진행 금지 |
| Cancelled/unknown result | 중단 또는 외부 부작용 불명 | source Stage `HOLD` | workspace/evidence 재조사 후 결정 |
| No progress/budget exhausted | 반복·진동·한도 도달 | 현재 Stage `HOLD` | operator가 전략/범위 결정 |

### 14.1 Failure classification is evidence — NORMATIVE

분류는 원본 오류를 대체하는 요약이 아니다. source Telemetry와 classifier/policy
version을 함께 보존한다. 분류가 바뀌면 과거 record를 수정하지 않고 새 판단으로
supersede한다.

### 14.2 Multiple failures — NORMATIVE

한 attempt에 여러 category가 있을 수 있다. security/persistence/approval처럼 진행을
막는 상위 blocker를 먼저 해결한다. 여러 결함을 하나의 넓은 Recover dispatch로
합치는 것은 각각이 같은 bounded scope와 verification plan을 공유할 때만 허용한다.

### 14.3 Runtime failure is not criterion failure — NORMATIVE

테스트를 실행하지 못한 것과 테스트가 실패한 것은 다르다. 전자는 runtime/evidence
failure이고 후자는 mechanical/acceptance evidence다. 둘을 구분하지 않으면 잘못된
코드 수정을 반복할 수 있다.

---

## 15. Lifecycle Invariants

아래 조건 중 하나라도 깨지면 상태 머신 구현은 올바르지 않다.

1. 한 Mission의 canonical current Stage는 한 번에 하나다.
2. Mission creation 외 모든 forward Stage 전이는 source Gate의 `CLEAR`를 요구한다.
3. `HOLD`는 forward progression을 허가하지 않는다.
4. corrective Stage 전이는 source `HOLD`와 durable RecoveryDirective를 요구한다.
5. 모든 GateDecision은 evidence reference와 policy/schema version을 가진다.
6. evidence가 없거나 stale/malformed이면 fail closed한다.
7. 승인된 exact Blueprint revision 없이 Execute하지 않는다.
8. Blueprint 변경은 새 revision과 재승인을 요구한다.
9. 모든 Execute/Verify/Recover attempt는 Blueprint revision을 고정한다.
10. Attempt 재실행은 새 identity를 사용하고 이전 기록을 덮어쓰지 않는다.
11. Runtime success와 Execute `CLEAR`, Mission 완료를 구분한다.
12. 작업 주체는 자신의 result로 Gate를 직접 승인하지 않는다.
13. Execute `CLEAR`는 Verify로만 진행한다.
14. Recover `CLEAR`는 Verify로 진행하며 완료를 선언하지 않는다.
15. `MISSION COMPLETE`는 Verify Gate의 `CLEAR`만 선언한다.
16. specification gap을 Recover 코드 수정으로 덮지 않는다.
17. 실패한 criterion과 Recover scope는 추적 가능해야 한다.
18. 자동 retry와 Recover는 유한 policy budget 안에서만 수행한다.
19. 반복/진동/무진전 시 자동 실행을 중단하고 `HOLD`한다.
20. 권한 부족에서 자동 privilege escalation을 하지 않는다.
21. 저장 실패나 version conflict에서 Stage를 메모리로만 진행하지 않는다.
22. 새 host/session이 durable state만으로 현재 blocker와 next action을 설명할 수 있다.

---

## 16. Lifecycle Test Scenarios

아래는 구현 전 상태 전이 테스트로 표현해야 하는 최소 시나리오다.

### 16.1 Success path

| ID | Scenario | Expected |
|---|---|---|
| L-S01 | 명확한 Brief + 사용자 승인 | Brief `CLEAR`, Blueprint 진입 |
| L-S02 | 승인 가능한 Blueprint exact revision | Blueprint `CLEAR`, Execute 진입 |
| L-S03 | bounded Execute 결과와 필수 Telemetry | Execute `CLEAR`, Verify 진입; 미션은 미완료 |
| L-S04 | 모든 AC와 Exit Condition evidence 충족 | Verify `CLEAR`, `MISSION COMPLETE` |

### 16.2 Brief/Blueprint HOLD

| ID | Scenario | Expected |
|---|---|---|
| L-B01 | 질문 횟수는 많지만 Non-goal 미정 | Brief `HOLD` |
| L-B02 | clarity 충분하지만 사용자 승인 없음 | Brief `HOLD` |
| L-B03 | AC가 구현 방식만 말하고 결과를 검증할 수 없음 | Blueprint `HOLD` |
| L-B04 | revision A를 승인한 뒤 revision B로 변경 | B는 미승인, Execute 금지 |
| L-B05 | Execute 중 Goal 변경 | attempt 보존, Brief/Blueprint route, 새 승인 전 실행 금지 |

### 16.3 Execute/Verify separation

| ID | Scenario | Expected |
|---|---|---|
| L-E01 | Runtime이 “완료” 보고, test evidence 없음 | Execute 또는 Verify `HOLD`; 완료 금지 |
| L-E02 | Runtime exit 0, 허용 path 밖 변경 | scope drift `HOLD` |
| L-E03 | 코드 변경 성공, 필수 Telemetry 준비 | Verify로만 진행 |
| L-V01 | mechanical check 실패, semantic evaluator는 긍정 | Verify `HOLD` |
| L-V02 | 모든 test 통과, AC 한 개의 실제 동작 evidence 없음 | Verify `HOLD` |
| L-V03 | 수행자 자기평가만 존재 | Verify `HOLD` |

### 16.4 Recover routing

| ID | Scenario | Expected |
|---|---|---|
| L-R01 | 유효한 AC를 구현이 미충족, 범위 제한 가능 | Verify `HOLD` + RecoverDirective → Recover |
| L-R02 | Recover correction 완료 | Recover `CLEAR` → Verify, 완료 아님 |
| L-R03 | 실패 원인이 AC 모순 | Recover 금지, Blueprint route |
| L-R04 | 실패 원인이 Goal 의미 미정 | Recover 금지, Brief route |
| L-R05 | 동일 전략/오류 반복, budget 소진 | 자동 중단, `HOLD`, operator action |
| L-R06 | A/B 수정이 서로를 계속 깨뜨림 | oscillation 감지, `HOLD` |
| L-R07 | Recover가 unrelated refactor 수행 | scope drift `HOLD` |

### 16.5 Attempt and durability

| ID | Scenario | Expected |
|---|---|---|
| L-A01 | 같은 dispatch 재시도 | 새 attempt ID, 이전 Telemetry 보존 |
| L-A02 | Runtime 완료 후 state save 실패 | Stage 불변, orphan/reconcile evidence 보존 |
| L-A03 | 두 host가 같은 state version으로 전이 | 하나만 commit, 다른 요청 stale/conflict |
| L-A04 | adapter timeout 후 부작용 여부 불명 | unknown/partial attempt, 자동 성공/재실행 금지 |
| L-A05 | 과거 revision의 성공 evidence를 새 Blueprint에 사용 | 기본 거부 또는 명시적 applicability proof 요구 |

### 16.6 Capability and security

| ID | Scenario | Expected |
|---|---|---|
| L-C01 | Brief backend가 file write를 요청 | capability 차단, security Telemetry |
| L-C02 | Runtime이 required sandbox restriction 미지원 | `HOLD`, 지원하는 adapter/사용자 결정 요구 |
| L-C03 | Flight Controller가 Mission Control MCP 재호출 | 차단, attempt failure/security evidence |
| L-C04 | 권한 부족 후 더 강한 권한 자동 재시도 | 정책 위반으로 테스트 실패 |

### 16.7 Pause/resume scenarios — PROPOSED, only if adopted

아래 시나리오는 제안 검증용이며 채택 전 v1 규범 테스트가 아니다.

| ID | Scenario | Expected |
|---|---|---|
| L-P01 | Execute 중 pause, cancel 성공 | Stage 유지, attempt cancelled, 새 work 없음 |
| L-P02 | pause 후 Runtime 결과 불명 | partial/unknown 보존, resume 시 reconcile |
| L-P03 | pause 동안 Blueprint 변경 | stale attempt 자동 resume 금지 |
| L-P04 | 새 host가 resume | durable state/version 확인 후 동일 의미로 재개 |

---

## 17. Observability and User-facing Status

Lifecycle 조회는 최소한 다음을 구분해 보여야 한다.

```text
Mission status: ACTIVE | COMPLETE
Current Stage: Brief | Blueprint | Execute | Verify | Recover
Control condition: running | waiting | paused (PROPOSED; not v1 required)
Latest Gate: CLEAR | HOLD
Active Blueprint revision
Active/latest attempt
Blocking conditions
Recommended next action
Evidence and decision references
```

표시 문구는 CLI/MCP 문서가 정하지만 서로 다른 개념을 하나의 `status=failed`로
압축해서는 안 된다.

### 17.1 Recommended user language — NORMATIVE terminology

- `CLEAR — Clear for Blueprint`
- `CLEAR — Clear for Execute`
- `CLEAR — Clear for Verify`
- `CLEAR — MISSION COMPLETE`
- `HOLD — <구체적인 blocker와 next action>`

`NO-GO`는 사용하지 않는다. Recover에서 Verify로 갈 때는 `Clear for Verify`라고
표현하며 `recovered successfully`만으로 완료처럼 보이게 하지 않는다.

---

## 18. Decision Ledger

### 18.1 Constitution에서 확정된 규칙

| 결정 | 상태 |
|---|---|
| 사용자 Stage는 Brief → Blueprint → Execute → Verify이며 Recover는 corrective path다. | NORMATIVE |
| Gate result는 `CLEAR`, `HOLD`만 사용한다. | NORMATIVE |
| 최종 성공은 Verify의 `MISSION COMPLETE`다. | NORMATIVE |
| 사용자 승인 없는 Brief/Blueprint forward progression은 금지된다. | NORMATIVE |
| 실행과 공식 검증은 분리한다. | NORMATIVE |
| 재시도는 새 attempt이며 실패 Telemetry를 보존한다. | NORMATIVE |
| Recover는 failure evidence를 입력으로 받고 bounded해야 한다. | NORMATIVE |

### 18.2 이 문서가 정한 v1 최소 기준

| 결정 | 상태 |
|---|---|
| canonical Stage는 Brief, Blueprint, Execute, Verify, Recover 다섯 개다. | NORMATIVE |
| `COMPLETE`는 Stage가 아닌 terminal mission status다. | NORMATIVE |
| `HOLD`와 corrective routing은 GateDecision과 RecoveryDirective로 분리한다. | NORMATIVE |
| Recover의 정상 교정 결과는 Verify로 돌아간다. | NORMATIVE |
| spec 의미는 Brief, 실행 명세는 Blueprint, 구현 결함은 Recover가 소유한다. | NORMATIVE |
| 모든 downstream attempt는 exact Blueprint revision에 묶인다. | NORMATIVE |
| retry budget의 소유자는 Recovery Policy다. | NORMATIVE |

### 18.3 제안

| 결정 | 상태 | 이유 |
|---|---|---|
| Pause를 Stage/Gate가 아닌 control overlay로 모델링 | PROPOSED | 품질 판단과 운영 중단 분리 |
| Stage activation identity 도입 | PROPOSED | backward route 후 같은 Stage 이력 구분 |
| failure fingerprint와 strategy identifier 기록 | PROPOSED | 무진전/진동 감지 |
| content hash 변경 시 새 Blueprint revision으로 취급 | PROPOSED default | silent mutation 방지 |

---

## 19. Decisions Requiring Confirmation

아래 항목은 구현 전에 upstream 조사, 사용자 확인 또는 ADR이 필요하다.

### 19.1 State representation

- exact Python enum과 serialized value는 무엇인가?
- PROPOSED `PAUSED` overlay를 채택한다면 status, flag, event 중 무엇으로 저장하는가?
- 사용자 취소/포기/보관을 terminal status로 추가할 것인가?
- Stage activation을 first-class record로 둘 것인가?

### 19.2 Gate and approval

- Brief clarity 계산식과 threshold는 무엇인가?
- Blueprint QA 조건과 exact Seed revision에 대한 사용자 승인 기록 형식은 무엇인가?
- 사용자 identity/approval provenance를 어느 수준으로 검증하는가?
- Gate 재평가를 command로 노출할지 Stage action의 일부로 둘지?

### 19.3 Attempt and retry

- Stage/failure별 attempt budget 수치는 무엇인가?
- timeout, 비용, 토큰, wall-clock budget을 어떻게 합성하는가?
- 무진전 fingerprint와 progress 판정 알고리즘은 무엇인가?
- pre-side-effect transport retry의 증명 signal, 허용 횟수와 backoff는 무엇인가?
- partial/unknown Runtime result의 reconciliation protocol은 무엇인가?

### 19.4 Recover routing

- Execute `HOLD`에서 same-stage retry와 Recover의 경계는 무엇인가?
- Recover → Execute route가 필요한 upstream 사례는 무엇인가?
- 여러 failure를 하나의 directive로 묶는 최대 범위는 무엇인가?
- 자동 Recover 전에 사용자에게 보여 줄 위험/비용 threshold는 무엇인가?

### 19.5 Revision and evidence

- editorial Blueprint change를 semantic revision과 구분할 것인가?
- 새 revision에서 이전 mechanical evidence를 재사용할 수 있는 조건은 무엇인가?
- workspace drift를 어떤 identifier/hash로 검증할 것인가?
- GateDecision과 Telemetry의 schema/version migration은 어떻게 하는가?

미확정 수치에는 임의의 “3회 재시도” 같은 값을 넣지 않는다. 자동 실행이 필요하면
해당 범위의 임시 policy를 명시하고 기록한 뒤 검증한다.

---

## 20. Implementation Order for Lifecycle

첫 vertical slice는 전체 Runtime/MCP보다 작은 pure state machine에서 시작한다.

1. Stage, GateDecision, Blueprint revision, Attempt의 최소 domain model
2. 불법 전이와 no-self-approval을 막는 transition policy
3. in-memory repository와 deterministic evidence로 transition tests
4. Brief `HOLD`/`CLEAR`와 사용자 승인 경로
5. Blueprint revision 승인과 Execute entry guard
6. Execute/Verify 분리와 `MISSION COMPLETE`
7. failure category, RecoveryDirective, Recover → Verify loop
8. persistence crash/version conflict test
9. Runtime adapter contract
10. CLI와 MCP surface

이는 패키지나 commit 계획을 고정하지 않는다. 첫 구현은
[`05_BRIEF.md`](./05_BRIEF.md)의 Stage contract와 upstream 조사까지 준비된 뒤 시작한다.

---

## 21. Lifecycle Review Checklist

새 전이, status, retry 또는 Recover 전략을 추가할 때 확인한다.

- [ ] 이것은 Stage, Gate, attempt outcome, control condition 중 무엇인가?
- [ ] forward progression에 source `CLEAR`가 있는가?
- [ ] corrective transition에 source `HOLD`와 directive가 있는가?
- [ ] 정확한 Blueprint revision과 policy version을 고정했는가?
- [ ] 작업 수행 주체가 자기 작업을 승인하지 않는가?
- [ ] evidence 누락/파싱 실패에서 fail closed하는가?
- [ ] 실패 분류가 원본 Telemetry를 보존하는가?
- [ ] Recover scope가 failed criterion에 추적되는가?
- [ ] 결과가 반드시 Verify로 돌아가는가?
- [ ] 재시도가 새 attempt이며 유한 budget 안에 있는가?
- [ ] 무진전/진동에서 자동 실행이 멈추는가?
- [ ] requirement change를 새 Blueprint revision으로 처리하는가?
- [ ] 저장 실패, stale writer, host disconnect를 테스트했는가?
- [ ] 새 상태가 Constitution 용어와 우선순위를 바꾸지 않는가?

---

## Closing Lifecycle Principle

Mission Control의 상태 머신은 일이 잘될 때의 진행 표시가 아니다. 모호함, 실행
실패, 증거 누락, 모델 과신, host 종료가 있어도 원래 Goal과 승인 기준을 잃지 않게
하는 제어 장치다.

> **No silent transition. No erased attempt. No completion without evidence.**
