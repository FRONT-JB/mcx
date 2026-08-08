# ADR 0024 — Execute v1 실행 모델

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: §17 (Scope와 Reasoning Discipline), [ADR-0002](./0002-approved-seed-is-immutable.md), [ADR-0004](./0004-stage-scoped-minimum-capability.md), [ADR-0023](./0023-execute-entry-and-provenance.md)
- Upstream evidence: [RUN_UPSTREAM_FINDINGS.md](../research/RUN_UPSTREAM_FINDINGS.md) §7~§9

## Context

Execute 첫 vertical slice를 [Execute Guide](../07_EXECUTE.md)에 고정하려면
실행 단위·순서·상태·기록의 축이 필요하다. 넷 다 도메인 개념의 이름과 축이므로
되돌리기 비싼 결정이다.

upstream 사실 (RUN_UPSTREAM_FINDINGS):

- 실행 단위는 별도의 task 개념이 아니라 **AC 자체**다. AC 하나가 실행 capsule
  하나로 dispatch된다 (§7).
- 분해는 기본 경로가 아니라 예외 경로다 — preflight 평가 또는 실패 후
  bounce에서만 고려되고, 기본 처분이 ATOMIC이다 (§7).
- dependency는 선언 신호와 LLM 추론의 합집합이고, ready는 결정적 토폴로지
  워크다. LLM 실패 시 선언 신호만으로 진행한다 (§8).
- dispatch마다 tools 목록·workspace·approval mode가 명시되고, 권한을 낳는
  입력 전체의 digest가 capsule에 바인딩된다 (§9).

## Decision

### 1. 실행 단위는 승인된 Blueprint의 AC와 1:1이다

별도의 work item 엔티티를 만들지 않는다. 실행 대상의 identity는 AC key
([ADR-0017](./0017-blueprint-schema-baseline.md) — 내용 digest)이고, 실행
기록은 그 key에 대한 **attempt**다. upstream과 같다 — AC가 곧 단위이고,
"task로 변환"하는 중간 개념이 없다.

AC는 계약이고 attempt는 시도다. 같은 AC에 여러 attempt가 쌓일 수 있으며,
attempt는 자신이 실행한 blueprint revision과 AC key를 가리킨다.

### 2. 분해는 v1에 도입하지 않는다

atomic-first([Execute Guide](../07_EXECUTE.md) §6.2)의 1단계 — "AC를 하나의
제한된 작업으로 그대로 실행" — 만 구현한다. upstream도 분해를 예외 경로로
두므로 이것은 기본 경로의 충실한 구현이지 축소가 아니다. 분해를 도입할 때는
upstream의 한도(자식 2~5, 라이브 깊이 2, repair 1)와 대조해 별도 ADR로
정한다. [ADR-0025](./0025-execute-deliberate-divergences.md)에 보류로
등록한다.

### 3. v1은 선언 순서 순차 실행이고, 실행 실패는 후속을 막는다

dependency 파생을 v1에 도입하지 않는다. 근거가 둘이다 — 우리 Blueprint AC에는
upstream이 선언 신호로 읽는 metadata 자체가 없고(ADR-0017 스키마), LLM 추론
pass는 결정적 first slice의 범위 밖이다. upstream도 신호가 없으면 의존 없음
으로 진행한다(§8 structured fallback과 단일 level).

순서 의미는 다음과 같다.

- AC 목록의 선언 순서대로 한 번에 하나씩 dispatch한다 (Guide §6.4의 순차
  baseline).
- 직전 attempt가 **실행 실패**(EXECUTION_FAILED)면 후속 AC를 dispatch하지
  않는다 — "의존 artifact가 명백히 실패한 상태에서 후속 작업을 실행해서는
  안 된다"(Guide §6.3)의 최소 구현이다.
- 병렬 도입 Gate와 dependency graph 표현은 Guide §17에 남는다.

### 4. Attempt 상태는 셋으로 시작하고, 지속이 dispatch보다 먼저다

| 상태 | 의미 |
|---|---|
| `DISPATCHED` | attempt가 durable하게 기록되었고 Runtime에 위임되었다 |
| `EXECUTED_UNVERIFIED` | Runtime이 결과를 돌려주었다. **검증되지 않았다** |
| `EXECUTION_FAILED` | 실행 자체가 실패했다 (결과 없음과 다르다) |

attempt는 **dispatch 전에 지속한다** (Guide §8 step 7). 따라서 프로세스가
결과를 받기 전에 죽으면 `DISPATCHED`로 남은 attempt가 곧 "결과를 잃어 상태를
알 수 없음"이며, 별도 LOST 상태를 만들지 않는다 — 상태를 하나 더 두면 누가
언제 LOST로 전이시키는지가 새 문제가 된다. cancelled/timeout은 동기 fake
실행에 발생 경로가 없으므로 concrete adapter(Phase 5)와 함께 도입한다.

