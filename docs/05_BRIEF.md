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
| 주요 상태 | 질문·답변, 관찰 사실, 요구사항 후보(Non-goal·가정·충돌·미해결을 축으로 구분), clarity 평가, 승인 |
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

이 대응표는 **개념적 mapping**이다.

2026-08-07에 pinned baseline
(`Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943`)에서 종료 Gate,
provenance, clarity 계산을 file:line 근거로 조사했다. 결과는
[INTERVIEW_UPSTREAM_FINDINGS.md](./research/INTERVIEW_UPSTREAM_FINDINGS.md)에
있고, 그로부터 확정한 결정은
[ADR-0009](./adr/0009-brief-completion-gate-policy.md),
[ADR-0010](./adr/0010-answer-provenance-and-requirement-authority.md),
[ADR-0011](./adr/0011-brief-deliberate-divergences.md)에 있다.

조사로 확인한 사실:

- Interview state와 round의 schema, answer provenance 필드
- clarity 차원·방향·범위·집계식과 dimension별 hard floor
- 종료 threshold, 안정성 streak, 최소 round의 조합
- 사용자 done/approval 신호가 surface마다 다른 의미를 가진다는 점
- 질문 생성이 tool-less one-turn 역할로 분리되어 있다는 점

아직 조사하지 않은 항목:

- 관련 upstream test가 보호하는 실패 상황 (Phase 1 test case 설계 직전)
- `ooo seed` 진입이 interview score를 다시 강제하는지 (Phase 2)

**pinned upstream에서 경로를 확인하지 않은 내용은 여전히 구현 근거로 인용하지
않는다.**

### 3.1 Reconstruction 원칙

- upstream 동작을 이해하기 전에 더 좋아 보이는 방식으로 교체하지 않는다.
- upstream의 수치 예시를 Mission Control 기본값으로 복사하지 않는다.
- 의도적으로 단순화하거나 다르게 만든 동작은 테스트와
  [divergence register](./adr/0011-brief-deliberate-divergences.md)로 드러낸다.
  research note는 관찰의 자리이지 결정의 자리가 아니다 (Constitution Appendix A
  16번).
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

### 5.2 Requirement authority

위 세 종류는 **지식의 성격**을 나눈다. 이와 직교하는 두 번째 축이 필요하다.
어떤 답변이 요구사항을 만들 권한을 갖는가?

| authority | 의미 | 예 |
|---|---|---|
| `decision` | 사용자가 내렸거나 사용자를 대신해 확정된 규범적 선택 | 사용자 답변, 사용자가 승인한 기본값 |
| `observation` | 다른 곳에서 채택한 사실 | 코드·설정에서 읽은 값, 문서·리서치 인용 |

이 축의 기준은 **인간이 입력했는지가 아니라 결정인지 채택된 사실인지**다.
시스템이 사용자를 대신해 확정한 기본값은 사람이 타이핑하지 않았어도
`decision`이다. 반대로 사용자가 직접 붙여 넣은 코드 스니펫은 사람이
입력했어도 `observation`이다.

`observation`은 **요구사항을 만들 권한이 없다.** 이것은 권고가 아니라 §9의
handoff 투영으로 강제한다. 강제하지 않으면 “현재 코드는 3회 재시도한다”는
관찰이 요구사항 추출 과정에서 “3회 재시도해야 한다”로 바뀌고, 아무도 결정한
적 없는 조건이 명세가 된다.

