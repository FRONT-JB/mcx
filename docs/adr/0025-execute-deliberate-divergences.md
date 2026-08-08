# ADR 0025 — Deliberate divergences from upstream in Execute

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 10 (Reconstruct before improve), §17 (Scope와 Reasoning Discipline), Appendix A 16번
- Upstream evidence: [RUN_UPSTREAM_FINDINGS.md](../research/RUN_UPSTREAM_FINDINGS.md)

## Context

[ADR README](./README.md)의 규칙대로 Execute Stage의 upstream 대비 차이를 한
곳에 모은다 (Brief는 [0011](./0011-brief-deliberate-divergences.md), Blueprint는
[0022](./0022-blueprint-deliberate-divergences.md)).
[ADR-0023](./0023-execute-entry-and-provenance.md) §3이 이관을 예고한 항목을
여기로 옮긴다.

## Decision

### Divergences — 의도적으로 다르게 간다

| 항목 | upstream | Mission Control | 결정 |
|---|---|---|---|
| Telemetry provenance의 위치 | 이벤트 payload(JSON) 안의 emitter 관례. events 스키마에 actor 컬럼 없음 | 생성 경로·실행 주체·lineage·시도 네 항목을 1급 선언 필드로 강제 | [ADR-0023](./0023-execute-entry-and-provenance.md) §3 (이관 완료) |
| 순환 의존의 처리 | 경고 후 남은 AC 전부를 같은 level로 실행 (hard fail 아님) | v1은 dependency 파생이 없어 발생 불가. 도입 시 **명시적 HOLD**로 간다 — 순환을 조용히 병렬로 바꾸면 의존이 있다는 신호 자체가 사라진다 | 이 표 (도입 시 ADR로 확정) |

### Deferrals — 보류. 차이가 아니라 미구현

| 항목 | upstream | 상태 | 기록 |
|---|---|---|---|
| AC 분해 (preflight/bounce, 자식 2~5, 라이브 깊이 2, repair 1) | 예외 경로로 존재 | v1 미도입 — atomic-first의 1단계만. 도입 시 upstream 한도와 대조 | [ADR-0024](./0024-execute-v1-execution-model.md) §2 |
| dependency 파생 (선언 신호 ∪ LLM 추론, 토폴로지 level) | 존재 | v1 미도입 — 선언 순서 순차 + 실패 시 중단 | [ADR-0024](./0024-execute-v1-execution-model.md) §3 |
| 병렬 실행 (stage 안 병렬, serial-only 분리) | 존재 | v1 미도입. **Phase 11** (2026-08-09 사용자 결정 — OpenCode adapter와 한 묶음). 도입 Gate는 [Execute Guide](../07_EXECUTE.md) §17 | [ADR-0024](./0024-execute-v1-execution-model.md) §3 |
| cancelled/timeout attempt 상태 | 존재 (stall scope, cancel) | **Phase 7** (2026-08-09 재지정 — 장기 job 취소 계약과 함께). 원래 시한 "concrete adapter(Phase 5)"는 도과했다: Phase 5 adapter는 단발 실행이라 취소 경로를 만들지 않았다 | [ADR-0024](./0024-execute-v1-execution-model.md) §4 |
| capability의 실제 차단 | runtime 계층에서 tools 목록·approval mode 전달 | **Phase 5 부분 이행** — 실행측은 sandbox 수준(`--sandbox workspace-write`), 텍스트 lane은 도구 카탈로그(ADR-0036 §4)까지. **도구 단위 allowlist 차단은 Codex CLI에 표면이 없어 보류 유지** (ADR-0033 §6 표) | [ADR-0024](./0024-execute-v1-execution-model.md) §6 |
| context reference 예산 (참조 256개, 12,000자) | 존재 | v1 미도입 — dispatch 입력이 AC 하나라 예산 문제가 아직 없다 | 이 표 |

### 미확인 — 대조하지 못했다. "차이 없음"이 아니다

| 항목 | 내용 |
|---|---|
| ~~evaluate가 실행 lineage를 요구하는지~~ | **2026-08-08 확인 완료 — 요구하지 않는다** ([EVALUATE_UPSTREAM_FINDINGS §2](../research/EVALUATE_UPSTREAM_FINDINGS.md)). 우리는 요구한다 — 의도적 divergence로 [ADR-0026](./0026-verify-entry-requires-lineage.md)에 등록 (Verify 등록부 신설 시 이관) |
| 분해 SPLIT 판정의 실제 주체와 preflight 기준 | 분해 도입 시 조사 (§10) |
| resume/cancel 계약 | **Phase 7에서 조사** (2026-08-09 사용자 결정 — 장기 실행 job 계약과 한 묶음). 원래 시한 "Phase 5에서 조사"는 도과했다 — Phase 5는 단발 실행 계약만 확정했다 |
| ~~runtime handle 직렬화의 정확한 필드 목록~~ | **2026-08-08 확인 완료** — backend/kind/native_session_id/cwd/approval_mode/metadata ([EVALUATE_UPSTREAM_FINDINGS §7](../research/EVALUATE_UPSTREAM_FINDINGS.md)) |
| ~~실행 실패 후 같은 AC 재시도의 정책~~ | **2026-08-08 확인 완료** — 상한은 `ac_retry_attempts` 기본 2회 ([VERIFY_UPSTREAM_FINDINGS §2](../research/VERIFY_UPSTREAM_FINDINGS.md)), 실패 증거는 재시도 프롬프트에 분류+오류 tail+마지막 시도의 전환 지시로 전달 ([REPAIR_UPSTREAM_FINDINGS §3](../research/REPAIR_UPSTREAM_FINDINGS.md)). 우리 채택은 [ADR-0031](./0031-recover-v1-failure-and-retry-contract.md) §4~§5 — Execute의 "동일 요청 무제한 재시도" 한계가 Recover에서 해소된다 |

## Consequences

- Phase 3 종료 검토 질문 3(미등록 이탈)의 대조 기준이 구현 시작 전에 생겼다.
- v1 실행 모델의 모든 축소가 "등록된 보류"로 남아, 이후 도입 시 upstream
  대조 의무가 표에서 바로 보인다.

## Rejected alternatives

- **ADR-0023 §3에 계속 두기**: 등록부 없이 개별 ADR에 흩어지는 것을 막으려고
  0022를 만들었다. 같은 규칙을 Execute에도 적용한다.

## Verification

- Execute 관련 ADR(0023, 0024)의 divergence·보류 서술이 모두 이 표에서
  링크된다.
- 미확인 항목이 "차이 없음"으로 표기되지 않는다.
