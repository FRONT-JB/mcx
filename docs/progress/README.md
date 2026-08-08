# Project Progress

> 이 문서는 계획이 아니라 **검증된 현재 상태**를 기록한다.

| 항목 | 현재 값 |
|---|---|
| Project phase | Phase 3 — Execute vertical slice COMPLETE; Phase 4 준비 |
| Mission status | ACTIVE |
| Gate | Phase 0 COMPLETE; Phase 1 COMPLETE; Phase 2 COMPLETE (2026-08-08, [종료 검토](./0002_BLUEPRINT_VERTICAL_SLICE.md)); Phase 3 COMPLETE (2026-08-08, [종료 검토](./0003_EXECUTE_VERTICAL_SLICE.md)) |
| Source code | `domain/brief/` (state, provenance, clarity, requirement, closure, gate, handoff), `domain/blueprint/` (spec, assembly, qa, state, gate), `domain/execute/` (state, plan, gate), `domain/stage.py`, `domain/errors.py`, `application/` (brief·blueprint·execute service, ports), `adapters/persistence/` (brief·blueprint·execute) |
| Automated tests | 388 passed (unit + integration) |
| First implementation target | Brief domain/state/Gate vertical slice — 완료 |
| Updated | 2026-08-08 |

## Current facts

- Git 저장소는 문서 작업 전에 비어 있었다.
- Python 3.12 + uv + pydantic + pytest, layered layout으로 확정했다 (ADR-0012).
- Brief Stage와 Blueprint Stage의 domain/application/adapter가 구현되었고
  331개 테스트가 통과한다. Blueprint는 생성 → QA 반복 → 수정 → 승인 →
  Execute 진입 Gate가 파일 저장소를 거쳐 end-to-end로 돈다 (결정적 fake
  생성기·채점자 기준).
- Mission Control의 Constitution과 설계 문서 초안이 작성되었다.
- upstream `Q00/ouroboros`의 기준 commit을 기록했다.
- 사용자 용어와 내부/upstream 용어 mapping을 확정했다.
- Runtime은 Codex/OpenCode 방향이며 Gemini는 v1 범위에서 제외했다.
- Brief의 threshold와 durable state, Blueprint의 QA 정책은 확정했다
  (ADR-0009, ADR-0013, ADR-0019). 이후 Stage의 수치와 exact API는 아직
  결정하지 않았다.
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
| `05_BRIEF.md` | Verified contract | Phase 1 구현으로 검증, §11.6·B-040~043은 ADR-0020 소급 (미착수 행은 progress 0001 참조) |
| `06_BLUEPRINT.md` | Draft | schema·QA·revision policy는 ADR-0017~0019·0021로 확정, Phase 2 종료 검토에서 구현 evidence 대조 |
| `07_EXECUTE.md` | Draft | v1 계약(§6·§7·§13·§14)은 Phase 3 구현으로 검증 ([종료 검토](./0003_EXECUTE_VERTICAL_SLICE.md)). telemetry schema·runtime contract·timeout·병렬 Gate는 미정 |
| `08_VERIFY.md` | Draft | mechanical/semantic contract 결정 |
| `09_RECOVER.md` | Draft | failure taxonomy/retry policy 결정 |
| `adr/` | 27 Accepted ADRs | 구현으로 검증 (0009~0016은 Phase 1과 후속 감사로, 0017~0019·0021~0022는 Phase 2로, 0020은 Phase 1 소급, 0023~0025는 Phase 3 선행 결정, 0026~0027은 Phase 4 선행 결정) |
| `research/` | Baseline created | Open Questions를 evidence로 해소 |

`Draft`는 빈 placeholder라는 뜻이 아니다. self-contained 설계와 체크리스트가
작성되었지만 사용자가 검토하고 구현 evidence로 검증하기 전이라는 뜻이다.

## Progress records

- [0000 — Documentation Foundation](./0000_DOCUMENTATION_FOUNDATION.md)
- [0001 — Brief Vertical Slice](./0001_BRIEF_VERTICAL_SLICE.md)
- [0002 — Blueprint Vertical Slice](./0002_BLUEPRINT_VERTICAL_SLICE.md)
- [0003 — Execute Vertical Slice](./0003_EXECUTE_VERTICAL_SLICE.md)

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

