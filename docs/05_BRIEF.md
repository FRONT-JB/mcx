# Brief Stage Guide

> **사용자 용어:** Brief<br>
> **내부·원본 대응 용어:** Interview<br>
> **진입 전제:** 새 Mission 또는 명시적으로 Brief로 되돌아온 Mission<br>
> **다음 Stage:** Blueprint (Seed)<br>
> **문서 상태:** Active Draft — 구현 전 계약<br>
> **규범 기준:** `docs/00_MISSION_CONTROL.md`

Brief는 모호한 요청을 곧바로 구현 작업으로 바꾸는 단계가 아니다. 사용자의
의도, 코드베이스에서 관찰한 사실, 아직 검증하지 않은 가정을 분리하고, 다음
Stage가 제품 결정을 추측하지 않아도 될 만큼 미션을 명확하게 만드는 Stage다.

이 문서에서 **MUST**, **MUST NOT**, **SHOULD**, **MAY**는 각각 반드시 지켜야
함, 금지, 특별한 이유가 없다면 지켜야 함, 선택 가능을 뜻한다. 이 문서가 Project
Constitution과 충돌하면 Constitution이 우선한다.

---

## 1. Stage Contract 한눈에 보기

| 항목 | 계약 |
|---|---|
| 목적 | 목표·제약·비범위·성공 조건의 결정적 모호함을 질문과 근거로 제거한다. |
| 입력 | 초기 의도, 허용된 조사 범위, 기존 Brief state, 재진입 사유가 있다면 해당 Telemetry |
| 주요 상태 | 질문·답변, 관찰 사실, 제품 결정, 가정, 미해결 항목, clarity 평가, 승인 |
| 산출물 | 출처가 연결된 Brief handoff와 Gate decision |
| 성공 Gate | `CLEAR — Clear for Blueprint` |
| 보류 Gate | `HOLD — Brief 유지`와 이유·부족한 조건·다음 행동 |
| 핵심 금지 | 구현, 파일 쓰기, Git 변경, Shell 실행, 자기 승인, 무근거 자동 응답 |

정상 흐름은 다음과 같다.

    Initial intent
      → Brief state 생성
      → 가장 영향이 큰 미해결 항목 선택
      → 코드 사실은 제한된 읽기 경로로 조사
      → 제품 결정은 사용자에게 질문
      → 답변과 출처 저장
      → ambiguity/clarity 재평가
      → 필요하면 질문 반복
      → 정확한 state revision에 대한 사용자 승인
      → Brief Gate
          ├─ CLEAR → Blueprint
          └─ HOLD  → 현재 Brief 보완

---

## 2. 목적

Brief는 다음을 달성해야 한다.

1. 사용자가 실제로 원하는 결과를 명시한다.
2. 실행과 검증에 영향을 주는 제약을 드러낸다.
3. 이번 미션에서 의도적으로 하지 않을 일을 분리한다.
4. 관찰하거나 검증할 수 있는 성공 조건의 재료를 확보한다.
5. 제품 결정, 코드베이스 사실, 가정을 서로 다른 종류의 정보로 보존한다.
6. 추가 질문이 실제 Blueprint를 바꾸는지 판단할 수 있는 상태를 만든다.
7. 대화 세션이 사라져도 다음 세션이 이어갈 수 있는 durable state를 남긴다.
8. 사용자 승인과 Gate 판정을 분리한다.

Brief의 품질은 질문 수나 대화 길이로 측정하지 않는다. **다음 Stage가 중요한
결정을 추측할 필요가 있는가**로 측정한다.

### 2.1 비목적

Brief는 다음을 수행하는 단계가 아니다.

- 코드를 작성하거나 수정하는 단계
- 리팩터링, 의존성 변경, 파일 생성, Git 작업을 수행하는 단계
- 실행 계획이나 구현 수단을 최종 확정하는 단계
- Blueprint/Seed를 자동 승인하는 단계
- 사용자가 답해야 할 제품 결정을 모델이 대신 정하는 단계
- 코드에서 확인할 수 있는 사실을 습관적으로 사용자에게 되묻는 단계
- 질문 생성 Flight Controller가 저장소를 직접 탐색하는 단계
- 모델의 “충분히 명확하다”는 문장만으로 종료하는 단계
- 모든 불확실성을 0으로 만드는 끝없는 조사 단계

Brief 중 구현 아이디어가 발견되어도 현재 Stage에서는 실행하지 않는다. 필요하면
Blueprint 후보 context로 기록하되 승인된 범위로 간주하지 않는다.

---

## 3. Upstream Correspondence

| Mission Control | Ouroboros 대응 개념 | 유지하려는 설계 의도 |
|---|---|---|
| Brief | Interview / Big Bang interview | 질문을 통해 암묵적 요구사항을 명시적 상태로 만든다. |
| Brief round | Interview round | 질문과 답변을 순서와 출처가 있는 기록으로 남긴다. |
| Clarity assessment | Ambiguity scoring | 모델의 직감이 아니라 명시적 평가를 종료 Gate 입력으로 사용한다. |
| Brief handoff | Seed generation context | 대화를 실행 명세 생성에 사용할 구조화된 입력으로 바꾼다. |
| Brief Gate | Interview-to-Seed gate | 충분히 명확하고 승인된 경우에만 다음 단계로 진행한다. |

이 대응표는 **개념적 mapping**이다. 현재 upstream의 정확한 클래스명, 파일 경로,
계산식, 완료 threshold, 안정성 streak, brownfield/greenfield 차이는 아직 이
저장소에서 고정된 사실이 아니다.

