# ADR 0010 — Answer provenance and requirement authority

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 1 (Specification before execution), Principle 3 (Evidence over reasoning), Principle 6 (Scope is a hard boundary)
- Upstream evidence: [INTERVIEW_UPSTREAM_FINDINGS.md](../research/INTERVIEW_UPSTREAM_FINDINGS.md) §5

## Context

[Brief Guide](../05_BRIEF.md)는 정보를 codebase fact / user decision /
assumption으로 분류하고 “code fact는 미래 제품 결정을 자동으로 정하지 않는다”고
규정했다. 그러나 이 규칙을 **강제하는 지점이 없었다.** §9 Output Contract는
관찰된 사실을 handoff에 포함시키기만 했고, Blueprint가 그 사실을 요구사항으로
승격하는 것을 막는 장치가 없었다.

또한 §7 Input Contract는 provenance를 “user, code, document, research,
assumption”으로 나열해 지식의 종류와 정보의 출처를 하나의 축에 섞어 두었다.

upstream은 이 문제를 두 개의 설계로 해결한다.

1. 답변을 `user` / `observation` 이진값으로 분류한다. 기준은 인간 입력 여부가
   아니라 **결정인지 채택된 사실인지**다. 자동 driver가 사용자를 대신해 확정한
   값은 `user`로 분류된다.
2. 요구사항을 생산하는 모든 소비자에게 상태를 투영할 때 `observation` 답변의
   본문을 placeholder로 대체한다. 질문 텍스트는 그대로 둔다.

upstream은 이 분류를 여러 surface에서 재해석하다 결함을 겪었고(`[from-research]`가
한 handler에서 human으로 분류됨), 그 대응으로 분류 지점을 단일화했다.

## Decision

### 1. 두 개의 직교하는 축

지식의 종류(fact / decision / assumption)는 유지한다. 이와 별도로 **requirement
authority** 축을 도입한다.

| authority | 의미 |
|---|---|
| `decision` | 사용자가 내렸거나 사용자를 대신해 확정된 규범적 선택 |
| `observation` | 다른 곳에서 채택한 사실 |

기준은 결정 여부다. 시스템이 확정한 기본값은 `decision`이고, 사용자가 붙여 넣은
코드 스니펫은 `observation`이다.

### 2. Observation은 요구사항을 만들지 않는다

이를 원칙이 아니라 **투영으로 강제**한다. Brief handoff는 두 채널을 제공한다.

| 채널 | `observation` 처리 |
|---|---|
| Requirement input (Goal/Constraints/Non-goals/성공 조건 도출) | 답변 본문 제외, 질문 텍스트는 유지 |
| Observed facts (source locator 포함) | 온전히 유지 |

withholding은 사실을 숨기는 장치가 아니라 사실이 요구사항으로 승격되는 경로를
끊는 장치다. Blueprint는 여전히 observed facts 채널로 현재 상태와 제약을 읽는다.

투영은 요약이나 검토 단계가 아니라 **입력 지점**에 적용한다. 추출기가 관찰
문장을 한 번 재작성하면 표기가 사라져 결정과 구분할 수 없게 된다.

### 3. 분류는 단일 지점에서 한 번

authority는 답변이 canonical state에 기록되는 지점에서 결정하고, 이후 모든
소비자는 저장된 값을 읽는다. 소비자가 원문 표기를 재해석하지 않는다.

### 4. Assumption은 별도로 유지

Assumption은 두 authority 값 어디에도 자동으로 속하지 않는다. 명시적으로
표시하고 material하면 `CLEAR`를 막는다. 이는 upstream의 이진 분류에 없는 Mission
Control의 확장이며, Constitution §9.1(“가정은 사실처럼 기록하지 않는다”)이
요구한다.

## Consequences

### Positive

- 아무도 결정하지 않은 조건이 명세가 되는 경로가 구조적으로 차단된다.
- 요구사항 권위와 정보 출처가 분리되어 각각 독립적으로 검증할 수 있다.
- 단일 분류 지점이 surface 간 재해석 drift를 방지한다.
- 관찰된 사실은 제약 맥락으로 계속 사용할 수 있다.

### Cost

- handoff가 평면 구조가 아니라 두 채널을 가지므로 Blueprint 입력 계약이 복잡해진다.
- authority 분류 기준이 직관과 어긋나는 경우(자동 확정값이 `decision`)를 문서와
  UX에서 설명해야 한다.
- assumption 축이 추가되어 upstream과 1:1 대응이 아니다.

## Rejected alternatives

- **원칙만 문서화하고 강제하지 않음**: 현재 상태이며, 추출 단계에서 관찰이
  요구사항으로 바뀌는 것을 막지 못한다.
- **출처 축 하나로 5개 값 유지**: 권위와 출처가 섞여 “이 답변이 요구사항을 만들
   수 있는가”를 단일 필드로 판정할 수 없다.
- **handoff에서 observation 전체를 제거**: Blueprint가 제약과 현재 상태를 모른 채
  명세를 만들게 된다.
- **소비자마다 표기를 재해석**: upstream이 실제로 겪은 결함이다.
- **인간/기계 축으로 분류**: 자동 확정값 전체가 요구사항에서 제외되어 정당한
  결정까지 사라진다.

## Verification

- `observation` 답변이 requirement input 투영에서 제외되고 observed facts 채널과
  질문 텍스트에는 남는다 ([Brief Guide](../05_BRIEF.md) §17의 B-031).
- 여러 소비자가 같은 답변을 읽어도 저장된 authority 값을 사용한다 (B-032).
- 시스템이 확정한 기본값이 `decision`으로 분류된다 (B-033).
- assumption이 fact/decision으로 자동 승격되지 않는다 (B-006).