**2026-08-08 소급 추가 — closure 감사 (ADR-0020, B-040~B-043).** upstream
조사(research §13)에서 종료 gate에 판단 감사가 있음을 확인해 Phase 1 완료
범위를 소급 확장했다. 3-lane(closer/contrarian/gap_hunter) 전부 재구성, 합성은
결정적 도메인 코드, `CLEAR`는 현재 revision의 ready 감사를 요구한다. 계약
문장은 upstream 영어 원문이며, ambiguity 점수 비전달이 등록된 divergence다.
`domain/brief/closure.py` + `BriefService.audit_closure` + 테스트 21건, 기존
CLEAR 경로 테스트 전부 감사 단계를 포함하도록 갱신했다.

### Phase 2 — Blueprint vertical slice — COMPLETE

목표: Brief를 승인 가능한 불변 Seed revision으로 변환한다.

2026-08-08 완료. Gate·evidence·종료 검토는
[progress 0002](./0002_BLUEPRINT_VERTICAL_SLICE.md)에 있다. 검토가 계약 미달
하나(중복 AC 검사 부재)를 잡아 수정했다 (b00e0c2).

- [x] Blueprint schema baseline과 AC identity (ADR-0017)
- [-] generation/QA/refinement loop
  - [x] 생성 계약: 위임 경계와 결정적 범위 검사 (ADR-0018)
  - [x] QA 루프 정책과 반복 상한, 최선 시도 추적 (ADR-0019)
  - [x] 루프의 durable 상태와 채점 허용 규칙 — 상한·FAIL 중단·통과 재채점
    금지가 재시작을 건너 유지된다 (ADR-0021 §4, `test_state.py`·
    `test_blueprint_flow.py`)
  - [-] 수정 후보 제시와 사용자 채택 절차 → **Phase 6·7로 이관**
    ([progress 0002](./0002_BLUEPRINT_VERTICAL_SLICE.md) 처분). 채택된 수정이
    들어오는 application 진입점(`revise` — 범위 재검사, 새 revision)은 구현됨
- [-] AC quality validation — 구조 검사(중복 계약·빈 goal·`output_assertion`
  명령 요구)는 충족. 의미 판정은 QA 채점자 어댑터와 함께 **Phase 5로 이관**
  (ADR-0019 §4, [progress 0002](./0002_BLUEPRINT_VERTICAL_SLICE.md) 처분)
- [x] explicit user approval and revision lineage
  - [x] `BlueprintApproval` — QA 결과와 임계 미달 수락을 승인 기록에 고정
    (ADR-0019 §8)
  - [x] `BlueprintService` — handoff 조회 → 생성 → 조립 → QA 반복 → 승인 →
    저장 (ADR-0021, commit 709f9ec, `test_blueprint_service.py` 22건)
- [x] approved Seed revision binding — 승인은 채점된 현재 revision에 묶이고,
  revise가 revision을 올리면 stale이 된다 (ADR-0021 §5)
- [x] Execute entry Gate — `evaluate_blueprint_gate`가 승인된 현재 revision과
  현재 Brief revision 일치를 요구한다 (ADR-0021 §6, `test_gate.py`)

**upstream 런타임 관측 반영 (2026-08-08).** v0.50.8 도그푸딩 세션 전사를 대조해
세 항목을 고쳤다 —
[SEED_UPSTREAM_FINDINGS §12](../research/SEED_UPSTREAM_FINDINGS.md).

| 항목 | 조치 |
|---|---|
| `QaDimension`에 `DOMAIN_SPECIFIC` 누락 (research §8은 다섯 축으로 기록) | 축 추가, 일치 테스트 고정 |
| 동점 규칙이 관측과 반대 (`먼저 나온 것`) | 축별 평균으로 판정, ADR-0019 §5 개정 |
| QA 결과를 담을 자리 없음 | `BlueprintApproval` 신설, ADR-0019 §8 추가 |

관측이 확인해 준 것: 인터뷰에는 QA가 붙지 않고 Seed에만 붙는다(research §8 유지),
`generate_seed`가 저장된 session을 요구한다(ADR-0016 방향 일치), skill 계층 QA의
개정본이 store로 돌아가지 않는다(ADR-0019 §1 근거 강화).

### Phase 3 — Execute with deterministic Runtime — COMPLETE

목표: AC 기반 bounded work와 executed-unverified 상태를 검증한다.