구현 전 research는 다음을 MUST 확인해야 한다.

- 조사한 Ouroboros repository URL, commit 또는 release
- Interview state와 round의 실제 schema
- 답변 source/provenance 구분 방식
- ambiguity/clarity의 차원, 방향, 범위, 계산식
- 종료 threshold와 별도 hard floor의 존재 여부
- 여러 번 안정적으로 조건을 만족해야 하는지 여부
- 사용자 done/approval 신호의 실제 의미
- 질문 생성과 코드 조사 역할이 어떻게 분리되는지
- 관련 upstream test가 보호하는 실패 상황

이전 조사에서 `bigbang/interview`, `bigbang/ambiguity`, Seed generator,
MCP authoring handler 계열이 연구 후보로 언급되었지만, **pinned upstream에서
경로를 다시 확인하기 전에는 구현 근거로 인용하지 않는다.**

### 3.1 Reconstruction 원칙

- upstream 동작을 이해하기 전에 더 좋아 보이는 방식으로 교체하지 않는다.
- upstream의 수치 예시를 Mission Control 기본값으로 복사하지 않는다.
- 의도적으로 단순화한 동작은 테스트와 ADR 또는 research note로 드러낸다.
- 코드 복사와 행동 재구성을 구분하고 라이선스·고지 의무를 확인한다.

---

## 4. Actors와 Capability Restrictions

Brief 안에서도 책임과 권한을 분리한다. 아래 이름은 책임을 설명하는 용어이며,
구체 클래스명이나 프로세스 수를 확정하지 않는다.

### 4.1 User / Operator

사용자는 다음을 소유한다.

- 목표, 우선순위, 제품 동작에 대한 최종 결정
- 제약과 비범위
- 저장소나 외부 자료 조사 권한
- 현재 Brief revision에 대한 승인
- 충돌하는 요구사항의 해소

사용자는 코드베이스의 현재 사실을 외워서 답할 의무가 없다. 허용된 읽기 범위에서
확인할 수 있으면 시스템이 근거와 함께 조사해야 한다.

### 4.2 Mission Control — Brief Coordinator

Mission Control은 다음을 MUST 수행한다.

- canonical Brief state와 revision 관리
- 다음에 해결할 knowledge gap 선택
- 역할별로 필요한 context만 전달
- 질문·답변·근거·평가·승인 저장
- 질문 루프와 중단 조건 관리
- `CLEAR` 또는 `HOLD` Gate decision 생성

Mission Control은 질문을 직접 답하거나, 사용자 결정을 추측하거나, 코드를
수정해서는 안 된다.

### 4.3 Question Generator Flight Controller

질문 생성기는 **한 번의 dispatch에서 질문 하나를 생성하는 제한된 역할**이다.

| 구분 | 계약 |
|---|---|
| 입력 | Mission Control이 선별한 현재 요약, 미해결 항목, 이전 질문의 최소 context |
| 허용 | 한 번의 모델 completion, 구조화된 질문 결과 반환 |
| 금지 | 파일 읽기·쓰기, Shell, Git, 코드 수정, Browser, 임의 network, MCP 재귀 호출 |
| turn budget | 한 dispatch당 한 turn |
| 출력 | 질문 하나, 겨냥한 gap, 질문이 필요한 이유를 나타내는 제한된 metadata |

질문 생성기는 저장소를 조사하지 않는다. 필요한 사실은 Mission Control이 별도
read-only fact resolution 결과로 제공한다. 질문 생성기는 자신의 질문이 충분한지,
Brief가 완료되었는지, 다음 Stage로 갈지를 결정할 수 없다.

### 4.4 Read-only Fact Resolver

코드베이스나 승인된 문서에서 확인 가능한 사실은 별도의 제한된 책임으로
해결한다.

- 사용자가 명시적으로 허용한 경로와 자료만 읽는다.
- 읽기 전용 repository/document interface만 사용한다.
- 파일 쓰기, Shell 실행, Git 변경, 외부 전송을 하지 않는다.
- 관찰한 값과 source locator를 함께 반환한다.
- 해석과 원문 관찰을 구분한다.
- 찾지 못한 값을 추측하지 않는다.

실제 구현에서 read-only 검색에 어떤 도구를 사용할지는 open decision이다.
중요한 불변 조건은 질문 생성기의 무도구 경계와 사실 조사자의 읽기 전용 경계를
합치지 않는 것이다.

### 4.5 Clarity Assessor

Clarity Assessor는 Brief snapshot을 평가해 다음을 구조화해서 반환한다.

- 평가한 dimension
- 명확한 부분과 부족한 부분
- 충돌과 material assumption
- unresolved item
- score가 있다면 값, 방향, policy version, 근거

Assessor의 출력은 Gate 입력일 뿐 Gate decision이 아니다. Assessor가 LLM을
사용하더라도 tool access 없이 bounded completion으로 실행하고, 파싱 불가능한
결과를 성공으로 해석하지 않는다.

### 4.6 Brief Gate

Gate는 Mission Control의 정책 경계다. 질문 생성기, Fact Resolver, Assessor,
사용자 중 어느 하나도 단독으로 `CLEAR`를 선언하지 않는다. 사용자 승인은
필수지만, 필수 정보와 근거가 없는 상태를 자동으로 통과시키는 유일 조건은 아니다.

---

## 5. 정보 분류: 사실, 결정, 가정

Brief의 모든 중요한 진술은 내용뿐 아니라 **무슨 종류의 지식인지**를 보존해야
한다.

