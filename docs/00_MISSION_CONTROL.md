# Mission Control Project Constitution

> **mcx — coordinates AI coding missions. Executed is not verified.**
>
> **Mission Control is not an AI.**<br>
> **Mission Control does not generate code.**<br>
> **Mission Control does not review code.**<br>
> **Mission Control coordinates missions.**

| 항목 | 값 |
|---|---|
| 문서 지위 | Active Draft — 현재 프로젝트의 최상위 작업 기준 |
| 프로젝트 | **Mission Control** |
| CLI | `mcx` |
| 구현 언어 | Python |
| 작성일 | 2026-08-07 |
| 적용 범위 | v1: Ouroboros 설계를 참고한 핵심 워크플로 구현과 학습 |

이 문서는 Mission Control의 **Project Constitution**이자 새 Claude, Codex,
OpenCode 세션을 위한 필수 온보딩 문서다. 프로젝트의 목적, 책임 경계,
변하지 않아야 할 원칙, 사용자 용어와 내부 용어, 단계 전이 규칙을 정의한다.

이 문서는 상세 API 명세나 클래스 설계서가 아니다. 아직 검증하지 않은 수치,
파일 구조, 저장 기술, 재시도 횟수 등을 헌법으로 고정하지 않는다. 그런 결정은
후속 설계 문서와 ADR에서 근거를 남긴 뒤 확정한다.

---

## 1. 5분 안에 이해하는 Mission Control

Mission Control은 모호한 요청을 곧바로 코딩 모델에 던지지 않는다.

```text
모호한 의도
  → 질문으로 명확화
  → 승인 가능한 명세로 고정
  → 범위가 제한된 작업으로 실행
  → 증거로 검증
  → 실패 증거를 이용해 제한적으로 복구
```

이 흐름에서 각 주체의 역할은 명확히 분리된다.

```text
사용자
  └─ 목표, 제약, 권한, 최종 제품 결정을 소유한다.

Mission Control
  └─ 미션 상태, 단계 전이, 작업 범위, 게이트를 소유한다.

Flight Controller
  └─ 허용된 범위와 도구 안에서 작업하고 Telemetry를 반환한다.

Telemetry
  └─ 무엇이 실제로 수행되고 검증되었는지 증명한다.
```

Mission Control의 핵심 문장은 다음 네 줄이다.

> **Mission Control owns the mission state.**<br>
> **Flight Controllers execute bounded missions.**<br>
> **Telemetry determines progress.**<br>
> **Mission Control decides the next step.**

여기서 “owns the mission”은 사용자의 목표나 저장소에 대한 소유권을 뜻하지
않는다. **미션의 상태와 진행 제어를 소유한다**는 뜻이다. 사용자만이 목표,
제약, 허용 권한과 요구사항 변경의 최종 권한을 가진다.

---

## 2. North Star

Mission Control v1의 목적은 더 화려한 AI 에이전트 프레임워크를 발명하는
것이 아니다.

> **Ouroboros의 핵심 워크플로와 설계 의도를 참고해 작은 Python 시스템을
> 만들면서, 왜 그 구조가 필요한지 끝까지 이해한다.**

따라서 v1은 다음 순서를 따른다.

```text
Ouroboros 동작과 설계 의도 조사
  → 대응 개념 문서화
  → 최소 구현
  → 테스트와 Telemetry로 검증
  → Ouroboros와 차이 분석
  → 이해가 끝난 뒤에만 개선 제안
```

Mission Control은 Ouroboros의 복제품이라는 브랜드를 사용하지 않는다.
제품 경험과 CLI는 Mission Control 고유 용어를 사용한다. 다만 내부 도메인
개념은 Ouroboros와 직접 비교할 수 있도록 `Interview`, `Seed`, `Run`,
`Evaluate`, `Repair`를 유지한다.

### 성공의 기준

이 프로젝트의 성공은 코드 양이나 지원 모델 수로 측정하지 않는다.

- 새로운 세션이 이 문서만으로 프로젝트의 방향을 설명할 수 있다.
- 각 단계가 왜 존재하는지 구현과 테스트로 설명할 수 있다.
- LLM의 주장과 실제 완료 상태가 분리되어 있다.
- 단계 전이가 코드와 명시적 정책에 의해 통제된다.
- 각 역할에 필요한 최소 권한만 부여된다.
- Ouroboros와 다른 부분은 실수로 생기지 않고 문서화된 결정으로 존재한다.
- 대화 세션이 사라져도 미션 상태와 근거를 이어갈 수 있다.

---

## 3. 규범 언어

이 문서의 다음 단어는 강도를 나타낸다.

- **MUST**: 반드시 지켜야 하는 헌법적 요구사항
- **MUST NOT**: 허용되지 않는 동작
- **SHOULD**: 특별한 근거가 없다면 지켜야 하는 기본값
- **MAY**: 필요와 근거가 있을 때 선택할 수 있는 사항

구현 편의만으로 `MUST` 또는 `MUST NOT`을 우회할 수 없다. 변경이 필요하면
먼저 이 문서의 변경 절차를 따른다.

---

## 4. 진실의 원천과 우선순위

프로젝트의 결정은 채팅 기록에만 남아 있어서는 안 된다. 대화는 탐색 과정이고,
문서와 검증 가능한 상태가 프로젝트의 기억이다.

충돌이 생기면 다음 순서를 기준으로 판단한다.

1. 사용자가 현재 범위에서 명시적으로 내린 결정과 권한
2. 이 Project Constitution
3. 채택된 RFC와 ADR
4. Architecture 및 Mission Lifecycle 문서
5. 해당 Stage Guide와 승인된 Blueprint/Seed
6. 검증 테스트와 명시적 인터페이스 계약
7. 현재 구현
8. 채팅 기록, 모델의 추론, 임시 메모

하위 항목이 상위 항목과 충돌하면 하위 항목을 고친다. 상위 항목 자체가 잘못된
경우에는 조용히 무시하지 않고 변경 이유와 영향을 문서화한다.

### 승인된 Blueprint의 특별한 지위

개별 미션을 실행하는 동안에는 승인된 Blueprint/Seed가 그 미션의 실행 기준이다.
일반 프로젝트 문서가 특정 미션의 목표를 임의로 확장할 수 없고, Flight
Controller의 제안이 Blueprint를 자동 변경할 수도 없다.

---

## 5. Canonical Terminology

Mission Control은 사용자 경험과 내부 구현의 언어를 의도적으로 분리한다.

| 사용자·CLI 용어 | 내부·Ouroboros 대응 용어 | 의미 |
|---|---|---|
| `brief` / Brief | Interview | 목표, 제약, 성공 조건의 모호함을 제거한다. |
| `blueprint` / Blueprint | Seed | 실행과 검증의 기준이 될 구조화된 명세를 만든다. |
| `execute` / Execute | Run | 승인된 기준 안에서 작업을 위임하고 수행한다. |
| `verify` / Verify | Evaluate | 결과가 기준을 만족하는지 증거로 판정한다. |
| `recover` / Recover | Repair | 실패 증거를 입력으로 제한된 교정 작업을 수행한다. |

사용자에게 노출할 **확정된 canonical command 이름**은 다음과 같다. 현재는 문서
계약이며 CLI 구현이 존재한다는 뜻은 아니다.

```text
mcx brief
mcx blueprint
mcx execute
mcx verify
mcx recover
```

명령 인자, 옵션, 입출력 형식과 실제 제공 시점은 아직 이 문서에서 정의하지 않는다.

