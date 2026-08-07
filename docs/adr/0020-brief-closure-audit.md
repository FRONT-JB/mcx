# ADR 0020 — Brief 종료의 closure 감사: 점수는 감사의 자격이지 종료의 자격이 아니다

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 3 (Evidence over reasoning), Principle 5 (User authority), §6.5 (surface 간 동일 state)
- Upstream evidence: [SEED_UPSTREAM_FINDINGS.md](../research/SEED_UPSTREAM_FINDINGS.md) §12, §13

## Context

[ADR-0009](./0009-brief-completion-gate-policy.md)의 종료 후보 조건 네 가지는
모두 **점수 기반**이다. upstream은 그 위에 판단 감사를 하나 더 얹는다 —
`agents/seed-closer.md:13`:

> "Treat a low ambiguity score as permission to audit closure, not permission
> to close."

강제는 두 겹이다. MCP 계층이 인터뷰어 프롬프트에 closure gate 요약을
삽입하고(`mcp/tools/subagent.py:1213` — "Do not treat ambiguity <= 0.2 as
sufficient for closure"), skill 계층이 종료 선언 직전에 **3-lane fan-out**을
규정한다(`skills/interview/SKILL.md` step 8).

- `closer` — seed-closer 기준(6축 점검표 포함) 적용. **이 lane의 verdict만
  gate다.**
- `contrarian` — 숨은 가정, 과적된 용어, 건너뛴 결정 공격. HIGH 심각도만 차단.
- `gap_hunter` — 빠진 요구, 미기재 제약, 검증 불가 AC 사냥. HIGH만 차단.

합성은 LLM 없는 순수 함수다(`synthesize_seed_closer_tripanel`,
`subagent.py:2732` — "This is pure and deterministic — no LLM judge — so
seed_ready is testable"). 도그푸딩 관측(§12)에서 이 감사가 실제로 blocking을
만들었다 — 검수 기준 3개가 전부 회귀 방지여서 근본 문제를 아무것도 재지
않는다는 검증 축 판정.

Mission Control의 Brief Gate는 현재 결정적 조건(clarity 정책 + 승인 + 승격
판정)만 본다. 점수가 통과 범위이고 승인이 있으면 material한 미해결 결정이
남아 있어도 `CLEAR`가 가능하다 — §11.5가 산문으로 금지하는 상황을 코드가
막지 않는다.

## Decision

### 1. 감사를 Core의 Brief Gate에 둔다

upstream은 skill 계층에 둔다. 우리는 domain에 두어 모든 surface가 같은 감사를
거친다. Brief 종료 gate, Seed 진입 gate, QA 루프에 이어 같은 비대칭의 **네
번째** 확인이며 대응도 같다 ([ADR-0011](./0011-brief-deliberate-divergences.md)
Divergence 1, [ADR-0019](./0019-blueprint-qa-loop.md) §1). skill 계층 배치의
대가는 §12.2(QA 결과 store 미반영)·§12.3(Runtime 바인딩 우회)으로 실측되었다.

### 2. 3-lane을 전부 재구성한다

사용자 결정(2026-08-08). upstream의 **기본값**이 3-lane이고 closer 단일
실행은 "병렬 primitive가 없는 환경"의 backward-compatible fallback이다
(`skills/interview/SKILL.md:665`). Core에는 그 제약이 없으므로 기본값을
따른다.

역할은 포트 둘로 나뉜다 — 판정을 내는 `ClosureAssessor`(closer)와 관점 공격을
하는 `ClosureChallenger`(contrarian·gap_hunter가 같은 포트를 다른 과제로 두 번).
출력 형태가 다르기 때문이다(closer는 verdict, advisory는 severity).

### 3. 합성은 결정적 도메인 코드다

`ClosureAudit.decision`이 upstream `synthesize_seed_closer_tripanel`의 규칙을
그대로 구현한다.

| 입력 | 결과 |
|---|---|
| closer가 `not_ready` | 차단. 질문 = `blocking_question`, 없으면 `reason` |
| advisory가 HIGH | 차단. 질문 = `question`, 없으면 `finding` |
| advisory가 MEDIUM/LOW | 차단하지 않음 |
| closer `ready` ∧ HIGH 없음 | ready |

upstream의 missing-lane 차단 규칙(세 lane 결과가 모두 있어야 ready)은 별도
검사가 아니라 **타입으로 해소된다** — `ClosureAudit`은 세 report를 필수 필드로
요구한다.

### 4. lane 계약 문장은 upstream 원문 그대로 쓴다

closer의 gate summary, 두 advisory의 과제 문장, severity 규칙을 **영어
원문으로** 상수에 담는다. quality bar를 한국어로 번역해 넣고 등록하지 않았던
이탈([ADR-0019](./0019-blueprint-qa-loop.md) §4)의 재발 방지다. 계약이 문장
자체인 곳에서 번역은 변형이다.

### 5. ambiguity 점수를 감사 요청에 전달하지 않는다

**upstream과 다르다 — divergence로 등록한다.** upstream은 점수를 전달하고
"충분조건으로 쓰지 마라"는 경고를 얹는다. 우리는 anchoring 위험 자체를
제거한다. 평가자에게 통과선을 알리지 않는 기존 패턴(ADR-0009, ADR-0019 §3)과
같은 방향이며, 경고로 위험을 관리하는 것보다 위험을 없애는 편이 낫다.

### 6. 감사 결과는 revision에 묶어 상태에 저장한다

승인과 같은 방식이다(`ClosureAuditRecord.revision`). material 변경이
revision을 올리므로 오래된 감사는 자동으로 stale이 되고, 세 곳의 reset을
수정할 필요가 없다. 감사가 상태로 남아야 Gate 판정을 나중에 재구성할 수 있다
(Principle 3).

### 7. Gate CLEAR는 현재 revision의 ready 감사를 요구한다

새 blocker 세 가지 — `CLOSURE_AUDIT_MISSING`(감사 없음),
`CLOSURE_AUDIT_STALE`(다른 revision의 감사), `CLOSURE_BLOCKED`(차단 질문마다
하나). 감사는 승인 요청보다 앞선 단계이므로 사용자 흐름은 "종료 후보 도달 →
감사 → (통과 시) 재진술·승인 요청 → Gate"가 된다.

### 8. closer의 verdict 반환은 ADR-0019 §3와 충돌하지 않는다

그 원칙은 **점수와 통과선의 분리**다 — 채점자가 임계를 알면 그 선에 맞출 수
있다. closer의 판단("구현을 실질적으로 바꿀 미해결 결정이 있는가")은 임계
비교가 아니라 판단 그 자체이고, 숨길 통과선이 존재하지 않는다. upstream도
closer만 verdict를 반환하는 같은 모양이다.

### 9. 감사는 항상 돈다

6축 점검표의 brownfield/system-level 한정은 gate summary 문장 안의 조건이며
(`"For brownfield or system-level work, check ..."`), 적용 여부 판단은 closer의
일이다. 감사 자체를 조건부로 만들지 않는다 — upstream의 acceptance guard도
항상 돈다.

## Consequences

### Positive

- 점수 통과만으로 조기 종료할 수 없다. §11.5의 산문 금지가 코드로 성립한다.
- 합성이 결정적이므로 차단 규칙 전체가 LLM 없이 테스트된다.
- 감사가 revision에 묶인 상태로 남아 Gate 판정의 근거를 재구성할 수 있다.

### Cost

- `CLEAR` 전에 LLM 판단 3회가 추가된다. 비용과 지연은 의도된 마찰이다.
- **세 lane을 현재 순차로 실행한다** (`BriefService.audit_closure`). upstream
  기본은 병렬 batch이고 순차는 공인 fallback이다
  (`skills/interview/SKILL.md:665`) — 판정 결과는 동일하며 벽시계 시간만
  lane 3개 분량이 된다. 병렬화(`asyncio.gather`)는 구조를 바꾸지 않는 성능
  최적화이므로 필요해질 때 한다.
- **Phase 1 완료 범위의 소급 변경이다.** 기존 gate `CLEAR` 테스트가 감사를
  요구하도록 갱신된다.
- 실제 assessor/challenger 어댑터는 아직 없다. Phase 2 범위에서는 결정적
  fake로 계약만 검증한다 (Brief의 다른 포트와 같다).

## Rejected alternatives

- **closer 단일 (upstream 공인 fallback)**: fallback은 병렬 primitive가 없는
  환경용이다. Core에 그 제약이 없고, 사용자가 기본값 재구성을 선택했다.
- **6축을 6개 역할로 분할**: upstream에 없다. 6축은 closer 한 역할의
  점검표이며, 분할은 불필요한 다중 에이전트 확장이다.
- **skill/surface 계층 배치**: §12.2·§12.3에서 실측된 실패 유형.
- **ambiguity 점수 전달**: 경고를 얹어 위험을 관리하는 것보다 제거가 낫다.
- **감사 결과를 저장하지 않고 Gate마다 재실행**: 판정 근거가 재구성 불가능해
  지고, 같은 상태에 대한 Gate 판정이 호출마다 달라질 수 있다.
- **계약 문장의 한국어 번역**: 문장이 계약인 곳에서 번역은 변형이다
  (ADR-0019 §4의 교훈).

## Verification

- closer가 `not_ready`면 차단되고 질문(없으면 reason)이 남는다.
- advisory HIGH가 차단하고 question(없으면 finding)이 남는다.
- MEDIUM/LOW advisory는 차단하지 않는다.
- ready는 closer `ready`이면서 HIGH가 없을 때뿐이다.
- lane이 뒤바뀐 `ClosureAudit`은 거부된다.
- 감사가 없거나 다른 revision의 감사만 있으면 `CLEAR`가 거부된다.
- material 변경(답변·후보 기록·확정)이 감사를 stale로 만든다.
- 계약 문장 상수가 upstream 원문과 일치한다.