| 종류 | 의미 | 권위 있는 출처 예 | 처리 |
|---|---|---|---|
| Codebase fact | 현재 코드·설정·문서에서 관찰한 사실 | 파일 위치, symbol, config, versioned document | 읽기 근거와 snapshot을 연결한다. |
| User/product decision | 앞으로 무엇을 만들지에 대한 규범적 선택 | 사용자의 명시적 답변 또는 승인 | 코드가 대신 결정하지 않는다. |
| Assumption | 아직 확인하거나 승인하지 않은 임시 전제 | 모델 추론, 불완전한 문맥 | 명시적으로 표시하고 material하면 CLEAR를 막는다. |

### 5.1 분류 규칙

- “현재 인증은 JWT다”는 관찰 가능한 codebase fact일 수 있다.
- “새 기능도 JWT만 사용한다”는 제품 결정 또는 승인된 constraint다.
- “아마 JWT를 유지할 것이다”는 assumption이다.
- codebase fact는 현재 상태를 설명할 뿐 미래 제품 결정을 자동으로 정하지 않는다.
- 사용자 답변도 코드의 현재 상태에 대한 증거가 필요하면 관찰 사실과 대조한다.
- 사실과 결정이 충돌하면 하나를 조용히 덮어쓰지 않고 conflict로 기록한다.
- 출처가 없는 모델 요약은 codebase fact로 승격하지 않는다.

### 5.2 질문 라우팅 규칙

1. 질문이 허용된 범위에서 관찰 가능한 현재 사실인가?
   - 그렇다면 Fact Resolver에 보낸다.
2. 질문이 목표, 정책, 우선순위, 위험 허용 같은 미래 결정인가?
   - 그렇다면 사용자에게 묻는다.
3. 사실 조사 권한이 없거나 근거가 불충분한가?
   - 권한을 요청하거나 `HOLD`한다. 추측으로 채우지 않는다.
4. 답이 Blueprint나 Verify 기준을 실질적으로 바꾸지 않는가?
   - 불필요한 질문으로 만들지 않는다.

---

## 6. Entry Contract

Brief에 진입하려면 최소한 다음이 있어야 한다.

- Mission identity
- 사용자의 초기 의도 또는 문제 설명
- 작업 대상 context
- 허용된 조사 범위와 권한
- 기존 Brief가 있다면 읽을 수 있는 최신 revision
- 재진입이라면 돌아온 이유와 관련 Gate/Telemetry reference

다음 상태에서는 정상 진입으로 간주하지 않는다.

- Mission identity 없이 임시 채팅만 존재함
- 다른 Stage가 canonical current Stage인데 전이 기록 없이 Brief를 시작함
- 초기 의도를 저장할 수 없는 persistence 상태
- 사용자 권한을 넘어선 저장소나 외부 시스템 조사를 전제로 함

Blueprint 이후 specification gap은 source Stage의 `HOLD`와 근거를 보존한 뒤
Brief로 직접 corrective routing한다. 이것은 Recover가 실행하는 repair가 아니다.
재진입은 source Gate/evidence를 참조하고, 변경된 요구사항은 새 Brief revision과
후속 Blueprint 재승인으로 이어져야 한다. 정확한 record serialization은
[Mission Lifecycle](./02_MISSION_LIFECYCLE.md)이 소유한다.

---

## 7. Input Contract

Brief use case는 의미상 다음 입력을 받는다. 이는 conceptual contract이며 최종
Python class나 저장 schema가 아니다.

| 입력 | 필수 | 설명 |
|---|---:|---|
| Mission reference | 예 | canonical Mission을 식별한다. |
| Initial intent | 최초 진입 시 | 사용자의 원문 요청을 보존한다. |
| Authorized context scope | 예 | 읽을 수 있는 repository/document 범위다. |
| Current Brief revision | 재개 시 | stale update를 막기 위한 기준 revision이다. |
| User answer | 답변 시 | 어떤 질문에 대한 답인지 연결한다. |
| Provenance | 예 | user, code, document, research, assumption 등을 구분한다. |
| Re-entry evidence | 재진입 시 | 이전 Stage의 gap과 관련 Telemetry다. |

입력 원문과 정규화된 요약을 분리한다. 모델이 만든 요약만 남기고 사용자의 원문을
버려서는 안 된다.

---

## 8. Brief State

구현은 다음 의미를 보존하는 durable state를 제공해야 한다.

    BriefState
    ├─ mission reference
    ├─ revision and lifecycle metadata
    ├─ initial intent: original + normalized view
    ├─ rounds
    │   ├─ question identity and text
    │   ├─ targeted knowledge gap
    │   ├─ answer
    │   └─ provenance
    ├─ observed facts with source locators
    ├─ user/product decisions
    ├─ assumptions
    ├─ conflicts
    ├─ unresolved items
    ├─ clarity assessments and policy versions
    ├─ user approvals
    └─ Gate decisions and Telemetry references

### 8.1 상태 불변 규칙

1. 질문과 답변은 identity로 연결된다.
2. 답변 source와 knowledge kind를 혼동하지 않는다.
3. 수정은 revision을 증가시키고 이전 값을 감사 가능하게 남긴다.
4. 승인 이후 material field가 바뀌면 기존 승인은 현재 revision에 유효하지 않다.
5. 미답변 질문을 답변된 것처럼 저장하지 않는다.
6. score와 함께 사용한 policy version을 남긴다.
7. Gate decision은 평가한 정확한 Brief revision을 참조한다.
8. persistence 실패 시 메모리 상태만 전이된 것처럼 응답하지 않는다.

