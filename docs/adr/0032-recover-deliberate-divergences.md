# ADR 0032 — Deliberate divergences from upstream in Recover

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 10 (Reconstruct before improve), §17 (Scope와 Reasoning Discipline), Appendix A 16번
- Upstream evidence: [REPAIR_UPSTREAM_FINDINGS.md](../research/REPAIR_UPSTREAM_FINDINGS.md)

## Context

[ADR README](./README.md)의 규칙대로 Recover Stage의 upstream 대비 차이를 한
곳에 모은다 (Brief 0011, Blueprint 0022, Execute 0025, Verify 0029와 같은
패턴).

## Decision

### Divergences — 의도적으로 다르게 간다

| 항목 | upstream | Mission Control | 결정 |
|---|---|---|---|
| STALL의 처방 | REDISPATCH(재분해) 또는 lateral 전환 | v1은 `HOLD` — 분해·lateral 부재에서 자동 처방을 발명하지 않는다 | [ADR-0031](./0031-recover-v1-failure-and-retry-contract.md) §3 |
| 실패 분류의 폭 | verifier가 6종 전부를 매김 | v1은 결정적 인식 가능한 BLOCKED·STALL + UNCLASSIFIED — 매길 수 없는 분류를 흉내 내지 않는다 | [ADR-0031](./0031-recover-v1-failure-and-retry-contract.md) §3 |

### Deferrals — 보류. 차이가 아니라 미구현

| 항목 | upstream | 상태 | 기록 |
|---|---|---|---|
| 세밀한 실패 분류 (FABRICATION_SUSPECTED, SCOPE_CREEP, EVIDENCE 계열) | verifier 증거 계약 위의 분류 | **시한 도과 — 재지정 대기** (2026-08-09 발견): Phase 5에서 verifier(실제 semantic 평가자)가 실체화됐으나 분류는 미도입. 도입 시 정책 테이블(§2) 대조 | [REPAIR_UPSTREAM_FINDINGS §1~§2](../research/REPAIR_UPSTREAM_FINDINGS.md) |
| ESCALATE_MODEL (상위 tier 재실행) | FABRICATION의 처방 | 모델 라우팅 부재 — **조건 유지, 로드맵 미배치** (Phase 5는 라우팅을 만들지 않고 지나갔다) | 위 findings §2 |
| REDISPATCH_ALT_HARNESS (vendor 교체 재실행) | meta-harness 고유 수단 | **Phase 11 재평가 완료 — 미발동.** 병렬 worker가 늘었지만 concrete execution Runtime은 Codex 하나라 교체 대상이 없다. OpenCode adapter 실물 활성화 시점에 다시 본다 (2026-08-10) | 위 findings §2, [progress 0011](../progress/0011_PARALLEL_EXECUTION_GATE.md) |
| lateral 전환 (persona 선택, 개입 예산 1회) | RecoveryPlanner | v1 미도입 — 접근 전환은 마지막 재시도의 지시문까지 | [ADR-0031](./0031-recover-v1-failure-and-retry-contract.md) §5, findings §5 |
| OSCILLATION·NO_DRIFT·DIMINISHING_RETURNS 탐지 | 4패턴 해시·이력 기반 | v1은 SPINNING(동일 오류 3회)만 — 나머지는 실행 이력 축적 후 | findings §4 |
| rollback / worktree 복구 | ~~`core/worktree.py`~~ → **정정 2026-08-09**: 그 파일에 되돌리기는 없다. 실제 위치는 `scripts/ralph.sh`(파일)와 `core/lineage.py`(계보) 둘이다 ([ROLLBACK findings](../research/ROLLBACK_UPSTREAM_FINDINGS.md) §0) | **해소 2026-08-09** ([ADR-0047](./0047-rollback-to-the-last-proven-point.md) Proposed) — 재투입 전 마지막 입증 지점으로 되돌린다. 태그 없이 HEAD가 지점이며, dirty 가드는 격리·checkpoint가 대신하므로 이식하지 않는다 | [Open Questions §6](../research/OPEN_QUESTIONS.md) |
| cancelled 상태 | 존재 | **Phase 9로 재지정** (2026-08-09, Phase 7 종료 검토 — Phase 7 시한 무처분 도과). Recover 쪽 대가가 특히 크다: 취소 오류 문자열이 상수라 3회 취소가 `STALL` 오판을 만든다 ([progress 0007](../progress/0007_MCP_CONTROL_SURFACE.md) §2.3) | [ADR-0025](./0025-execute-deliberate-divergences.md) 보류와 같은 시점 |

### 미확인 — 대조하지 못했다. "차이 없음"이 아니다

| 항목 | 내용 |
|---|---|
| evolution 루프의 repair phase 상세 (wonder/reflect와의 관계) | 진화 루프는 v1 범위 밖 — 필요 시 조사 (findings §6) |
| lateral persona의 상세 계약 | lateral 도입 시 조사 |

## Consequences

- Recover 구현 전에 종료 검토 질문 3(미등록 이탈)의 대조 기준이 생겼다.
- v1의 모든 축소가 등록된 보류로 남아, 도입 시 upstream 대조 의무가 표에서
  보인다.

## Rejected alternatives

- **개별 ADR에 분산 유지**: Stage별 등록부 패턴(0011·0022·0025·0029)을
  따른다.

## Verification

- Recover 관련 ADR(0031)의 divergence·보류 서술이 모두 이 표에서 링크된다.
- 미확인 항목이 "차이 없음"으로 표기되지 않는다.