### 용어 사용 규칙

- CLI, 사용자 메시지, 온보딩 설명에는 Mission Control 용어를 사용한다.
- 코드, Ouroboros 대응표, 구현 연구에는 내부 용어를 함께 표기한다.
- 최초 등장 시 `Brief (Interview)`처럼 두 용어를 연결한다.
- `NO-GO`는 사용하지 않는다.
- 게이트 결과는 대문자 `CLEAR`, `HOLD`를 사용한다.
- 최종 성공은 `MISSION COMPLETE`라고 표현한다.
- 이전 후보였던 다른 프로젝트명이나 CLI 명칭은 현재 용어가 아니다.

### 핵심 역할과 산출물

| 용어 | 정의 |
|---|---|
| Mission | 하나의 승인 가능한 목표를 Brief부터 완료 판정까지 추적하는 작업 단위 |
| Mission Control | 미션 상태와 단계 전이를 관리하는 control plane |
| Flight Controller | 특정 런타임에서 범위가 제한된 작업을 수행하는 실행 주체 |
| Telemetry | 실행, 관찰, 검사 결과를 게이트 판단과 연결하는 구조화된 증거 |
| Gate | 현재 단계에서 다음 단계로 진행할 수 있는지 판정하는 경계 |
| Blueprint | 사용자에게 보이는 실행 명세; 내부적으로 승인된 Seed에 대응 |

`Capability Envelope`, `Work Unit`, 구체적인 Telemetry 타입 이름 등은 유용한
후보지만 아직 헌법적 명칭으로 고정하지 않는다.

---

## 6. 책임 경계

### 6.1 User / Operator

사용자는 다음을 소유한다.

- 미션의 목표와 우선순위
- 제품 요구사항과 의미적 결정
- 제약, 비범위, 위험 허용 수준
- 저장소와 외부 시스템에 대한 권한
- Blueprint 승인 및 요구사항 변경 승인
- 파괴적이거나 범위를 확장하는 행동에 대한 추가 승인

사용자에게 물어야 할 제품 결정을 코드에서 추측해서는 안 된다. 반대로 코드와
문서에서 확인 가능한 사실을 불필요하게 사용자에게 되묻지 않도록 출처를
구분해야 한다.

### 6.2 Mission Control

Mission Control은 다음을 소유한다.

- 미션 식별자와 현재 상태
- 현재 Stage와 허용된 전이
- Stage별 진입 조건과 종료 조건
- Flight Controller에 전달할 범위와 권한
- 재시도, 복구, 중단 정책
- Telemetry 수집과 Gate 판정
- 미션의 감사 가능한 기록

Mission Control은 코드 작성자나 코드 리뷰어 역할을 직접 수행하지 않는다.
질문 생성, 코드 변경, 의미 평가가 필요하면 적절히 제한된 Flight Controller나
LLM backend에 위임한다. 위임 결과를 그대로 믿지 않고 정책과 Telemetry를 통해
다음 단계를 판단한다.

### 6.3 Flight Controller

Flight Controller는 다음을 수행한다.

- 한 번에 정의된 하나의 제한된 책임을 수행한다.
- 승인된 목표와 제약을 유지한다.
- 허용된 도구와 파일 범위를 지킨다.
- 실행 결과와 실패를 숨기지 않고 Telemetry로 반환한다.
- 자신의 판단이 아닌 관찰 가능한 근거를 함께 제공한다.

Flight Controller는 다음을 수행할 수 없다.

- 미션 목표나 Blueprint를 임의로 변경한다.
- 범위를 넓히거나 승인되지 않은 기능을 추가한다.
- 자신의 작업을 스스로 `CLEAR` 처리한다.
- 현재 Stage나 다음 Stage를 결정한다.
- 허용되지 않은 도구를 발견해 우회 호출한다.
- 위임받은 작업 안에서 Mission Control을 재귀적으로 다시 호출한다.

### 6.4 Runtime Adapter

Runtime Adapter는 공통 요청을 Codex, OpenCode 같은 구체 런타임의 호출로
변환하고, 런타임의 이벤트와 결과를 공통 형태로 정규화한다.

Runtime Adapter는 다음을 결정하지 않는다.

- 미션의 목표
- Stage 전이
- Gate 결과
- 재시도와 Recover 정책
- 완료 여부

런타임에 없는 기능을 있는 것처럼 흉내 내지 않는다. 지원하지 않는 capability는
명시적으로 보고해야 한다.

### 6.5 CLI와 MCP

CLI와 MCP는 Mission Control에 접근하는 **surface 또는 adapter**다. 어느 쪽도
별도의 워크플로 엔진이나 상태 소유자가 되어서는 안 된다. 같은 미션을 CLI와
MCP에서 다루더라도 하나의 canonical state를 바라봐야 한다.

---

## 7. Constitutional Principles

### Principle 1 — Specification before execution

승인된 실행 명세 없이 구현을 시작하지 않는다.

```text
대화 ≠ 명세
초안 ≠ 승인된 Blueprint
승인된 Blueprint → Execute 가능
```

모호함을 실행 단계에 떠넘기면 Flight Controller가 제품 결정을 추측하게 된다.
Mission Control은 그 상황을 성능 문제가 아니라 제어 실패로 본다.

### Principle 2 — Workflow before model

모델은 질문, 명세 초안, 코드, 평가 의견을 생성할 수 있다. 하지만 다음 단계,
종료 조건, 재시도, 권한, 완료 여부는 Workflow가 결정한다.

```text
Model proposes.
Workflow constrains.
Telemetry proves.
Gate decides.
```

### Principle 3 — Evidence over reasoning

Flight Controller가 “완료했다”고 말한 것은 완료가 아니다. 빌드, 테스트, 관찰,
변경 내역, Acceptance Criterion별 결과 같은 Telemetry가 있어야 한다.

```text
Agent said done ≠ Done
Verified criteria with evidence = Eligible for CLEAR
```

Telemetry가 없거나 읽을 수 없거나 출처가 불명확하면 낙관적으로 성공 처리하지
않고 `HOLD`한다.

### Principle 4 — Least capability by stage

모든 역할은 현재 책임을 수행하는 데 필요한 최소 도구만 가져야 한다. 최소 권한은
프롬프트 문구가 아니라 런타임과 도구 구성으로 강제해야 한다.

예를 들어 Brief의 질문 생성 역할은 질문과 상태 갱신에 필요한 기능만 가져야
하며, 파일 쓰기, Git 변경, Shell 실행, 코드 구현 권한을 가져서는 안 된다.
정확한 도구 목록은 Stage Guide에서 정의한다.

### Principle 5 — No self-approval

작업을 수행한 주체가 자신의 작업을 다음 단계로 승인할 수 없다. Flight
Controller는 결과와 Telemetry를 반환하고, Mission Control의 Gate가 별도로
판정한다.

### Principle 6 — Scope is a hard boundary

좋아 보이는 아이디어는 승인된 범위가 아니다. 리팩터링, 새 기능, 의존성 교체,
폴더 재구성은 Blueprint 또는 명시적 작업 범위에 없으면 실행하지 않는다.

범위 변경이 필요하면 실행 중 몰래 반영하지 않고 해당 결정을 Brief 또는
Blueprint로 되돌려 승인받는다.

### Principle 7 — Durable state over conversation memory

