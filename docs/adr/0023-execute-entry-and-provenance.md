# ADR 0023 — Execute 진입 경로와 Telemetry provenance

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 3 (Evidence over reasoning, [ADR-0005](./0005-evidence-over-reasoning.md)), [ADR-0004](./0004-stage-scoped-minimum-capability.md), §6.5 (surface 간 동일 state)
- Upstream evidence: [RUN_UPSTREAM_FINDINGS.md](../research/RUN_UPSTREAM_FINDINGS.md), [SEED_UPSTREAM_FINDINGS.md](../research/SEED_UPSTREAM_FINDINGS.md) §12.3

## Context

[Open Questions §4](../research/OPEN_QUESTIONS.md)는 Execute 구현 시작 전에
두 가지를 정하라고 요구한다 — Execute 진입 경로가 하나임을 무엇이 보장하는지,
Telemetry가 "무엇이 이 작업을 만들었는가"를 기록하는지. 계층 경계 결정이므로
나중에 바꾸면 전면 수정이다.

upstream 관측(§12.3)에서 실제 사고가 있었다: config는 execute를 codex에
매핑했는데 host 세션이 자기 도구로 직접 구현했고, 세 단계가 커밋된 뒤에야
사용자가 알아챘다. 경고도 Telemetry도 Gate도 없었다.

소스 확인([RUN_UPSTREAM_FINDINGS](../research/RUN_UPSTREAM_FINDINGS.md)) 결과
이것은 버그가 아니라 배치의 결과다.

- Python 쪽 실행 진입은 `OrchestratorRunner`로 수렴하고, 경로 **안**은
  엄격하다 — AC당 capsule 하나, backend·workspace 불일치 거부, fingerprint
  바인딩 (§3).
- 경로 안에서는 provenance가 기록된다 — AC 이벤트 payload에
  `runtime_backend`와 runtime handle 전체 (§4). 단 **payload 관례**이고,
  events 스키마에는 actor 컬럼이 없다.
- 경로 **밖**(host 세션이 자기 도구로 작업)은 코어 코드가 아예 실행되지
  않으므로 탐지가 구조적으로 불가능하고, "수용되는 작업에 실행 기록이
  있는가"를 검사하는 gate도 없다 (§5).

## Decision

### 1. 작업 생성은 application 계층의 단일 use case 경로다

Execute 작업(work unit)을 만들고 durable state에 기록할 수 있는 것은
application 계층의 Execute use case 하나다 (Phase 3에서 `ExecuteService`류로
구현). 진입은 Blueprint Gate의 `CLEAR — Clear for Execute`
([ADR-0021](./0021-blueprint-state-and-revisions.md) §6 — 채점·승인된 현재
revision)를 요구한다.

Runtime adapter는 use case가 구성한 입력만 받아 실행하며 **스스로 작업을
만들지 않는다** ([ADR-0004](./0004-stage-scoped-minimum-capability.md)).
CLI/MCP surface는 이 use case를 호출할 뿐 자체 실행 경로를 갖지 않는다
(§6.5, [ADR-0007](./0007-mcp-is-control-surface.md)).

이는 Brief·Blueprint에서 이미 확립한 배치의 연장이다: 관문은 state를 소유하는
계층에 있다 ([ADR-0011](./0011-brief-deliberate-divergences.md) Divergence 1,
[ADR-0019](./0019-blueprint-qa-loop.md) §1). upstream의 실패는 관문이 있는
계층(skill)이 결과를 소유하지 않고 결과를 소유한 계층(core)이 관문을 갖지
않는 배치에서 왔다.

### 2. 경로 밖 작업의 탐지를 약속하지 않는다

Mission Control 프로세스가 뜨지 않은 채 일어난 작업을 코어가 탐지하는 것은
불가능하다 — 실행될 코드가 없다. upstream도 같다 (§2). 이 한계를 숨기지 않고
방어선을 다음으로 정의한다: **기록의 부재가 판정 가능해야 한다.** Mission
Control이 만들지 않은 작업은 Telemetry가 없고, Telemetry 없는 작업은 실행되지
않은 작업과 구별되지 않는다. 그런 작업을 Verify가 `CLEAR`할 수 있는지는
[Open Questions §5](../research/OPEN_QUESTIONS.md)의 결정이며(Phase 4 전),
MCP host가 자기 도구로 작업하는 경로의 취급은 §8의 결정이다(Phase 7 전).
이 ADR은 그 두 결정이 딛고 설 기록 계약만 고정한다.

### 3. Telemetry는 생성 주체를 선언 필드로 기록한다