### 8.2 논리적 진행 상태

정확한 enum 이름은 Lifecycle 설계에서 확정하되 구현은 다음 상태 의미를 구분해야
한다.

- context를 수집·정규화하는 중
- codebase fact를 조사하는 중
- 사용자 답변을 기다리는 중
- clarity를 평가하는 중
- 사용자 승인을 기다리는 중
- Gate가 `CLEAR`한 revision
- `HOLD`되어 보완이 필요한 revision

`HOLD`는 Brief를 종료한 최종 실패가 아니다. 현재 revision으로 다음 Stage에
진행할 수 없다는 Gate decision이다.

---

## 9. Output Contract

Brief는 Blueprint가 대화 전체를 재해석하지 않아도 되는 **Brief handoff**를
산출한다.

handoff는 최소한 다음 의미를 포함해야 한다.

- Mission과 Brief revision
- 정리된 Goal intent
- Constraints
- Non-goals
- 검증 가능한 성공 조건 후보
- 제품 결정과 결정 주체
- 관련 codebase facts와 source locators
- 남겨 둔 non-material assumption
- unresolved item과 conflict
- 사용한 clarity policy와 평가 결과
- 사용자 approval과 승인한 revision
- Gate decision과 근거 reference

Brief handoff는 승인된 Blueprint가 아니다. Blueprint Stage가 이를 바탕으로
Seed를 생성하고 QA·refinement·승인을 별도로 수행한다.

### 9.1 Exit Contract

Brief에서의 정상 exit는 저장된 `CLEAR — Clear for Blueprint` 하나뿐이다.
`HOLD`는 Stage exit가 아니라 현재 Brief를 유지하는 Gate decision이다.

- CLEAR 시 exact Brief revision, handoff, user approval, Gate evidence를 하나의
  설명 가능한 전이로 보존한다.
- 다음 canonical Stage가 Blueprint로 바뀌기 전에 필요한 state가 모두 durable해야
  한다.
- persistence가 부분 실패하면 Blueprint로 전이하지 않는다.
- 취소·권한 부족·runtime 장애로 진행할 수 없으면 이유와 재개 조건을 남기고
  Brief에 머문다.
- CLEAR된 Brief가 material하게 수정되면 과거 CLEAR를 덮어쓰지 않고 새 revision,
  재평가, 재승인, 새 Gate decision을 요구한다.

---

## 10. Normal Sequence

### Step 1 — Mission과 initial intent 고정

Mission Control은 사용자의 원문 요청을 그대로 보존하고 별도의 normalized view를
만든다. normalization이 요구사항을 추가하거나 삭제해서는 안 된다.

### Step 2 — 최초 knowledge map 생성

Goal, Constraints, Non-goals, Success conditions, unresolved decisions를 기준으로
현재 알려진 것과 부족한 것을 분리한다. 이 dimension 목록은 초기 기준이며 정확한
scoring dimension은 upstream research와 ADR로 확정한다.

### Step 3 — 가장 영향이 큰 gap 선택

다음 Blueprint 또는 검증 가능성에 가장 큰 영향을 주는 gap을 한 번에 하나
선택한다. 질문 수를 늘리기 위해 사소한 항목을 먼저 묻지 않는다.

### Step 4 — 사실인지 결정인지 분류

- 현재 코드·설정·문서에서 확인 가능하면 제한된 Fact Resolver에 위임한다.
- 사용자만 결정할 수 있으면 Question Generator로 질문을 만들고 사용자에게 묻는다.
- 권한이나 근거가 없으면 assumption으로 숨기지 않고 gap으로 유지한다.

### Step 5 — 질문 하나 생성

Mission Control은 필요한 최소 context만 Question Generator에 전달한다. Generator는
한 turn 안에 질문 하나를 반환한다. 여러 질문을 한꺼번에 생성하거나 도구를
호출하지 않는다.

좋은 질문은 다음 성질을 가진다.

- 하나의 중요한 결정을 겨냥한다.
- 답에 따라 Blueprint가 어떻게 달라질지 설명 가능하다.
- 이미 답한 내용을 반복하지 않는다.
- 전문 용어 없이 사용자가 결정할 수 있다.
- 선택지가 자연스럽다면 중립적인 선택지를 제공할 수 있다.
- 특정 구현을 정답으로 유도하지 않는다.

### Step 6 — 답변과 provenance 저장

답변을 해당 question identity, 원문, 수신 시각, source, knowledge kind와 함께
저장한다. 자동으로 해결한 codebase fact는 user answer처럼 가장하지 않는다.

### Step 7 — 충돌과 미해결 항목 갱신

새 답변이 기존 결정, 사실, assumption과 충돌하는지 확인한다. material conflict를
요약으로 지우지 않고 명시적으로 해결한다.

### Step 8 — Ambiguity/Clarity 재평가

현재 snapshot을 versioned policy로 평가한다. score만 저장하지 않고 어떤
dimension이 왜 부족한지 남긴다.

### Step 9 — 반복 또는 승인 요청

material gap이 남으면 Step 3으로 돌아간다. Gate 후보 조건을 만족하면 정확한
Brief revision의 요약을 사용자에게 보여 주고 Blueprint 진행 승인을 요청한다.

### Step 10 — Gate decision

Mission Control은 승인, assessment, unresolved item, provenance, persistence
상태를 함께 평가해 `CLEAR` 또는 `HOLD`를 기록한다.

