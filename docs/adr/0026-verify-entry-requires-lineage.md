# ADR 0026 — Verify 진입은 실행 lineage를 요구한다

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 3 (Evidence over reasoning, [ADR-0005](./0005-evidence-over-reasoning.md)), [ADR-0023](./0023-execute-entry-and-provenance.md) §2
- Upstream evidence: [EVALUATE_UPSTREAM_FINDINGS.md](../research/EVALUATE_UPSTREAM_FINDINGS.md) §1~§2

## Context

[Open Questions §5](../research/OPEN_QUESTIONS.md)의 굵은 항목: **Execute
Telemetry 없이 나타난 작업을 Verify가 `CLEAR`할 수 있는가.** AC가 통과해도 그
작업을 무엇이 만들었는지 기록이 없으면 완료 선언의 근거가 비어 있다.
`MISSION COMPLETE`를 선언할 수 있는 유일한 Gate의 진입 조건이므로 되돌리기
비싼 결정이다.

upstream 소스 확인 결과([EVALUATE_UPSTREAM_FINDINGS](../research/EVALUATE_UPSTREAM_FINDINGS.md)):

- upstream evaluate는 실행 lineage를 **요구하지 않는다**. 입력의
  `execution_id`는 검증 없는 문자열이고, artifact는 호출자 제공 텍스트이며,
  MCP 경로의 모든 lineage 조회는 문서화된 best-effort다 — 실행 이벤트가
  하나도 없어도 평가는 그대로 진행된다 (§2).
- 닫힌 루프(evolve)의 lineage는 검사가 아니라 배선이다 — 실행 단계의 출력이
  평가 입력으로 직접 넘어간다 (§2).
- [SEED_UPSTREAM_FINDINGS §12.3](../research/SEED_UPSTREAM_FINDINGS.md)의
  사고(경로 밖 작업이 평가·수용됨)는 이 배치의 직접 결과다.

## Decision

### 1. Verify 진입은 Execute Gate `CLEAR — Clear for Verify`를 요구한다

Verify use case(Phase 4)는 판정을 시작하기 전에 Execute Gate를 재평가한다 —
ExecuteService가 Blueprint Gate를 재확인하는 것과 같은 배치다("진입 확인이
모든 일보다 먼저"). 따라서 §5의 질문에 대한 답은 **CLEAR할 수 없다**를 넘어
**진입 자체가 불가능하다**이다: 현재 Blueprint revision의 어느 AC에든
`EXECUTED_UNVERIFIED` attempt가 없으면 `CRITERION_UNEXECUTED`로, 결과 불명
attempt가 있으면 `ATTEMPT_OPEN`으로 진입이 막힌다.

기록 위에서만 판정한다는 것이지, 기록을 믿는다는 것이 아니다 — Verify의
판정 자체는 여전히 attempt의 `result_summary`가 아니라 독립 실행된 증거
(mechanical 명령, [ADR-0027](./0027-telemetry-layers-and-v1-schema.md))를
근거로 한다. lineage는 "무엇을 검증하는가"를 고정하고, 증거는 "통과했는가"를
답한다.

### 2. 이것은 upstream과의 의도적 차이다

upstream은 요구하지 않고, 우리는 요구한다. 근거는 upstream 자신의
관측이다 — §12.3에서 기록 없는 작업이 평가를 통과해 수용되었고, 사용자는 세
단계가 커밋된 뒤에야 알아챘다. [ADR-0023](./0023-execute-entry-and-provenance.md)
§2가 "기록의 부재가 판정 가능해야 한다"를 방어선으로 정한 것이 정확히 이
결정을 위해서다: 부재를 판정할 수 있어도 부재를 **거부하는 곳**이 없으면
방어선은 장식이다. 그 거부가 Verify 진입이다.

Verify Stage divergence 등록부(Brief 0011, Blueprint 0022, Execute 0025의
Verify 대응물)는 Phase 4 시작 시 만들고 이 항목을 이관한다.

### 3. 기록 밖 artifact의 평가는 v1 Verify의 범위 밖이다

upstream 열린 surface(MCP evaluate)의 use case — 루프 밖에서 만들어진
artifact의 임의 평가 — 는 Mission Control v1이 제공하지 않는다. Verify를
lineage 우회 채점기로 쓰는 경로를 만들지 않는다. MCP host가 자기 도구로
작업하고 Verify만 호출하는 경로의 취급은 [Open Questions
§8](../research/OPEN_QUESTIONS.md)의 결정으로 남는다(Phase 7 전) — 이 ADR은
그 결정이 "기록 요구를 유지한 채" 내려져야 한다는 제약만 건다.

## Consequences

### Positive

- §12.3 사고 유형이 우리 쪽에서 재현 불가능해진다 — 기록 없는 작업은 Verify에
  도달하지 못한다.
- `MISSION COMPLETE`가 항상 실행 기록 위에서 선언된다 (ADR-0005의 실현).
- Brief→Blueprint→Execute→Verify 전 구간에서 "진입 확인이 모든 일보다 먼저"
  배치가 일관된다.

### Cost

- 루프 밖 작업(사용자가 직접 고친 코드 등)을 Verify로 평가할 수 없다. 그런
  작업을 수용하려면 Execute를 거치거나 §8 결정을 기다려야 한다.
- upstream보다 좁은 surface다 — upstream MCP evaluate의 임의 artifact 평가
  기능은 대응물이 없다.

## Rejected alternatives

- **upstream 그대로 (lineage 없이 평가 허용)**: §12.3이 보여준 실패를 알면서
  재현하는 것이다. upstream의 열린 surface는 의도된 기능이지만, 그 기능이
  사고의 통로였다는 것도 관측된 사실이다.
- **경고만 하고 진행**: 경고는 흐름을 막지 않으므로 자동화된 루프에서 반드시
  무시된다. §12.3에서도 아무 경고가 없었던 것이 아니라 판정 지점이 없었다.
- **Verify가 attempt 기록의 내용을 신뢰**: lineage 요구를 "기록된 요약을
  증거로 승격"으로 오해하는 것이다. 판정 증거는 독립 실행에서 나온다
  (ADR-0027).

## Verification

- Execute Gate가 `CLEAR`가 아닌 mission에 대해 Verify use case가 판정을
  시작하지 않는다 (attempt 없음·결과 불명·실행 실패 각각).
- Brief 또는 Blueprint가 그 사이 바뀐 경우 Verify 진입이 막힌다 (진입 재확인).
- Verify의 `CLEAR — MISSION COMPLETE`가 존재하는 attempt 기록과 독립 실행
  증거를 모두 참조한다.