2026-08-08 완료. Gate·evidence·종료 검토는
[progress 0003](./0003_EXECUTE_VERTICAL_SLICE.md)에 있다. 검토가 Test Matrix
누락 2행(테스트 추가, 2f951e2), ADR 과장 1건, 표시 없는 보류 3건(telemetry
schema 시점, 고아 attempt, 재시도 정책)을 잡았다. `[-]` 항목은 v1 범위와
잔여의 구분이며, 잔여의 처분(Phase 4·5, §9 결정 대기)은 record에 있다.

- [x] work derivation — AC key가 곧 실행 단위, 선언 순서 순차, 분해 미도입
  (ADR-0024 §1~§3, commit 016c1b8, `test_plan.py`)
- [-] dependency readiness — v1은 파생 없이 실패 중단 규칙만
  (ADR-0024 §3, ADR-0025 보류 등록). graph 도입은 이후 결정
- [-] capability scope — envelope(workspace + 도구 목록)의 전달·기록까지
  (ADR-0024 §6). 실제 차단은 Phase 5
- [-] Runtime contract — `ExecutionRuntime` port(backend + execute)와 결정적
  fake. concrete adapter conformance는 Phase 5
- [-] Telemetry — attempt 기록이 provenance 네 항목을 선언 필드로 강제
  (ADR-0023 §3, `test_state.py` 누락 거부). event/report/bundle schema는
  미정 ([Open Questions §9](../research/OPEN_QUESTIONS.md))

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
([progress 0001](./0001_BRIEF_VERTICAL_SLICE.md)). 이후 같은 날 감사에서 드러난
계약 미달 세 건을 닫았다 — 요구사항 후보 모델(ADR-0015), Brief handoff
투영(ADR-0016), 그리고 미해결 후보의 application 진입점.

Phase 2의 첫 결정(Blueprint schema)은 2026-08-07 완료되었다
([ADR-0017](../adr/0017-blueprint-schema-baseline.md),
[SEED_UPSTREAM_FINDINGS](../research/SEED_UPSTREAM_FINDINGS.md)).

생성 계약(ADR-0018)과 QA 루프 정책(ADR-0019)은 2026-08-07 확정되었다.

Phase 2는 2026-08-08 완료되었다
([progress 0002](./0002_BLUEPRINT_VERTICAL_SLICE.md) — 종료 검토 포함). handoff
조회 → 생성 → 조립 → QA 반복 → 수정 → 승인 → Execute 진입 Gate가 파일 저장소를
거쳐 이어지고, 승인은 채점된 현재 revision에 묶인다.

Execute 시작 전 결정은 2026-08-08 닫혔다
([ADR-0023](../adr/0023-execute-entry-and-provenance.md),
[RUN_UPSTREAM_FINDINGS](../research/RUN_UPSTREAM_FINDINGS.md)) — 작업 생성은
단일 use case 경로, provenance 네 항목은 선언 필드.

Execute 첫 vertical slice는 2026-08-08 구현되었다 (ADR-0023~0025,
commit 016c1b8). 승인된 Blueprint에서 순차 dispatch → 결과 기록 →
`CLEAR — Clear for Verify`가 파일 저장소를 거쳐 이어지고, 지속이 dispatch보다
먼저이며, provenance 없는 attempt는 만들어지지 않는다.

Phase 3은 2026-08-08 완료되었다
([progress 0003](./0003_EXECUTE_VERTICAL_SLICE.md) — 종료 검토 포함). 검토가
Test Matrix 누락 2행(2f951e2로 테스트 추가), ADR-0024 Verification 과장 1건,
표시 없는 보류 3건을 잡았다. §9 Required Telemetry 대조 결과 미답 항목(시각,
변경 artifact, 명령 결과, 이벤트)의 처분은 **결격이 아니라 Open Questions §9
결정 대기**이며, 시한은 Phase 4 진입 전으로 고정되었다.

Verify 진입 전 결정 두 개는 2026-08-08 닫혔다
([EVALUATE_UPSTREAM_FINDINGS](../research/EVALUATE_UPSTREAM_FINDINGS.md)) —
upstream evaluate는 실행 lineage를 요구하지 않음을 소스로 확인했고(§12.3
사고의 직접 원인), 우리는 Verify 진입이 Execute Gate `CLEAR`를 요구하는
의도적 divergence로 확정했다
([ADR-0026](../adr/0026-verify-entry-requires-lineage.md)). telemetry 세 층은
소비자·시점을 배치하고 report 층 v1 스키마를 확정했다
([ADR-0027](../adr/0027-telemetry-layers-and-v1-schema.md)).

