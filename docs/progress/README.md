# Project Progress

> 이 문서는 계획이 아니라 **검증된 현재 상태**를 기록한다.

| 항목 | 현재 값 |
|---|---|
| Project phase | Phase 2 — Blueprint vertical slice 시작 전 |
| Mission status | ACTIVE |
| Gate | Phase 0 COMPLETE; Phase 1 COMPLETE |
| Source code | `domain/brief/`, `domain/stage.py`, `domain/errors.py`, `application/` (ports, brief_service), `adapters/persistence/` |
| Automated tests | 140 passed (unit + integration) |
| First implementation target | Brief domain/state/Gate vertical slice — 완료 |
| Updated | 2026-08-07 |

## Current facts

- Git 저장소는 문서 작업 전에 비어 있었다.
- Python 3.12 + uv + pydantic + pytest, layered layout으로 확정했다 (ADR-0012).
- Brief Stage의 domain/application/adapter가 구현되었고 140개 테스트가 통과한다.
- Mission Control의 Constitution과 설계 문서 초안이 작성되었다.
- upstream `Q00/ouroboros`의 기준 commit을 기록했다.
- 사용자 용어와 내부/upstream 용어 mapping을 확정했다.
- Runtime은 Codex/OpenCode 방향이며 Gemini는 v1 범위에서 제외했다.
- Brief의 threshold와 durable state는 확정했다 (ADR-0009, ADR-0013). 이후
  Stage의 수치와 exact API는 아직 결정하지 않았다.
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
| `05_BRIEF.md` | Verified contract | Phase 1 구현과 140개 테스트로 검증 (미착수 행은 progress 0001 참조) |
| `06_BLUEPRINT.md` | Draft | schema/QA/revision policy 확정 |
| `07_EXECUTE.md` | Draft | work unit/dependency/runtime contract 결정 |
| `08_VERIFY.md` | Draft | mechanical/semantic contract 결정 |
| `09_RECOVER.md` | Draft | failure taxonomy/retry policy 결정 |
| `adr/` | 13 Accepted ADRs | 구현으로 검증 (0009~0013은 Phase 1로 검증됨) |
| `research/` | Baseline created | Open Questions를 evidence로 해소 |

`Draft`는 빈 placeholder라는 뜻이 아니다. self-contained 설계와 체크리스트가
작성되었지만 사용자가 검토하고 구현 evidence로 검증하기 전이라는 뜻이다.

## Progress records

- [0000 — Documentation Foundation](./0000_DOCUMENTATION_FOUNDATION.md)
- [0001 — Brief Vertical Slice](./0001_BRIEF_VERTICAL_SLICE.md)

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

### Phase 1 — Brief vertical slice — COMPLETE

목표: 첫 구현을 Brief에 필요한 최소 Core로 제한하고, 질문 loop와 CLEAR/HOLD Gate를
외부 Runtime 없이 검증한다.

- [x] Brief에 필요한 최소 Stage, GateDecision domain model
  - Mission aggregate와 Attempt는 만들지 않았다. Brief는 attempt lineage를 쓰지
    않고 Mission 참조는 `mission_id`로 충분하다. Mission의 canonical stage 저장은
    Blueprint로 나가는 전이가 실제로 필요해지는 Phase 2에서 다룬다.
- [x] Interview revision, round, answer provenance
  - [x] answer authority와 requirement input 투영 (B-031·B-032·B-033)
  - [x] round 축적, revision 증가, 승인 revision 바인딩과 stale 처리 (B-008·B-014)
- [x] one-question tool-less text backend contract와 deterministic fake (B-002, B-003)
- [x] ambiguity/clarity policy와 user approval
  - [x] 종료 후보 네 조건과 경계값, stability signal 전이 (B-027~B-030, B-035)
  - [x] 승인의 revision 바인딩 (B-014)
  - [x] 상태·정책·승인을 묶는 Gate 판정 (B-012, B-013, B-025, B-030)
  - [x] clarity 평가 port와 최소 round 이전 생략, 실패 처리 (B-029·B-035·B-036)
- [x] 최소 durable state 방식 ADR와 repository (ADR-0013, B-017·B-019)
- [x] Brief 허용/금지 Stage transition tests (L-S01·L-B02·L-B04)

Gate와 evidence는 [progress 0001](./0001_BRIEF_VERTICAL_SLICE.md)에 있다.

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

Brief 우선 조사(Open Questions §0)와 그에 따른 결정은 2026-08-07 완료되었다.
근거는 [INTERVIEW_UPSTREAM_FINDINGS.md](../research/INTERVIEW_UPSTREAM_FINDINGS.md),
결정은 ADR-0009~0011, 계약은 [Brief Guide](../05_BRIEF.md) §11·§12·§9.1에 있다.
Test Matrix는 B-039까지 확장되었다.

선행 결정은 ADR-0012(toolchain·실행 모델)와 ADR-0013(durable state)으로
확정했고, 첫 코드가 들어왔다.

Phase 1은 2026-08-07 완료되었다
([progress 0001](./0001_BRIEF_VERTICAL_SLICE.md)).

다음 검증 가능한 목표 한 개: **Brief handoff 객체를 정의해 Blueprint의 입력
계약을 고정한다** (B-026). 두 채널(requirement input / observed facts) 투영
함수는 이미 있으므로, 승인된 revision과 Gate evidence를 함께 담는 형태를 정하고
Blueprint가 그것만 읽도록 만든다. 이것이 Phase 2의 첫 작업이다.

### CLEAR 조건 중 강제되지 않는 것