미션의 연속성은 특정 Claude, Codex, OpenCode 대화 세션에 의존하지 않는다.
질문과 답변, 출처, Blueprint, 실행 attempt, Telemetry, Gate 결과는 다시 읽을 수
있는 상태로 보존해야 한다.

### Principle 8 — Runtime neutrality

Core Workflow는 모델명, CLI 문법, vendor별 이벤트 형식을 알아서는 안 된다.
구체 런타임의 차이는 Adapter 경계 안에 격리한다.

초기 대상으로 Codex와 OpenCode를 고려한다. OpenCode는 로컬 모델 또는
OpenCode가 제공하는 agent를 사용할 수 있다. Gemini는 v1 대상이 아니다.

### Principle 9 — Recovery uses failure evidence

복구는 “다시 잘해 봐”가 아니다. 실패한 기준, 실제 오류, 이전 시도, 허용된 수정
범위를 새 시도의 입력으로 제공한다. 이전 Telemetry를 덮어쓰지 않고 새로운
attempt로 남긴다.

### Principle 10 — Reconstruct before improve

v1에서 Ouroboros와 다른 동작을 넣기 전에 먼저 Ouroboros의 동작, 보호하려는 실패 상황,
차이의 이유를 문서화한다. 개인 취향이나 최신 유행만으로 Workflow를 바꾸지
않는다.

---

## 8. Mission Lifecycle

정상적인 성공 경로는 다음과 같다.

```mermaid
flowchart LR
    A["Brief<br/>Interview"] -->|"CLEAR"| B["Blueprint<br/>Seed"]
    B -->|"CLEAR"| C["Execute<br/>Run"]
    C -->|"CLEAR"| D["Verify<br/>Evaluate"]
    D -->|"CLEAR"| E["MISSION COMPLETE"]
```

각 경계에는 명시적 Gate가 존재한다.

```text
Brief
  ├─ CLEAR → Clear for Blueprint
  └─ HOLD  → Brief 유지, 부족한 결정 또는 근거 보완

Blueprint
  ├─ CLEAR → Clear for Execute
  └─ HOLD  → Blueprint 수정·QA·승인 계속

Execute
  ├─ CLEAR → Clear for Verify
  └─ HOLD  → 실패 근거를 보존하고 정책에 따라 교정

Verify
  ├─ CLEAR → MISSION COMPLETE
  └─ HOLD  → 충족되지 않은 기준과 증거를 제시
```

Recover는 모든 성공 미션이 반드시 통과하는 마지막 직선 단계가 아니다.
**실패 또는 부족한 증거를 다루는 정책 기반 corrective path**다. Recover가 어느
Stage로 복귀하는지, 재시도 한도, 회복 불가능 상태의 표현은
`02_MISSION_LIFECYCLE.md`에서 확정한다.

### 전이 불변 규칙

- 한 미션의 canonical current Stage는 한 번에 하나다.
- 암묵적 Stage 전이는 없다.
- 모든 전이는 Gate decision과 근거 Telemetry를 남긴다.
- `HOLD`는 실패 선언이 아니라 “현재 조건으로는 진행 불가”라는 판정이다.
- 재시도는 기존 기록을 수정하는 대신 새로운 attempt로 생성한다.
- Runtime 오류와 Acceptance Criterion 미충족을 같은 실패로 뭉개지 않는다.
- `MISSION COMPLETE`는 Verify Gate만 선언할 수 있다.

---

## 9. Stage Contracts

이 절은 각 Stage의 헌법적 목적과 경계를 정의한다. 정확한 상태 모델, prompt,
도구 목록, 수치 임계값은 각 Stage Guide에서 정의한다.

### 9.1 Brief (Interview)

#### 목적

사용자의 초기 요청에서 실행 중 임의 판단이 필요한 모호함을 제거한다.

#### 필수 입력

- 사용자의 초기 의도 또는 문제 설명
- 작업 대상과 사용자가 허용한 조사 범위
- 이미 알려진 제약과 권한

#### 필수로 명확해져야 하는 내용

- 목표
- 제약
- 비범위
- 검증 가능한 성공 조건
- 아직 해결되지 않은 결정
- 중요한 답변의 출처

#### 핵심 규칙

- 질문 횟수나 모델의 직감만으로 종료하지 않는다.
- Ambiguity/Clarity에 대한 명시적 평가를 Gate 입력으로 사용한다.
- 사용자의 제품 결정과 코드에서 관찰한 사실을 구분한다.
- 가정은 사실처럼 기록하지 않고 가정임을 표시한다.
- 사용자 승인 없이 Blueprint 단계로 진행하지 않는다.
- Brief 역할은 코드를 구현하지 않는다.

구체적인 계산식과 통과 임계값은 Ouroboros의 버전과 실제 구현을 조사한 후 고정한다.
예시 수치를 헌법으로 복사하지 않는다.

#### 주요 산출물

- 지속 가능한 Interview/Brief state
- 질문·답변 기록과 출처
- unresolved decisions
- ambiguity/clarity 평가
- Blueprint 생성에 사용할 정리된 context

#### CLEAR 조건의 최소 의미

다음 구현 단계가 제품 결정을 추측하지 않아도 될 정도로 목표, 제약, 비범위,
성공 조건이 명확하고 사용자가 진행을 승인했다.

### 9.2 Blueprint (Seed)

#### 목적

Brief의 긴 대화와 관찰을 실행 가능하고 검토 가능한 단일 명세로 결정화한다.

#### Blueprint의 최소 내용

- Goal
- Constraints
- Non-goals
- Acceptance Criteria
- Exit Conditions
- Brief/Interview에 대한 추적 참조

#### 핵심 규칙

- 첫 생성 결과를 자동으로 최종 승인하지 않는다.
- QA와 보완 과정을 거친다.
- Acceptance Criterion은 관찰하거나 검증할 수 있는 결과를 표현한다.
- 구현 수단을 결과 조건처럼 가장하지 않는다.
- 승인된 Seed는 실행 중 조용히 변경하지 않는다.
- 요구사항 변경은 새 revision과 재승인을 요구한다.
- Blueprint가 `HOLD`인 동안 Execute를 시작하지 않는다.

#### CLEAR 조건의 최소 의미

Blueprint가 내부적으로 일관되고, 각 Acceptance Criterion과 Exit Condition을
검증할 수 있으며, 사용자가 실행에 사용할 정확한 revision을 명시적으로 승인했다.

### 9.3 Execute (Run)

#### 목적

승인된 Blueprint를 범위가 제한된 작업으로 변환하여 적절한 Flight
Controller에 위임한다.

#### 각 실행 작업이 가져야 하는 정보

- 해당 작업이 만족해야 하는 Acceptance Criterion
- 전체 Goal과 관련 Constraints/Non-goals
- 허용된 파일, 도구, 외부 행동 범위
- 선행 의존성과 이미 완료된 근거
- 반환해야 할 Telemetry 계약
- 이전 실패가 있다면 관련 실패 증거

#### 핵심 규칙

- Flight Controller에게 전체 미션을 무제한으로 넘기지 않는다.
- 작업은 가능한 한 Acceptance Criterion에 추적 가능해야 한다.
- 필요성이 입증되기 전에 과도하게 잘게 분해하지 않는다.
- 의존성을 무시한 실행으로 우연한 성공을 만들지 않는다.
- 실행 결과를 즉시 완료로 처리하지 않는다.
- 실행과 공식 검증을 별도 상태로 유지한다.
- 범위를 넘어선 유용한 제안은 실행하지 않고 별도 기록으로 남긴다.

#### CLEAR 조건의 최소 의미

