# ADR 0003 — Runtime abstraction boundary

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Runtime neutrality

## Context

Codex와 OpenCode는 서로 다른 명령, session model, tool surface, sandbox, event
format을 가진다. Core가 이 차이를 직접 다루면 모든 Stage에 vendor 조건문이
생기고 동일 Seed라도 Workflow 의미가 달라진다.

또한 질문/평가처럼 한 번의 text completion이 필요한 경로와 파일을 수정하는
stateful execution Runtime은 같은 책임이 아니다.

## Decision

Mission Control Core는 backend-neutral contract만 사용한다.

- execution Runtime은 공통 dispatch/result/session/cancel/capability 계약을 구현한다.
- concrete adapter가 native 명령과 event를 정규화한다.
- text-generation backend와 execution Runtime을 별도 port로 모델링한다.
- Runtime Adapter는 Gate, retry, Recover, Mission state를 결정하지 않는다.
- feature parity가 없으면 capability mismatch를 명시한다.

초기 concrete 방향은 Codex와 OpenCode이며 Gemini는 v1 범위에 포함하지 않는다.

## Consequences

### Positive

- 동일 Core tests를 모든 Runtime에 적용할 수 있다.
- Runtime 선택이 Mission Lifecycle을 바꾸지 않는다.
- OpenCode local model과 제공 agent의 차이를 adapter/capability로 격리할 수 있다.
- 새 Runtime이 Core에 vendor 조건문을 추가하지 않는다.

### Cost

- 공통 분모를 잘못 설계하면 Runtime 기능을 과도하게 숨길 수 있다.
- streaming, resume, cancellation을 정규화하는 비용이 든다.
- native event와 normalized Telemetry를 모두 추적해야 한다.

## Rejected alternatives

- `if runtime == "codex"`를 Stage마다 사용한다.
- 모든 Runtime이 동일 기능을 가진다고 가정한다.
- text completion과 execution을 하나의 거대한 interface로 합친다.

## Verification

- fake adapter와 concrete adapters가 같은 conformance suite를 통과한다.
- capability 부족이 Runtime 내부 예외가 아니라 명시적 결과가 된다.
- adapter는 Mission state 저장소를 직접 수정하지 못한다.