[Brief Guide](../05_BRIEF.md) §13.1은 `CLEAR` 조건 11개를 규정한다. `Gate`가
실제로 검사하는 것은 4개다 — clarity 네 조건, 현재 revision 승인, material
미해결 항목, 판정에 기록되는 policy version. 나머지는 **계약 미달**이며 계약
위반과 구분해 여기에 명시한다.

| 조건 | 상태 |
|---|---|
| 중요한 Non-goals가 기록되어 있다 | 코드에 개념이 없다. L-B01이 검사하려는 HOLD를 만들 수 있는 경로가 없다 |
| 적용 가능한 Constraints가 기록되어 있다 | LLM의 `constraint` 명확도 점수가 대신하고 있을 뿐, 기록 여부를 확인하지 않는다 |
| Goal이 재해석 없이 충분히 명확하다 | `goal` dimension floor로만 근사한다 |
| material conflict가 없다 | conflict를 모델링하지 않는다 |
| material assumption이 해결/승인되었다 | assumption을 모델링하지 않는다 |
| 중요한 사실과 결정에 provenance가 있다 | `authority`는 타입으로 강제되나 `source`가 없고 존재 여부도 검사하지 않는다 |
| state와 approval이 durable하게 보존되었다 | Gate는 순수 함수라 확인할 수 없다. `decide_gate`가 저장소에서 읽기 때문에 우연히 성립할 뿐이다 |
| Gate decision이 판단 근거를 참조한다 | policy version만 있고 evidence reference가 없다 |

또한 미해결 항목은 승인 외 유일한 Gate 차단 사유인데 **application 경계에
진입점이 없다.** `note_unresolved`는 도메인에만 있고 `BriefService`가 호출하지
않아, 실제 사용 경로로는 이 차단을 발생시킬 수 없다.

### 현재 구현의 알려진 한계

계약 위반은 아니지만 이후 확장이 필요한 지점이다.

- 승인 이력이 최신 하나만 유지된다. “rev2를 승인했다가 rev4에서 재승인”의
  흐름은 Gate decision과 Telemetry가 들어올 때 보존 방식을 정한다.
- Gate decision을 저장하지 않는다. 판정은 매번 상태에서 다시 계산되며 `CLEAR`의
  근거 reference가 남지 않는다 (B-015 부분). Telemetry와 함께 다룬다.
- 저장된 평가의 `policy_version`이 현재 정책과 다른 경우를 검사하지 않는다.
  정책을 바꾸면 이전 정책으로 매긴 점수가 그대로 재사용된다. 지금은 정책이
  하나뿐이라 발생하지 않으며, 두 번째 정책이 생길 때 결정한다.
- clarity 평가자에게 `observation` 답변의 본문을 그대로 전달한다. requirement
  input 투영은 upstream 기준으로 요구사항 추출 입력에만 적용되므로 여기서는
  적용하지 않았다. 다만 "점수를 매긴 입력"과 "Blueprint가 받는 입력"이 달라지는
  긴장이 있으므로, handoff를 정의할 때 함께 판단한다.
- 질문 생성기가 한 문자열 안에 여러 질문을 담는 경우를 탐지하지 않는다. 반환
  타입이 질문 하나만 담도록 구조적으로 제한하며, 문장 단위 탐지는 신뢰할 만한
  방법이 없어 프롬프트와 출력 스키마의 문제로 남긴다.
- stale write 충돌 시 재확인을 요청하지 않는다. 탐지 후 오류를 전파하는 데서
  멈추며, `StaleWriteError`를 잡는 코드가 없다
  ([ADR-0014](../adr/0014-brief-concurrent-write-protection.md) §3). 동시 writer가
  실제로 생기는 Phase 7에서 구현한다.
- 답변이 질문에 identity로 연결되지 않는다. `record_answer`는 질문 식별자를 받지
  않고 대기 중인 마지막 round를 채운다. 지금 안전한 이유는 "열린 질문은 항상
  하나"라는 상태 불변 조건뿐이며, 질문을 여러 개 여는 변경은 §8.1 규칙 1을 조용히
  깬다.
- clarity 정책의 주입 가능성이 검증되지 않았다. `greenfield_v1()` 외의 정책을
  만드는 테스트가 없어, threshold를 코드에 하드코딩해도 테스트가 통과한다.
- 질문이 겨냥한 gap(`targeted_gap`)을 생성기가 반환하지만 저장하지 않는다.
  재개 시에는 `"resumed"`라는 실제 gap이 아닌 값을 반환한다 (§8 state 목록 미달).
- `observation` 답변도 최소 round 수에 포함된다. 사용자가 결정한 것이 하나도 없어도
  최소 round 조건을 통과할 수 있다. Fact Resolver 도입 시 함께 판단한다.
- stability signal이 `required_stability`에서 상한에 걸린다. 이후 정책이 연속
  횟수를 늘리면 이미 상한에 있던 상태는 차액만 채우면 된다.
- assumption과 conflict를 별도 개념으로 모델링하지 않았다 (§8, B-006·B-009).
  현재는 `unresolved_items`의 `is_material`로만 다룬다.
- `mission_id`와 `initial_intent`의 빈 값 검증이 없다. Entry Contract(§6)
  강제는 application use case 계층에서 다룬다.
- 시각(timestamp)을 다루지 않는다. Clock port 도입 시 함께 추가한다.

## Update protocol

작업이 끝날 때마다 이 문서를 다음처럼 갱신한다.

1. 계획이 아니라 실제 완료 evidence를 확인한다.
2. 완료 checklist에 관련 test/commit/artifact를 연결한다.
3. 현재 HOLD/CLEAR 이유를 갱신한다.
4. 다음 한 개의 검증 가능한 목표를 지정한다.
5. Stage Guide와 구현이 다르면 차이를 숨기지 않는다.