검증 대상으로 보낼 실행 결과와 필수 Telemetry가 준비되어 있으며, 처리되지 않은
실행 오류가 숨겨져 있지 않다. 이는 미션 완료가 아니라 **Clear for Verify**다.

### 9.4 Verify (Evaluate)

#### 목적

실행 결과가 단순히 존재하는지가 아니라 승인된 Blueprint를 실제로 만족하는지
판정한다.

#### 검증 순서

1. **Mechanical verification**
   lint, typecheck, build, test처럼 가능한 한 결정적이고 저렴한 검사를 먼저
   수행한다.
2. **Semantic verification**
   변경 결과를 Goal, Constraints, Non-goals, Acceptance Criteria와 대조한다.
3. **Conditional escalation**
   애매하거나 위험이 큰 경우에만 추가 평가자나 합의 절차를 사용할 수 있다.

#### 핵심 규칙

- 기계 검사가 실패하면 그 사실을 숨긴 채 의미 평가로 성공을 만들지 않는다.
- 각 Acceptance Criterion에 판정과 증거를 연결한다.
- diff만으로 검증할 수 없는 실제 동작은 실행·관찰한다.
- 범위 이탈도 실패 근거로 다룬다.
- 평가자의 자연어 확신만으로 `CLEAR`하지 않는다.
- 작업을 수행한 Flight Controller의 자기 평가를 독립 검증으로 간주하지 않는다.

#### CLEAR 조건의 최소 의미

모든 필수 Acceptance Criterion과 Exit Condition이 충분한 Telemetry로 충족되었고,
미해결 위험이나 범위 이탈이 완료 판정을 막지 않는다.

### 9.5 Recover (Repair)

#### 목적

실패한 기준과 구체적인 Telemetry를 제한된 교정 작업의 입력으로 변환한다.

#### Recover 입력

- 실패한 Acceptance Criterion 또는 Gate condition
- 실행한 검사와 실제 오류
- 이전 attempt와 변경 내역
- 허용된 수정 범위
- 재검증해야 할 조건

#### 핵심 규칙

- 전체 미션을 이유 없이 처음부터 다시 시작하지 않는다.
- 이전 실패를 요약해 지우지 않고 원본 Telemetry를 참조한다.
- 교정 범위를 실패와 관련된 부분으로 제한한다.
- 반복, 진동, 무진전이 관찰되면 같은 전략을 무한 반복하지 않는다.
- 정해진 정책 안에서 회복할 수 없으면 `HOLD`하고 이유와 필요한 결정을 알린다.
- Recover 결과는 반드시 다시 검증된다.

Recover는 canonical corrective Stage이며, `CLEAR`는 항상 Verify로 진행한다. 제품
결정이나 명세 수정이 필요하면 Recover에 진입해 우회하지 않고 source `HOLD`에서
Brief 또는 Blueprint로 직접 corrective routing한다. 정확한 RecoveryDirective
serialization과 retry budget은 Lifecycle/ADR에서 결정한다.

---

## 10. Gate Contract

Gate는 boolean 성공 플래그보다 풍부한 정책 결정이다.

### `CLEAR`

`CLEAR`는 현재 Stage의 Exit Criteria와 필수 Telemetry가 충족되어 지정된 다음
단계로 진행할 수 있다는 뜻이다.

좋은 표현:

```text
CLEAR — Clear for Blueprint
CLEAR — Clear for Execute
CLEAR — Clear for Verify
CLEAR — MISSION COMPLETE
```

### `HOLD`

`HOLD`는 현재 상태로 다음 단계에 진행할 수 없다는 뜻이다. 최종 실패와 동일하지
않다. 모든 `HOLD`는 최소한 다음 내용을 제공해야 한다.

- 현재 Stage
- 진행할 수 없는 이유
- 부족하거나 충돌하는 근거
- 해결해야 하는 질문 또는 조건
- 권장되는 다음 행동
- 관련 Telemetry 참조

### Gate decision의 최소 정보

구체적인 schema는 후속 문서에서 정하지만, 의미상 다음 정보가 필요하다.

```text
mission
stage
attempt
decision: CLEAR | HOLD
reason
evidence references
decided at
policy or schema version
next destination when CLEAR
```

### Gate 불변 규칙

- 근거 없는 `CLEAR`는 허용하지 않는다.
- 파싱할 수 없는 결과를 성공으로 간주하지 않는다.
- Gate는 런타임의 종료 코드 하나만으로 전체 의미를 결정하지 않는다.
- 동일 입력과 동일 Telemetry에 대한 결정은 설명 가능해야 한다.
- 정책 버전이 바뀌면 과거 결정의 기준을 추적할 수 있어야 한다.

---

## 11. Capability와 Trust Boundary

Mission Control은 LLM을 신뢰 가능한 내부 함수가 아니라 **제한하고 검증해야 하는
외부 실행 주체**로 취급한다.

### 최소 권한 원칙

각 dispatch는 최소한 다음 경계를 명시해야 한다.

- 수행할 역할
- 허용된 목표와 비범위
- 읽을 수 있는 context
- 사용할 수 있는 도구
- 변경 가능한 파일 또는 시스템 범위
- 외부 네트워크·메시지·배포 권한
- 반환할 결과와 Telemetry
- 시간, 시도, 비용 등 적용 가능한 budget

Prompt에서 “하지 마”라고 쓰는 것만으로는 충분하지 않다. 가능한 경우 sandbox,
tool allowlist, filesystem scope, approval policy 등 실제 제어 수단으로 강제한다.

### Stage isolation

한 Stage의 권한을 다음 Stage로 자동 상속하지 않는다.

```text
Brief의 질문 생성 권한
≠ Execute의 파일 수정 권한

Execute의 파일 수정 권한
≠ Verify의 승인 권한
```

### 재귀 호출 방지

Flight Controller는 자신에게 위임된 작업 안에서 Mission Control MCP를 다시
발견하고 호출해 또 다른 미션을 생성해서는 안 된다. 오케스트레이션의 소유자는
항상 상위 Mission Control 하나여야 한다.

### 민감정보와 파괴적 행동

- 자격 증명, 토큰, 비밀값을 Telemetry에 기록하지 않는다.
- 파괴적 행동은 명시된 권한과 별도 정책을 요구한다.
- 런타임 출력이 Mission state를 직접 수정할 수 없게 한다.
- 외부 전송이나 배포는 구현 작업과 동일한 권한으로 암묵 승인하지 않는다.

---

## 12. Runtime Architecture

Workflow와 Runtime은 분리되어야 한다.

```text
Mission Control Core
        │
        │ common runtime contract
        ▼
Runtime Adapter
        │
        ├─ Codex
        └─ OpenCode
             ├─ local model
             └─ OpenCode-provided agent
```

### Core가 알아야 하는 것

- 작업 목적과 범위
- 필요한 capability
- 입력 context와 artifact
- 결과 및 Telemetry 계약
- 취소, timeout, 오류처럼 공통으로 다룰 실행 신호

### Core가 몰라야 하는 것

- 특정 CLI의 인자 조합
- vendor별 세션 ID 형식
- provider별 JSONL 이벤트 이름
- 모델별 prompt hack
- 런타임 내부의 인증 방식

### 초기 범위

- Python으로 Runtime protocol을 정의한다.
- Codex와 OpenCode adapter를 초기 대상으로 삼는다.
- OpenCode의 local model과 제공 agent 차이를 adapter/capability 수준에서 다룬다.
- Gemini는 v1 지원 범위에 포함하지 않는다.