다음 검증 가능한 목표 한 개: **Phase 4 Verify 첫 slice의 계약을
[Verify Guide](../08_VERIFY.md)에 고정한다** — ADR-0026(진입)·0027(report
스키마 최종 필드명)을 반영하고, mechanical verification의 Test Matrix 행에
upstream 근거를 표시한 뒤 구현에 들어간다. mechanical.toml 스키마와 명령 발견
규칙의 upstream 조사(EVALUATE_UPSTREAM_FINDINGS §8)가 선행이다.

### CLEAR 조건 중 강제되지 않는 것

[Brief Guide](../05_BRIEF.md) §13.1은 `CLEAR` 조건 11개를 규정한다. `Gate`가
실제로 검사하는 것은 4개다 — clarity 네 조건, 현재 revision 승인, material
미해결 항목, 판정에 기록되는 policy version. 나머지는 **계약 미달**이며 계약
위반과 구분해 여기에 명시한다.

| 조건 | 상태 |
|---|---|
| 중요한 Non-goals가 기록되어 있다 | `non_goal` section은 생겼으나 **기록 여부를 검사하지 않는다.** upstream도 core gate가 아니라 auto driver의 grading에서만 확인한다 |
| 적용 가능한 Constraints가 기록되어 있다 | 위와 같다. LLM의 `constraint` 명확도 점수가 대신하고 있을 뿐이다 |
| Goal이 재해석 없이 충분히 명확하다 | `goal` dimension floor로만 근사한다 |
| 중요한 사실과 결정에 provenance가 있다 | `confirmation_authority`가 승격 판정에 쓰이나 `source` locator가 없고 존재 여부도 검사하지 않는다 |
| state와 approval이 durable하게 보존되었다 | Gate는 순수 함수라 확인할 수 없다. `decide_gate`가 저장소에서 읽기 때문에 우연히 성립할 뿐이다 |
| Gate decision이 판단 근거를 참조한다 | policy version만 있고 evidence reference가 없다 |

2026-08-07 [ADR-0015](../adr/0015-requirement-candidate-model.md)로 다음 두 조건이
강제 상태가 되었다 — **material conflict 부재**(`resolution=conflicting`은
`required`와 무관하게 차단)와 **material assumption 해결**(`model_inferred` 내용은
사용자 확인 없이 승격되지 않음). 미해결 후보를 만들 application 진입점
(`record_candidate` / `resolve_candidate`)도 함께 생겨, 승인 외 Gate 차단 사유가
실제 사용 경로에서 도달 가능해졌다.

### Blueprint의 알려진 한계

- **AC가 결과인지 수단인지는 QA 품질 기준이 판정한다** ([ADR-0019](../adr/0019-blueprint-qa-loop.md) §4).
  `check_scope`는 여전히 존재 여부만 보며, 이 판정은 채점자 어댑터가 붙어야
  실제로 동작한다.
- **AC의 출처를 추적하지 않는다.** 성공 조건과 무관한 AC를 만들어도 범위 검사를
  통과한다 ([ADR-0018](../adr/0018-blueprint-generation-contract.md) Cost).
- **종료코드 검사 개념이 없다.** upstream은 `verify_command`가 있으면 runner가
  종료코드 0을 자동 확인하므로 명령 자체가 완결된 계약이다(§3.2). Mission
  Control의 `is_mechanically_verifiable`은 "확인 수단이 적혀 있다"까지만 뜻하며,
  실제 실행은 Verify(Phase 4)가 도입한다.
- **`context`를 채우는 장치가 없다.** 생성기가 확인 명령을 만들려면 "이 프로젝트는
  pytest를 쓴다" 같은 사실이 필요한데, 그것을 조사하는 Fact Resolver가 미구현이다
  (B-004). 현재는 사용자가 직접 `context` 후보로 기록해야 한다.
- **생성기가 제약·Non-goal 문자열을 그대로 옮겨야 한다.** 표현을 다듬으면 범위
  위반으로 거부된다. 생성 프롬프트가 원문 보존을 지시해야 한다.
