# ADR 0029 — Deliberate divergences from upstream in Verify

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 10 (Reconstruct before improve), §17 (Scope와 Reasoning Discipline), Appendix A 16번
- Upstream evidence: [EVALUATE_UPSTREAM_FINDINGS.md](../research/EVALUATE_UPSTREAM_FINDINGS.md), [VERIFY_UPSTREAM_FINDINGS.md](../research/VERIFY_UPSTREAM_FINDINGS.md)

## Context

[ADR README](./README.md)의 규칙대로 Verify Stage의 upstream 대비 차이를 한
곳에 모은다 (Brief는 [0011](./0011-brief-deliberate-divergences.md), Blueprint는
[0022](./0022-blueprint-deliberate-divergences.md), Execute는
[0025](./0025-execute-deliberate-divergences.md)).
[ADR-0026](./0026-verify-entry-requires-lineage.md) §2가 예고한 이관을
수행한다.

## Decision

### Divergences — 의도적으로 다르게 간다

| 항목 | upstream | Mission Control | 결정 |
|---|---|---|---|
| 평가 진입의 lineage 요구 | 요구하지 않음 — 열린 MCP surface는 호출자 artifact를 best-effort 조회만으로 채점 (§12.3 사고의 통로) | Verify 진입이 Execute Gate `CLEAR`를 요구 — 기록 없는 작업은 진입 불가 | [ADR-0026](./0026-verify-entry-requires-lineage.md) (이관 완료) |
| 성공 계약 검사의 시점 | 두 번 — 실행 수용 시점(orchestrator gate)과 평가 Stage 1 | 한 번 — Verify Stage. v1 Execute는 명령을 실행하지 않으므로(ADR-0024) 검사가 Stage 경계와 일치하는 한 곳에 온다 | [ADR-0028](./0028-verify-v1-mechanical-contract.md) §1 |
| 기록 밖 artifact의 평가 surface | MCP evaluate가 임의 artifact 평가를 제공 | v1 미제공 — Verify를 lineage 우회 채점기로 쓰는 경로를 만들지 않음. §8(MCP host 직접 작업) 결정의 제약으로 유지 | [ADR-0026](./0026-verify-entry-requires-lineage.md) §3 |

### Deferrals — 보류. 차이가 아니라 미구현

| 항목 | upstream | 상태 | 기록 |
|---|---|---|---|
| repo 수준 명령 실행 (mechanical.toml: lint/build/test/static/coverage) | Stage 1 + AI detector 발견 + 4겹 안전 모델 | v1 미도입 — 승인된 verify_command만 실행. 도입 시 allowlist·argv·entry-point 모델과 대조 | [ADR-0028](./0028-verify-v1-mechanical-contract.md) §2, [VERIFY_UPSTREAM_FINDINGS §3~§4](../research/VERIFY_UPSTREAM_FINDINGS.md) |
| workspace mutation guard (검증 명령의 작업물 변경 거부) | 실행 전후 content digest 대조로 FAIL | v1 미도입 — 도입 시 digest 범위를 함께 결정 | [ADR-0028](./0028-verify-v1-mechanical-contract.md) §5, 계약 기록은 findings §2 |
| changed_files 수집 (git 기반) | VerificationArtifacts에 포함 | 실제 파일 변경이 생기는 concrete adapter(Phase 5)와 함께 | [ADR-0027](./0027-telemetry-layers-and-v1-schema.md) §1, [ADR-0028](./0028-verify-v1-mechanical-contract.md) §4 |
| coverage 판정 (coverage_threshold 0.7) | Stage 1 축 | v1 미도입 | [ADR-0028](./0028-verify-v1-mechanical-contract.md) §5 |
| consensus (Stage 3: trigger 6조건, ADVOCATE/DEVIL/JUDGE 숙의, 배심 독립성 4-label) | 존재 — uncertainty·drift escalation의 해소 경로 | v1 미도입 — escalation은 `HOLD`가 전부. 도입 시 임계(0.3)·"votes beat purity"·독립성 라벨과 대조 | [ADR-0030](./0030-verify-semantic-verdict-contract.md) §5, [VERIFY_UPSTREAM_FINDINGS §7](../research/VERIFY_UPSTREAM_FINDINGS.md) |
| `not_observed` 류 관찰 status와 observation adapter | UI/API 관찰 경로 | v1 미도입 — verdict는 bool + uncertainty (upstream 정렬). 관찰 status는 observation adapter(Guide §13 Slice 5) 도입 시 재평가 | [ADR-0030](./0030-verify-semantic-verdict-contract.md) §1 |
| `exit_conditions` (Mission 전체 종료 조건) | seed 필드 + 진화 루프 소비 | ADR-0017 유예의 시한(Phase 4)이 도래해 재평가 — 핵심 조건은 Gate의 AC 전수 요구가 덮고, 잔여(project 검사, 사용자 acceptance)는 repo 명령 층·Phase 6·7 surface 도입 시 | [ADR-0017](./0017-blueprint-schema-baseline.md) 2026-08-08 재평가 |

### 미확인 — 대조하지 못했다. "차이 없음"이 아니다

| 항목 | 내용 |
|---|---|
| ~~semantic(Stage 2) 프롬프트 계약과 평가 축~~ | **2026-08-08 확인 완료** — AC 단위, 선언 계약 대조, 구조화 JSON, `compliance AND score >= 0.8` ([VERIFY_UPSTREAM_FINDINGS §6](../research/VERIFY_UPSTREAM_FINDINGS.md), 계약은 [ADR-0030](./0030-verify-semantic-verdict-contract.md)) |
| ~~consensus(Stage 3) reviewer 독립성 규칙 (executor vendor 배제 포함)~~ | **2026-08-08 확인 완료** — vendor 배제 + 정족수 우선 + 정직 라벨 4종 ([VERIFY_UPSTREAM_FINDINGS §7](../research/VERIFY_UPSTREAM_FINDINGS.md)). 도입은 보류 표 참조 |
| consensus 심의 프롬프트의 상세 (ADVOCATE/DEVIL/JUDGE 각 계약) | consensus 도입 시 조사 (findings §8) |
| coverage_threshold의 실제 적용 지점 | coverage 도입 시 조사 |

## Consequences

- Phase 4 종료 검토 질문 3(미등록 이탈)의 대조 기준이 구현 시작 전에 생겼다.
- ADR-0026이 예고한 등록부 이관이 완료되어, Verify의 모든 차이·보류가 한
  표에서 보인다.

## Rejected alternatives

- **ADR-0026·0028 본문에 분산 유지**: 등록부 없이 흩어지는 것을 막으려고
  0022·0025를 만들었다. 같은 규칙을 Verify에도 적용한다.

## Verification

- Verify 관련 ADR(0026, 0028)의 divergence·보류 서술이 모두 이 표에서
  링크된다.
- 미확인 항목이 "차이 없음"으로 표기되지 않는다.