`CodexRuntime`, `OpenCodeRuntime`은 자연스러운 내부 클래스 후보지만, 정확한
인터페이스와 클래스명은 `03_RUNTIME.md`와 ADR에서 확정한다.

### LLM backend와 execution runtime

질문 한 번을 생성하거나 구조화된 평가를 반환하는 text-generation backend와,
파일을 수정하고 명령을 실행하는 stateful execution runtime은 같은 개념이 아니다.
Mission Control은 둘을 별도 책임으로 모델링해야 한다.

---

## 13. CLI와 MCP의 위치

### CLI

`mcx`는 사용자가 Mission Lifecycle을 직접 조작하고 관찰하는 기본 인터페이스다.
CLI는 Core의 상태 전이 규칙을 복제하지 않고 동일한 application boundary를
호출해야 한다.

### MCP

MCP는 Claude, Codex 또는 다른 host가 Mission Control 기능을 호출할 수 있게
하는 표준화된 control surface다.

```text
Host session
    │
    │ MCP request
    ▼
Mission Control
    │
    │ bounded dispatch through a Runtime Adapter
    ▼
Flight Controller
```

MCP는 프로젝트의 본체가 아니다. 본체는 Mission state, Workflow, Gate,
Capability policy, Telemetry를 소유하는 Core다.

### 구현 순서

```text
Domain and Workflow
  → testable application boundary
  → Runtime protocol and deterministic test double
  → CLI
  → concrete Runtime adapters
  → MCP surface
```

구체적인 세부 순서는 Architecture 문서에서 조정할 수 있지만, MCP 편의를 위해
Core 규칙을 host별로 복제해서는 안 된다.

---

## 14. Mission State와 Artifacts

미션은 채팅이 아니라 상태와 artifact의 연속이다.

### 최소 개념 모델

```text
Mission
├─ identity and current stage
├─ Brief / Interview state
├─ Blueprint / approved Seed revisions
├─ execution attempts
├─ Telemetry references
├─ Gate decisions
├─ recovery attempts
└─ final verification report
```

### 지속성 원칙

- 세션을 닫거나 모델을 바꿔도 미션을 다시 읽을 수 있어야 한다.
- 각 상태 변경의 원인과 이전 상태를 추적할 수 있어야 한다.
- 질문, 답변, 관찰, 가정의 출처를 보존한다.
- 승인된 Blueprint revision과 실제 실행 revision을 연결한다.
- 실행 결과와 검증 결과를 분리한다.
- 저장 실패를 성공적인 상태 전이로 가장하지 않는다.

SQLite, 파일 기반 저장, event store 등 구체 기술은 아직 정하지 않는다.
저장 방식보다 위의 의미적 계약이 우선이다.

---

## 15. Telemetry

Telemetry는 단순 로그 모음이 아니다.

> **Telemetry는 특정 Stage의 특정 attempt에서 무엇이 수행되었고, 어떤 결과가
> 관찰되었으며, Gate가 왜 그 결정을 내렸는지를 연결하는 구조화된 증거다.**

### Telemetry가 답할 수 있어야 하는 질문

- 어느 미션과 Stage의 몇 번째 attempt인가?
- 누가 어떤 Runtime을 통해 작업했는가?
- 어떤 범위와 capability가 허용되었는가?
- 실제로 무엇을 실행하고 변경했는가?
- 어떤 테스트, 빌드, 관찰을 수행했는가?
- 각 Acceptance Criterion의 근거는 무엇인가?
- 실패했다면 실제 오류와 중단 지점은 무엇인가?
- 어떤 Gate decision이 이 증거를 사용했는가?

### Telemetry 불변 규칙

- 원문 결과와 요약을 구분한다.
- 실패 결과도 삭제하지 않는다.
- 재시도는 이전 attempt의 Telemetry를 덮어쓰지 않는다.
- 누락된 증거를 모델의 설명으로 채워 넣지 않는다.
- 비밀값과 불필요한 개인정보를 저장하지 않는다.
- 미래의 세션이 Gate 결정을 이해할 만큼의 근거를 남긴다.

`TelemetryEvent`, `TelemetryBundle`, `TelemetryReport`는 후보 타입 이름이다.
정확한 schema, 보존 기간, append-only 여부는 별도 문서에서 결정한다.

---

## 16. Failure, HOLD, Recovery

Mission Control에서 실패는 폐기할 결과가 아니라 다음 결정을 위한 데이터다.

```text
attempt
  → result
  → Telemetry
  → Gate: HOLD
  → bounded Recover instruction
  → new attempt
  → Verify
```

### 실패 분류는 보존되어야 한다

최소한 다음 종류를 구분할 수 있어야 한다.

- Runtime/adapter 호출 자체의 실패
- 명령, build, test 같은 mechanical failure
- Acceptance Criterion 미충족
- Goal 또는 Non-goal로부터의 scope drift
- 필수 Telemetry 누락
- 사용자 결정이 필요한 specification gap
- 권한 또는 capability 부족
- 반복 시도에도 진전이 없는 상태

이 분류는 복구 전략을 결정하지만, 정확한 enum은 후속 설계에서 정한다.

### 무한 루프 방지

Recover는 bounded해야 한다. 구체 횟수는 아직 정하지 않지만 다음은 MUST다.

- 각 attempt를 식별한다.
- 동일 실패의 반복을 감지할 수 있다.
- 진전이 없으면 같은 지시를 무한 반복하지 않는다.
- 정책 한도에 도달하면 `HOLD`하고 사용자에게 필요한 결정을 요청한다.
- 중단 이유와 남은 선택지를 Telemetry로 남긴다.

---

## 17. Scope와 Reasoning Discipline

사용자가 특히 피하려는 실패는 과추론으로 인해 워크플로가 느려지고 원래 의도에서
벗어나는 것이다. Mission Control은 이것을 모델 성향이 아니라 시스템 경계의
문제로 다룬다.

### 기본 규칙

- 필요한 질문만 한다.
- 현재 Stage가 요구하지 않는 작업을 미리 수행하지 않는다.
- 간단한 작업을 불필요한 다중 에이전트 구조로 확장하지 않는다.
- 개선 아이디어와 현재 승인 범위를 분리한다.
- 추가 추론이 Gate 결과나 구현 선택을 실질적으로 바꾸지 않으면 중단한다.
- 새로운 요구사항을 발견하면 자동 구현하지 않고 Blueprint 변경 후보로 기록한다.
- 역할을 늘리는 것보다 명확한 계약과 Telemetry를 우선한다.

Reasoning budget의 구체 모델과 자동 Scope Guard는 유용한 향후 설계 후보지만,
현재 헌법은 특정 제품 기능이나 수치로 고정하지 않는다.

---

## 18. Upstream Reference Policy

Mission Control v1은 Ouroboros의 핵심 설계를 참고 기준(baseline)으로 삼아
학습한다.

### 각 기능을 구현하기 전에 기록할 내용

1. 대응하는 Ouroboros 개념과 코드 경로
2. Ouroboros가 보호하려는 실패 상황
3. 관찰한 상태 전이와 Gate
4. Ouroboros 테스트가 보장하는 행동
5. Mission Control에서 유지할 부분
6. 의도적으로 단순화하거나 변경할 부분과 이유
7. 아직 확인하지 못한 가정

### 대조 규칙