---

## 11. Ambiguity와 Clarity Policy

점수는 질문 루프를 통제하는 수단이지 진실 그 자체가 아니다.

### 11.1 필수 계약

scoring 구현은 다음을 MUST 명시한다.

- 무엇을 평가하는지
- 높은 값과 낮은 값 중 어느 쪽이 더 명확한지
- 값의 허용 범위
- overall 값의 계산 또는 집계 방식
- dimension별 hard condition 존재 여부
- threshold를 어디서 읽는지
- policy version
- 평가 실패와 confidence를 어떻게 표현하는지

### 11.2 이 문서가 고정하지 않는 것

다음은 upstream 확인과 ADR 전까지 숫자로 고정하지 않는다.

- 정확한 dimension과 weight
- ambiguity 또는 clarity 중 canonical metric
- 통과 threshold
- 특정 dimension의 minimum floor
- 연속 몇 번 조건을 만족해야 하는지
- 최대 질문 수
- greenfield와 brownfield의 서로 다른 정책

구현은 threshold를 prompt 안의 magic number로 숨겨서는 안 된다. versioned
policy로 주입하고 domain test에서 경계값을 검증할 수 있어야 한다.

### 11.3 Score 단독 종료 금지

score가 통과 범위여도 다음 중 하나가 있으면 `HOLD`다.

- material unresolved decision
- Goal 또는 Constraint 충돌
- 검증할 수 없는 성공 조건
- material assumption
- 필요한 provenance 누락
- 현재 revision에 대한 사용자 승인 누락
- persistence 또는 assessment 오류

반대로 score가 하나의 참고값에 불과한데 모델 설명만으로 임의 `CLEAR`해서도
안 된다.

---

## 12. User Approval

사용자 승인은 질문 루프의 종료 신호인 동시에 Blueprint로 진행할 권한이다.

### 승인 계약

- 승인은 특정 Mission의 특정 Brief revision을 참조한다.
- 승인 전에 사용자가 Goal, Constraints, Non-goals, 성공 조건 요약을 볼 수 있어야 한다.
- 승인의 원문 또는 명시적 action을 보존한다.
- 오래된 revision에 대한 승인을 최신 revision에 재사용하지 않는다.
- 승인 뒤 material decision이 바뀌면 새 revision과 재승인이 필요하다.
- “질문을 그만하자”와 “이 내용으로 Blueprint에 진행한다”를 동일하게 취급할지는
  아직 open decision이며, 구현에서 암묵적으로 합치지 않는다.

사용자 승인은 필요조건이지만 충분조건은 아니다. 필수 gap이 남아 있으면
Mission Control은 `HOLD` 이유를 설명해야 한다.

---

## 13. Gate Contract

### 13.1 CLEAR — Clear for Blueprint

Brief Gate는 다음 조건을 모두 만족할 때만 `CLEAR`할 수 있다.

- Goal이 다음 Stage가 재해석할 필요 없이 충분히 명확하다.
- 적용 가능한 Constraints가 기록되어 있다.
- 중요한 Non-goals 또는 의도적 제외가 기록되어 있다.
- 성공 조건이 Blueprint에서 검증 가능한 AC로 정제될 수 있다.
- material unresolved decision과 conflict가 없다.
- material assumption이 해결되었거나 사용자에게 명시적으로 승인되었다.
- clarity policy의 통과 조건을 만족한다.
- 중요한 사실과 결정에 provenance가 있다.
- 사용자가 정확한 Brief revision의 진행을 승인했다.
- state와 approval이 durable storage에 성공적으로 보존되었다.
- Gate decision이 판단 근거와 policy version을 참조한다.

`CLEAR`는 Blueprint가 완성되었다는 뜻이 아니다. Blueprint를 생성·검토할 수
있다는 뜻이다.

### 13.2 HOLD — Brief 유지

위 조건 중 하나라도 충족하지 않으면 낙관적으로 진행하지 않고 `HOLD`한다.
모든 HOLD 결과는 다음을 제공한다.

- 현재 Mission과 Brief revision
- 진행할 수 없는 구체적 이유
- 부족하거나 충돌하는 정보
- 관련 question, assessment, provenance 또는 error reference
- 사용자가 답해야 할 질문 또는 시스템이 수행할 다음 조사
- 권장되는 다음 행동

대표 HOLD 사유:

- 목표가 여러 해석으로 갈린다.
- 사용자만 결정할 수 있는 정책이 미정이다.
- 성공 여부를 관찰할 수 없다.
- codebase fact와 사용자 설명이 충돌한다.
- material assumption이 남아 있다.
- 승인이 없거나 stale하다.
- score policy 결과를 파싱하거나 재현할 수 없다.
- state 저장에 실패했다.
- runtime/capability 문제로 필수 근거를 수집하지 못했다.

---

## 14. Persistence, Provenance, Telemetry

### 14.1 Persistence

Brief state는 특정 Claude, Codex, OpenCode 대화에만 존재해서는 안 된다.

- 각 mutation은 Mission과 previous revision을 확인한다.
- 질문 생성 전후, 답변 수신, assessment, approval, Gate decision을 재개할 수 있다.
- 중복 요청은 같은 round를 두 번 생성하지 않도록 식별 가능해야 한다.
- stale revision update는 조용히 덮어쓰지 않는다.
- 저장 성공 전에는 사용자에게 전이가 완료되었다고 알리지 않는다.
- 재시도는 기존 기록을 삭제하지 않고 별도 attempt/event로 남긴다.

