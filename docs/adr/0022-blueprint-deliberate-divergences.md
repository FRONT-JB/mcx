# ADR 0022 — Deliberate divergences from upstream in Blueprint

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 10 (Reconstruct before improve), §17 (Scope와 Reasoning Discipline), Appendix A 16번
- Upstream evidence: [SEED_UPSTREAM_FINDINGS.md](../research/SEED_UPSTREAM_FINDINGS.md)

## Context

[ADR README](./README.md)의 규칙은 Stage별 divergence를 ADR 하나에 모으고, 다른
ADR에서 결정했더라도 여기서 링크하도록 요구한다. Brief는
[ADR-0011](./0011-brief-deliberate-divergences.md)이 그 자리이고, Blueprint는
0017~0019가 차이를 각자 기록한 채 등록부가 없었다. 이 ADR이 그 자리다.

각 항목의 근거와 기각된 대안은 결정한 ADR에 있다. 여기서는 항목, 방향, 링크만
유지한다. 새 차이가 생기면 결정 ADR에 기록하고 이 표에 행을 추가한다.

## Decision

Blueprint Stage의 upstream 대비 차이를 다음 표로 등록한다.

### Divergences — 의도적으로 다르게 간다

| 항목 | upstream | Mission Control | 결정 |
|---|---|---|---|
| QA 루프 위치 | skill 계층에만 있고 CLI에는 없다 | application 계층 — 모든 surface가 같은 루프를 거친다 | [ADR-0019](./0019-blueprint-qa-loop.md) §1 |
| 승인 | 승인 객체가 없다. 생성·저장이 곧 진행이다 | `BlueprintApproval`을 신설하고 QA 결과(정책 버전·임계값·점수·미달 수락)를 승인 기록이 보유한다 | [ADR-0019](./0019-blueprint-qa-loop.md) §8 |
| 선언되지 않은 필드 | `extra="allow"` — 세션이 임의 키를 실을 수 있다 | `extra="forbid"` — 검토 경로를 거치지 않은 내용이 승인 대상에 실리지 않는다 | [ADR-0017](./0017-blueprint-schema-baseline.md) §4 |
| `non_goals` | 스키마에 선언되지 않았고 `extra="allow"`로만 실릴 수 있다 | 1급 선언 필드 | [ADR-0017](./0017-blueprint-schema-baseline.md) §3 |
| Gen 1 생성기 입력 | 대화 원문에서 전부 추출한다 | 승인된 handoff의 칸만 전달한다 | [ADR-0018](./0018-blueprint-generation-contract.md), [ADR-0016](./0016-brief-handoff-projection.md) |
| 저장 형태 | seed마다 개별 YAML 파일, `parent_seed_id`로 lineage | mission당 단일 JSON 문서에 revision 나열 — 승인과의 원자적 연결 | [ADR-0021](./0021-blueprint-state-and-revisions.md) §1 |
| Gen 2+ 승인 | Reflect 결과를 후속 Seed로 만들고 같은 generation 호출에서 자율 실행·평가 | Evolve 결과는 같은 Mission의 pending Blueprint revision이며 매 generation QA + exact user approval 뒤에만 Execute | [ADR-0051](./0051-evolve-successor-blueprint-contract.md) §1·§6 |
| Evolve의 방향 변경 | Reflect가 goal·constraints를 refine | 자동 생산자는 goal·constraints·non-goals를 verbatim 보존; 변경 제안은 Brief 사용자 결정으로 HOLD | [ADR-0051](./0051-evolve-successor-blueprint-contract.md) §5 |
| Evolve replay 저장 | event store를 replay해 `OntologyLineage` read model 구성 | Blueprint 상태 문서 안 `EvolutionRecord` phase snapshot으로 재개 | [ADR-0051](./0051-evolve-successor-blueprint-contract.md) §8 |

### Adaptations — 형태가 다른 이식