- Ouroboros를 이해하기 전에 더 좋아 보이는 구조로 대체하지 않는다.
- 동작 호환성과 코드 복사를 구분한다.
- Ouroboros 코드나 문서를 가져오기 전에 현재 라이선스와 고지 의무를 확인한다.
- Ouroboros의 버전 또는 commit을 기록해 시간에 따른 변경을 추적한다.
- Ouroboros와 다른 동작은 테스트와 ADR로 드러낸다.
- upstream mapping을 새 세션이 찾을 수 있는 문서로 남긴다.

### 학습 루프

```text
Read
  → Explain the protected failure
  → Build minimally
  → Test behavior
  → Compare with upstream
  → Record the difference
  → Update documentation
```

---

## 19. Documentation-First Development

문서는 구현이 끝난 뒤 작성하는 보고서가 아니다. 이 프로젝트에서는 문서가 구현의
입력이고, Telemetry와 테스트가 구현의 검증이며, 업데이트된 문서가 다음 세션의
입력이다.

### 기능 개발의 기본 흐름

```text
Research
  → RFC or design note when needed
  → ADR for consequential decisions
  → Architecture / Stage Guide update
  → Implementation
  → Verification and Telemetry
  → Upstream diff analysis
  → Documentation update
```

모든 작은 수정에 무거운 RFC를 요구하지는 않는다. 그러나 다음 변경은 문서가
코드보다 먼저 존재해야 한다.

- Stage 추가 또는 순서 변경
- Gate 의미나 결과 추가
- Blueprint 불변성 변경
- Runtime boundary 변경
- 최소 권한 정책 완화
- Telemetry 없이 진행할 수 있는 예외 추가
- 사용자-facing 명령 또는 용어 변경
- Ouroboros와 의도적으로 다른 핵심 동작

### 각 Stage 작업의 학습 체크리스트

- [ ] Ouroboros 개념과 관련 코드를 읽었다.
- [ ] 그 구조가 막는 실패를 내 언어로 설명했다.
- [ ] Stage의 input, output, entry, exit를 문서화했다.
- [ ] 허용·금지 capability를 문서화했다.
- [ ] 정상, 실패, 재개 경로를 테스트로 정의했다.
- [ ] 최소 구현을 만들었다.
- [ ] 테스트와 실제 관찰로 검증했다.
- [ ] Ouroboros와의 차이를 기록했다.
- [ ] 다음 세션이 이어갈 수 있게 문서를 갱신했다.

---

## 20. Documentation System

이 Constitution을 기준으로 다음 문서 체계를 사용한다.

```text
docs/
├─ 00_MISSION_CONTROL.md       # 현재 문서: Constitution / North Star
├─ 01_ARCHITECTURE.md          # 컴포넌트, 경계, 의존 방향
├─ 02_MISSION_LIFECYCLE.md     # 상태 머신, Gate, Recover 전이
├─ 03_RUNTIME.md               # Runtime protocol과 adapters
├─ 04_MCP.md                   # MCP surface와 host 통합
├─ 05_BRIEF.md                 # Interview Stage Guide
├─ 06_BLUEPRINT.md             # Seed Stage Guide
├─ 07_EXECUTE.md               # Run Stage Guide
├─ 08_VERIFY.md                # Evaluate Stage Guide
├─ 09_RECOVER.md               # Repair Stage Guide
├─ adr/                        # Architecture Decision Records
├─ progress/                   # 현재 구현 상태와 다음 검증 가능한 목표
└─ research/                   # upstream 조사와 대응표
```

필요가 확인되면 Telemetry, Security, CLI Reference 문서를 추가할 수 있다.

### 읽는 순서

1. [Architecture](./01_ARCHITECTURE.md)
2. [Mission Lifecycle](./02_MISSION_LIFECYCLE.md)
3. [Runtime](./03_RUNTIME.md)
4. [MCP](./04_MCP.md)
5. [Brief](./05_BRIEF.md)
6. [Blueprint](./06_BLUEPRINT.md)
7. [Execute](./07_EXECUTE.md)
8. [Verify](./08_VERIFY.md)
9. [Recover](./09_RECOVER.md)
10. [ADR Index](./adr/README.md)
11. [Project Progress](./progress/README.md)
12. [Research Index](./research/README.md)

### 문서별 책임

| 문서 종류 | 답해야 하는 질문 |
|---|---|
| Constitution | 무엇을 왜 만들며 무엇을 절대 어기지 않는가? |
| Architecture | 구성 요소와 책임, 의존 방향은 무엇인가? |
| Lifecycle | 정확히 어떤 상태와 전이가 존재하는가? |
| Stage Guide | 이 Stage를 어떻게 구현하고 검증하는가? |
| ADR | 왜 이 결정을 내렸고 어떤 대안을 거절했는가? |
| Progress | 현재 사실상 어디까지 완료되었는가? |
| Research | Ouroboros에서 무엇을 확인했고 어떤 차이가 있는가? |

Progress 문서는 계획이 아니라 **검증된 현재 상태**를 기록해야 한다.

---

## 21. Verification Policy for the Project Itself

Mission Control 코드도 Mission Control의 철학을 따라야 한다.

### 변경 완료 조건

변경은 최소한 다음을 충족해야 완료 후보가 된다.

- 관련 헌법과 설계 문서를 위반하지 않는다.
- 변경 목표와 비범위가 명확하다.
- 관련 테스트가 존재하고 통과한다.
- 실패 경로와 상태 전이를 검증한다.
- Runtime 또는 MCP 없이도 가능한 Core 규칙은 독립 테스트할 수 있다.
- 사용자-facing 동작이 있으면 실제 인터페이스를 관찰한다.
- Telemetry 또는 검증 결과를 남긴다.
- 문서와 실제 구현의 차이가 남지 않는다.

### 권장 테스트 층

```text
Domain invariants
  → State transition tests
  → Gate policy tests
  → Adapter contract tests
  → CLI/MCP integration tests
  → End-to-end mission scenarios
```

구체적인 test framework와 품질 임계값은 기술 스택 결정 후 확정한다.

---

## 22. v1 Scope Boundary

### v1에 반드시 포함할 핵심

- Python 기반 Mission state와 Stage model
- Brief / Interview loop와 명시적 clarity gate
- 승인 가능한 Blueprint / Seed와 revision 원칙
- 제한된 Execute / Run dispatch
- Mechanical 및 Semantic Verify / Evaluate
- 실패 Telemetry 기반 Recover / Repair
- `CLEAR`, `HOLD`, `MISSION COMPLETE` Gate semantics
- Stage별 최소 capability 강제
- Runtime-neutral Core
- Codex와 OpenCode를 위한 초기 adapter 방향
- `mcx` CLI
- Core 위에 얹는 MCP control surface
- 지속 가능한 상태와 Telemetry
- upstream 대응 및 차이 문서

### v1에서 하지 않는 것

- Mission Control 자체를 코드 작성자 또는 리뷰어로 만드는 것
- LLM이 Stage 전이나 완료 여부를 직접 결정하게 하는 것
- 승인 없이 요구사항과 범위를 확장하는 것
- Telemetry 없는 낙관적 성공 처리
- 특정 vendor를 Core Workflow의 전제로 만드는 것
- Gemini runtime 지원
- Ouroboros 이해보다 새 기능 발명을 우선하는 것
- 필요성이 입증되지 않은 복잡한 다중 에이전트 구조