구체적인 파일/SQLite/event store 선택은 Architecture/ADR에서 결정한다.

### 14.2 Provenance

중요한 항목은 최소한 다음 질문에 답할 수 있어야 한다.

- 누가 또는 무엇이 이 내용을 제공했는가?
- 원문은 무엇인가?
- 언제, 어떤 Mission/Brief revision에서 수집했는가?
- code/document fact라면 정확히 어디에서 관찰했는가?
- 해석인지 직접 관찰인지?
- 이후 더 최신 근거로 대체되었는가?

repository fact는 가능하면 repository snapshot identity와 locator를 함께 남긴다.
정확한 snapshot 방식은 open decision이다.

### 14.3 Brief Telemetry

최소 Telemetry 의미:

- Brief 시작·재개
- question generation dispatch와 capability envelope
- 생성된 question과 겨냥한 gap
- Fact Resolver 관찰과 source
- answer receipt와 provenance
- assessment 입력 revision, policy version, 결과
- approval receipt와 대상 revision
- Gate decision, 이유, evidence references
- parsing/runtime/persistence/capability error

Telemetry에는 자격 증명이나 불필요한 개인정보를 남기지 않는다. 원문과 요약을
구분하고 실패 기록도 삭제하지 않는다.

---

## 15. Error와 Recovery Paths

Brief의 오류는 구현 오류와 specification gap을 구분한다.

| 상황 | 필수 동작 | 금지 동작 |
|---|---|---|
| Question Generator 결과 파싱 실패 | 원문 오류를 기록하고 bounded retry 또는 HOLD | 빈 질문을 성공으로 저장 |
| Generator가 여러 질문을 반환 | 계약 위반으로 거부하고 한 질문 형식으로 재요청 | 여러 round로 자동 분해 |
| Generator가 tool 호출을 시도 | 실행을 차단하고 capability violation 기록 | 편의를 위해 권한 허용 |
| runtime unavailable/timeout | 현재 revision 보존, 오류 Telemetry, 정책상 재시도 또는 HOLD | state 초기화 |
| persistence 실패 | 전이·승인·CLEAR 중단 | 메모리 결과만 성공으로 응답 |
| stale answer/revision | 최신 question과 revision을 제시해 재확인 | 최신 state 덮어쓰기 |
| 동일 질문 반복 | no-progress로 기록하고 다른 gap/표현 선택 또는 HOLD | 무한 반복 |
| code fact를 찾지 못함 | unknown과 조사 범위 기록, 권한 요청 또는 사용자 확인 | assumption을 fact로 저장 |
| 사실과 제품 결정 충돌 | conflict로 보존하고 사용자에게 의미를 설명 | 한쪽을 자동 삭제 |
| 사용자가 답변 변경 | 새 revision, 관련 assessment·approval 무효화 | 승인된 snapshot 몰래 수정 |
| user approval만 있고 material gap 존재 | 구체적 이유와 함께 HOLD | approval을 만능 override로 사용 |
| 민감정보가 답변에 포함 | 저장·Telemetry 정책에 따라 최소화/마스킹 | 모든 로그에 복제 |
| 재귀 Mission Control 호출 시도 | 차단하고 capability violation 기록 | 하위 오케스트레이터 생성 |

retry 횟수와 timeout 값은 이 문서에서 고정하지 않는다. 모든 재시도는 식별되고
bounded해야 하며, 진전이 없으면 `HOLD`로 전환한다.

---

## 16. CLI UX 예시

이 Stage의 확정된 canonical command 이름은 `mcx brief`다. 아직 CLI 구현은 없다.
아래는 상호작용 의미를 설명하는 비규범 예시이며 옵션, 인자, 색상, 정확한 출력
schema를 확정하지 않는다.

    $ mcx brief

    Mission Control:
      어떤 결과를 만들고 싶은지 설명해 주세요.

    User:
      기존 서비스에 댓글 기능을 추가하고 싶다.

    Mission Control:
      댓글 작성 권한은 어떤 사용자에게 주어야 하나요?

    User:
      로그인 사용자만 작성할 수 있다.

    Mission Control:
      Brief summary
      - Goal: 기존 서비스에 댓글 작성·조회 기능 추가
      - Constraint: 작성은 로그인 사용자만 가능
      - Scope decision gap: 수정·삭제 포함 여부 미정
      - Verification gap: 실패 시 사용자 경험이 미정

      HOLD — Brief 유지
      Reason: 수정·삭제 범위와 실패 표시 기준에 제품 결정이 필요합니다.
      Next: 위 두 결정을 확인합니다.

조건을 충족하고 사용자가 해당 revision을 승인한 경우:

    CLEAR — Clear for Blueprint
    Evidence:
      - approved Brief revision
      - clarity assessment
      - sourced decisions and facts

CLI는 Gate를 자체 계산하지 않고 Core application boundary의 결과를 표시해야 한다.

---

## 17. Test Matrix

