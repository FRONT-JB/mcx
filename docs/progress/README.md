# Project Progress

> 이 문서는 계획이 아니라 **검증된 현재 상태**를 기록한다.

| 항목 | 현재 값 |
|---|---|
| Project phase | Phase 1 준비 — Brief upstream research |
| Mission status | ACTIVE |
| Gate | Phase 0 documentation COMPLETE; 구현은 Brief 우선 조사 완료 후 착수 |
| Source code | 없음 |
| Automated tests | 없음 |
| First implementation target | Brief domain/state/Gate vertical slice |
| Updated | 2026-08-07 |

## Current facts

- Git 저장소는 문서 작업 전에 비어 있었다.
- 구현 코드, packaging, dependency, test framework는 아직 선택하지 않았다.
- Mission Control의 Constitution과 설계 문서 초안이 작성되었다.
- upstream `Q00/ouroboros`의 기준 commit을 기록했다.
- 사용자 용어와 내부/upstream 용어 mapping을 확정했다.
- Runtime은 Codex/OpenCode 방향이며 Gemini는 v1 범위에서 제외했다.
- 상세 수치, persistence 기술, exact API는 아직 결정하지 않았다.
- 25개 Markdown 문서의 link, navigation, fence, parser, whitespace, terminology와
  lifecycle consistency 통합 검사가 통과했다.
- 사용자가 2026-08-07 세션에서 방향과 v1 boundary를 검토·승인했다
  ([progress 0000](./0000_DOCUMENTATION_FOUNDATION.md) Gate 참조).
- 루트에 에이전트 온보딩 지침 `AGENTS.md`와 `CLAUDE.md` symlink가 추가되었다.

## Documentation status

| 문서 | 상태 | 다음 Gate |
|---|---|---|
| `00_MISSION_CONTROL.md` | Active Draft | 구현 evidence로 검증 (사용자 검토 완료) |
| `01_ARCHITECTURE.md` | Draft | persistence/application boundary 결정 검토 |
| `02_MISSION_LIFECYCLE.md` | Draft | exact state/Recover open decisions 검토 |
| `03_RUNTIME.md` | Draft | protocol examples로 contract tests 정의 |
| `04_MCP.md` | Draft | tool schema와 transport 결정 전 Core boundary 유지 |
| `05_BRIEF.md` | Draft | upstream findings 반영과 첫 test cases 확정 |
| `06_BLUEPRINT.md` | Draft | schema/QA/revision policy 확정 |
| `07_EXECUTE.md` | Draft | work unit/dependency/runtime contract 결정 |
| `08_VERIFY.md` | Draft | mechanical/semantic contract 결정 |
| `09_RECOVER.md` | Draft | failure taxonomy/retry policy 결정 |
| `adr/` | 8 Accepted baseline ADRs | 구현으로 검증 |
| `research/` | Baseline created | Open Questions를 evidence로 해소 |

`Draft`는 빈 placeholder라는 뜻이 아니다. self-contained 설계와 체크리스트가
작성되었지만 사용자가 검토하고 구현 evidence로 검증하기 전이라는 뜻이다.

## Progress records

- [0000 — Documentation Foundation](./0000_DOCUMENTATION_FOUNDATION.md)

## Phase roadmap

시간 단위가 아니라 검증 가능한 outcome 단위로 진행한다.

### Phase 0 — Documentation Foundation

목표: 새 세션이 대화 기록 없이 프로젝트를 이해한다.

- [x] Constitution
- [x] Architecture
- [x] Mission Lifecycle
- [x] Runtime
- [x] MCP
- [x] Stage Guides
- [x] baseline ADRs
- [x] upstream mapping과 open questions
- [x] 전체 문서 통합 검사
- [x] 사용자 검토와 수정 (2026-08-07)

### Phase 1 — Brief vertical slice

목표: 첫 구현을 Brief에 필요한 최소 Core로 제한하고, 질문 loop와 CLEAR/HOLD Gate를
외부 Runtime 없이 검증한다.