대시보드, TUI, 병렬 실행, 고급 모델 라우팅, 다중 모델 합의, 완전한 event
sourcing 등은 현재 필수 범위가 아니다. 영구 금지 사항도 아니다. 핵심 Workflow를
구현한 뒤 명확한 문제와 근거가 있을 때 별도 제안으로 평가한다.

---

## 23. Change Governance

### 변경 종류

#### Editorial change

의미를 바꾸지 않는 오탈자, 표현, 예시 개선이다. 가벼운 검토로 변경할 수 있다.

#### Design change

API, 저장 방식, adapter 구현처럼 헌법 안에서 선택할 수 있는 설계 변경이다. 중요한
경우 ADR을 남긴다.

#### Constitutional change

다음은 헌법 변경이다.

- 프로젝트 목적 또는 v1 North Star 변경
- 사용자·내부 용어 매핑 변경
- `CLEAR`, `HOLD`, `MISSION COMPLETE` 의미 변경
- Stage 순서 또는 책임 변경
- Blueprint 승인·불변성 규칙 완화
- 최소 권한 또는 no-self-approval 원칙 변경
- Evidence over reasoning 원칙 변경
- Runtime neutrality 변경

헌법 변경에는 최소한 다음이 필요하다.

1. 변경 이유와 해결하려는 실제 문제
2. 현재 규칙으로 해결할 수 없는 근거
3. 사용자 경험과 호환성 영향
4. 상태·데이터 migration 영향
5. 테스트와 문서 변경 계획
6. 사용자의 명시적 승인

### Breaking terminology changes

CLI 명령과 Gate 의미는 public contract로 취급한다. 변경 시 deprecation 또는
migration 계획 없이 즉시 교체하지 않는다.

### 충돌 처리

코드 또는 하위 문서가 이 Constitution과 충돌하면 기본적으로 코드 또는 하위
문서의 결함이다. Constitution이 현실과 맞지 않는다면 구현에 맞춰 조용히
덮어쓰지 않고 먼저 헌법 변경 절차를 진행한다.

---

## 24. New Session Onboarding Protocol

새 Claude, Codex, OpenCode 세션은 작업을 시작하기 전에 다음 순서를 따른다.

1. 이 문서를 처음부터 끝까지 읽는다.
2. 관련 Architecture, Lifecycle, Stage Guide, ADR이 있으면 읽는다.
3. Progress 문서와 Git 상태를 확인해 현재 사실을 파악한다.
4. 사용자의 요청을 현재 Stage, Goal, Non-goal, 권한으로 다시 표현한다.
5. 문서와 구현이 충돌하면 구현을 임의로 정답으로 가정하지 않는다.
6. 작업 전에 필요한 upstream 대응과 검증 방법을 확인한다.
7. 현재 범위 밖 아이디어는 구현하지 않고 별도로 표시한다.
8. 변경 후 테스트, Telemetry, 문서를 함께 갱신한다.

### 새 세션이 답할 수 있어야 하는 질문

- Mission Control은 무엇이며 무엇이 아닌가?
- 사용자와 Mission Control, Flight Controller의 권한은 어떻게 다른가?
- Brief와 Interview는 어떤 관계인가?
- Blueprint와 Seed는 어떤 관계인가?
- 누가 Stage 전이를 결정하는가?
- `CLEAR`와 `HOLD`는 무엇을 의미하는가?
- 왜 Flight Controller의 “완료” 보고가 충분하지 않은가?
- 왜 MCP보다 Core Workflow가 먼저인가?
- Ouroboros와 다르게 만들려면 어떤 기록이 필요한가?
- 지금 구현할 수 있는 가장 작은 검증 가능한 다음 단계는 무엇인가?

이 질문에 답할 수 없다면 구현을 시작하기 전에 문맥을 더 읽어야 한다.

---

## 25. Decision Ledger

### 확정된 결정

| 결정 | 상태 |
|---|---|
| 프로젝트명은 Mission Control이다. | Confirmed |
| CLI는 `mcx`다. | Confirmed |
| 사용자 Stage는 Brief, Blueprint, Execute, Verify, Recover다. | Confirmed |
| 내부 대응 용어는 Interview, Seed, Run, Evaluate, Repair다. | Confirmed |
| Gate 결과는 `CLEAR`, `HOLD`다. | Confirmed |
| 최종 성공은 `MISSION COMPLETE`다. | Confirmed |
| 실행 주체는 Flight Controller, 증거는 Telemetry라 부른다. | Confirmed |
| 구현 언어는 Python이다. | Confirmed |
| Core Workflow는 Runtime과 분리한다. | Confirmed |
| 초기 Runtime 방향은 Codex와 OpenCode이며 Gemini는 제외한다. | Confirmed |
| MCP는 Core가 아니라 control surface/adapter다. | Confirmed |
| 원본 Workflow와 최소 권한 철학을 먼저 재구성한다. | Confirmed |
| 첫 산출물은 이 Constitution이다. | Confirmed |
| Brief 종료는 threshold·dimension floor·stability·최소 round를 모두 만족해야 하며, 그것만으로 `CLEAR`가 되지 않는다. | Confirmed (ADR-0009) |
| 답변은 requirement authority(`decision`/`observation`)를 별도 축으로 가지며 observation은 요구사항을 만들지 않는다. | Confirmed (ADR-0010) |
| Python 3.12 + uv + pydantic + pytest, layered layout. | Confirmed (ADR-0012) |
| Persistence는 mission당 단일 JSON 문서의 파일 저장이다 (SQLite·event sourcing 아님). | Confirmed (ADR-0013, ADR-0024 §4) |
| Blueprint QA는 통과 0.90 / FAIL 0.40 / 최대 5회이며, 승인 기록이 QA 근거를 보존한다. | Confirmed (ADR-0019) |
| Recover 재시도 예산은 AC당 2회(새 revision이 리셋)이고, 동일 오류 해시 3회면 중단한다. | Confirmed (ADR-0031) |
| Runtime protocol은 단발 실행(`backend` + `execute`)이다. **cancel은 이행**(ADR-0041 §5), resume은 Phase 9, 스트리밍은 event 층과 함께(시한 미배치). | Confirmed (ADR-0033) |
| 텍스트 lane의 기본 vendor는 Claude, 실행은 Codex다. | Confirmed (ADR-0036) |
| `mcx` CLI 표면은 비대화형 단발 명령이고 exit code는 0(성공/CLEAR)·1(오류)·2(판정 부정)다. | Confirmed (ADR-0038) |
| 병렬 실행과 조건부 consensus는 v1에 포함하지 않는다 — 병렬은 Phase 11(독립 항목), consensus 부재의 출구는 escalation `HOLD`다. | Confirmed (ADR-0024 §3, ADR-0030 §5) |

**2026-08-09 갱신.** 이 표는 Phase 1~6이 진행되는 동안 갱신되지 않아, 11개
항목 중 10개가 이미 ADR로 확정된 상태에서 "미확정"으로 남아 있었다. 최상위
문서가 낡으면 새 세션이 확정된 결정을 되돌리므로, 확정분을 위 표로 옮기고
잔여만 남긴다.