`EXECUTED_UNVERIFIED`는 Verify 통과가 아니다. Execute Gate의 `CLEAR`는
`Clear for Verify`이며 완료 선언이 아니다 (Guide §10).

### 5. Attempt 기록은 ADR-0023의 provenance 네 항목을 선언 필드로 담는다

생성 경로(execution id), 실행 주체(runtime backend 이름 + adapter가 준 native
session id), lineage(blueprint revision + AC key), 시도 번호. 필드 누락은
기록 생성 시점에 거부된다.

### 6. Capability envelope는 dispatch에 명시된다

dispatch 입력에 workspace 경로와 허용 도구 목록을 담는다 (Guide §5,
upstream §9의 dispatch 계약과 같은 축). v1 fake runtime에서는 계약의 전달과
기록까지가 범위이고, 실제 차단은 concrete adapter(Phase 5)가 한다 — Brief의
tool-less port와 같은 강제 수준이다 (ADR-0004, "Phase 1의 강제 범위는
여기까지다"와 동일한 명시).

### 7. 열린 attempt는 mission당 하나다

`DISPATCHED` 상태의 attempt가 있으면 새 dispatch를 거부한다. 순차 실행(§3)의
상태 표현이자, 중복 dispatch를 막는 최소 장치다. side-effecting command의
idempotency **key schema**(exact key, namespace, 보존)는 여전히 TBD다
(Guide §7·§17) — 이 규칙은 그 결정을 대체하지 않고 최소 불변 조건만 세운다.

## Consequences

### Positive

- 첫 slice가 upstream의 기본 경로(AC 그대로, 예외 없이)와 정확히 겹쳐 대조
  가능성이 유지된다.
- AC key가 Brief→Blueprint→Execute를 관통하는 identity가 된다 (ADR-0017의
  의도 실현).
- 실행과 검증의 분리가 상태 이름에 박힌다 (`EXECUTED_UNVERIFIED`).

### Cost

- 독립적인 AC도 순차로 기다린다. 병렬 도입 전까지 실행이 느리다.
- 실행 실패가 전체 진행을 멈춘다. AC 간 독립성을 아는 시스템이라면 계속할 수
  있는 작업도 멈춘다 — dependency 파생을 도입할 때 되살릴 여지다.
- 분해가 없으므로 너무 큰 AC는 실패하고 사용자에게 돌아온다. upstream의
  bounce 경로가 하던 일을 v1에서는 사람이 한다.

## Rejected alternatives

- **별도 WorkUnit 엔티티**: upstream에 없는 구조의 발명이다 (AGENTS.md).
  AC(계약)와 attempt(시도) 사이에 세 번째 개념이 필요해지는 시점은 분해
  도입 시점이고, 그때 upstream의 node identity와 대조해 정한다.
- **dependency 파생을 지금 구현**: 선언 신호가 없는 상태에서 남는 것은 LLM
  추론뿐이고, 그것은 결정적 slice의 목적(상태 전이·Telemetry 계약 검증,
  Guide §6.4)과 충돌한다.
- **LOST/CANCELLED 상태를 미리 추가**: 발생시킬 경로가 없는 상태는 테스트할
  수 없고, 테스트되지 않은 상태 전이는 계약이 아니라 장식이다.
- **실패해도 후속 진행**: 의존성을 모르는 채 진행하면 실패한 산출물 위에
  쌓는다. 보수적 중단이 v1의 안전한 기본값이다.

## Verification

- 승인된 Blueprint 없이 attempt가 만들어지지 않는다 (ADR-0023 §1).
- attempt가 AC key와 blueprint revision을 가리킨다. 대상 AC는 단일 생성
  경로가 승인된 Blueprint에서 선택하므로 경로상 존재하지 않는 key는
  만들어질 수 없고, 경로 밖 기록의 탐지는 약속하지 않는다 (ADR-0023 §2).
  *(2026-08-08 Phase 3 종료 검토 정정 — 원문 "해당 revision에 존재하지
  않으면 거부된다"는 어느 계층도 수행하지 않는 존재 검증을 과장했다.)*
- dispatch 전에 attempt가 저장되고, 저장 실패 시 dispatch가 일어나지 않는다.
- `DISPATCHED` attempt가 있으면 새 dispatch가 거부된다.
- `EXECUTION_FAILED` 뒤에 후속 AC dispatch가 거부된다.
- provenance 네 항목이 없는 attempt 기록이 거부된다.
- capability envelope(workspace, 도구 목록)가 dispatch 입력과 기록에 남는다.
