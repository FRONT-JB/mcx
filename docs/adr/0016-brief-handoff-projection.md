# ADR 0016 — Brief handoff는 저장되는 상태가 아니라 파생 투영이다

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 1 (Specification before execution), Principle 7 (Durable state over conversation memory), §17
- Upstream evidence: [INTERVIEW_UPSTREAM_FINDINGS.md](../research/INTERVIEW_UPSTREAM_FINDINGS.md) §5.5

## Context

[Brief Guide](../05_BRIEF.md) §9는 Brief가 **Brief handoff**를 산출하고 Blueprint가
그것을 읽는다고 규정한다. 목적은 "Blueprint가 대화 전체를 재해석하지 않아도
되게" 하는 것이다.

구현 직전 upstream을 확인한 결과 **대응하는 객체가 없다.**
`SeedGenerator.generate(state, ambiguity_score, ...)`
(`bigbang/seed_generator.py:1719`)는 `InterviewState` 전체와 점수를 그대로 받고,
필요한 것을 내부에서 만든다. `build_requirement_distillation(state)`가 후보를
derive하고 `apply_requirement_distillation`이 승격된 후보를 goal/criteria/
constraint로 나눈다 (`bigbang/requirement_distillation.py:238-275`). 그 결과에
Stage 경계 산출물이라는 지위는 없다.

즉 upstream은 **경계에서 derive하되 결과에 이름을 붙이지 않는다.** Mission
Control이 handoff를 1급 개념으로 두는 것은 upstream에 없는 구조이며, 등록되지
않은 상태였다.

## Decision

### 1. Divergence — handoff를 명시적 타입으로 둔다

**upstream**: Seed 생성기가 interview state 전체를 받는다. 경계 계약이 없다.

**Mission Control**: `BriefHandoff`를 명시적 타입으로 두고 Blueprint는 그것만
읽는다.

**근거**: [ADR-0007](./0007-mcp-is-control-surface.md)과
[Architecture](../01_ARCHITECTURE.md) §6.4가 Stage 간 의존을 계약으로 제한한다.
Blueprint가 `BriefState` 전체를 읽으면 round 원문과 revision 이력과 stability
signal까지 볼 수 있고, §9.1의 두 채널 투영을 우회하는 경로가 열린다. 관찰이
요구사항으로 승격되는 것을 막는 장치가 handoff 밖에 있으면 강제되지 않는다.

### 2. handoff는 저장하지 않는다 — 파생 투영이다

`BriefState`에서 순수 함수로 만들고 저장소에 기록하지 않는다.

저장하면 상태와 handoff가 어긋날 수 있고, 어긋났을 때 어느 쪽이 진실인지 판정할
근거가 없다. 이 점에서는 upstream과 같다 — upstream도 경계에서 매번 derive하며
파생 결과에 권위를 주지 않는다 (파생 캐시는 지문으로 무효화한다).

### 3. `CLEAR` 없이는 만들어지지 않는다

`build_brief_handoff`는 세 가지를 거부한다.

- Gate 판정이 `CLEAR`가 아님
- 판정이 현재와 다른 revision을 평가함
- `CLEAR`인데 승인이 없음 (불변 조건 위반에 대한 방어)

Brief의 정상 exit는 저장된 `CLEAR` 하나뿐이라는 §9.2를 타입 경계에서 강제한다.
use case는 호출자가 건네준 판정을 쓰지 않고 저장된 상태로 다시 판정한다 —
판정 이후 내용이 바뀐 상태에서 옛 판정으로 handoff가 만들어지는 경로를 열지
않기 위해서다.

### 4. 승격되지 않은 후보를 이유와 함께 싣는다

칸별 목록에는 `PROMOTE` 판정을 받은 후보만 담기고, `OMIT`된 후보는 판정 이유와
함께 별도 필드에 남는다. 왜 이 진술이 다음 Stage에 가지 않았는지 설명할 수
있어야 한다. `BLOCK`이 있으면 애초에 `CLEAR`가 아니므로 handoff가 만들어지지
않는다.

## Consequences

### Positive

- Blueprint의 입력이 타입으로 고정되어 대화 원문을 재해석할 경로가 없다.
- 두 채널 투영(§9.1)이 handoff 경계에서 구조적으로 강제된다.
- 상태와 handoff가 어긋날 수 없다.
- 빠진 후보가 이유와 함께 드러난다.

### Cost

- upstream에 대응 객체가 없어 이 지점의 1:1 대조가 성립하지 않는다.
- Blueprint가 handoff에 없는 정보를 필요로 하면 계약을 넓혀야 하며, 그때마다
  "왜 필요한가"를 정당화해야 한다. 이는 의도한 마찰이다.
- 매번 다시 계산하므로 Gate 판정과 승격 판정이 handoff 요청마다 수행된다.

## Rejected alternatives

- **upstream처럼 상태 전체를 넘김**: 계약이 없어 Blueprint가 무엇에 의존하는지
  추적할 수 없고, §9.1 투영을 우회할 수 있다.
- **handoff를 상태에 저장**: 상태와 어긋날 수 있고 어느 쪽이 진실인지 판정할
  근거가 없다. revision마다 저장하면 문서가 커지고 승인 대상이 둘이 된다.
- **`CLEAR` 없이도 만들되 플래그로 표시**: "미완성 handoff"가 존재하면 다음
  Stage가 그것을 읽을 수 있고, §9.2의 단일 exit가 무너진다.

## Verification

- `CLEAR`된 revision에서 Goal/Constraints/Non-goals/성공 조건/출처/승인 revision을
  Blueprint가 읽을 수 있다 ([Brief Guide](../05_BRIEF.md) §17의 B-026).
- `observation` 답변 본문이 요구사항 입력에서 빠지고 관찰 채널에 남는다 (B-031).
- `HOLD`, 차단된 후보, 다른 revision의 판정에서 handoff가 만들어지지 않는다.
