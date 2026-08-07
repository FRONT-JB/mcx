# ADR 0011 — Deliberate divergences from upstream in Brief

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 10 (Reconstruct before improve), §17 (Scope와 Reasoning Discipline), Appendix A
- Upstream evidence: [INTERVIEW_UPSTREAM_FINDINGS.md](../research/INTERVIEW_UPSTREAM_FINDINGS.md) §2, §4, §7

## Context

Mission Control v1의 기준은 upstream Ouroboros의 재구성이다
([ADR-0001](./0001-workflow-before-runtime.md), Constitution §18). 그러나 Brief
조사에서 upstream을 그대로 따르면 Constitution을 위반하거나, 반대로 Constitution
§17이 금지하는 복잡도를 미리 도입하게 되는 지점이 확인되었다.

Constitution Appendix A 16번은 “원본과 의도적으로 다른 핵심 동작은 ADR과 test로
드러난다”고 요구한다. 이 ADR이 그 기록이다.

## Decision

### 1. Divergence — surface 간 동일 Gate

**upstream**: CLI 대화 루프(`ooo interview`)에는 ambiguity Gate가 없다. 최소 3
round 이후 “계속할까요?”를 묻고 사용자가 거부하면 종료한다. score 기반 조건은
MCP handler에만 있다.

**Mission Control**: CLI와 MCP가 동일한 clarity policy와 Gate 조건을 사용한다.

**근거**: Constitution §6.5는 “같은 미션을 CLI와 MCP에서 다루더라도 하나의
canonical state를 바라봐야 한다”고 규정하고,
[ADR-0007](./0007-mcp-is-control-surface.md)은 두 surface가 같은 application
boundary를 호출하도록 요구한다. upstream의 비대칭을 따르면 어느 창구를 쓰느냐가
완료 기준을 바꾼다.

### 2. Divergence — approval을 1급 상태로 보존

**upstream**: 별도 approval 객체가 없다. `status = COMPLETED` 전이와 best-effort
HITL 이벤트가 근거다.

**Mission Control**: 승인을 특정 Brief revision에 묶어 명시적으로 저장하고, 승인
기록의 저장 실패를 승인 없음으로 취급한다.

**근거**: Appendix A 7·8번(“사용자 승인 없이 Blueprint로 진행하지 않는다”,
“승인은 정확한 Brief revision을 참조한다”)과 Principle 5.

### 3. Adaptation — Read-only Fact Resolver

**upstream**: interview 중 코드 사실은 host 세션이 코드를 읽어
`[from-code]` 표기를 붙여 답변으로 제출한다. 별도 fact resolution 역할이 없다.

**Mission Control**: 제한된 read-only Fact Resolver를 별도 역할로 둔다
([Brief Guide](../05_BRIEF.md) §4.4).

**근거**: 이는 경쟁하는 발명이 아니라 host 없는 환경으로의 이식이다. v1 첫
구현은 CLI를 대상으로 하므로 코드 사실을 가져오는 host 세션이 존재하지 않는다.
누군가는 그 자리를 채워야 하며, [ADR-0004](./0004-stage-scoped-minimum-capability.md)는
그 역할이 질문 생성기와 분리된 최소 권한 경계를 갖도록 요구한다. 충실해야 할
대상은 “누가 사실을 가져오는가”가 아니라 provenance 의미론이며 그것은
[ADR-0010](./0010-answer-provenance-and-requirement-authority.md)에서 유지된다.

### 4. Deferral — 질문 후보 패널

**upstream**: 5개 내부 perspective(researcher, simplifier, architect,
breadth-keeper, seed-closer)로 질문 후보를 생성하고 선택한다.

**Mission Control v1**: 한 dispatch에서 질문 하나를 생성한다.

**근거**: Constitution §17(“간단한 작업을 불필요한 다중 에이전트 구조로 확장하지
않는다”)과 [UPSTREAM_MAPPING](../research/UPSTREAM_MAPPING.md) §10(persona
system 전체를 먼저 복사하지 않을 항목으로 분류). 질문 품질이 실제 문제로
확인되면 별도 RFC로 평가한다.

### 5. Deferral — 다중 관점 acceptance guard

**upstream**: skill 계층이 closer/contrarian/gap_hunter 3-lane fan-out으로
seed-ready를 압박 테스트한다.

**Mission Control v1**: 도입하지 않는다. 단, 이 관문이 수행하던 **사용자 확인
역할은 Restate gate로 채택**한다 ([Brief Guide](../05_BRIEF.md) §12.1).

**근거**: §17과 동일. 다중 관점 검토를 유예해도 “점수만으로 통과”가 되지 않는
이유는 Restate gate와 §11.5의 hard condition이 남기 때문이다.

### 6. Deferral — brownfield 탐색 단계

**upstream**: brownfield는 1급 구분이다. 별도 weight와 4번째 차원(context
clarity), 그리고 인터뷰 이전의 read-only 코드베이스 탐색 단계를 가진다.

**Mission Control v1**: 정책 구조에서 brownfield weight와 4번째 차원의 **자리를
예약**하되, 전용 탐색 단계는 구현하지 않는다. 첫 구현은 greenfield 경로를
대상으로 한다.

**근거**: §17과 UPSTREAM_MAPPING §10. 자리를 미리 예약하는 이유는 나중에
활성화할 때 policy 구조가 깨지지 않게 하기 위해서다.

## Consequences

### Positive

- upstream과 다른 지점이 우연이 아니라 근거를 가진 결정으로 존재한다.
- 유예 항목의 재도입 조건이 명시되어 있다.
- 헌법 위반 없이 upstream 구조를 최대한 따른다.

### Cost

- upstream과 1:1 대조가 일부 지점에서 성립하지 않는다.
- Divergence 1·2는 upstream보다 엄격하므로 구현 비용이 더 든다.
- Deferral 항목은 upstream 대비 질문 품질과 closure 검증 강도가 낮을 수 있다.

## Rejected alternatives

- **upstream을 그대로 복제**: Divergence 1·2에서 Constitution과 충돌한다.
- **차이를 문서화하지 않고 구현**: Appendix A 16번 위반.
- **유예 항목을 v1에 모두 포함**: §17이 금지하는 검증되지 않은 복잡도 도입.
- **Fact Resolver를 없애고 사용자에게 코드 사실을 묻기**: Constitution §6.1
  (“사용자는 코드베이스의 현재 사실을 외워서 답할 의무가 없다”)에 어긋난다.

## Verification

- 동일 Brief를 CLI와 MCP에서 처리하면 같은 Gate 판정이 나온다
  ([Brief Guide](../05_BRIEF.md) §17의 B-039).
- 승인 기록 저장 실패 시 `CLEAR`가 기록되지 않는다 (B-016).
- 질문 생성기가 read-only 조사 권한을 갖지 않는다 (B-002, B-004).
- Restate 문장 수정이 자동 승인으로 이어지지 않는다 (B-038).
- 유예 항목은 재도입 시 이 ADR을 대체하는 새 ADR을 요구한다.