- **파싱 실패 재시도 정책이 없다.** QA 반복(ADR-0019)과는 다른 실패다.
  upstream은 추출 파싱 실패 시 한 번 재시도한다
  ([ADR-0018](../adr/0018-blueprint-generation-contract.md) §6).
- **문자열/배열 크기 제한이 없다** ([Blueprint Guide](../06_BLUEPRINT.md) §7.2
  항목). 비정상적으로 큰 명세가 구조 검사를 통과한다. Phase 2 종료 검토에서
  확인해 여기에 표시한다.
- **QA 채점자 어댑터가 없다.** port와 정책만 있으므로 실제 채점은 아직
  일어나지 않는다.
- **상한 도달 시 최선의 시도가 현재 revision이 아니면 그것을 채택하는 경로가
  없다.** 승인은 현재 revision만 대상이므로, 이 경우 사용자는 이전 revision의
  내용을 수락할 수 없다. 수정 후보 채택 절차(Phase 6·7)와 함께 다루며, 내용
  동일성 판정이 필요해지면 content hash open decision을 그때 확정한다
  ([ADR-0021](../adr/0021-blueprint-state-and-revisions.md) §5).
- **FAIL 이후의 출구가 없다.** 채점·승인이 모두 거부되므로 에스컬레이션(Brief
  복귀)이 유일한 경로인데, 그 복귀 절차 자체는 미구현이다
  ([ADR-0021](../adr/0021-blueprint-state-and-revisions.md) Cost).

### Execute Gate CLEAR 조건 중 강제되지 않는 것

[Execute Guide](../07_EXECUTE.md) §10은 `CLEAR — Clear for Verify` 조건 6개를
규정한다. `evaluate_execute_gate`가 실제로 검사하는 것은 3개다 — attempt
종료(ATTEMPT_OPEN), 현재 revision의 전 AC 실행(CRITERION_UNEXECUTED), 실행
실패 부재(CRITERION_FAILED). 승인 Seed revision 연결은 Gate 앞의 진입
확인(`_cleared_blueprint`)과 revision 스코프 판정이 구조적으로 성립시킨다.
나머지는 **계약 미달**이며 여기 명시한다 ([progress
0003](./0003_EXECUTE_VERTICAL_SLICE.md) 종료 검토에서 추가).

| 조건 | 상태 |
|---|---|
| 대상 AC와 **변경 artifact**를 추적할 수 있다 | AC는 `ac_key`로 추적된다. 변경 artifact는 **개념 자체가 없다** — §9 telemetry schema 결정 대기 |
| 필수 Runtime events와 명령 결과가 보존되어 있다 | **검사하지 않는다.** event·command result 층이 없다 — §9 결정 대기. 지금의 `CLEAR`는 이 보존을 보장하지 않는다 |
| Verify가 독립적으로 판정할 충분한 입력이 있다 | **검사하지 않는다.** "충분"의 정의가 Verify 계약(Phase 4) 소유다. 현재는 `EXECUTED_UNVERIFIED` 존재까지만 |

### Execute의 알려진 한계

- **같은 AC 재시도에 상한이 없고, 재시도가 동일 요청이다.** 실패 증거를 다음
  시도에 전달하지 않는다(§7 초안의 `previous_failure_refs` 미구현). Guide
  §11("같은 prompt를 반복하지 않는다")의 분석 주체는 Recover(Phase 4)이며,
  upstream의 재시도 제한·증거 전달 방식은 미조사다
  ([ADR-0025](../adr/0025-execute-deliberate-divergences.md) 미확인 표).
  v1에서 반복의 주체는 호출자(사용자)라 자동 무한 루프는 없다.
- **고아가 된 열린 attempt를 해소할 진입점이 없다.** 결과 저장 실패나 크래시
  후 `DISPATCHED`로 남은 attempt는 Gate가 "결과 불명"으로 드러내지만, 늦은
  결과 기록이나 실패 처리를 할 경로가 없어 mission이 멈춘다. resume(Phase 5)과
  Recover(Phase 4)에서 다룬다.
- **attempt에 시각이 없다.** §9의 "언제 시작하고 종료했는가"에 답하지 못한다.
  Clock port 도입(Brief 한계와 같은 축) 및 §9 schema와 함께 다룬다.
- **envelope가 인스턴스 구성으로 주입된다.** workspace 격리 방식이 미정이라
  (Guide §17) mission별 envelope 파생이 없다 — 모든 mission이 같은 경계를
  받는다.