정확한 test framework는 미확정이지만 다음 행동은 구현 전에 test case로 정의한다.

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| B-001 | 모호한 초기 요청으로 시작 | Mission과 Brief revision이 생성되고 중요한 질문 하나를 반환한다. |
| B-002 | Question Generator dispatch | 한 turn, tool 없음, file write/shell/git 없음이 강제된다. |
| B-003 | Generator가 여러 질문 반환 | 결과를 계약 위반으로 거부하고 state를 손상시키지 않는다. |
| B-004 | 현재 코드에서 확인 가능한 사실 | 사용자에게 묻기 전에 제한된 Fact Resolver가 읽기 근거를 반환한다. |
| B-005 | 미래 제품 정책 결정 | code fact로 자동 답하지 않고 사용자에게 질문한다. |
| B-006 | 모델이 만든 추정 | assumption으로 저장하고 fact/decision으로 승격하지 않는다. |
| B-007 | material assumption이 남음 | score가 좋아도 Gate는 HOLD다. |
| B-008 | 중요한 답변 저장 | question, answer, source, knowledge kind, revision이 연결된다. |
| B-009 | code fact와 사용자 설명 충돌 | conflict를 보존하고 해결 전 HOLD한다. |
| B-010 | scoring policy 주입 | threshold나 weight가 prompt magic number가 아니라 versioned policy로 적용된다. |
| B-011 | assessment 결과 파싱 실패 | CLEAR하지 않고 오류 Telemetry와 HOLD/재시도 경로를 따른다. |
| B-012 | score 조건 충족, unresolved decision 존재 | HOLD한다. |
| B-013 | 모든 정보 충족, approval 없음 | HOLD하며 승인 필요를 명시한다. |
| B-014 | 이전 revision 승인 후 내용 변경 | 기존 approval이 stale 처리되고 재승인을 요구한다. |
| B-015 | 현재 revision 승인 및 모든 조건 충족 | CLEAR for Blueprint와 근거 reference를 저장한다. |
| B-016 | persistence 실패 직후 승인 | CLEAR를 기록하거나 표시하지 않는다. |
| B-017 | stale answer가 도착 | 최신 state를 덮어쓰지 않고 재확인을 요청한다. |
| B-018 | 같은 질문이 반복됨 | no-progress를 감지하고 무한 루프를 막는다. |
| B-019 | runtime timeout 후 재개 | 이전 rounds와 unresolved item을 잃지 않고 재개한다. |
| B-020 | generator가 Mission Control MCP 재호출 시도 | 호출을 차단하고 capability violation을 기록한다. |
| B-021 | 사용자가 Brief 중 코드 구현 요청 | 구현하지 않고 현재 Stage 책임과 다음 Gate를 안내한다. |
| B-022 | 사용자 원문과 normalized summary 비교 | 원문을 보존하고 요약이 새 요구사항을 추가하지 않는다. |
| B-023 | 민감정보가 포함된 답변 | 정책에 따라 최소화/마스킹되고 일반 Telemetry에 복제되지 않는다. |
| B-024 | 동일 입력으로 재전송된 answer | idempotency 정책에 따라 round가 중복 생성되지 않는다. |
| B-025 | 사용자 승인은 했지만 성공 조건이 검증 불가 | 승인과 별개로 HOLD하고 gap을 설명한다. |
| B-026 | CLEAR 후 handoff 생성 | Goal/Constraints/Non-goals/성공 조건/출처/승인 revision을 Blueprint가 읽을 수 있다. |

### 17.1 Test doubles

Core test는 실제 Codex/OpenCode 없이 다음 deterministic double로 실행 가능해야 한다.

- 미리 정한 질문을 한 개 반환하는 Question Generator
- source locator가 있는 fact를 반환하는 Fact Resolver
- 경계값과 오류를 제어할 수 있는 Clarity Assessor
- 성공·실패·stale write를 재현하는 Brief repository
- 특정 revision 승인과 거절을 재현하는 approval port

---

## 18. Implementation Checklist

### Upstream research

- [x] upstream repository와 baseline commit을 pin했다.
- [x] 핵심 Interview source에서 state, round, provenance 모델을 baseline scan했다.
- [ ] ambiguity/clarity 계산과 종료 정책을 확인했다.
- [ ] 관련 upstream test가 보호하는 실패 상황을 정리했다.
- [ ] 유지·단순화·변경할 동작을 research note에 기록했다.

위 두 완료 항목은 baseline scan 범위다. handler/skill/test를 포함한 종료 Gate의
end-to-end 조사는 아래 미완료 항목과 research backlog에 남아 있다.

### Domain

- [ ] Mission과 Brief revision identity를 정의했다.
- [ ] question/answer round와 provenance 계약을 정의했다.
- [ ] fact, decision, assumption, conflict를 구분한다.
- [ ] unresolved item과 materiality를 표현한다.
- [ ] approval이 특정 revision을 참조한다.
- [ ] Gate decision이 assessment와 evidence를 참조한다.

### Policy

- [ ] clarity policy를 주입 가능하고 versioned하게 만들었다.
- [ ] threshold와 weight를 prompt에서 분리했다.
- [ ] score 외 hard condition을 테스트할 수 있다.
- [ ] no-progress와 bounded retry 정책의 소유 경계를 정했다.

### Application flow

- [ ] Brief 시작, 질문 생성, 답변 기록, 재개 use case를 분리했다.
- [ ] codebase fact와 user decision의 routing을 구현했다.
- [ ] question generation을 one-turn/no-tool로 강제했다.
- [ ] assessment와 Gate decision을 분리했다.
- [ ] approval 누락·stale approval에서 진행을 막는다.
- [ ] persistence 성공 전 전이를 표시하지 않는다.

### Adapters and surfaces

- [ ] deterministic test double이 실제 runtime 없이 동작한다.
- [ ] runtime 결과를 canonical question/assessment 형태로 정규화한다.
- [ ] `mcx brief`가 Core 규칙을 복제하지 않는다.
- [ ] MCP가 추가되더라도 같은 canonical Brief state를 사용한다.
- [ ] recursive Mission Control 호출이 차단된다.