- [ ] Brief에 필요한 최소 Mission, Stage, GateDecision, Attempt domain model
- [ ] Interview revision, round, answer provenance
- [ ] one-question tool-less text backend contract와 deterministic fake
- [ ] ambiguity/clarity policy와 user approval
- [ ] 최소 durable state 방식 ADR와 repository
- [ ] Brief 허용/금지 Stage transition tests

### Phase 2 — Blueprint vertical slice

목표: Brief를 승인 가능한 불변 Seed revision으로 변환한다.

- [ ] Seed schema
- [ ] generation/QA/refinement loop
- [ ] AC quality validation
- [ ] explicit user approval and revision lineage
- [ ] approved Seed revision binding
- [ ] Execute entry Gate

### Phase 3 — Execute with deterministic Runtime

목표: AC 기반 bounded work와 executed-unverified 상태를 검증한다.

- [ ] work derivation
- [ ] dependency readiness
- [ ] capability scope
- [ ] Runtime contract
- [ ] Telemetry

### Phase 4 — Verify and Recover

목표: evidence-driven completion과 bounded correction을 검증한다.

- [ ] mechanical verification
- [ ] semantic AC verdict
- [ ] failure packet
- [ ] Recover attempt history/budget
- [ ] MISSION COMPLETE Gate

### Phase 5 — Concrete Runtime adapters

목표: 동일 Core contract를 Codex와 OpenCode에서 실행한다.

- [ ] Codex adapter conformance
- [ ] OpenCode adapter conformance
- [ ] session/resume/cancel
- [ ] local model vs provided agent capability mapping

### Phase 6 — `mcx` CLI

목표: 다섯 Stage를 동일 application boundary로 조작한다.

- [ ] `mcx brief`
- [ ] `mcx blueprint`
- [ ] `mcx execute`
- [ ] `mcx verify`
- [ ] `mcx recover`

### Phase 7 — MCP control surface

목표: host가 CLI와 같은 Mission state/Gate 의미를 사용한다.

- [ ] read-only Mission query
- [ ] Brief mutation
- [ ] Blueprint approval
- [ ] long-running Execute/Verify/Recover job contract
- [ ] CLI/MCP parity tests
- [ ] recursion/security tests

## Implementation HOLD

코드 구현의 HOLD 조건은 다음과 같았고, 2026-08-07에 모두 충족되었다.

- [x] 전체 문서 link/terminology/decision-state 검사가 통과한다.
- [x] 사용자가 방향과 핵심 v1 boundary를 검토한다. (2026-08-07)
- [x] Brief 구현에 필요한 Open Questions를 우선순위화한다.
  ([Open Questions §0](../research/OPEN_QUESTIONS.md) 참조)
- [x] 첫 test-first vertical slice가 `05_BRIEF.md`에 고정되었다.

Brief 우선 조사(Open Questions §0)는 2026-08-07 완료되어
[INTERVIEW_UPSTREAM_FINDINGS.md](../research/INTERVIEW_UPSTREAM_FINDINGS.md)에
기록되었다 (LICENSE 재확인만 구현 직전 반복).

다음 검증 가능한 목표 한 개: **findings §8의 Proposed 항목을 결정으로
바꿔 `05_BRIEF.md`와 필요한 ADR에 반영하고, Phase 1의 첫 test cases를
확정한다.** 결정 반영 전에는 threshold 같은 미확정 값을 구현에서 고정하지
않는다.

## Update protocol

작업이 끝날 때마다 이 문서를 다음처럼 갱신한다.

1. 계획이 아니라 실제 완료 evidence를 확인한다.
2. 완료 checklist에 관련 test/commit/artifact를 연결한다.
3. 현재 HOLD/CLEAR 이유를 갱신한다.
4. 다음 한 개의 검증 가능한 목표를 지정한다.
5. Stage Guide와 구현이 다르면 차이를 숨기지 않는다.
