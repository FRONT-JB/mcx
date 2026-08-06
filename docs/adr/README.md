# Architecture Decision Records

ADR은 Mission Control의 중요한 결정을 “무엇을 선택했는가”뿐 아니라 “왜 다른
선택을 하지 않았는가”까지 보존한다.

## 규칙

- 한 ADR은 하나의 결정만 다룬다.
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