### Verification and documentation

- [ ] Test Matrix의 정상·실패·재개 경로를 자동화했다.
- [ ] capability restriction을 prompt가 아니라 실행 경계에서도 검증했다.
- [ ] Gate 결정에 필요한 Telemetry가 남는다.
- [ ] upstream과 다른 동작을 ADR/test로 드러냈다.
- [ ] 실제 CLI 상호작용을 관찰했다.
- [ ] 구현 후 이 Stage Guide의 가정과 실제 동작을 맞췄다.

---

## 19. Learning Questions

구현자는 다음 질문에 자신의 말과 test로 답할 수 있어야 한다.

1. 대화 기록과 Brief state는 왜 다른가?
2. codebase fact와 product decision을 섞으면 어떤 실패가 생기는가?
3. assumption을 명시하면 다음 Stage의 안전성이 어떻게 달라지는가?
4. 질문 생성기가 저장소 도구를 가져서는 안 되는 이유는 무엇인가?
5. 왜 질문을 한 번에 하나씩 생성하는가?
6. score 하나만으로 Interview를 끝내면 어떤 모호함을 놓칠 수 있는가?
7. user approval이 왜 필요조건이면서 충분조건은 아닌가?
8. approval을 revision에 묶지 않으면 어떤 stale-state 문제가 생기는가?
9. Mission Control과 Clarity Assessor의 책임은 어떻게 다른가?
10. `HOLD`가 실패가 아니라 제어 상태인 이유는 무엇인가?
11. persistence 실패를 성공처럼 응답하면 왜 헌법 위반인가?
12. 어떤 질문은 사용자가 아니라 코드에서 답해야 하는가?
13. upstream의 종료 threshold를 그대로 복사하기 전에 무엇을 확인해야 하는가?
14. Brief의 Telemetry는 다음 세션과 Blueprint에 어떤 설명 가능성을 제공하는가?

---

## 20. Open Decisions

아래 항목은 이 문서가 구현 편의로 확정하지 않는다.

| 결정 | 필요한 근거/결정 위치 |
|---|---|
| pinned Ouroboros version과 정확한 source path | upstream research |
| canonical metric이 ambiguity인지 clarity인지 | upstream research + ADR |
| dimension, range, direction, weight, 집계식 | upstream research + ADR |
| 통과 threshold와 dimension별 hard floor | Brief policy ADR |
| stability streak 또는 최소 round 필요 여부 | upstream test + ADR |
| greenfield/brownfield 별도 정책 | upstream research |
| maximum rounds, timeout, retry/no-progress budget | Lifecycle/ADR |
| “질문 종료”와 “Blueprint 진행 승인”의 관계 | UX/approval ADR |
| material assumption의 정의와 예외 승인 방식 | Brief policy ADR |
| Fact Resolver의 읽기 도구와 repository snapshot identity | Architecture/Security ADR |
| exact Brief state enum과 persistence schema | Lifecycle/Architecture |
| provenance와 Telemetry의 concrete schema/retention | Architecture/Telemetry design |
| CLI interactive input, resume, 출력 형식 | CLI Reference |
| Question Generator structured output schema | Runtime/Application design |
| corrective re-entry record의 exact schema와 activation identity | Mission Lifecycle |
| 다국어 질문과 저장 원문의 canonical language | UX ADR |

open decision이 해결되기 전 임시 구현값이 필요하면 숨은 default로 두지 않는다.
테스트에서 주입 가능하게 만들고, 임시 상태와 근거를 명시한다.

---

## Appendix A. Brief Invariants

다음 중 하나라도 깨지면 Brief의 올바른 구현으로 간주하지 않는다.

1. Brief Flight Controller는 코드를 구현하지 않는다.
2. Question Generator는 one-turn/no-tool이며 file write, shell, git을 사용할 수 없다.
3. 사용자 결정과 codebase fact와 assumption이 구분된다.
4. 중요한 답변에는 provenance가 있다.
5. score만으로 `CLEAR`하지 않는다.
6. material unresolved item이 있으면 `CLEAR`하지 않는다.
7. 사용자 승인 없이 Blueprint로 진행하지 않는다.
8. 승인은 정확한 Brief revision을 참조한다.
9. 저장 실패를 성공적인 전이로 표시하지 않는다.
10. Question Generator나 Assessor가 자신의 결과를 승인하지 않는다.
11. Gate decision은 Mission Control이 근거와 함께 남긴다.
12. `CLEAR`는 Blueprint 생성 자격이지 승인된 Blueprint 자체가 아니다.

---

## Appendix B. Definition of Ready for Blueprint

Brief revision은 다음 질문에 모두 근거와 함께 답할 수 있을 때에만 Blueprint
후보가 된다.

- 무엇을 왜 만들어야 하는가?
- 반드시 지켜야 할 제약은 무엇인가?
- 이번 미션에서 하지 않을 것은 무엇인가?
- 어떤 관찰 가능한 결과가 성공을 뜻하는가?
- 어떤 내용이 사용자 결정이고 어떤 내용이 현재 코드의 사실인가?
- 아직 assumption 또는 conflict가 남아 있는가?
- 이 결론을 어떤 출처에서 얻었는가?
- 사용자가 이 exact revision으로 Blueprint에 진행하도록 승인했는가?

답할 수 없는 항목이 있으면 Brief는 질문이나 근거 수집을 계속하거나, 진행할 수
없는 이유와 다음 행동을 포함해 `HOLD`한다.