| 항목 | 내용 | 결정 |
|---|---|---|
| AC identity | 같은 payload·알고리즘·길이의 key를 upstream은 필드로 저장하고 우리는 항상 파생한다. Evolve의 model index는 application 경계에서 parent content key로 바꾸며 explicit revise는 mechanical contract를 이어받고 key를 새로 파생한다 | [ADR-0017](./0017-blueprint-schema-baseline.md) §2, [ADR-0051](./0051-evolve-successor-blueprint-contract.md) §4 |
| 방어적 파싱 계층 | upstream의 2,637줄 파싱 방어 대신 구조화된 출력을 port 타입으로 요구한다 | [ADR-0018](./0018-blueprint-generation-contract.md) |
| QA 동점 규칙 | upstream 성문 규칙 없음 — 관측된 실행(축별 평균 우위)을 채택 | [ADR-0019](./0019-blueprint-qa-loop.md) §5 |

### Deferrals — 보류. 차이가 아니라 미구현

| 항목 | 상태 | 기록 |
|---|---|---|
| upstream Seed 필드 중 evaluation_principles, exit_conditions, task_type, brownfield_context | 미포함. `ontology_schema` 유예는 Phase 10 소비자가 생겨 해소 | [ADR-0017](./0017-blueprint-schema-baseline.md) Cost, [ADR-0051](./0051-evolve-successor-blueprint-contract.md) §3 |
| `verify_command` 한 줄 검사 | 보류 | [ADR-0017](./0017-blueprint-schema-baseline.md) Cost |
| 파싱 실패 시 1회 재시도 | 보류 | [ADR-0018](./0018-blueprint-generation-contract.md) §6 |
| quality bar 원문 사용 여부 | 한국어 번역 사용 중 — judge 어댑터 도입 시 재평가 | [ADR-0019](./0019-blueprint-qa-loop.md) §4 |

### 미확인 — 대조하지 못했다. "차이 없음"이 아니다

| 항목 | 내용 |
|---|---|
| FAIL 이후 루프 폐쇄 | `fail_threshold` 값은 upstream 것이나, FAIL 후 재채점·재편집을 금지하는 성문 규칙은 확인하지 못했다 ([ADR-0021](./0021-blueprint-state-and-revisions.md) §4) |
| 직전 채점 지적의 전달 | `QaRequest.previous_findings`는 직전 채점의 지적만 다음 채점에 전달한다. upstream skill 루프는 대화 안에 있어 전체 이력이 암묵적으로 전달되는데, 성문 규정과 전달 범위는 확인하지 못했다 (Phase 2 종료 검토에서 발견, [progress 0002](../progress/0002_BLUEPRINT_VERTICAL_SLICE.md)) |
| `ooo seed` 진입이 interview score를 다시 강제하는지 | [SEED_UPSTREAM_FINDINGS](../research/SEED_UPSTREAM_FINDINGS.md) §11 미조사 항목 |

### 해소된 미확인

| 항목 | 처분 |
|---|---|
| Seed revision lineage와 `parent_seed_id`의 정확한 의미 | Phase 10 pinned source·focused test 대조로 해소. `parent_seed_id`는 Gen 2+ successor가 직전 실행·평가된 Seed를 가리키는 generation lineage다. mcx는 같은 Mission의 `generation` + `evolved_from_revision`으로 대응한다 ([EVOLVE findings](../research/EVOLVE_UPSTREAM_FINDINGS.md), [ADR-0051](./0051-evolve-successor-blueprint-contract.md) §2) |

## Consequences

- Phase 2 종료 검토 질문 3(미등록 이탈)의 대조 기준이 한 곳에 생긴다.
- 새 차이를 만들 때 결정 ADR과 이 표 두 곳을 갱신해야 한다. 이 마찰은 의도된
  것이다 — 등록 비용이 없으면 차이가 조용히 쌓인다.

## Rejected alternatives

- **각 ADR의 기록으로 충분하다**: 대조하려면 ADR 전체를 다시 읽어야 하고,
  미확인 항목은 어느 ADR에도 자리가 없다.
- **여기서 근거까지 재서술**: 같은 내용이 두 곳에서 어긋나게 진화한다. 근거의
  진실은 결정 ADR 하나다.

## Verification

- Blueprint 관련 ADR(0017~0019, 0021, 0051)의 divergence 서술이 모두 이 표에서
  링크된다.
- 미확인 항목이 "차이 없음"으로 표기되지 않는다.