authority는 답변이 상태에 들어오는 **단일 지점에서 한 번** 결정하고 이후에는
저장된 값을 읽기만 한다 (§8.1 규칙 9). surface마다 출처 표기를 다시 해석하면
같은 표기가 화면에 따라 다르게 분류되는 drift가 생긴다. 이는
[upstream이 실제로 겪은 결함](./research/INTERVIEW_UPSTREAM_FINDINGS.md#5-answer-provenance와-requirement-authority)이며,
단일 분류 지점은 그 대응책이다.

Assumption은 두 축 어디에도 자동으로 속하지 않는다. 명시적으로 표시하고
material하면 `CLEAR`를 막는다.

### 5.3 질문 라우팅 규칙

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
| Current Brief revision | 재개 시 | 승인 유효성 판정의 기준이 되는 내용 버전이다. 덮어쓰기 판정은 쓰기 순서가 담당한다 (§8.1 규칙 3). |
| User answer | 답변 시 | 어떤 질문에 대한 답인지 연결한다. |
| Provenance | 예 | 두 축을 함께 기록한다. authority는 `decision` 또는 `observation` (§5.2), source는 관찰 위치나 응답 주체다. |
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
    │   └─ provenance: authority + source
    ├─ clarity stability signal (연속 통과 횟수)
    ├─ observed facts with source locators
    ├─ requirement candidates
    │   ├─ section (goal / constraint / non_goal / ... )
    │   ├─ text
    │   ├─ content source (user_stated / model_inferred / repo_observed / ... )
    │   ├─ resolution (confirmed / needs_confirmation / unknown / conflicting)
    │   ├─ confirmation authority (user / repo_evidence / none)
    │   └─ required
    ├─ clarity assessments and policy versions
    ├─ user approvals
    └─ Gate decisions and Telemetry references

### 8.1 상태 불변 규칙

1. 질문과 답변은 identity로 연결된다.
2. 답변 source와 knowledge kind를 혼동하지 않는다.
3. 상태는 두 개의 축을 가진다. **내용 버전**(revision)은 요구사항에 영향을 주는
   변경에서만 증가하며 이전 값을 감사 가능하게 남긴다. **쓰기 순서**(sequence)는
   상태가 바뀌는 모든 저장에서 증가하며 덮어쓰기 판정에 쓰인다. 질문 제시,
   clarity 평가 기록, 승인 기록은 저장되지만 내용 버전을 올리지 않는다
   ([ADR-0014](./adr/0014-brief-concurrent-write-protection.md)).
4. 승인 이후 material field가 바뀌면 기존 승인은 현재 revision에 유효하지 않다.
5. 미답변 질문을 답변된 것처럼 저장하지 않는다.
6. score와 함께 사용한 policy version을 남긴다.
7. Gate decision은 평가한 정확한 Brief revision을 참조한다.
8. persistence 실패 시 메모리 상태만 전이된 것처럼 응답하지 않는다.
9. answer authority는 답변이 상태에 들어오는 단일 지점에서 한 번 결정하고,
   이후 모든 소비자는 저장된 값을 읽는다. 소비자가 원문 표기를 다시 해석하지
   않는다.
10. Brief가 material하게 변경되면 저장된 clarity 평가와 stability signal이
    함께 무효화된다. 둘 중 하나만 남기지 않는다.

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

handoff는 **저장되는 상태가 아니라 파생 투영**이다. `CLEAR`된 상태에서 매번
계산하며 저장소에 기록하지 않는다. 칸별 목록에는 승격 판정을 통과한 후보만
담기고, 생략된 후보는 이유와 함께 남는다
([ADR-0016](./adr/0016-brief-handoff-projection.md)).

### 9.1 Requirement projection — observation withholding

handoff는 하나의 평면적 대화 기록이 아니라 **두 개의 구분된 채널**을 제공한다.

| 채널 | 내용 | 소비 방식 |
|---|---|---|
| Requirement input | Goal, Constraints, Non-goals, 성공 조건을 도출하는 입력 | Blueprint의 요구사항·AC 생성이 읽는다. |
| Observed facts | 관찰된 코드·문서 사실과 source locator | Blueprint가 제약과 현재 상태를 이해하는 데 읽는다. |

Requirement input 채널에서는 `observation` authority를 가진 답변의 **본문이
제외되고**, 관찰이 존재했다는 사실과 그것이 어떤 질문을 낳았는지만 남는다.
질문 텍스트는 그대로 투영한다. 관찰을 수집한 목적이 다음 질문을 날카롭게 하는
것이었으므로 그 맥락까지 지우면 안 된다.

Observed facts 채널은 온전히 유지된다. **withholding은 사실을 숨기는 장치가
아니라 사실이 요구사항으로 승격되는 경로를 끊는 장치다.** 이 구분이 무너지면
Blueprint가 제약을 모른 채 명세를 만들거나, 반대로 관찰이 요구사항으로
둔갑한다.

이 투영은 요약이나 검토 단계가 아니라 **입력 지점에서** 적용해야 한다. 요구사항
추출기가 관찰 문장을 한 번 재작성하고 나면 표기가 사라져서 결정과 구분할 수
없게 된다.

### 9.2 Exit Contract

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

초기 context가 prompt-safe 한도를 넘으면 일반 질문보다 먼저 **요약 round**를
수행한다. 원문은 그대로 보존하고, 이후 prompt에는 사용자가 확인한 요약을
사용한다. 한도 값은 policy로 주입하며 초기 기본값은 `3500`자다. 모델이 임의로
잘라낸 context로 질문을 생성하지 않는다.

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

최소 round 수에 도달하기 전에는 평가를 **수행하지 않는다**. 그 구간에서는
어떤 결과가 나와도 종료 후보가 될 수 없으므로 평가 비용이 순수 낭비다.
평가를 생략한 구간과 평가했으나 통과하지 못한 구간을 상태에서 구분한다.

평가 결과는 stability signal을 갱신한다 (§11.1).

### Step 9 — 반복 또는 승인 요청

material gap이 남으면 Step 3으로 돌아간다. 종료 후보 조건을 모두 만족하면
질문 루프를 멈추고 **승인 요청 단계로 넘어간다** (§12). 이 전이는 Gate
`CLEAR`가 아니다. 조건 충족은 “사용자에게 승인을 물을 수 있는 상태”를 뜻하며,
승인 없이 다음 Stage로 진행하지 않는다.

### Step 10 — Gate decision

Mission Control은 승인, assessment, unresolved item, provenance, persistence
상태를 함께 평가해 `CLEAR` 또는 `HOLD`를 기록한다.

---

## 11. Ambiguity와 Clarity Policy

점수는 질문 루프를 통제하는 수단이지 진실 그 자체가 아니다.

정책의 근거와 대안 검토는
[ADR-0009](./adr/0009-brief-completion-gate-policy.md)에 있다. 아래 값은
policy의 **초기 기본값**이며 versioned policy로 주입한다.

### 11.1 종료 후보 조건 — 네 가지가 모두 필요하다

질문 루프를 멈출 수 있는 상태(“종료 후보”)는 다음을 **모두** 만족해야 한다.
하나라도 미달이면 루프를 계속한다.

| 조건 | 초기 기본값 | 이 조건이 막는 실패 |
|---|---|---|
| 전체 ambiguity threshold | `overall <= 0.20` | 전반적으로 모호한 상태의 조기 종료 |
| dimension별 minimum floor | goal `0.75`, constraint `0.65`, success criteria `0.70`, context `0.60`(brownfield) | 한 축이 무너졌는데 다른 축의 높은 점수가 가중 평균으로 가리는 상황 |
| stability signal | 연속 `2`회 통과 | 단발성으로 낮게 나온 평가에 의한 종료 |
| minimum rounds | `3` | 근거가 쌓이기 전의 종료 |

`floor`가 별도로 필요한 이유는 집계 방식 때문이다. 가중 평균만 사용하면 성공
조건이 전혀 검증 불가능해도 goal과 constraint 점수가 높아 전체 threshold를
통과할 수 있다. floor는 그 상쇄를 막는다.

### 11.2 Metric 정의

- canonical metric은 **ambiguity**이며 **낮을수록 명확**하다. 범위는
  `0.0`~`1.0`이다.
- dimension은 **clarity**로 평가하며 **높을수록 명확**하다. 범위는 동일하다.
- 집계: `ambiguity = 1 − Σ(dimension clarity × weight)`.
- 초기 weight — greenfield 3차원: goal `0.40`, constraint `0.30`,
  success criteria `0.30`. brownfield 4차원: goal `0.35`, constraint `0.25`,
  success criteria `0.25`, context `0.15`.
- 두 metric의 방향이 반대이므로 저장·로그·CLI 출력에서 어느 쪽인지 항상
  명시한다.

brownfield 정책은 차원과 weight의 **자리를 예약**한다. v1 첫 구현은 greenfield
경로를 대상으로 하며, brownfield 전용 탐색 단계는 범위에 포함하지 않는다
([ADR-0011](./adr/0011-brief-deliberate-divergences.md)).

### 11.3 정책 주입과 실패 표현

- threshold, floor, weight, streak, minimum round는 prompt 안의 magic number가
  아니라 versioned policy 객체로 주입한다.
- 저장된 평가 결과는 사용한 policy version을 함께 남긴다.
- 평가 실패(파싱 불가, runtime 오류)는 낮은 점수나 높은 점수 어느 쪽으로도
  해석하지 않는다. 결과 없음으로 기록하고 stability signal을 초기화한다.
- domain test가 각 조건의 경계값을 독립적으로 검증할 수 있어야 한다.

### 11.4 Stability signal의 수명

- 평가가 종료 후보 조건을 만족하면 signal을 1 증가시키고, 만족하지 못하면
  `0`으로 초기화한다.
- Brief가 material하게 변경되면 저장된 평가와 signal을 함께 무효화한다
  (§8.1 규칙 10).
- `CLEAR` 이후 사용자가 Brief를 다시 열면 signal은 `0`에서 시작한다. 재개는
  이전 종료 판단에 대한 도전이므로 이전 안정성을 승계하지 않는다.
- signal 갱신은 durable하게 저장한 뒤에만 사용자에게 보고한다. 저장에
  실패했는데 “한 번 더 확인하면 됩니다”라고 응답하면 사용자는 진행되지 않는
  루프에 갇힌다.

### 11.5 Score 단독 종료 금지

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

### 11.6 Closure audit — 점수는 감사의 자격이지 종료의 자격이 아니다

종료 후보 조건(§11.1)을 모두 만족해도 곧바로 승인 요청으로 가지 않는다.
**closure 감사**가 material한 미해결 결정이 남아 있지 않은지 판정한다.
upstream 근거: `agents/seed-closer.md`("Treat a low ambiguity score as
permission to audit closure, not permission to close"),
`skills/interview/SKILL.md` step 8, 합성 함수
`mcp/tools/subagent.py:2732` — 상세는
[SEED_UPSTREAM_FINDINGS §13](./research/SEED_UPSTREAM_FINDINGS.md). 결정은
[ADR-0020](./adr/0020-brief-closure-audit.md).

세 관점(lane)이 독립적으로 본다.

| lane | 과제 | 판정력 |
|---|---|---|
| closer | 6축 점검표(소유권/SSoT·API 계약·lifecycle/복구·마이그레이션·cross-client·검증, brownfield/system-level 한정) 포함 closure gate 적용 | **verdict가 gate** |
| contrarian | 숨은 가정·과적된 용어·건너뛴 결정 공격 | HIGH 심각도만 차단 |
| gap_hunter | 빠진 요구·미기재 제약·검증 불가 성공 조건 사냥 | HIGH 심각도만 차단 |

합성은 결정적이다 — closer가 `not_ready`면 차단(질문은 blocking_question,
없으면 reason), advisory HIGH마다 차단(질문은 question, 없으면 finding),
MEDIUM/LOW는 차단하지 않는다. 차단 질문은 다음 round의 입력이 된다.

감사 결과는 revision에 묶어 저장한다. material 변경이 revision을 올리므로
오래된 감사는 자동으로 무효가 된다. 계약 문장(gate summary, lane 과제,
severity 규칙)은 upstream 영어 원문 그대로 쓴다 — 번역은 변형이다
(ADR-0020 §4). ambiguity 점수는 감사 요청에 전달하지 않는다
(`upstream과 다름` — ADR-0020 §5에 등록).

---

## 12. User Approval

“질문을 그만하자”와 “이 내용으로 Blueprint에 진행한다”는 **서로 다른 두
신호**다. 구현에서 하나로 합치지 않는다.

| 신호 | 의미 | 효과 |
|---|---|---|
| 종료 후보 도달 | §11.1의 네 조건 충족 또는 사용자의 중단 요청 | 질문 루프를 멈추고 승인 요청 단계로 넘어간다. |
| 진행 승인 | 사용자가 특정 revision으로 Blueprint 진행을 승인 | Gate가 `CLEAR`를 판정할 수 있는 조건 하나가 충족된다. |

질문을 그만두는 것만으로는 다음 Stage로 가지 않는다. 반대로 사용자가 언제든
중단을 요청할 수 있지만, 그 경우에도 §11.5의 hard condition이 남아 있으면
Gate는 `HOLD`한다.

### 12.1 Restate gate — 승인을 요청하는 방식

승인 요청은 대화 전체를 다시 보여 주는 방식이 아니다. 합의된 목표를 **한
문장으로 재진술**하고, 그 한 줄만 읽은 사람도 같은 결론에 도달하는지 확인한다.

- Brief의 다른 모든 기록은 원문과 구조를 보존한다. 압축은 이 지점에만 적용한다.
- 재진술은 새로운 요구사항을 추가하거나 합의된 제약을 빠뜨리지 않는다.
- 사용자가 재진술을 수정하면 그 수정이 새 답변으로 기록되고 revision이
  올라간다. 수정된 재진술을 승인 없이 그대로 통과시키지 않는다.
- 재진술과 함께 Goal, Constraints, Non-goals, 성공 조건 요약을 볼 수 있어야
  한다.

### 12.2 승인 계약

- 승인은 특정 Mission의 특정 Brief revision을 참조한다.
- 승인의 원문 또는 명시적 action을 보존한다. 상태 전이만으로 승인을 갈음하지
  않는다.
- 오래된 revision에 대한 승인을 최신 revision에 재사용하지 않는다.
- 승인 뒤 material decision이 바뀌면 새 revision과 재승인이 필요하다.
- 승인 기록의 저장이 실패하면 승인받지 않은 것으로 취급한다.

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
- 승격할 수 없는 요구사항 후보가 없다. 충돌은 `required` 여부와 무관하게 막고,
  미해결·미확인·권위 부족은 `required`인 후보에서 막는다
  ([ADR-0015](./adr/0015-requirement-candidate-model.md)).
- clarity policy의 종료 후보 조건 네 가지를 모두 만족한다 (§11.1).
- 현재 revision의 closure 감사가 존재하고 ready다 (§11.6,
  [ADR-0020](./adr/0020-brief-closure-audit.md)).
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
- stale write는 조용히 덮어쓰지 않는다. 판정 기준은 내용 버전이 아니라 쓰기
  순서다 — 요구사항을 바꾸지 않는 변경도 저장은 되어야 하기 때문이다
  (`upstream 대응물 없음`, [ADR-0014](./adr/0014-brief-concurrent-write-protection.md)).
- 저장 성공 전에는 사용자에게 전이가 완료되었다고 알리지 않는다.
- 재시도는 기존 기록을 삭제하지 않고 별도 attempt/event로 남긴다.
- 사용자 답변은 canonical state에 먼저 저장한 뒤 Telemetry를 기록한다.
  Telemetry 저장소의 실패나 지연이 Brief 진행을 막아서는 안 된다. 반대로
  Telemetry 성공을 상태 저장 성공으로 간주하지도 않는다.

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
| stale write 충돌 | 최신 question과 revision을 제시해 재확인 (`Phase 7 미구현` — Phase 1은 탐지 후 오류 전파까지) | 최신 state 덮어쓰기 |
| 동일 질문 반복 | no-progress로 기록하고 다른 gap/표현 선택 또는 HOLD | 무한 반복 |
| code fact를 찾지 못함 | unknown과 조사 범위 기록, 권한 요청 또는 사용자 확인 | assumption을 fact로 저장 |
| 사실과 제품 결정 충돌 | conflict로 보존하고 사용자에게 의미를 설명 | 한쪽을 자동 삭제 |
| 사용자가 답변 변경 | 새 revision, 관련 assessment·approval 무효화 | 승인된 snapshot 몰래 수정 |
| user approval만 있고 material gap 존재 | 구체적 이유와 함께 HOLD | approval을 만능 override로 사용 |
| 민감정보가 답변에 포함 | 저장·Telemetry 정책에 따라 최소화/마스킹 | 모든 로그에 복제 |
| 재귀 Mission Control 호출 시도 | 차단하고 capability violation 기록 | 하위 오케스트레이터 생성 |
| 초기 context가 prompt-safe 한도 초과 | 요약 round를 먼저 요구하고 원문 보존 | 모델이 임의로 잘라낸 context로 질문 생성 |
| 질문 생성이 반복 실패하고 사용자가 재시도를 거부 | 재개 조건과 이유를 명시한 `HOLD`로 남긴다 | 조용한 종료 또는 상태 삭제 |
| clarity 평가 결과를 파싱할 수 없음 | 결과 없음으로 기록하고 stability signal을 초기화 | 실패를 낮은 ambiguity로 해석 |
| stability signal 저장 실패 | 오류로 처리하고 진행 가능 상태를 보고하지 않음 | 저장되지 않은 signal로 “한 번 더 확인” 응답 |

retry 횟수와 timeout 값은 이 문서에서 고정하지 않는다. 모든 재시도는 식별되고
bounded해야 하며, 진전이 없으면 `HOLD`로 전환한다.

재개 불가능한 terminal status를 별도로 도입할지는
[Mission Lifecycle](./02_MISSION_LIFECYCLE.md)이 소유하는 결정이다. Brief는
그때까지 재개 조건을 명시한 `HOLD`로 표현하며, 상태를 삭제하거나 조용히
종료하지 않는다.

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

종료 후보 조건을 모두 충족하면 질문을 멈추고 재진술로 승인을 요청한다.

    Mission Control:
      합의된 내용을 한 문장으로 정리했습니다.

        goal: 로그인 사용자가 게시물에 댓글을 작성·조회할 수 있게 한다.
              (수정·삭제는 이번 범위 밖)

      이 한 줄만 읽은 사람도 같은 결과를 떠올릴까요?

    User:
      맞다.

사용자가 해당 revision을 승인한 경우:

    CLEAR — Clear for Blueprint
    Evidence:
      - approved Brief revision
      - clarity assessment (policy version, stability signal)
      - sourced decisions and facts

CLI는 Gate를 자체 계산하지 않고 Core application boundary의 결과를 표시해야 한다.

---

## 17. Test Matrix

정확한 test framework는 미확정이지만 다음 행동은 구현 전에 test case로 정의한다.

> **upstream 근거 표시.** 이 표는 Brief upstream 조사(`a2cb097`) **이전에**
> 작성되었고, 조사 결과를 반영한 재조정(`9886877`)은 모든 행을 다시 훑지 않았다.
> 따라서 **표시가 없는 행은 upstream과 개별 대조되지 않았다.** 검증된 계약으로
> 취급하지 않는다.
>
> 개별 대조가 끝난 행에는 근거를 함께 적는다. 대응물이 없으면
> `upstream 대응물 없음`과 등록 ADR을, 확인하지 못했으면 `upstream 미확인`을
> 그 자리에 적는다.

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| B-001 | 모호한 초기 요청으로 시작 | Mission과 Brief revision이 생성되고 중요한 질문 하나를 반환한다. |
| B-002 | Question Generator dispatch | 한 turn, tool 없음, file write/shell/git 없음이 강제된다. |
| B-003 | Generator가 여러 질문 반환 | 결과를 계약 위반으로 거부하고 state를 손상시키지 않는다. |
| B-004 | 현재 코드에서 확인 가능한 사실 | 사용자에게 묻기 전에 제한된 Fact Resolver가 읽기 근거를 반환한다. |
| B-005 | 미래 제품 정책 결정 | code fact로 자동 답하지 않고 사용자에게 질문한다. |
| B-006 | 모델이 만든 추정 (`content_source=model_inferred`) | 사용자 확인 없이는 요구사항 칸으로 승격되지 않는다. |
| B-007 | `required`인 후보가 미해결·미확인으로 남음 | score가 좋아도 Gate는 HOLD다. 선택 후보는 이유와 함께 생략된다. |
| B-008 | 중요한 답변 저장 | question, answer, source, knowledge kind, revision이 연결된다. |
| B-009 | code fact와 사용자 설명 충돌 (`resolution=conflicting`) | `required` 여부와 무관하게 HOLD한다. tradeoff는 사용자만 고른다. |
| B-010 | scoring policy 주입 | threshold나 weight가 prompt magic number가 아니라 versioned policy로 적용된다. |
| B-011 | assessment 결과 파싱 실패 | CLEAR하지 않고 오류 Telemetry와 HOLD/재시도 경로를 따른다. |
| B-012 | score 조건 충족, unresolved decision 존재 | HOLD한다. |
| B-013 | 모든 정보 충족, approval 없음 | HOLD하며 승인 필요를 명시한다. |
| B-014 | 이전 revision 승인 후 내용 변경 | 기존 approval이 stale 처리되고 재승인을 요구한다. |
| B-015 | 현재 revision 승인 및 모든 조건 충족 | CLEAR for Blueprint와 근거 reference를 저장한다. |
| B-016 | persistence 실패 직후 승인 | CLEAR를 기록하거나 표시하지 않는다. |
| B-017 | 저장된 것보다 앞서지 않는 쓰기가 도착 (`upstream 대응물 없음`, [ADR-0014](./adr/0014-brief-concurrent-write-protection.md)) | 최신 state를 덮어쓰지 않는다. 재확인 요청은 Phase 7에서 구현한다. |
| B-018 | 같은 질문이 반복됨 | no-progress를 감지하고 무한 루프를 막는다. |
| B-019 | runtime timeout 후 재개 | 이전 rounds와 unresolved item을 잃지 않고 재개한다. |
| B-020 | generator가 Mission Control MCP 재호출 시도 | 호출을 차단하고 capability violation을 기록한다. |
| B-021 | 사용자가 Brief 중 코드 구현 요청 | 구현하지 않고 현재 Stage 책임과 다음 Gate를 안내한다. |
| B-022 | 사용자 원문과 normalized summary 비교 | 원문을 보존하고 요약이 새 요구사항을 추가하지 않는다. |
| B-023 | 민감정보가 포함된 답변 | 정책에 따라 최소화/마스킹되고 일반 Telemetry에 복제되지 않는다. |
| B-024 | 동일 입력으로 재전송된 answer | idempotency 정책에 따라 round가 중복 생성되지 않는다. |
| B-025 | 사용자 승인은 했지만 성공 조건이 검증 불가 | 승인과 별개로 HOLD하고 gap을 설명한다. |
| B-026 | CLEAR 후 handoff 생성 (`upstream 대응물 없음`, [ADR-0016](./adr/0016-brief-handoff-projection.md)) | Goal/Constraints/Non-goals/성공 조건/출처/승인 revision을 Blueprint가 읽을 수 있다. HOLD·차단·다른 revision에서는 만들어지지 않는다. |
| B-027 | 전체 threshold는 통과, 한 dimension이 floor 미달 | 종료 후보가 되지 않고 질문을 계속한다. |
| B-028 | 종료 조건을 한 번만 만족 | stability signal이 1이며 종료 후보가 아니다. |
| B-029 | 최소 round 도달 전 | clarity 평가를 수행하지 않고, 미평가 상태가 미통과와 구분된다. |
| B-030 | 네 조건 모두 충족 | 질문 루프가 멈추고 승인 요청 단계로 전이한다. 승인 없이 `CLEAR`하지 않는다. |
| B-031 | observation authority 답변 포함 | requirement input 투영에서 본문이 제외되고, observed facts 채널과 질문 텍스트에는 남는다. |
| B-032 | 동일 답변을 여러 소비자가 읽음 | 저장된 authority 값을 읽으며 원문 표기를 재해석하지 않는다. |
| B-033 | 시스템이 사용자를 대신해 확정한 기본값 | observation이 아니라 decision으로 분류된다. |
| B-034 | `CLEAR` 이후 사용자가 답변을 추가 | 저장된 평가와 stability signal이 함께 초기화되고 재승인이 필요하다. |
| B-035 | clarity 평가 결과 파싱 실패 | 결과 없음으로 기록하고 signal을 초기화하며 낮은 ambiguity로 해석하지 않는다. |
| B-036 | stability signal 저장 실패 | 오류로 처리하고 진행 가능 상태를 보고하지 않는다. |
| B-037 | 초기 context가 한도 초과 | 일반 질문보다 요약 round를 먼저 수행하고 원문을 보존한다. |
| B-038 | 사용자가 Restate 문장을 수정 | 새 revision으로 기록되고 자동 승인되지 않는다. |
| B-039 | 동일 Brief를 CLI와 MCP에서 처리 | 같은 policy와 Gate 조건이 적용되어 동일한 판정을 만든다. |
| B-040 | 종료 후보 조건 충족, closure 감사 없음 (`skills/interview/SKILL.md` step 8, [ADR-0020](./adr/0020-brief-closure-audit.md)) | `CLEAR` 거부. 점수는 감사의 자격이지 종료의 자격이 아니다. |
| B-041 | closer가 `not_ready` (`subagent.py:2732` 합성 규칙) | 차단. blocking_question(없으면 reason)이 HOLD 사유로 남는다. |
| B-042 | advisory lane이 HIGH 심각도 (`subagent.py:2760` 근방) | 차단. MEDIUM/LOW는 차단하지 않는다. |
| B-043 | 감사 후 material 변경 발생 (`upstream 대응물 없음` — revision 바인딩은 우리 방식, [ADR-0020](./adr/0020-brief-closure-audit.md) §6) | 감사가 stale이 되어 `CLEAR` 거부. 재감사가 필요하다. |

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
- [x] ambiguity/clarity 계산과 종료 정책을 확인했다. (CLI/MCP/skill 3개 surface end-to-end)
- [x] 관련 upstream test가 보호하는 실패 상황을 정리했다. (findings §8.5)
- [x] 유지·단순화·변경할 동작을 research note에 기록했다.

조사 결과는
[INTERVIEW_UPSTREAM_FINDINGS.md](./research/INTERVIEW_UPSTREAM_FINDINGS.md),
결정은 ADR-0009~0011에 있다. upstream test 조사는 Phase 1 test case를 코드로
옮기기 직전에 수행한다.

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
| maximum rounds, timeout, retry/no-progress budget | Lifecycle/ADR |
| material assumption의 정의와 예외 승인 방식 | Brief policy ADR |
| Fact Resolver의 읽기 도구와 repository snapshot identity | Architecture/Security ADR |
| exact Brief state enum과 persistence schema | Lifecycle/Architecture |
| provenance와 Telemetry의 concrete schema/retention | Architecture/Telemetry design |
| CLI interactive input, resume, 출력 형식 | CLI Reference |
| Question Generator structured output schema | Runtime/Application design |
| corrective re-entry record의 exact schema와 activation identity | Mission Lifecycle |
| 재개 불가 terminal status 도입 여부 | Mission Lifecycle |
| 다국어 질문과 저장 원문의 canonical language | UX ADR |
| brownfield 탐색 단계와 4번째 차원의 활성화 시점 | 별도 RFC (v1 이후) |
| 질문 후보 패널과 다중 관점 검토의 도입 조건 | 별도 RFC (v1 이후) |

2026-08-07에 다음 항목이 ADR-0009~0011로 닫혔다: pinned source path, canonical
metric과 방향, dimension·weight·집계식, 통과 threshold와 dimension floor,
stability streak와 최소 round, greenfield/brownfield 정책 구조, “질문 종료”와
“진행 승인”의 관계.

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
13. `observation` authority를 가진 답변은 요구사항을 만들지 않는다.
14. 종료 후보 조건 충족은 승인 요청 자격이지 `CLEAR`가 아니다.
15. answer authority는 단일 지점에서 한 번 결정되고 소비자가 재해석하지 않는다.
16. CLI와 MCP는 동일한 clarity policy와 Gate 조건을 사용한다.

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