- **execution_id가 attempt 번호에서 파생된다** (`exec-<mission>-<n>`).
  idempotency exact key schema(§17 미정)가 결정되면 재평가한다.

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

## Phase 종료 검토

Phase를 완료로 선언하기 전에 아래 여섯 질문에 답하고, 답을 그 phase의
progress record에 남긴다. 이 검토는 새 절차가 아니라 기존 관행의 기록이다 —
지금까지의 이탈은 전부 사후 감사(사용자 질문, 도그푸딩 대조, 완료 당일
감사)에서 잡혔고, 이 목록은 그 감사를 운이 아니라 절차로 만든다.

각 질문은 예/아니오가 아니라 **증거**를 요구한다. 근거 없는 체크 표시는
거짓 안심이므로, 답할 수 없는 항목은 답하지 못했다고 그대로 기록한다.

1. **구조 검사** — 이 phase가 만든 방어 각각에 대해 "어떤 결함을 막는가"를
   한 문장으로 말할 수 있는가? 산문·프롬프트로만 막고 있는 계약은
   "강제되지 않는 것" 류의 표에 올라갔는가?
2. **부품/단계 구분** — end-to-end로 도는가(결정적 fake로라도)? 미조립
   부품을 완료로 기록하지 않았는가?
3. **미등록 이탈** — upstream과 다른 곳 중 ADR/divergence register에 없는
   것이 있는가? *(실례: quality bar 한국어 번역 — ADR-0019 §4로 소급 등록)*
4. **표시 없는 보류** — 보류·미확인이 문서의 그 자리에 표시되어 있는가?
   *(실례: verify_command 한 줄 규칙 보류 — ADR-0017 Cost로 소급 기록)*
5. **계약 문장 원문 여부** — 문장이 곧 계약인 곳에 번역·의역이 없는가?
   *(재발 방지 사례: closure 계약 문장은 영어 원문 — ADR-0020 §4)*
6. **관측 대조** — 도그푸딩·런타임 관측과 모순되는 규칙이 없는가?
   *(실례: QA 동점 규칙이 관측과 반대 — ADR-0019 §5로 개정)*

최종 목표인 Phase 7까지 모든 구현 phase가 이 검토를 거친다. Phase 0은 문서
기반이라 대상이 아니다.

| Phase | 검토 상태 | 기록 |
|---|---|---|
| Phase 1 — Brief | 소급 충족 — 완료 당일 감사(ADR-0015·0016), 관측 대조에 따른 closure 소급(ADR-0020), 등록된 이탈은 ADR-0011과 ADR-0020 §5 | [progress 0001](./0001_BRIEF_VERTICAL_SLICE.md) |
| Phase 2 — Blueprint | **충족 (2026-08-08)** — 완료 선언 전 절차로 첫 수행. 계약 미달 1건 발견·수정(중복 AC, b00e0c2), 표시 누락 1건 추가(크기 제한), 미확인 이탈 1건 등록(previous_findings → ADR-0022) | [progress 0002](./0002_BLUEPRINT_VERTICAL_SLICE.md) |
| Phase 3 — Execute | **충족 (2026-08-08)** — Test Matrix 누락 2행 테스트 추가(2f951e2), ADR-0024 과장 정정, §10 미검사 조건 표 추가, telemetry schema 시점 정정(§9 → Phase 4 전), 재시도 정책 미확인 등록(ADR-0025) | [progress 0003](./0003_EXECUTE_VERTICAL_SLICE.md) |
| Phase 4 — Verify/Recover | 대기 | — |
| Phase 5 — Runtime adapters | 대기 | — |
| Phase 6 — `mcx` CLI | 대기 | — |
| Phase 7 — MCP control surface | 대기 | — |

## Update protocol

작업이 끝날 때마다 이 문서를 다음처럼 갱신한다.

1. 계획이 아니라 실제 완료 evidence를 확인한다.
2. 완료 checklist에 관련 test/commit/artifact를 연결한다.
3. 현재 HOLD/CLEAR 이유를 갱신한다.
4. 다음 한 개의 검증 가능한 목표를 지정한다.
5. Stage Guide와 구현이 다르면 차이를 숨기지 않는다.
6. Phase 완료를 선언하려면 먼저 위의 Phase 종료 검토를 수행하고 결과를
   progress record에 남긴다.
