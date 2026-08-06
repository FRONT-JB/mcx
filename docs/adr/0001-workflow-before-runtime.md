# ADR 0001 — Workflow before Runtime

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principles 1, 2, 8, 10

## Context

Mission Control의 목적은 특정 모델을 편리하게 호출하는 wrapper를 만드는 것이
아니다. 모델과 Runtime부터 구현하면 그 도구의 세션, 이벤트, 권한 모델이 Core
Workflow에 새어 들어가고, 다음 단계와 완료 조건까지 모델이 사실상 결정하게 된다.

이 프로젝트의 학습 목표도 Ouroboros의 specification-first 상태 전이와 Gate를
먼저 이해하는 것이다.

## Decision

Domain model, Mission state, Stage contracts, Gate policy를 구체 Runtime보다 먼저
정의하고 테스트한다.

Core는 deterministic fake/test Runtime으로 다음을 먼저 증명해야 한다.

- 승인되지 않은 Seed는 Execute에 진입하지 못한다.
- Flight Controller의 완료 주장이 Stage를 전이시키지 못한다.
- Telemetry가 부족하면 HOLD한다.
- 실패가 Recover input으로 보존된다.

Concrete Codex/OpenCode adapters는 이 계약을 구현한다.

## Consequences

### Positive

- Runtime 교체가 Workflow 의미를 바꾸지 않는다.
- Core state transition을 빠르고 재현 가능하게 테스트할 수 있다.
- MCP/CLI가 같은 application boundary를 공유할 수 있다.
- upstream 동작과 Core 개념을 비교하기 쉽다.

### Cost

- 눈에 보이는 모델 실행보다 domain/test double 구현이 먼저다.
- 초기에는 end-to-end 데모가 늦어 보일 수 있다.
- adapter가 원하는 API보다 Core 계약을 우선해야 한다.

## Rejected alternatives

- Codex subprocess부터 구현한 뒤 Workflow를 둘러싼다.
- MCP tool handler 안에 상태 전이 로직을 직접 작성한다.
- 모델 prompt가 다음 Stage를 선택하게 한다.

이 대안들은 구현은 빨라 보여도 Runtime lock-in과 상태 규칙 중복을 만든다.

## Verification

- Core transition test는 Codex/OpenCode 설치 없이 실행된다.
- fake Runtime 성공/실패/timeout으로 동일 Gate 규칙을 테스트한다.
- concrete adapter conformance suite가 Core contract를 변경하지 않고 통과한다.