모든 work unit과 실행 Telemetry 레코드는 다음을 **1급 선언 필드**로 담는다.

| 항목 | 내용 | upstream 대응 |
|---|---|---|
| 생성 경로 | 어느 use case 호출(execution id)이 이 작업을 만들었는가 | `execution_id` (payload) |
| 실행 주체 | runtime adapter identity — backend 이름과 adapter가 준 native session id | `runtime_backend`, `runtime` handle (payload) |
| 근거 lineage | 승인된 Blueprint revision과 AC key | `semantic_ac_key`, seed 참조 (payload) |
| 시도 | attempt/retry 번호 | `attempt_number`, `retry_attempt` (payload) |

정확한 스키마(필드 이름, event/report/bundle 구조)는
[Open Questions §9](../research/OPEN_QUESTIONS.md)대로 Phase 3 설계에서
확정한다. 이 ADR이 고정하는 것은 **이 네 항목이 선언 필드로 반드시
존재한다**는 계약이다.

**upstream과 다른 점**: upstream은 이 정보를 이벤트 payload(JSON) 안에 emitter
관례로 담고 스키마에는 actor 컬럼이 없다. 우리는 선언 필드로 강제한다 —
관례는 emitter가 빠뜨려도 아무것도 잡지 못하고, "무엇이 승인/실행 대상인가를
스키마로 답할 수 있어야 한다"는 [ADR-0017](./0017-blueprint-schema-baseline.md)
§4와 같은 이유다. 이 차이는 Execute Stage divergence 등록부
([ADR-0025](./0025-execute-deliberate-divergences.md))에 등록되었다 —
2026-08-08 이관 완료.

## Consequences

### Positive

- Execute 구현(Phase 3)이 시작되기 전에 계층 경계가 고정된다 — 작업 생성
  권한은 use case에, 실행은 adapter에, 관문은 state 소유 계층에.
- "이 작업을 무엇이 만들었는가"가 스키마 수준에서 항상 답 가능하다. §5·§8
  결정이 추측이 아니라 기록 위에서 내려진다.
- upstream §12.3의 사고 유형(조용한 우회)이 최소한 **판정 가능**해진다 —
  기록이 없다는 사실 자체가 신호다.

### Cost

- 경로 밖 작업은 여전히 일어날 수 있다. 이 ADR은 그것을 막지 못하며, 막는다고
  주장하지도 않는다.
- 선언 필드 강제는 telemetry 스키마 설계(Phase 3)에 제약을 미리 건다. 네
  항목이 과하다고 판명되면 이 ADR을 대체해야 한다.
- Execute divergence 등록부 신설이 Phase 3 시작으로 미뤄져, 그때까지 이
  ADR의 §3이 유일한 등록 위치다.

## Rejected alternatives

- **경로 밖 작업 탐지 시도** (파일시스템 감시, git hook 등): 코어가 뜨지
  않으면 실행될 코드가 없다. 불가능한 보장을 약속하는 것이고, 감시가 도는
  환경에서만 성립하는 보장은 보장이 아니다.
- **provenance를 payload 관례로** (upstream 형태): emitter가 빠뜨리면
  스키마가 잡지 못한다. upstream에서 이 관례의 바깥(경로 밖)이 실제로
  비어 있었다.
- **runtime adapter의 자체 작업 생성 허용**: 진입 경로가 둘이 되고
  ADR-0004의 최소 capability 경계가 무너진다.
- **telemetry 전체 스키마를 지금 확정**: §9가 Phase 3 직전 결정으로 명시한
  것을 앞당겨 선결정하는 것이다. 필수 항목의 존재만 고정하면 §4의 목적은
  달성된다.
- **Stage→Runtime 바인딩 테이블 도입을 지금 결정**: 우리 Runtime adapter
  구조(ADR-0003)가 Phase 5에서 구체화되므로, 바인딩 표현은 그때 upstream의
  닫힌 enum + 3단 해석 규칙(RUN_UPSTREAM_FINDINGS §1)과 대조해 정한다.

## Verification

- Execute use case 외의 경로(adapter, surface, 테스트 fixture 제외)로 work
  unit이 durable state에 기록되지 않는다.
- Blueprint Gate `CLEAR` 없이 Execute use case가 작업을 만들지 않는다.
- 모든 work unit/Telemetry 레코드에 네 provenance 항목이 선언 필드로 존재하고,
  누락된 레코드는 생성 시점에 거부된다.
- Phase 3 telemetry 스키마 설계가 이 ADR을 인용하고, 네 항목의 최종 필드
  이름을 §9 결정으로 확정한다.