| 항목 | 결정 위치 |
|---|---|
| RecoveryDirective의 exact serialization | [Open Questions §6](../docs/research/OPEN_QUESTIONS.md) — 진입과 packet 축은 ADR-0031로 확정, 필드명만 잔여 |
| Telemetry event·bundle 층 schema와 보존·redaction 정책 | Open Questions §9 — report 층은 ADR-0027로 확정. redaction은 Phase 7 진입 조건 |
| OpenCode adapter의 클래스명과 호출 방식 | 실물 구현 이연 (ADR-0003 note 3) — Execute backend 교체 **구조**는 Phase 6 라우팅 테이블이 연다 |
| reflect(자가개선) 단계의 mcx 대응물과 Hermes 취급 | Phase 10 (Open Questions §10) |
| ~~MCP tool 목록과 transport 세부사항~~ | **확정 (2026-08-09, ADR-0041)** — tool은 `build_parser()`에서 파생(CLI 24 + 비동기 3 + job 2), transport는 stdio 하나, SDK는 optional extra |
| worker가 Mission Control을 재귀 호출하는 것을 무엇이 막는가 | Phase 8 (Open Questions §8) — 텍스트 lane에는 격리가 있고 **실행 lane에는 없다** |

미확정 항목을 구현 편의로 사실상 고정하지 않는다. 반대로, **확정된 항목을
미확정으로 방치하지도 않는다** — Phase 종료 검토 질문 7이 이 표의 갱신
여부를 함께 본다.

---

## 26. First Implementation Gate

이 문서가 작성되었다고 바로 코드를 시작하지 않는다. 첫 구현 전에 다음이 필요하다.

- [x] 이 Constitution을 사용자가 검토하고 필요한 수정을 반영한다.
- [x] `01_ARCHITECTURE.md`에서 Core 경계와 의존 방향을 정의한다.
- [x] `02_MISSION_LIFECYCLE.md`에서 최소 상태 전이와 Recover 정책을 정의한다.
- [x] Brief upstream architecture와 핵심 Interview source를 baseline scan하고, 미완료 심층 조사 항목을 research backlog에 기록한다.
- [x] `05_BRIEF.md`에 input, state, tool restriction, Gate, 테스트를 작성한다.
- [x] 첫 구현 범위를 Brief의 최소 vertical slice로 제한한다.
- [x] 구현 전에 검증할 상태 전이 테스트를 정의한다.

첫 코드의 목표는 “많이 구현하기”가 아니다.

> **Brief가 제한된 capability 안에서 질문과 답변을 상태로 축적하고, 명시적인
> 근거와 사용자 승인 없이는 Blueprint로 넘어가지 못하게 하는 것.**

---

## Appendix A. Constitutional Invariants

아래 조건 중 하나라도 깨지면 기능이 동작하더라도 Mission Control의 올바른
구현으로 간주하지 않는다.

1. 사용자가 Goal과 권한의 최종 소유자다.
2. 한 미션의 상태 전이는 Mission Control만 결정한다.
3. Flight Controller는 자신의 작업을 승인하지 않는다.
4. 승인된 Blueprint 없이 Execute하지 않는다.
5. 승인된 Blueprint를 실행 중 몰래 변경하지 않는다.
6. 모든 Stage 전이는 명시적 `CLEAR` 또는 `HOLD`를 남긴다.
7. 모든 `CLEAR`는 관련 Telemetry를 참조한다.
8. 실행 완료와 검증 완료는 다른 상태다.
9. `MISSION COMPLETE`는 Verify Gate 이후에만 가능하다.
10. 각 역할은 Stage에 필요한 최소 capability만 가진다.
11. Flight Controller는 Mission Control을 재귀 호출하지 않는다.
12. Core Workflow는 특정 Runtime에 종속되지 않는다.
13. 실패 Telemetry는 삭제하지 않고 Recover 입력으로 사용한다.
14. 복구는 bounded하며 무한 반복하지 않는다.
15. 대화 기록만이 미션 상태의 유일한 저장소가 되어서는 안 된다.
16. Ouroboros와 의도적으로 다른 핵심 동작은 ADR과 테스트로 드러난다.
17. 범위 밖 개선은 승인 없이 구현하지 않는다.
18. 문서와 코드의 충돌을 숨기지 않는다.

---

## Appendix B. Example Mission

다음 예시는 흐름을 이해하기 위한 비규범 예시다.

```text
User:
  "기존 서비스에 댓글 기능을 추가하고 싶다."

Brief:
  - 누가 작성할 수 있는가?
  - 수정/삭제가 필요한가?
  - 무엇이 이번 범위 밖인가?
  - 완료를 어떻게 검증할 것인가?

Gate:
  HOLD — 비로그인 사용자 정책과 오류 표시 기준이 미정

Brief continued:
  사용자가 정책과 성공 조건을 결정

Gate:
  CLEAR — Clear for Blueprint

Blueprint:
  Goal, Constraints, Non-goals, Acceptance Criteria, Exit Conditions 작성
  QA 및 사용자 승인

Gate:
  CLEAR — Clear for Execute

Execute:
  각 Acceptance Criterion에 추적되는 제한된 작업 dispatch
  Flight Controllers가 변경과 실행 결과를 Telemetry로 반환

Gate:
  CLEAR — Clear for Verify

Verify:
  테스트/빌드 → 실제 동작 → AC/Non-goal 대조

Gate:
  HOLD — 오류 상태가 UI에 표시되지 않음

Recover:
  실패한 AC, 실패 테스트, 관련 파일 범위만 전달해 교정

Verify:
  실패 테스트와 관련 회귀 검사를 다시 실행

Gate:
  CLEAR — MISSION COMPLETE
```

이 예시에서 중요한 것은 어떤 모델이 코드를 작성했는지가 아니다. 승인된 명세,
제한된 권한, 지속 가능한 상태, 실제 Telemetry, 독립 Gate가 끝까지 유지되었다는
점이다.

---

## Appendix C. Glossary

| 용어 | 설명 |
|---|---|
| Acceptance Criterion | 완료 여부를 관찰·검증할 수 있는 결과 조건 |
| Adapter | Core 계약과 외부 Runtime/Interface 차이를 변환하는 경계 |
| Attempt | 하나의 식별 가능한 실행 또는 복구 시도 |
| Brief | 사용자-facing Interview Stage |
| Blueprint | 사용자-facing Seed 및 그 생성·승인 Stage |
| CLEAR | 현재 Stage의 조건을 충족해 지정된 다음 단계로 진행 가능 |
| Flight Controller | 제한된 작업을 수행하고 Telemetry를 반환하는 실행 주체 |
| Gate | Stage의 진행 가능 여부를 근거와 함께 판단하는 정책 경계 |
| HOLD | 현재 근거로는 진행 불가하며 보완이 필요한 상태 |
| MCP | 외부 host가 Core 기능을 호출하는 control surface 중 하나 |
| MISSION COMPLETE | Verify Gate를 통과한 최종 성공 상태 |
| Mission | Brief부터 최종 판정까지 추적되는 목표 단위 |
| Mission Control | 미션 상태, 정책, dispatch, Gate를 소유하는 control plane |
| Non-goal | 의도적으로 현재 미션 범위에서 제외한 결과 |
| Recover | 실패 증거를 사용한 제한적 corrective path |
| Runtime | Flight Controller 작업을 실제로 수행하는 실행 환경 |
| Seed | 내부에서 사용하는 승인 가능한 불변 실행 명세 |
| Stage | Mission Lifecycle의 책임과 권한이 분리된 구간 |
| Telemetry | 실행과 Gate 결정을 연결하는 구조화된 증거 |

---

## Closing Principle

Mission Control의 품질은 연결한 모델의 수가 아니라, 모델이 실수하거나 과추론해도
원래 의도와 검증 기준을 잃지 않는 능력으로 판단한다.

> **Bounded execution. Durable intent. Evidence-driven progress.**
