# Architecture Decision Records

ADR은 Mission Control의 중요한 결정을 “무엇을 선택했는가”뿐 아니라 “왜 다른
선택을 하지 않았는가”까지 보존한다.

## 규칙

- 한 ADR은 하나의 결정만 다룬다.
- upstream과 의도적으로 다른 동작은 Stage별 divergence ADR 하나에 모은다
  (Brief는 [0011](./0011-brief-deliberate-divergences.md)). 다른 ADR에서
  결정했더라도 그 divergence ADR에서 링크한다. 대조하지 못한 항목은 "차이 없음"이
  아니라 미확인으로 같은 곳에 적는다.
- 상태는 `Proposed`, `Accepted`, `Superseded`, `Rejected` 중 하나다.
- Accepted ADR의 의미를 바꿀 때는 기존 파일을 덮어쓰지 않고 새 ADR로 대체한다.
- 코드와 하위 문서는 Accepted ADR을 따라야 한다.
- Constitution을 바꾸는 결정은 ADR만으로 확정되지 않으며 사용자 승인이 필요하다.
- 구현 세부사항이 아직 없더라도 검증 가능한 consequence를 기록한다.

## Index

| ADR | 결정 | 상태 |
|---|---|---|
| [0001](./0001-workflow-before-runtime.md) | Workflow가 Runtime과 모델보다 우선한다. | Accepted |
| [0002](./0002-approved-seed-is-immutable.md) | 승인된 Seed는 실행 중 불변이다. | Accepted |
| [0003](./0003-runtime-abstraction.md) | Core와 구체 Runtime을 adapter로 분리한다. | Accepted |
| [0004](./0004-stage-scoped-minimum-capability.md) | 각 Stage는 최소 capability만 가진다. | Accepted |
| [0005](./0005-evidence-over-reasoning.md) | 진행과 완료는 Telemetry로 판정한다. | Accepted |
| [0006](./0006-dual-terminology.md) | 사용자 용어와 내부 Ouroboros 용어를 분리한다. | Accepted |
| [0007](./0007-mcp-is-control-surface.md) | MCP는 Core가 아니라 control surface다. | Accepted |
| [0008](./0008-bounded-recovery.md) | Recover는 evidence-driven이며 bounded하다. | Accepted |
| [0009](./0009-brief-completion-gate-policy.md) | Brief 종료는 네 조건을 모두 만족해야 하며 그것만으로 `CLEAR`가 되지 않는다. | Accepted |
| [0010](./0010-answer-provenance-and-requirement-authority.md) | 답변 authority를 분리하고 observation의 요구사항 승격을 투영으로 차단한다. | Accepted |
| [0011](./0011-brief-deliberate-divergences.md) | Brief에서 upstream과 다르게 가는 지점을 기록한다. | Accepted |
| [0012](./0012-python-toolchain-and-layout.md) | Python 3.12 + uv + pydantic + pytest를 사용하고, 실행 모델은 upstream처럼 도메인 동기 / use case·port async로 나눈다. | Accepted |
| [0013](./0013-brief-durable-state-baseline.md) | Brief durable state는 revision 이력을 포함한 단일 JSON 문서로 시작한다. | Accepted |
| [0014](./0014-brief-concurrent-write-protection.md) | stale write 거부를 유지하고 내용 버전과 쓰기 순서를 두 축으로 나눈다. | Accepted |
| [0015](./0015-requirement-candidate-model.md) | Non-goal·충돌·가정·미해결을 하나의 요구사항 후보 모델로 다룬다. | Accepted |
| [0016](./0016-brief-handoff-projection.md) | Brief handoff는 저장하지 않고 CLEAR된 상태에서 매번 파생한다. | Accepted |
| [0017](./0017-blueprint-schema-baseline.md) | Blueprint v1은 방향만 담고 AC는 성공 계약의 내용으로 식별한다. | Accepted |
| [0018](./0018-blueprint-generation-contract.md) | 생성기는 성공 조건만 구체화하고 범위 검사는 결정적으로 한다. | Accepted |
| [0019](./0019-blueprint-qa-loop.md) | 생성 직후 QA 루프를 Core에 두고 최선 시도를 추적한다. | Accepted |

## Template

```markdown
# ADR NNNN — Title

- Status: Proposed
- Date: YYYY-MM-DD

## Context

## Decision

## Consequences

## Rejected alternatives

## Verification
```

