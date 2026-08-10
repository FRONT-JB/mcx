# Project Progress

> 이 문서는 계획이 아니라 **검증된 현재 상태**를 기록한다.

| 항목 | 현재 값 |
|---|---|
| Project phase | **Phase 9 COMPLETE (2026-08-10)** — 실사용 진입·되돌리기·관측 층, 종료 검토 포함 ([progress 0009](./0009_RECOVERY_LAYERS.md)). **Phase 10 Reflect/Evolve upstream 조사 진행 중** |
| Mission status | ACTIVE |
| Gate | **Phase 0~9 COMPLETE.** Phase 10 진입 조건 없음([progress 0009 §4](./0009_RECOVERY_LAYERS.md)); 구현 전 upstream Gen 2+ 연결 경로 조사와 설계 ADR 필요 |
| Source code | `domain/brief/` (state, provenance, clarity, requirement, closure, gate, handoff), `domain/blueprint/` (spec, assembly, qa, state, gate), `domain/execute/` (state, plan, gate), `domain/verify/` (evidence, verdict, gate), `domain/recover/` (packet, gate), `domain/stage.py`, `domain/errors.py`, `application/` (brief·blueprint·execute·verify·recover service, ports), `adapters/persistence/` (brief·blueprint·execute·verify), `adapters/verification/` (local runner), `adapters/runtime/` (codex), `adapters/text/` (완성 엔진 codex·claude + vendor 중립 위임 어댑터 7종), `domain/mission.py` (mission record), `adapters/persistence/file_mission_repository.py`, `cli/` (composition root + 24 명령, entry point `mcx`, 명령 원장·status 렌더, Stage→backend 라우팅), `security.py`·`cancellation.py`, `mcp/` (tool 29종 — CLI 파서 파생, 원장 유도 job, stdio, entry point `mcx-mcp`) |
| Automated tests | 967 passed (unit + integration, 2026-08-10 실측) |
| First implementation target | Brief domain/state/Gate vertical slice — 완료 |
| Updated | 2026-08-10 |

## Current facts

- Git 저장소는 문서 작업 전에 비어 있었다.
- Python 3.12 + uv + pydantic + pytest, layered layout으로 확정했다 (ADR-0012).
- 다섯 Stage의 domain/application/adapter와 `mcx` CLI·MCP·plugin 합성 계층이
  구현되었다. Phase 9의 brownfield 진입, worktree 격리, checkpoint, rollback,
  `changed_files`, 진행 관측도 실 AI 도그푸딩으로 검증되었다.
- Mission Control의 Constitution과 설계 문서 초안이 작성되었다.
- upstream `Q00/ouroboros`의 기준 commit을 기록했다.
- 사용자 용어와 내부/upstream 용어 mapping을 확정했다.
- Runtime은 Codex/OpenCode 방향이며 Gemini는 v1 범위에서 제외했다.
- Phase 1~9의 결정은 ADR-0009~0050과 각 Phase 종료 기록에 연결되어 있다.
- 문서 link·navigation·terminology·lifecycle consistency 검사를 포함한 전체
  테스트가 통과한다.
- 사용자가 2026-08-07 세션에서 방향과 v1 boundary를 검토·승인했다
  ([progress 0000](./0000_DOCUMENTATION_FOUNDATION.md) Gate 참조).
- 루트에 에이전트 온보딩 지침 `AGENTS.md`와 `CLAUDE.md` symlink가 추가되었다.

## Documentation status

| 문서 | 상태 | 다음 Gate |
|---|---|---|
| `00_MISSION_CONTROL.md` | Active Draft | 구현 evidence로 검증 (사용자 검토 완료) |
| `01_ARCHITECTURE.md` | Draft | Phase 1~9 경계는 구현 evidence로 검증; Phase 10 세대 루프 경계 갱신 대기 |
| `02_MISSION_LIFECYCLE.md` | Draft | 다섯 Stage 전이는 구현으로 검증; Phase 10의 세대 간 연결과 upstream 내부 국면 대조 대기 |
| `03_RUNTIME.md` | Draft | Codex 실행·Claude/Codex 텍스트 계약 검증; OpenCode 실물 이연, Hermes는 Phase 10 실측 후 결정 |
| `04_MCP.md` | Draft | tool 29종·stdio·job/cancel은 ADR-0041로 검증; worker 재귀 경계와 host 합성 책임은 ADR-0042로 검증 |
| `05_BRIEF.md` | Verified contract | Phase 1 구현으로 검증, §11.6·B-040~043은 ADR-0020 소급 (미착수 행은 progress 0001 참조) |
| `06_BLUEPRINT.md` | Draft | schema·QA·revision·결정적 품질 하한을 Phase 2·8·9에서 검증; Gen 2+ Brief 없는 생성 경로 결정 대기 |
| `07_EXECUTE.md` | Draft | v1 실행·Runtime·worktree·checkpoint 계약을 Phase 3·5·9에서 검증; 병렬 실행은 Phase 11 |
| `08_VERIFY.md` | Draft | 진입·mechanical·semantic·`changed_files`·MISSION COMPLETE 계약을 Phase 4·9에서 검증 |
| `09_RECOVER.md` | Draft | 실패 packet·재시도·rollback 계약을 Phase 4·9에서 검증; spec-gap 자동 분류는 Phase 10 설계 후 재평가 |
| `adr/` | 50 Accepted ADRs | ADR-0001~0050. Phase 9 종료 검토에서 upstream 원문 대조 규칙까지 추가 |
| `research/` | Phase 10 baseline in progress | upstream baseline·도그푸딩 0001~0005·Evolve 선행 조사 보존 |

`Draft`는 빈 placeholder라는 뜻이 아니다. self-contained 설계와 체크리스트가
작성되었지만 사용자가 검토하고 구현 evidence로 검증하기 전이라는 뜻이다.

## Progress records

- [0000 — Documentation Foundation](./0000_DOCUMENTATION_FOUNDATION.md)
- [0001 — Brief Vertical Slice](./0001_BRIEF_VERTICAL_SLICE.md)
- [0002 — Blueprint Vertical Slice](./0002_BLUEPRINT_VERTICAL_SLICE.md)
- [0003 — Execute Vertical Slice](./0003_EXECUTE_VERTICAL_SLICE.md)
- [0004 — Verify·Recover Vertical Slice](./0004_VERIFY_RECOVER_VERTICAL_SLICE.md)
- [0005 — Runtime Adapters 종료 검토](./0005_RUNTIME_ADAPTERS.md)
- [0006 — `mcx` CLI 종료 검토](./0006_MCX_CLI.md)
- [0007 — MCP control surface 종료 검토](./0007_MCP_CONTROL_SURFACE.md)
- [0008 — plugin 합성 계층 종료 검토](./0008_PLUGIN_COMPOSITION_LAYER.md)
- [0009 — 되돌리기·관측 층 종료 검토](./0009_RECOVERY_LAYERS.md)

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
  - [-] 수정 후보 제시와 사용자 채택 절차 → **Phase 7로 확정** (사용자 결정
    2026-08-09): host 에이전트가 QA 지적으로부터 revision 초안을 제안하고
    채택은 사용자 — upstream skill 계층 정렬. CLI 단독 사용의 공백은 수용
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
  (ADR-0024 §6). Phase 5의 실제 강제: 실행은 sandbox 수준
  (`--sandbox workspace-write`), 텍스트 lane은 도구 카탈로그
  (claude `--tools`, ADR-0036 §4). 실행측 도구 단위 allowlist 차단은
  Codex에 표면이 없어 보류 (ADR-0033 §6 표)
- [-] Runtime contract — `ExecutionRuntime` port(backend + execute)와 결정적
  fake. concrete adapter conformance는 Phase 5
- [-] Telemetry — attempt 기록이 provenance 네 항목을 선언 필드로 강제
  (ADR-0023 §3, `test_state.py` 누락 거부). event/report/bundle schema는
  미정 ([Open Questions §9](../research/OPEN_QUESTIONS.md))

### Phase 4 — Verify and Recover — COMPLETE

목표: evidence-driven completion과 bounded correction을 검증한다.

2026-08-08 완료. Gate·evidence·종료 검토는
[progress 0004](./0004_VERIFY_RECOVER_VERTICAL_SLICE.md)에 있다. 검토가 테스트
공백 1건(revision 예산 리셋, 0186450), 문서 충돌 1건(directive 저장 vs 파생),
시한 도래 유예 1건(exit_conditions), 미표시 한계 2건(canonical Stage 저장,
Verify Gate 미검사 조건)을 잡았다.

- [x] mechanical verification — 승인된 `verify_command`의 직접 실행과 증거
  보존, 진입은 Execute Gate `CLEAR` 재확인 (ADR-0026·0028, commit d663c7b,
  `test_verify_flow.py` — 실제 subprocess)
- [x] semantic AC verdict — AC 단위 bool+score+uncertainty+risk, 같은
  revision의 mechanical 증거 위에서만 기록, 재검증이 verdicts를 무효화
  (ADR-0030, commit 153f8d7, `test_verdict.py`·`test_gate.py`). 실제
  평가자는 Phase 5 — v1은 port + 결정적 fake
- [x] failure packet — 저장된 기록에서 결정적 파생(원천 4종 + BLOCKED·STALL
  분류), 파생이므로 저장하지 않음 (ADR-0031 §1~§3, commit 9424b4e,
  `test_packet.py`)
- [x] Recover attempt history/budget — AC당 교정 재시도 2회(revision 리셋),
  실패 증거를 실은 교정(`ExecutionRequest.previous_failure`), 동일 오류 해시
  3회 중단, 예산 소진·BLOCKED·STALL·escalation은 HOLD (ADR-0031 §4~§5,
  `test_recover_service.py`·`test_recover_flow.py` — 실패→교정→재검증→
  MISSION COMPLETE 전체 순환)
- [x] MISSION COMPLETE Gate — ADR-0030 §4 네 조건(두 층 통과·불확신 없음·
  게이밍 의심 없음)으로 `CLEAR — MISSION COMPLETE` 도달 가능. 불확신은
  실패가 아니라 escalation 대기 HOLD (commit 153f8d7,
  `test_verify_flow.py::test_both_layers_reach_mission_complete`)

### Phase 5 — Concrete Runtime adapters

목표: 동일 Core contract를 Codex와 OpenCode에서 실행한다.

- [-] Codex adapter conformance — **ExecutionRuntime adapter 완료**
  (ADR-0033, commit 33fa5ba): 명령 구성·프롬프트 렌더링·thread id·침묵
  timeout·실패 정규화가 stub CLI conformance 13건으로 고정, Core 무변경
  통합 증명 포함. **text backend 완료** (ADR-0034, commits 32a3f17·c1f78db):
  공통 완성 엔진 + 위임 port 7종 전부(semantic 평가자, 질문 생성기, clarity
  채점자, closer·challenger, Blueprint 생성기·QA 채점자) — quality bar는
  upstream 영어 원문으로 교체(ADR-0019 §4 재평가 이행). 실물 스모크 완료
  (RUNTIME findings §8). **다섯 Stage 전부가 실제 AI로 구동 가능하다.**
  실 AI 전체 파이프라인 도그푸딩 완료 (2026-08-08,
  [DOGFOODING_0001](../research/DOGFOODING_0001.md)) — Brief 질문 생성부터
  `CLEAR`(MISSION COMPLETE)까지 codex 47회 호출로 완주, 마찰 4건 등록.
  마찰 4건의 upstream 대조·처분 완료 (2026-08-08, ADR-0035 — 비용·속도
  upstream 동등 이상은 사용자 요구사항): 감사 lane 병렬화, 위임 투영에 후보
  전체 전달, QA에 threshold·궤적 전달(ADR-0019 §3 개정), 고정 필드 프롬프트.
  잔여: Recover 실패 경로 도그푸딩(미발동)
- [x] Claude 텍스트 lane adapter (ADR-0036, 2026-08-08) — 사용자 확정 구조:
  텍스트 lane(질문·채점·감사·생성·QA·semantic 판정)은 Claude, 실행은 Codex.
  `ClaudeCompletion` 엔진(`--json-schema` + `structured_output` 1급 소비,
  도구 카탈로그 봉투, 총시간 600s)과 vendor 중립 프롬프트 클래스
  (`Prompted*`, `CompletionEngine` protocol) — conformance 10건 + 실물
  스모크 3회 (RUNTIME findings §10, semantic 평가자가 read-only 봉투에서
  Grep으로 증거를 세어 인용)
- [-] OpenCode adapter — 조사 완료·구현 이연 (사용자 결정 2026-08-08,
  ADR-0003 범위 note 2). upstream 사용 시점·계약 재료·로컬 1.18.15
  드리프트 후보는 [RUNTIME findings §11](../research/RUNTIME_UPSTREAM_FINDINGS.md).
  **2026-08-09 재정리**: 용도 전제가 틀렸음이 조사로 드러났다 — upstream은
  OpenCode를 Execute 하네스로 배치한다. 사용자 결정은 **Execute backend
  교체 구조는 Phase 6에서 열고, 실물 adapter는 이연**(로컬 모델 성능)
- [-] session/resume/cancel — **Phase 7로 재지정** (사용자 결정 2026-08-09):
  장기 실행 job 계약·취소와 한 묶음. 단발 실행 계약에는 불필요하다는 판단은
  유지되나, 시한이 "OpenCode 실수요"에서 MCP로 앞당겨졌다 (ADR-0033 §6 이연분
  합류)
- [-] local model vs provided agent capability mapping — **OpenCode adapter와
  함께 이연** (실물 대상이 그때 생긴다 — 아래 "실수요 이연" 절)

### Phase 6 — `mcx` CLI — COMPLETE

목표: 다섯 Stage를 동일 application boundary로 조작한다. 표면 계약은
[ADR-0038](../adr/0038-mcx-cli-surface-contract.md).

- [x] `mcx brief` — start/ask/answer/candidate/resolve/assess/audit/approve/
  gate/handoff (tests/unit/cli)
- [x] `mcx blueprint` — generate/qa/revise/approve/gate
- [x] `mcx execute` — next/gate (workspace는 mission record가 나른다)
- [x] `mcx verify` — mechanical/semantic/gate (gate `CLEAR`만 MISSION
  COMPLETE 기록)
- [x] `mcx recover` — plan/dispatch/gate
- [x] mission record + `mcx status` — ADR-0037 구현: 합법 전이 그래프
  (Lifecycle §9 미러 테스트), CLI만 기록, 어긋남은 경고·표시
  (tests/unit/domain/test_mission.py, tests/unit/cli/)
- [x] 실 AI 도그푸딩으로 설치된 CLI 완주 검증 — **도그푸딩 0003 MISSION
  COMPLETE** (2026-08-09, [기록](../research/DOGFOODING_0003.md)): 단축형
  표면·exit code 3종·mission record 전체 전이 그래프(재검증 edge 포함)·
  QA EXHAUSTED→수락·자연 발생 Recover 전부 실물 검증. 도그푸딩이 잡은 결함
  2건(무도구 max-turns 계약, CLI 원인 사슬 삼킴) 수정 완료
- [x] status 박스 — [ADR-0038](../adr/0038-mcx-cli-surface-contract.md) §6.1
  개정 2 (2026-08-09). `cli/journal.py`(append-only JSONL, `start`/`end` 두
  줄 — 짝 없는 `start`가 "진행 중"), `cli/calls.py`(port 호출 **실측** 계수,
  명령 수 근사 아님), `cli/status_view.py`(Gate 재판정으로 로우 상태 파생),
  `cli/status_render.py`(세 화면 + `--full`/`--json`/`--plain`, CJK 폭 계산).
  차단 이유는 Gate `blocking_reasons`·closure 차단 질문의 **원문**이다.
  tests/unit/cli/{test_journal, test_status_render, test_status_box_wiring}
  — 레이아웃 스냅샷·상태 어휘 5종 폐쇄·"명령 수 ≠ 호출 수" 고정. 같은
  작업에서 semantic verdict 일괄 저장을 **유지**로 처분했다
  (OPEN_QUESTIONS §5 — 가시성은 원장이 덮고, 증분 저장은 부분
  `SemanticAssessment`를 만든다)
- [x] Stage→Runtime 라우팅 테이블 + `config.toml`
  ([ADR-0039](../adr/0039-stage-runtime-routing-table.md), 사용자 결정
  2026-08-09) — ADR-0023이 Phase 5에 약속하고 이행하지 않은 항목.
  `cli/routing.py`(닫힌 Stage 키·lane 쌍·3단 해석·fail-fast) +
  `cli/composition.py`(backend 레지스트리, 조회 지점 하나), 14 tests.
  **Execute의 backend 교체가 구조적으로 가능하다** — `EXECUTION_BACKENDS`에
  한 줄 추가가 교체 지점이고, 실물 OpenCode adapter는 이연이라 지금은 그
  이름이 로드에서 거부된다(등록된 이름만 통과)
- [x] Phase 6 종료 검토 — [progress 0006](./0006_MCX_CLI.md)

### Phase 7 — MCP control surface — COMPLETE

목표: host가 CLI와 같은 Mission state/Gate 의미를 사용한다.

**진입 조건 (사용자 결정 2026-08-09): secret redaction Security ADR** —
상태·Telemetry가 host 세션으로 나가기 전에 upstream redaction 계층을
조사해 확정한다 (OPEN_QUESTIONS §9).

2026-08-09 완료. Gate·evidence·종료 검토는
[progress 0007](./0007_MCP_CONTROL_SURFACE.md)에 있다. 검토가 미조립 부품
1건(Recover 비동기 짝 누락 — 고침), 무처분 도과 3건, 미표시 보류 2건, 미등록
이탈 1건을 잡았다.

- [x] read-only Mission query — `mcx_status`·`mcx_*_gate` 등 조회 tool
- [x] Brief mutation — `mcx_brief_*` 10종
- [x] Blueprint approval — `mcx_blueprint_approve` (**승인 actor는 여전히
  기록되지 않는다** — Open Questions §3, Phase 8)
- [x] long-running Execute/Verify/Recover job contract — 셋 전부
  (`mcx_start_execute_next`·`mcx_start_recover_dispatch`·
  `mcx_start_verify_semantic`). Recover 짝은 종료 검토가 잡아 추가했다:
  `recover dispatch`가 `execute next`와 같은 `codex exec`를 돈다
- [-] resume/cancel — **cancel 이행** (마커 + runtime 관측, 실물 프로세스 종료
  테스트). **resume은 Phase 9로 재지정** (ADR-0033 §6 — 되돌리기 층과 같은 자리)
- [-] 수정 후보 제시 — **재료 이행**(`mcx_blueprint_qa` 지적 +
  `mcx_blueprint_revise` 진입점), **제시 행위는 Phase 8**: 없는 것은 tool이
  아니라 "host가 그것을 하라"는 skill 계층 지시다 (ADR-0019 §7)
- [-] HOLD 차단 질문의 AskUser 릴레이 — **데이터 경로 이행**(차단 사유·질문이
  `blocking_reasons`에 원문으로 실린다), **중계는 Phase 8**. 서버가 사람에게
  직접 묻지 않는 결정을 Open Questions §8에 등록했다 (`upstream 미확인`)
- [x] CLI/MCP parity tests — 파리티를 테스트로 쫓지 않는다. 같은 `dispatch`를
  지나므로 구조가 보장하고, 검사는 방향 셋이다 (ADR-0041 §8)
- [x] recursion/security tests — Phase 8에서 실행 lane이
  `codex exec --ignore-user-config`로 사용자 설정을 상속하지 않게 해 재귀 경계를
  강제하고 실물 확인했다 ([ADR-0042 §6](../adr/0042-skill-and-core-ownership-boundary.md))

### Phase 8 — plugin 패키징: 합성 계층 — COMPLETE (사용자 결정 2026-08-09)

목표: host가 Stage 순서를 알고 스스로 이어 붙인다. 지금은 사람이 24개 명령의
순서를 알아야 하며, 도그푸딩 0003은 그 순서를 아는 사람이 60콜을 손으로
이어 붙인 실행이었다.

upstream 배포 실물은 **plugin = skills + MCP server + CLI 3층**이고, 품질
루프와 합성 규칙이 skill 계층에 산다
([CLI findings §2·§3](../research/CLI_UPSTREAM_FINDINGS.md)). 따라서 이
Phase는 manifest 작업이 아니라 **합성 계층 도입**이다 — 2026-08-09 대조에서
"skill 래퍼와 manifest만 얹으면 된다"(Open Questions §8 원문)가 같은 문서
§2의 조사 결과와 충돌함을 확인해 정정했다.

- [x] upstream skills 계층 조사 — 2026-08-09 완료
  ([SKILLS findings](../research/SKILLS_UPSTREAM_FINDINGS.md)). plugin은 3층·
  host 둘(Claude Code·Codex), skill이 capability 계약을 선언하고, QA 루프·
  User Adoption Gate·감사 기록·Core 판정 재감사가 전부 skill 소유다. 취소는
  CLI 직접, 동시 쓰기 재확인은 대응물 없음, 재귀 차단은 미확인
- [x] skill 계층 ADR — 2026-08-09 확정
  ([ADR-0042](../adr/0042-skill-and-core-ownership-boundary.md), Accepted).
  경계 원칙은 *"Core는 한 번의 판정, skill은 몇 번·어떤 순서로 부르고 무엇을
  묻는가"*. 사용자 결정 2건 반영: **재귀 차단**(실행 lane이
  `--ignore-user-config`로 사용자 codex 설정을 상속하지 않고, 모델은
  `config.toml`이 제공하되 없으면 현재 설정을 읽어 채택·기록)과 **Fact
  Resolver 폐기**. 같은 ADR §8이 우리 "upstream보다 강하다" 주장 8건을
  재대조해 3 성립·2 정당화 만료/파생·1 과장 정정으로 처분했다
  **Phase 7 종료 검토가 이 ADR이 답해야 할 항목 5개를 구체적으로 채웠다**
  ([progress 0007](./0007_MCP_CONTROL_SURFACE.md) §3): worker 재귀 경계,
  stale write 재확인의 중계, tool description, QA revision 제시, 승인 actor.
  다섯 전부가 "Core가 재료를 주고 skill이 행위를 한다"의 경계에 걸린다
- [x] **worker 재귀 차단** — `codex exec --ignore-user-config`를 채택·구현하고
  실물 확인했다 ([ADR-0042 §6](../adr/0042-skill-and-core-ownership-boundary.md))
- [x] 결정적 품질 gate — **2026-08-10 확정·구현**
  ([ADR-0043](../adr/0043-deterministic-blueprint-quality-floor.md), Accepted).
  조사가 전제를 좁혔다: upstream의 결정적 층이 실제로 보는 것은 **섹션 단위로
  필수 칸이 채워졌는가**이고(`gap_detector.py`), 그것은 우리 `check_scope`가
  이미 하는 일이다. 따라서 **등급 A/B/C와 점수 사전은 이식하지 않았다** —
  `CLEAR`/`HOLD` + `blocking_reasons`가 이미 같은 일을 하고, 더하면 "왜 못
  가는가"의 답이 두 군데가 된다. 새로 막는 것은 하나다: **확인 수단이 하나도
  없는 Blueprint**(`NO_VERIFIABLE_CRITERION`). `unverifiable_criteria`는 이미
  계산되고 있었으나 **어떤 Gate도 소비하지 않았다** — 전 AC가 확인 수단이
  없으면 mechanical 층이 공허하게 통과하고 `MISSION COMPLETE`가 semantic 판정
  하나에 얹힌다. 이 축은 **upstream 대응물 없는 발명**이며(upstream의
  `testability`는 섹션 단위) 그렇게 표시했다. 위치는 Core — 층 이동이다
  (upstream은 `auto/`). 부분 커버리지는 막지 않고 세어서 드러내는 것으로
  사용자 결정이 확정됐다(ADR-0043 §4)
- [x] skill 작성 + plugin manifest (Claude·Codex 양쪽 MCP 클라이언트) —
  2026-08-09. skill 6종(`mcx` 우산 + Stage 5종), `.claude-plugin/plugin.json`·
  `.codex-plugin/plugin.json`이 **같은 `./skills/`와 같은 `./.mcp.json`**을
  가리킨다(upstream은 server가 runtime 플래그를 받아 둘로 나누지만 우리 라우팅은
  `config.toml` 소유라 나눌 이유가 없다 — 등록된 divergence).
  `tests/unit/skills/test_skill_artifacts.py` 23건이 **skill이 존재하지 않는
  tool·인자를 부르지 못하게** 묶는다 — skill은 산문이라 컴파일되지 않으므로
  이 검사가 유일한 강제다. 실제로 작성 중 오류 3건을 잡았다(QA 액션 어휘를
  upstream 것으로 씀, `revise`의 `--draft-file` 누락, 임계 미달 승인의
  `--accept-below-threshold` 누락)
- [x] 설치·발견·설정 UX ([Open Questions §8](../research/OPEN_QUESTIONS.md)) —
  **2026-08-09 확정·검증.** 발견은 양쪽 매니페스트, 설정은
  `config.toml` 하나. 설치 경로를 [README](../../README.md)에 적었고
  **로컬 체크아웃 경로를 실물로 확인했다**: `uvx --from '<repo>[mcp]' mcx-mcp`가
  wheel 빌드→진입점 실행까지 통과하고(tool 29), `claude mcp add`로 등록하면
  **`✔ Connected`** 다. 포장·extras·진입점이 정상임을 확인했고, plugin은
  `${CLAUDE_PLUGIN_ROOT}`의 설치된 소스에서 직접 MCP 서버를 띄우므로 PyPI 배포를
  요구하지 않는다

### Phase 9 — 실사용 진입: brownfield + 되돌리기 — COMPLETE (사용자 결정 2026-08-09)

목표: 기존 코드베이스에 안전하게 적용한다. Evolve보다 먼저 — 실사용
데이터가 쌓여야 진화 루프가 의미를 갖는다.

> **이 Phase는 구현 Phase가 아니라 관측 Phase에 가깝다** (2026-08-09, Phase 8
> 종료 검토). 아래 목록 외에 **관측이 있어야 결정되는 항목 8개**가 이 Phase로
> 모였다 — stale write 재확인(발동 조건부), host 자기 도구 경로, telemetry
> event 층, spec-gap 분류, `cancelled` attempt 상태, runtime resume, 부분
> 커버리지 처분, setup/config skill 필요 여부. **한 묶음으로 다루지 않으면
> 관측 없이 하나씩 발명하게 된다** ([progress 0008](./0008_PLUGIN_COMPOSITION_LAYER.md) §3).

- [x] brownfield 탐색·기존 제약 등록 (ADR-0011 유예 해제) — **2026-08-09
  조사 완료, 결정 대기** ([BROWNFIELD findings](../research/BROWNFIELD_UPSTREAM_FINDINGS.md),
  [ADR-0044](../adr/0044-brownfield-entry-contract.md) Proposed). 조사가 전제를
  갈랐다: `brownfield`는 **한 기능이 아니라 세 역할**이고 ADR-0011 §6은 그중
  하나만 기록하고 있었다 — ① 모호함 4번째 축(`context_clarity`, weight 0.15,
  floor 0.60), ② 저장소 레지스트리(홈 스캔 + 기본 repo, SQLite), ③ mechanical
  명령 자동 검출(`.ouroboros/mechanical.toml`). 제안: ②는 **미도입**(우리 CLI는
  mission당 workspace 하나), ③은 **도입**하되 축을 AC 수준으로 바꾼다,
  ①은 **순서 제약** 때문에 ③ 뒤 관측 후 결정. **①을 혼자 켜면 brownfield
  미션이 Gate에서 영원히 막힌다** — 자리가 예약돼 있어 값싸 보이는 것이 함정이다.
  **2026-08-09 사용자 승인 → ADR-0044 Accepted, ③ 구현 완료** (800 tests):
  `domain/mechanical.py`(순수 판정 — 이 명령이 성립하려면 무엇이 있어야 하는가),
  `adapters/verification/entry_points.py`(디스크 대조 — package.json scripts·
  Makefile target·PATH), `adapters/text/mechanical_detector.py`(여덟 번째 위임
  port). **제안 타입과 검증된 타입을 나눠 검증을 건너뛸 수 없게 했다** —
  `ProposedCommands`를 그대로 쓰면 이름이 그 사실을 드러낸다. 버린 제안은
  이유와 함께 남는다(조용한 누락 금지). **배선 완료** — 검출 결과가
  `BlueprintGenerationRequest.context`로 흘러 생성기가 AC의 확인 명령을 쓸 때
  쓴다. 이것이 오래된 한계 *"`context`를 채우는 장치가 없다"*(B-004)를 닫는
  자리다. 검출은 `generate`가 미션당 한 번이므로 **한 번**이며, upstream이
  `mechanical.toml` 파일로 얻는 idempotency를 우리는 호출 지점 하나로 얻어
  캐시 파일이 없다 (ADR-0044 미결 해소)
- [x] worktree 격리 — **2026-08-09 완료**
  ([WORKTREE findings](../research/WORKTREE_UPSTREAM_FINDINGS.md),
  [ADR-0045](../adr/0045-worktree-isolation-contract.md) Accepted, 844 tests).
  격리 단위는 **미션 하나**다 — upstream은 병렬 AC 실행기를 가지고도 AC마다
  만들지 않는다. 브랜치 `mcx/<mission_id>`, 자리
  `<state-dir>/worktrees/<repo>/<mission_id>`.
  **경로를 저장하지 않고 유도한다** — upstream `TaskWorkspace`(8필드) 직렬화·복원
  계층이 우리에겐 없고, *"이 시도가 어디서 돌았는가"* 는 `ExecutionAttempt`의
  envelope가 이미 들고 있다 (ADR-0045 §2). **Verify는 배선 없이 따라온다** —
  `verify_service`가 그 envelope를 읽으므로(테스트로 고정), upstream이
  `verification_working_dir`로 명시하는 것을 우리는 기록으로 얻는다.
  새로 만들 때만 clean checkout을 요구하고(HEAD에서 분기하므로 커밋되지 않은
  변경은 따라오지 않는다), git 저장소가 아니면 격리 없이 그대로 간다.
  **되돌려 합치지 않으므로 위치 표시가 계약의 일부다** — `execute next`가
  경로·브랜치를 내고 `status`가 조회 지점을 준다(upstream 대응물 없음: 그쪽은
  한 프로세스가 떠 있어 시작 출력이면 충분하다). lock은 pid 생존만 보고 시간
  staleness는 버렸다. **정리는 별도 명령 `mcx cleanup`** (사용자 결정
  2026-08-09 — 초안의 "지우지 않는다"를 뒤집었다): 병합됐고 깨끗한 것만
  치우고 `running`·`dirty`는 `--force`로도 남으며, `--force`가 치운 것의
  브랜치는 남는다(작업이 사라지지 않는다). **자동 병합은 같은 자리에서
  기각됐다** — 검증 통과와 사용자 수용은 다른 판단이다 (ADR-0042 §5).
  `cleanup`은 mission에 속하지 않는 유일한 명령이라 MCP 표면에 올리지 않으며,
  이것이 ADR-0041 §1 1:1 규칙의 **유일한 예외**임을 테스트가 고정한다
- [x] AC별 checkpoint 커밋 — **2026-08-10 완료**
  ([CHECKPOINT findings](../research/CHECKPOINT_UPSTREAM_FINDINGS.md),
  [ADR-0046](../adr/0046-verified-checkpoint-commits.md) Accepted, 867 tests).
  **조사가 항목 이름을 정정했다**: upstream의 호출 지점은 실행 뒤가 아니라
  **평가 이후 하나뿐**이고 조건은 `authoritative_pass`(통과 + 권위 있는 판정)다.
  그리고 *"AC별"* 은 분할이 아니라 **라벨**이다 — upstream도 AC의 파일 목록을
  계산하지 않고 그 시점의 작업 트리 전체를 스테이징한다. 우리도 같게 하되,
  무엇이 입증인가는 **Verify Gate와 같은 함수**가 정한다
  (`_criterion_blockers`를 분리해 Gate와 `proven_criteria`가 공유 — 두 벌로
  쓰면 커밋된 것과 Gate가 인정한 것이 갈린다. `CLEAR ⟺ 전부 입증`을 테스트가
  고정한다). 비밀 경로(`.env`·`*secret*`·`*credential*`)는 스테이징에서 빼고
  `git commit -- <safe>`로 경로를 명시한다. **멱등성은 git에서 나온다** —
  커밋 후 트리가 깨끗하므로 상태를 만들지 않는다(ADR-0045 §2와 같은 판단).
  정책 스위치는 만들지 않았다: upstream이 `none` 기본값으로 막는 위험(사용자
  checkout 오염)을 ADR-0045가 **구조로** 막았다
- [x] rollback 범위 — **2026-08-10 완료**
  ([ROLLBACK findings](../research/ROLLBACK_UPSTREAM_FINDINGS.md),
  [ADR-0047](../adr/0047-rollback-to-the-last-proven-point.md) Accepted,
  878 tests). **조사가 ADR-0032의 근거 포인터를 정정했다** — `core/worktree.py`에
  되돌리기는 없고, 파일 되돌리기는 Core가 아니라 `scripts/ralph.sh`에 있다.
  범위는 **마지막 입증 지점**이고 시점은 **재투입 직전**이다(잔해 위에서
  재시도하면 실패 원인이 새 시도의 것인지 이전 찌꺼기인지 섞인다). 태그는
  도입하지 않았다(사용자 결정) — 브랜치의 커밋이 checkpoint뿐이라 **HEAD가 곧
  upstream의 "직전 성공 세대 태그"** 이고, 세대가 없는 v1에는 고를 지점이 없다.
  `reset --hard`가 아니라 upstream 세 걸음(`checkout HEAD -- .`·`reset HEAD`·
  `clean -fd`, `-x` 없음)이라 커밋 이력과 `.gitignore` 대상이 남는다.
  **dirty 가드는 이식하지 않았다** — 옮기면 실패 후 worktree가 늘 dirty라
  영원히 발동하지 않으며, 그 가드가 지키려던 것(사용자 미커밋 변경 보호)을
  격리(0045)와 checkpoint(0046)가 이미 지킨다. **둘 중 하나가 무너지면 이
  divergence의 근거가 사라진다**
- [x] `changed_files` 수집 — **2026-08-10 완료**
  ([CHANGED_FILES findings](../research/CHANGED_FILES_UPSTREAM_FINDINGS.md),
  [ADR-0048](../adr/0048-changed-files-collection.md) Accepted, 892 tests).
  **보류의 실질 이유는 비교 기준점 부재였고** checkpoint·rollback이 그것을
  만들었다 — 기준선 HEAD가 곧 마지막 입증 지점이라 목록이 **rollback이 지울
  집합과 같다**. 수집은 **검증 명령 실행 전**이다: 뒤로 미루면 명령이 만든
  캐시가 섞이고, checkpoint 뒤면 트리가 깨끗해 **언제나 빈 목록**이 된다.
  rename은 두 경로 모두 싣는다(staging용 파서와 다르며 upstream도 파서가 둘).
  **빈 목록과 수집 실패를 구분한다** — 뭉치면 "관찰 못 함"이 "변경 없음"으로
  읽힌다. `--stat`·원문 보존·평가자 전달은 미도입(등록된 divergence):
  upstream이 그것을 두는 이유는 QA가 workspace를 관찰할 수 없기 때문이고
  우리 평가자는 직접 관찰한다 (ADR-0034 정정)
- [x] **canonical event 층 + 스트리밍 생산자** — **항목이 두 층을 하나의 이름으로
  가리고 있었다** (2026-08-10 완료,
  [ADR-0049](../adr/0049-runtime-progress-observation.md) Accepted,
  [EVENT_LAYER findings](../research/EVENT_LAYER_UPSTREAM_FINDINGS.md), 936 tests).
  **적은 근거 둘 중 하나는 이미 소멸했다** — `changed_files`는 ADR-0048이
  `git status`로 끝냈고 event를 한 줄도 쓰지 않았다. 조사가 나머지도 뒤집었다:
  **upstream에서 진행 표시는 event 층의 소비자가 아니다**(`leaf_dispatcher.py:549`
  — 콘솔 출력이 store를 읽지 않고 같은 루프에서 정규화 결과를 직접 찍는다).
  event store를 읽는 넷 중 셋(TUI·auto listeners·replay/resume)이 우리에게 없고,
  넷째인 job 상태는 ADR-0041이 이미 **원장에서 유도**한다 — 지금 도입하면 그 ADR이
  기각한 "같은 사실의 두 번째 저장소"가 된다(등록된 divergence).
  **한 것**: 정규화 층(`RuntimeActivity` — 두 번째 Runtime을 흡수할 자리),
  codex JSONL 파서(`item.started`만 — 우리 질문은 "지금 무엇을 하는가"),
  원장이 비워 둔 칸을 채우는 **진행 꼬리**(`progress_<mission>_<seq>.jsonl`,
  MCP job이 `running` 너머를 답한다), 취소와 같은 **ambient 관측**(설치되지 않으면
  파싱조차 하지 않는다). 마스킹은 **생성 시점**이다 — detail이 도구 입력에서
  오므로 새 저장 표면이다 (ADR-0040 §3).
  **stall 판정은 바꾸지 않았다** — upstream은 도구 호출을 liveness로 보지만
  오탐이 곧 돌고 있는 프로세스를 죽이는 것이라 관측 없이 조일 일이 아니다
  (미결, 시한 Phase 10 진입 시)
- [x] ~~**spec-gap 분류와 `RecoveryDirective`**~~ — **항목 자체가 오류였다.
  Phase 9에서 제거하고 Phase 10 진입 시 재평가로 옮긴다 (2026-08-10 사용자
  질문이 잡았다).** 두 가지가 틀렸다:
  **(1) `RecoveryDirective`는 이미 v1 미채택 확정이다** —
  [Recover Guide](../09_RECOVER.md) §3이 2026-08-08에 확정했고(파생본을 저장하면
  두 진실이 생긴다, [ADR-0031](../adr/0031-recover-v1-failure-and-retry-contract.md) §1)
  2026-08-09 재평가에서도 결론 무변경이었다. **이미 내려진 결정을 할 일로 다시
  적은 것**이며, Phase 8 종료 검토가 등록할 때 그 확정을 확인하지 않았다.
  **(2) spec-gap 분류는 upstream이 다른 층에서 이미 푼다** — upstream에 분류
  축이 없는 것은 맞지만(전수 확인), 그 자리를 **세대 루프**가 채운다. 실패하면
  rollback하고 다음 세대가 seed를 다시 쓴다
  (`evolution/reflect.py`: *"Interview is Gen 1 only; Reflect handles all
  subsequent generations autonomously"*). 우리에겐 그 루프가 없으므로(Phase 10)
  **지금 만들면 아직 오지 않은 층의 일을 다른 방식으로 발명**하게 된다.
  막아야 할 것은 이미 막고 있다 — 재시도가 답이 아닌 실패는 Recover Gate가
  `HOLD`로 세우고 사용자에게 넘긴다. 없는 것은 자동 route뿐이고 그것은 Stage를
  자동으로 되돌리는 동작이라 더 위험하다. **Phase 10에서 Evolve가 HOLD를 어떻게
  소비하는지 정해질 때 필요 여부가 함께 정해진다**
- [x] **secret redaction 정책의 실물 재대조** (2026-08-10 완료,
  [REDACTION_FIELD_TRIAL](../research/REDACTION_FIELD_TRIAL.md), 907 tests).
  **정책은 옳았고 구현이 정책에 못 미쳤다** — 발견된 4종은 ADR-0040이
  감수하기로 한 "라벨 없는 미등록 형태"가 아니라 **라벨이 가장 분명한**
  형태였다: `\b`가 언더스코어에서 성립하지 않아 `DB_PASSWORD=`·
  `SUPABASE_API_KEY=`가 통과했고, 이름과 `:` 사이 따옴표 때문에
  **JSON이 통째로** 샜다(`{"api_key": "…"}` — MCP payload의 기본 형태).
  upstream에는 이 문제가 없다: 필드명을 경계 없이 **부분 문자열 포함**으로
  본다(`core/security.py:463`). **과잉 마스킹은 실제 명령 출력 5종에서
  관측 0건.** 맨몸 64자 16진·40자 base64는 의도적으로 남긴다 — sha256·git
  SHA의 형태이며 지우면 정상 출력이 망가진다. ADR-0040 Verification을
  형태 목록으로 교체했다

#### 도그푸딩 0004 — Brief에서 중단, 결함 1건 처분 (2026-08-10)

- [x] **도그푸딩 0004 수행** — 목표는 Phase 9 네 층의 실물 검증이었으나
  **Brief 단계에서 중단**했다 ([DOGFOODING_0004](../research/DOGFOODING_0004.md),
  claude 69콜 / 105명령 / 30분). 과제를 인코딩·파일명 축으로 잡은 것이
  선정 오류였다 — 0003이 "파서류는 감사 라운드가 자란다"를 기록했는데 그것을
  알고도 골랐다. `brief audit`이 시간의 80%
- [x] **Brief Gate가 빈 handoff에 `CLEAR`를 준다** — 처분 완료
  ([ADR-0050](../adr/0050-requirement-candidate-provenance.md) Accepted,
  952 tests). 원인은 **두 divergence의 교집합**이다: 후보를 upstream은
  파생하는데 우리는 수동 명령으로 받고, 전사를 upstream은 생성기에 넘기는데
  우리는 끊는다(ADR-0016·0018). 각각은 무해하나 둘 다 끊으면 생성기가 받는
  것이 의도 82자뿐이다. **승격 0건 미검사 자체는 upstream 파리티**이며
  upstream은 전사 backstop이 있어 필요가 없다. 처분: 파생 이식 + 수동 경로
  유지(실측 1/21로 파생만으론 부족) + Gate가 승격된 성공 조건 요구
  (Guide §13.1이 이미 요구하던 것 — 구현이 계약보다 얇았다)
- [x] **도그푸딩 0005 — Phase 9 다섯 층 전부 실물 검증** (2026-08-10 완료,
  [DOGFOODING_0005](../research/DOGFOODING_0005.md)). 격리·진행 표시·
  `changed_files`·checkpoint·rollback 전부 관측됐다. checkpoint 라벨에 AC 7개 중
  **입증된 6개만** 실린 것이 `proven_criteria`와 Gate가 같은 판정을 쓴다는
  실물 증거다. **과제 축이 0004의 원인이었음도 고정됐다** — 같은 도구로
  `brief audit`이 15회/24분 → **4회/6분**
- [x] **과잉 마스킹 실사용 관측 → 수정** (957 tests). JWT 형태가
  `unittest.defaultTestLoader.loadTestsFromModule`을 통째로 지웠다. 패턴은
  upstream과 자간까지 같고 **거는 자리가 다르다**(upstream은 필드 값, 우리는
  산문) — REDACTION_FIELD_TRIAL과 같은 구조의 divergence다. 라벨 없는 층에만
  `eyJ` 접두사를 요구한다. **그 문서의 "과잉 0건"은 측정 범위가 좁았던
  것**이며 실사용이 드러냈다
- [x] **QA 예산 소진 후 `revise`하면 영원히 승인할 수 없다** — 처분 완료
  ([ADR-0019 §6.1](../adr/0019-blueprint-qa-loop.md) 개정, 964 tests).
  **우리가 upstream 규칙의 절반만 이식한 것이 원인이었다** — upstream은 상한과
  *"one final manual edit + 재채점 없이 임계 미달 수락"* 을 한 문장에 함께
  두는데(`skills/seed/SKILL.md:113`), 우리는 상한만 코드로 옮기고 탈출구를
  산문에 두고 왔다. 물려받은 점수가 어느 revision의 것인지는
  `qa_scored_revision`이 기록해 §8이 지키는 질문을 보존한다.
  **도그푸딩 0005가 이어서 `MISSION COMPLETE`로 완주했다** (1시간 5분,
  claude 41 + codex 15콜)
- [x] **checkpoint 경로 파서가 첫 항목을 한 글자 잘랐다** — 수정 완료
  ([DOGFOODING_0005](../research/DOGFOODING_0005.md) §7). `_output`의
  `strip()`이 porcelain의 선행 공백(`" M"`)을 지워 `__pycache__` →
  `_pycache__`가 됐다. **ADR-0046 §3이 "두 번째 라운드부터 증분"이라고 적은
  바로 그 지점에서만 발동**했고 테스트가 untracked만 덮어 새어나갔다.
  `changes.py`의 파서는 strip 없이 넘겨 무사했다
- [x] ~~QA 데드락 미처분~~ (이전 기술, 위에서 처분됨
  [DOGFOODING_0005](../research/DOGFOODING_0005.md) §4). 예산은 mission 단위
  누적(ADR-0019 §6)인데 승인은 현재 revision의 QA 평가를 요구한다(§8) —
  소진 뒤 "명세가 틀렸으니 고치자"를 하면 미션이 잠긴다.
  **upstream엔 없다**: upstream QA는 `iteration`을 호출자가 넘기는
  파라미터로 받아 예산이 상태가 아니다. 처분 후보 셋 다 ADR-0019 계약을
  건드리므로 **ADR이 먼저다**

### Phase 10 — Reflect/Evolve: 자가개선 루프 — IN PROGRESS (사용자 결정 2026-08-09)

목표: **미션이 배운 것을 다음 미션의 스펙으로 자동 전환한다.** 사용자 지시는
"도입 여부 조사"가 아니라 **확실하게 구성**이다 — Hermes 사용 방식과 자가개선
결과가 다음 작업에 연결되는 경로를 깊이 파악해 반영한다.

upstream 실물 (2026-08-09 확인, Evidence: **Verified** — 소스):

- `reflect`는 닫힌 stage 어휘 4개 중 하나이고 지정된 하네스는 **Hermes**
  (`orchestrator_stage.py:1-20` — interview=Codex, execute=OpenCode/OMX,
  evaluate=Claude Code, reflect=Hermes).
- **WonderEngine** (`evolution/wonder.py`): *"What do we still not know?"* —
  현재 ontology·평가 결과·실행 산출물을 검사해 빈틈·긴장·미답 질문을 찾는다.
- **ReflectEngine** (`evolution/reflect.py`): 실행 결과 + ontology + wonder
  출력 → **다음 Seed의 개선된 AC와 ontology 변형**. 모듈 docstring:
  *"This is where the Ouroboros eats its tail"*, 그리고 **"Interview is Gen 1
  only; Reflect handles all subsequent generations autonomously."**
- Hermes는 upstream 정식 backend다 (`config/models.py`의
  `VALID_RUNTIME_BACKENDS`에 `hermes`/`hermes_cli`, `hermes_cli_path` 설정
  필드). 로컬 실물도 있다 (`~/.local/bin/hermes`) — 실 검증이 가능하다.

- [ ] Hermes를 reflect 단계에서 **어떻게 쓰는지** 깊이 조사 — 호출 계약,
  프롬프트, 출력 스키마, 다른 backend와 다른 점.
  **2026-08-10 정정**: 앞 문단의 *"지정된 하네스는 Hermes"* 는 과했다 —
  `orchestrator_stage.py`의 4단계 배치는 **아키텍처 문서의 의도**이고 코드는
  3단 fallback이라 설정이 없으면 Hermes로 가지 않는다
  (`stages.get(stage) or profile.default or orchestrator.runtime_backend`).
  즉 우리 [ADR-0039](../adr/0039-stage-runtime-routing-table.md) 라우팅
  테이블과 같은 물건이며 새 층이 아니다.
  **사용자 결정 2026-08-10: 고정 여부는 Phase 10에서 실측 후 확정.**
  진입 조건 — Wonder/Reflect를 **Hermes와 Claude로 각각 1회** 돌려 출력 품질·
  비용·지연을 대조한다. 우리가 vendor를 고정한 두 번(텍스트=Claude,
  실행=Codex)은 전부 도그푸딩 실측 뒤였고 Hermes는 실측이 0회다. 기다리는
  비용은 0이다(라우팅 테이블이 이미 있어 나중 고정은 설정 한 줄).
  배포 관점도 함께 본다 — Hermes는 별도 설치물이라 필수로 만들면 설치
  의존이 claude+codex+hermes 셋이 된다
- [ ] **자가개선 결과가 다음 작업에 연결되는 경로** 조사 —
  `evolution/loop.py`, `projector.py`, `parent_seed_id` lineage,
  `evolve_step` MCP tool. "무엇이 다음 세대의 입력이 되는가"의 전체 경로
- [x] **Reflect가 무엇을 대체하는지 조사 — 2026-08-10 완료**
  ([EVOLVE findings](../research/EVOLVE_UPSTREAM_FINDINGS.md)). 답: **Brief를
  대체한다** (Blueprint가 아니다). Seed는 양쪽 세대에 다 있고 바뀌는 것은
  **입력을 만드는 단계**다. Gen 2+에는 **모호함 채점이 돌지 않고**
  (`ambiguity_score`·`interview_id`가 부모 것 그대로), goal·constraints·AC만
  진화하며 판정 원칙과 종료 조건은 상속된다. AC는 **설명 문장만** 바뀌고
  기계적 확인 계약은 **위치로** 이어지며, 설명이 바뀌면 semantic key를 새로
  발급한다. 모호한 삭제·재정렬은 거부하고 `ACPatch`에 `delete`가 없다.
  **핵심 결론: `BlueprintService.generate`가 승인된 Brief handoff를 요구하므로
  Gen 2+에는 생성 경로가 없다 — 계층 경계 문제이며 Phase 10 설계 ADR의 1번
  항목이다**
- [ ] Wonder/Reflect 출력의 mcx 대응물 설계 ADR — 위 조사를 근거로. 결정할 것
  넷: (1) Brief 없는 Blueprint 생성 경로, (2) `revise`의 두 번째(자동) 생산자,
  (3) Gen 2+의 승인 주체(upstream은 자율, 우리는 사람+QA 근거 필수 — ADR-0021),
  (4) AC 식별 모델 차이(우리는 내용 식별 ADR-0017, upstream은 위치로 권위 이관)
- [ ] 구현 + Hermes adapter (필요 시 — 텍스트 lane 축이므로 `CompletionEngine`
  추가로 끝날 수 있다)
- [ ] **spec-gap 분류 필요 여부 재평가** (Phase 9에서 이관, 2026-08-10). 두
  갈래다: upstream처럼 루프가 매 세대 스펙을 다시 만들면 분류는 **불필요**하고,
  루프가 `HOLD`를 읽어 스펙 문제일 때만 Brief로 가면 **필요**하다. 어느 쪽인지는
  Evolve 설계가 정한다 — 지금 만들면 두 번째를 근거 없이 확정하는 것이다

### Phase 11 — 병렬 실행

목표: 여러 AC를 동시에 실행한다.

- [ ] 병렬 실행 도입 Gate ([Execute Guide](../07_EXECUTE.md) §17,
  [Open Questions §4](../research/OPEN_QUESTIONS.md))
- [ ] `REDISPATCH_ALT_HARNESS` 재평가 (ADR-0032 보류 — 다중 runtime 실물이
  생긴 뒤)

### 실수요 이연 — OpenCode adapter (사용자 판단 2026-08-09)

**구조는 Phase 6에서 열리고, 실물 구현만 이연한다.** ADR-0039 라우팅
테이블이 `[stages.execute] execution = "opencode"`를 표현할 수 있게 만들고,
backend 레지스트리는 등록된 adapter에 대해 열려 있다. adapter를 추가하면
설정 값이 유효해지고 기존 코드는 바뀌지 않는다 — 되돌리기 싼 항목이라
조건부 이연이 정당한 경우다.

이연 사유: 로컬 모델 성능이 실 하네스를 돌려 검증할 수준이 아니다
(사용자 판단). 발동 조건: 그 수준에 도달하거나 Codex와 비교할 실수요가 생길 때.

함께 이연: local model vs provided agent capability mapping (실물 대상이 그때
생긴다).

**용도 정정 (2026-08-09).** 2026-08-08에 기록된 "OpenCode의 용도는 종반의
병렬 부수 작업"은 upstream 사실이 아니라 그 시점의 사용자 의도였다. upstream
아키텍처는 OpenCode를 **Execute 하네스**로 배치한다
(`orchestrator_stage.py:6`). 사용자 결정은 upstream 방향 채택 — Execute의
backend를 codex/opencode로 갈아끼우는 구조다.

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

Phase 4 첫 slice 계약은 2026-08-08 고정되었다
([VERIFY_UPSTREAM_FINDINGS](../research/VERIFY_UPSTREAM_FINDINGS.md),
[ADR-0028](../adr/0028-verify-v1-mechanical-contract.md) mechanical 계약,
[ADR-0029](../adr/0029-verify-deliberate-divergences.md) 등록부) — 실행
주체는 Verify이고 worker 보고는 증거가 아니며, v1이 실행하는 명령은 승인된
Blueprint의 `verify_command`뿐이고, 증거 필드(`VerificationRun`/
`VerificationEvidence`)가 확정되었다.

Verify 첫 vertical slice는 2026-08-08 구현되었다 (commit d663c7b, 440 tests).
승인된 Blueprint의 `verify_command`가 실제 subprocess로 실행되고, 증거가 파일
보존 + 참조로 남으며, mechanical이 전부 통과해도 semantic 부재가 Gate에
blocker로 드러난다. 실행 attempt의 성공 주장은 어느 경로로도 증거가 되지
않는다.

semantic 층 계약은 2026-08-08 고정되었다
([VERIFY_UPSTREAM_FINDINGS §6~§7](../research/VERIFY_UPSTREAM_FINDINGS.md),
[ADR-0030](../adr/0030-verify-semantic-verdict-contract.md)) — verdict는 AC
단위 `satisfied`(bool) + `score` + `uncertainty` + `reward_hacking_risk`,
임계 셋(0.8/0.3/0.7)은 upstream 채택, consensus는 미도입(escalation은 HOLD).

semantic slice는 2026-08-08 구현되었다 (commit 153f8d7, 458 tests) — verdict가
같은 revision의 mechanical 증거 위에서만 기록되고, 재검증이 기존 verdicts를
무효화하며, Gate가 ADR-0030 §4의 네 조건으로 `CLEAR — MISSION COMPLETE`에
처음 도달했다 (결정적 fake 평가자 기준). Brief → Blueprint → Execute →
Verify 네 Stage가 파일 저장소를 거쳐 end-to-end로 이어진다.

Recover 첫 slice 계약은 2026-08-08 고정되었다
([REPAIR_UPSTREAM_FINDINGS](../research/REPAIR_UPSTREAM_FINDINGS.md),
[ADR-0031](../adr/0031-recover-v1-failure-and-retry-contract.md)·
[ADR-0032](../adr/0032-recover-deliberate-divergences.md)) — 실패 packet은
원천 4종 + 결정적 분류(BLOCKED·STALL), 재시도 예산은 AC당 2회(revision
리셋), 재시도는 실패 증거를 가지고 가며(마지막 시도엔 접근 전환 지시), 동일
오류 해시 3회면 중단한다. 전부 upstream 값 채택이다. ADR-0025의 마지막
미확인(실패 증거 전달)도 이 조사로 해소되었다.

Recover 첫 slice는 2026-08-08 구현되었다 (commit 9424b4e, 482 tests) — 실패
packet이 기록에서 결정적으로 파생되고, 교정 재시도가 실패 증거를 가지고 가며
(마지막 예산엔 접근 전환 신호), 예산·동일 오류·BLOCKED가 재시도를 중단한다.
**다섯 Stage 전부가 파일 저장소를 거쳐 이어진다** — 실패 → 교정 → 재검증 →
`MISSION COMPLETE`의 전체 순환이 실제 명령으로 검증되었다.

Phase 4는 2026-08-08 완료되었다
([progress 0004](./0004_VERIFY_RECOVER_VERTICAL_SLICE.md) — 종료 검토와
Gate·Test Matrix 전수 대조 포함). Brief → Blueprint → Execute → Verify →
Recover 다섯 Stage 전부가 파일 저장소를 거쳐 이어지고, 실패 → 교정 → 재검증 →
`MISSION COMPLETE`의 전체 순환이 실제 명령으로 검증되었다.

Phase 5 첫 결정은 2026-08-08 닫혔다
([RUNTIME_UPSTREAM_FINDINGS](../research/RUNTIME_UPSTREAM_FINDINGS.md),
[ADR-0033](../adr/0033-first-runtime-adapter-contract.md)) — port 분리는
upstream(LLMAdapter/AgentRuntime)과 일치 확정, 첫 adapter는 **Codex
ExecutionRuntime**(`codex exec` 단발, 프롬프트 stdin, sandbox 권한 —
bypass 경로 없음, 침묵 900초 timeout, adapter 자체 재시도 없음), 스트리밍·
resume·cancel·도구 단위 차단은 보류 등록.

Codex ExecutionRuntime adapter는 2026-08-08 구현되었다 (commit 33fa5ba,
496 tests) — 명령 구성·프롬프트·thread id·침묵 timeout·실패 정규화가 stub
CLI conformance로 고정되었고, Core 변경 없이 fake 자리에 끼워짐이 통합
테스트로 증명되었다. **실물 codex CLI 스모크(실제 AI 실행·비용 발생)는
사용자 승인 후 수행한다.**

Codex text backend는 2026-08-08 시작되었다 (ADR-0034, commit 32a3f17) —
공통 완성 엔진(`--output-schema` strict, 읽기 전용 sandbox, transient만
재시도)과 첫 port(semantic 평가자)가 stub conformance 11건으로 고정되었다.

실물 codex 스모크는 2026-08-08 사용자 승인 하에 완료되었다
([RUNTIME_UPSTREAM_FINDINGS §8](../research/RUNTIME_UPSTREAM_FINDINGS.md) —
Verified by execution). 가정 대부분이 사실로 확인되었고(thread id, strict
schema 왕복, `-C` 경계), 불일치 2건이 발견·정정되었다 — `--full-auto` 부재
(→ `--sandbox workspace-write`), semantic 요청의 workspace 부재(평가자가
엉뚱한 디렉토리를 검사 — 필수 필드로 추가). 정정 후 재실행에서 평가자가
workspace 안에서 검증 명령을 직접 재현하고 확신 있는 판정을 반환했다 —
**semantic 판정 품질의 첫 실물 관측이다.**

위임 port 7종의 Codex adapter는 2026-08-08 완료되었다 (commit c1f78db,
518 tests) — 다섯 Stage 전부가 실제 AI로 구동 가능하다. quality bar는
upstream 영어 원문으로 교체되었다 (ADR-0019 §4 재평가 이행).

실 AI 전체 파이프라인 도그푸딩은 2026-08-08 사용자 승인 하에 완료되었다
([DOGFOODING_0001](../research/DOGFOODING_0001.md) — Verified by execution).
미션 `dogfood-0001`(wordfreq CLI)이 Brief 질문 생성부터 Verify Gate
`CLEAR`(MISSION COMPLETE)까지 실제 codex 47회 호출로 완주했고, 산출물은
수동 spot check에서도 계약대로 동작했다. closure 감사의 HIGH 차단 4건은
전부 material했고 5순환에 READY로 수렴했으며, Blueprint 생성기는 제약
11개를 원문 그대로 보존했고 AC 기대 출력이 수동 검산과 일치했다. 마찰
4건(감사 입력 투영의 확정 후보 배제, 폐기 후보의 영구 잔존, QA 기각 사유
채널 부재로 인한 점수 정체 — 상한 소진·임계 미달 수락으로 출구, verbatim
잠금 필드에 대한 QA 제안)은 고치지 않고
[Open Questions §2·§3](../research/OPEN_QUESTIONS.md)에 등록했다 — 처분은
upstream 대조 후에 정한다. Recover는 전 AC 1회 통과로 미발동이라 실패
경로의 실물 관측이 남아 있다.

도그푸딩 마찰 4건의 upstream 대조·처분은 2026-08-08 완료되었다
([ADR-0035](../adr/0035-dogfooding-cost-parity-dispositions.md) — 대조표
포함, 520 tests). **비용·속도는 upstream 동등 이상**이 사용자 요구사항으로
확정되었다. 대조 결과 호출 수는 전 구간 upstream 동등 이하였고, 이탈 두
곳을 upstream 정렬로 수정했다 — closure 감사 3-lane 병렬화(wall-clock
순환당 2~4분 → 최장 lane 1개), 위임 투영에 후보 전체 전달(낭비 2순환
≈ 12호출의 원인 제거). QA에는 upstream과 같이 threshold와 반복 궤적을
전달한다 (ADR-0019 §3 개정). 기각 사유 채널과 후보 폐기 상태는 upstream에도
없어 발명하지 않았다.

Claude 텍스트 lane은 2026-08-08 완료되었다 (ADR-0036, 530 tests).
조사(RUNTIME findings §10)에서 upstream `claude_code_adapter.py`의 CLI
전송·도구 봉투·격리 플래그를 확인했고, upstream이 우회하던 스키마 강제가
로컬 claude CLI 2.1.226에서 `--json-schema` + envelope `structured_output`
필드로 1급 지원됨을 실물 스모크로 확인했다 (prose 재질의 불채택 — 등록된
divergence). 프롬프트 클래스 7종은 vendor 중립(`Prompted*`)으로 개명되어
`CompletionEngine` protocol만 요구한다 — 같은 프롬프트 한 벌이 Codex와
Claude 양쪽 엔진에서 돈다 (upstream의 persona/LLMAdapter 분리 정렬).

혼합 vendor 도그푸딩 0002는 2026-08-08 사용자 승인 하에 완료되었다
([DOGFOODING_0002](../research/DOGFOODING_0002.md) — Verified by execution,
48호출). 사용자 확정 구조(claude 텍스트 + codex 실행)로 미션
`dogfood-0002`(dedupe CLI)가 `CLEAR — MISSION COMPLETE`까지 완주했고,
**Recover 실패→교정→재검증 경로가 처음 실물로 돌았다** (투명한 결함 주입
— missing artifact → packet 파생 → 실패 증거 실은 교정 → 재검증 통과).
ADR-0035 효과 실측: 감사 wall-clock 1/2~1/3, 확정 사안 재차단 0건, QA가
0.72→0.87→0.90으로 **실 AI 첫 PASS** (0001은 역행·소진 출구). 미관측
잔여: 재시도 예산 소진·change_approach·동일 오류 해시 중단·BLOCKED/STALL
분류 (교정 1회 성공).

Phase 5 종료 검토는 2026-08-08 수행되었다
([progress 0005](./0005_RUNTIME_ADAPTERS.md)). 검토가 낡은 약속 1건(도구
차단 시점), 근거 미인용 1건(무도구 max-turns의 upstream pairing), 미표시
보류 1건(mechanical 명령의 workspace 밖 부작용)을 잡아 수정했다.

Phase 5는 2026-08-08 완료되었다 ([progress 0005](./0005_RUNTIME_ADAPTERS.md)).
잔여 3항목(OpenCode adapter·session/resume/cancel·capability mapping)은
OpenCode 사용 시점 조사(RUNTIME findings §11 — upstream도 자동 편입 없이
사용자 구성 3진입로뿐) 후 사용자 결정으로 실수요 시점 이연이 확정되었다
(ADR-0003 범위 note 2). **2026-08-09 재지정** — 조건부 시한이 기약 없이
밀리는 것을 막기 위해 전부 Phase로 배치했다: resume/cancel은 Phase 7,
OpenCode adapter와 capability mapping은 구조만 Phase 6에서 열고 실물은 이연
(로컬 모델 성능 — 사용자 판단 2026-08-09).

Phase 6 선행 조사는 2026-08-08 완료되었다
([CLI_UPSTREAM_FINDINGS](../research/CLI_UPSTREAM_FINDINGS.md)): ①
upstream CLI가 얇은 것은 의도(공유 핸들러 위임으로 CLI/MCP 불일치 차단,
품질 루프는 합성 계층 소유)이며 `ooo seed`는 전제 gate를 가진 재개용
primitive였다 — `mcx blueprint`의 QA 상시 포함은 upstream use case를
부수지 않는다. ② canonical Stage 저장은
[ADR-0037](../adr/0037-mission-record-and-canonical-stage.md)로 처분 —
합성 계층(Phase 6 CLI) 소유 mission 문서에 도입, enforcement는 Gate
재계산 유지.

Phase 6 표면은 2026-08-09 구현되었다: [ADR-0038](../adr/0038-mcx-cli-surface-contract.md)
계약(비대화형 단발, exit 0/1/2, mission record는 CLI만 기록) 그대로 24개
명령 + entry point `mcx`, 도그푸딩 드라이버의 검증된 표면을 승계. 579 tests,
LLM-free 경로 스모크(start→status→gate HOLD exit 2) 확인.

도그푸딩 0003은 2026-08-09 MISSION COMPLETE로 완주했다
([기록](../research/DOGFOODING_0003.md)) — 설치된 실물 CLI로 exit code
3종·mission record 전이 전체 그래프·QA EXHAUSTED→수락·자연 발생 Recover를
검증했고, 계약 결함 2건(무도구 max-turns, 원인 사슬 삼킴)을 잡아 수정했다.
콜 실측 60 (추정 30~50 — 초과분은 closure 감사 7라운드×3lane,
upstream 파리티 동작으로 확인).

status 박스는 2026-08-09 구현되었다 (ADR-0038 §6.1 개정 2) — 명령 원장 +
세 화면 렌더, 604 tests. OPEN_QUESTIONS §5(verdict 일괄 저장)는 같은
작업에서 **유지**로 처분했다.

라우팅 테이블은 2026-08-09 구현되었다 (ADR-0039) — `cli/routing.py`와
`cli/composition.py`의 backend 레지스트리, 618 tests. Recover의 재투입은
Execute 행이 아니라 **Recover 행**을 쓰며(실행 lane 라우팅 키가 다르다),
호출 계수는 라우팅된 실물까지 감싼다. 실물 확인: 알 수 없는 Stage 키와
미등록 backend 이름이 로드에서 exit 1로 거부되고, 파일 부재만 기본 조립으로
간다.

Phase 6 종료 검토는 2026-08-09 수행했다 —
[progress 0006](./0006_MCX_CLI.md). Phase 6에는 **progress record 자체가
없었고** 그것이 첫 발견이다. 잡은 것 넷: record 신설, 산문뿐이던 import
방향 계약을 검사로 승격, ADR-0037 Verification 문장 정정(도메인 예외 ≠ CLI
거부), ADR-0037 §5의 upstream Stage 국면 대조가 무처분 도과해 Phase 10으로
재지정. 질문 7 대상이던 `exit_conditions`는 이미 2026-08-09에 처분되어
있었다 (사용자 acceptance는 Phase 9 — [ADR-0017](../adr/0017-blueprint-schema-baseline.md)).

secret redaction은 2026-08-09 확정·구현했다 ([ADR-0040](../adr/0040-secret-redaction-boundaries.md))
— 프로필 둘(저장=자격증명만·경로 유지, host=자격증명+경로), lifecycle 기록은
마스킹이 아니라 거부, 강제는 호출이 아니라 모델·쓰기 경계. 조사에서
`state/current_mission`만 0644였음이 드러나 함께 고쳤다.

MCP control surface는 2026-08-09 구현했다 ([ADR-0041](../adr/0041-mcp-control-surface-contract.md))
— tool 29개(CLI 24 + start 3 + job 2)를 `build_parser()`에서 파생하고 호출은
CLI와 **같은 `dispatch`**를 지난다. exit 2(HOLD)는 `is_error=false`로 나가고,
job은 원장에서 유도하며(새 저장소 없음), 취소는 디스크 마커를 runtime이
관측해 실행 중인 프로세스를 실제로 종료한다. 진입점은 `mcx-mcp`(별도 실행
파일 — CLI에 붙이면 순환)이고 SDK는 optional extra다.

Phase 7 종료 검토는 2026-08-09 수행했다 —
[progress 0007](./0007_MCP_CONTROL_SURFACE.md). 로드맵 체크리스트 9항목이
이행 5·부분 2·미이행 2였음이 드러났다. 잡은 것 여섯: Recover 비동기 짝 누락
(`recover dispatch`가 `execute next`와 같은 `codex exec`를 도는데 짝이 없어
host가 900초까지 블로킹된 채 취소 수단이 없었다 — 고침), 실행 lane의 재귀 경계
부재(텍스트 lane에는 있다), `cancelled` attempt 상태 미이행과 그 오작동(3회
취소 → `STALL` 오판), stale write 재확인 미이행(Phase 7이 전제조건을 만들고도),
tool description이 도구 이름의 반복, 그리고 미이행을 담은 채 "구현 완료"로
기록돼 있던 체크리스트.

skill/Core 경계는 2026-08-09 조사·초안 작성했다
([SKILLS findings](../research/SKILLS_UPSTREAM_FINDINGS.md),
[ADR-0042](../adr/0042-skill-and-core-ownership-boundary.md) — Proposed).
경계 원칙은 *"Core는 한 번의 판정, skill은 몇 번·어떤 순서로 부르고 무엇을
묻는가"* 이고 판별 질문은 *"같은 입력에 항상 같은 답인가"* 다. 같은 작업에서
사용자 지적으로 **우리 "upstream보다 강하다" 주장 8건을 전수 재대조**해
3 성립·2 정당화 만료·1 과장 정정으로 처분했다 (ADR-0042 §8) — 대부분은
강화가 아니라 **같은 의도를 다른 층에 놓은 것**이었고, 앞으로 층 이동은 강함이
아니라 층 이동으로 기록한다.

재귀 경계는 2026-08-09 구현·실물 확인했다 (ADR-0042 §6, 731 tests).
`codex exec`가 `--ignore-user-config`를 조건 없이 달아 사용자 codex 설정을
상속하지 않고, 모델은 `config.toml`의 `[backends.codex_cli]`가 제공하되 없으면
사용자 설정을 읽어 채택·기록한다(동작 그대로, 기록만 생김 — ADR-0039 개정 3).
실측이 레버 선택을 바꿨다: 처음 추천했던 `-c mcp_servers={}`는 파싱만 되고
**병합이라 효과가 없었다**(`codex mcp list`로 확인). Fact Resolver는 폐기했다
(ADR-0011 §3 근거가 Phase 8의 host 도입으로 만료 — 미구현이라 비용 0).

Phase 8은 2026-08-09 구현했다 — skill 6종 + 양쪽 host 매니페스트(df38159),
결정적 품질 하한(ADR-0043, cc5f3f8), 설치 경로 확정·실물 검증. 같은 날 외부
지적 6건을 서브에이전트로 대조해 4건 거짓·2건 부분사실로 처분하고, 그 과정에서
**검토 셋을 통과한 시한 도과 1건**(telemetry event 층)과 **시한이 아예 없던
항목 1건**(spec-gap 분류)을 찾아 Phase 9로 제안 등록했다.

Phase 8 종료 검토는 2026-08-09 수행했다 —
[progress 0008](./0008_PLUGIN_COMPOSITION_LAYER.md). 잡은 것 다섯: tool
description이 이름의 반복이던 것(검토에서 이행 — CLI `help=` 파생, 24명령),
stale write 재확인의 **2회 연속 도과**(Phase 9 재지정 + 발동·종료 조건을 함께
걸어 무한 연기를 끊었다), host 자기 도구 경로의 두 번째 도과(Phase 9 —
brownfield와 같은 형태의 문제), skill 6종의 근거 부재(등록), 질문 형태 규칙이
산문 강제인 것(확인).

**Phase 9로 넘어가는 8항목이 성격이 하나로 모인다 — 전부 실물 관측이 있어야
결정할 수 있는 것들이다** (0008 §3). 그래서 Phase 9는 구현 Phase가 아니라
**관측 Phase**에 가깝다. 이 점을 놓치면 관측 없이 하나씩 발명하게 된다.

Phase 9의 첫 두 관문은 2026-08-09 닫혔다 — brownfield 진입(ADR-0044 ③)과
worktree 격리(ADR-0045). 둘 다 **뒤 항목의 선행이었다는 점이 같다**: 전자는
`context` 공백을, 후자는 checkpoint·rollback·`changed_files`가 딛고 설 git
경계를 열었다.

다음 검증 가능한 목표 한 개: **upstream Gen 2+의 전체 연결 경로를 소스에서
재구성한다.** Verify/Evaluate 결과 → Wonder → Reflect → 다음 Seed 생성 →
`parent_seed_id` lineage → 다음 Execute/Evaluate 기록을 추적하고,
`RALPH_HANDOFF`·`UNSTUCK_LATERAL`이 우리 다섯 Stage와 어떤 관계인지 같은 조사에서
대조한다. 결과는 Phase 10 설계 ADR의 입력이며, 그 전에는 `Stage.REFLECT`나
Hermes adapter를 구현하지 않는다.

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
  내용을 수락할 수 없다. 수정 후보 채택 절차(Phase 7)와 함께 다루며, 내용
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

### Verify Gate CLEAR 조건 중 강제되지 않는 것

[Verify Guide](../08_VERIFY.md) §9는 `CLEAR — MISSION COMPLETE` 조건 9개를
규정한다. `evaluate_verify_gate`가 검사하는 것은 mechanical 통과와 AC별
verdict(충족·score·불확신·게이밍)다. 나머지는 **계약 미달**이며 여기 명시한다
([progress 0004](./0004_VERIFY_RECOVER_VERTICAL_SLICE.md) 종료 검토에서 추가).

| 조건 | 상태 |
|---|---|
| mechanical 명령의 workspace 밖 부작용 | **차단하지 않는다** — 0002 도그푸딩에서 초안 verify 명령이 `/tmp` 고정 경로에 쓰는 것이 실물 관측됨 ([DOGFOODING_0002 §5](../research/DOGFOODING_0002.md)). repo 수준 검사 층(ADR-0028 §2 보류)과 같은 자리에서 다룬다 |
| 적용 가능한 검사 생략의 정책 근거 | repo 수준 검사 층 자체가 보류 (ADR-0028 §2) — 그 도입과 함께 |
| Exit Conditions 충족 | 필드 유예 재평가 완료 — 핵심은 AC 전수 요구가 덮고, 잔여는 도입 시점 이동 (ADR-0017 note, ADR-0029) |
| Constraint 위반·Non-goal 구현 없음 | **결정적 검사 없음** — semantic 평가자의 입력에는 있으나 판정 필드가 없다. scope drift 탐지(Phase 5)와 함께 |
| workspace revision 추적 | **검사 없음** — snapshot/revision 방식이 미결정 ([Open Questions §5](../research/OPEN_QUESTIONS.md)) |
| unresolved risk의 명시적 근거 | **검사 없음** — risk 표현은 reward_hacking_risk뿐 |

### Recover의 알려진 한계

- **spec-gap 분류가 없다.** 제품 결정 누락·AC 모순의 Brief/Blueprint routing은
  사용자가 기존 경로(Brief 재개, Blueprint revise)로 직접 수행한다 — 자동
  분류·route는 미도입 (09 §14 해당 행 대상 없음). **계약은 있고 코드가 없다** —
  [Recover Guide](../09_RECOVER.md) §4.1이 `RecoveryDirective`로 Brief/Blueprint에
  route하라고 규정한다. **2026-08-09: 시한이 아예 없었음을 확인하고 Phase 9로
  제안 등록했다** (외부 지적의 검증에서 드러났다. 시한 없는 항목은 도과를 탐지할
  수 없다 — [progress 0006](./0006_MCX_CLI.md) §1.7이 같은 문제를 지적했다).
  주의: upstream 대응물은 **없다** — upstream의 `FailureClass → RecoveryAction`은
  전부 실행 계층 동작이고, 스펙 품질 원인(`BounceCause`)을 실패 분류와 **의도적으로
  분리**한다 ([REPAIR findings](../research/REPAIR_UPSTREAM_FINDINGS.md)). 이
  항목은 우리 쪽이 더 나아간 자리이며 그래서 발명 위험도 우리 몫이다.
- **progress 기록이 없다.** 실패 수 감소 같은 신호를 기록하지 않으며, 유일한
  결정적 신호는 동일 오류 해시의 제거다 (ADR-0031).
- **`previous_failure`의 프롬프트 렌더링은 Phase 5 소관.** v1은 구조화 필드의
  전달까지 — fake runtime이 그것을 무시해도 탐지되지 않는다 (envelope와 같은
  강제 수준).

### 전 Stage 공통의 알려진 한계

- ~~**`executed-unverified`의 upstream 대응물이 미조사다.**~~ **2026-08-09
  같은 날 조사·해소.** 대응물이 실재한다 —
  `mcp/job_manager.py:249-258`(`verification_status: "executed_unverified"`,
  `next_step: "ooo evaluate"`)와 `auto/pipeline.py:4650-4676`
  (`complete_unverified`/`complete_verified`),
  [RUN findings §11.1](../research/RUN_UPSTREAM_FINDINGS.md). 슬로건과 Gate
  축이 upstream 정렬임이 확인됐고, 두 차이(1급 상태 표현, 미평가 작업 차단)는
  전자가 강화, 후자는 이미 ADR-0026에 등록된 divergence다.
- ~~**Stage→Runtime 바인딩 표현이 upstream과 대조되지 않았다.**~~
  **2026-08-09 같은 날 대조·결정.** ADR-0023이 Phase 5에 약속하고 이행하지
  않은 대조를 수행해
  [ADR-0039](../adr/0039-stage-runtime-routing-table.md)로 확정했다 —
  라우팅 테이블 도입(닫힌 Stage enum 키, lane별 backend 쌍, 3단 해석,
  fail-fast), 설정 표면은 `config.toml`(ADR-0038 개정). **구현은 Phase 6
  잔여 작업이다.**
- **leader-driven 실행 모델의 대응물이 없다 — 미결로 등록 (2026-08-09).**
  우리 실행은 단발이다(`codex exec` 한 번 = AC 하나, ADR-0033). upstream은
  그와 나란히 **코어가 leader가 되어 재개 가능한 worker 세션을 직접 구동하는**
  계열을 등록해 두고 있고, codex의 전송은 **MCP**다(`codex mcp-server`).
  이 발견으로 [RUNTIME findings §6](../research/RUNTIME_UPSTREAM_FINDINGS.md)의
  *"코어의 실행은 MCP가 아니라 subprocess다"* 를 정정했다 — `codex`·`claude`·
  `opencode` backend에 한해 참인 진술을 backend 축 전체로 넓혀 쓴 오류였다.
  실행 모델은 되돌리기 비싼 축이므로
  [Open Questions §7](../research/OPEN_QUESTIONS.md)에 미결로 등록했다.
  전모는 [RUNTIME findings §12](../research/RUNTIME_UPSTREAM_FINDINGS.md).

- **worker가 Mission Control을 재귀 호출하는 것을 실행 lane이 막지 않는다 —
  미결로 등록 (2026-08-09, Phase 7 종료 검토).**
  [ADR-0004](../adr/0004-stage-scoped-minimum-capability.md)의 금지가 산문으로만
  있다. 텍스트 lane(Claude)은 `--strict-mcp-config --setting-sources ""`로
  끊지만 실행 lane(`codex exec`)은 `~/.codex/config.toml`을 그대로 상속한다.
  거기에 `mcx-mcp`가 등록되면 경로가 열리고, **그 등록을 하는 것이 정확히
  Phase 8**이다 — 지금 도달 불가인 이유는 방어가 아니라 우연이다. upstream은
  같은 자리에 `--profile`을 *"worker-isolation boundary"* 로 두는데 우리에겐
  그 축이 없다. 결정은 [Open Questions §8](../research/OPEN_QUESTIONS.md),
  시한은 Phase 8.
- **취소된 attempt가 실패와 구분되지 않는다 — Phase 9 (2026-08-09 재지정).**
  취소는 프로세스를 죽이고 attempt를 일반 실패로 닫으며, 그 `error`가 상수
  문자열이다. 따라서 **같은 AC를 세 번 취소하면 Recover가 `STALL`로 판정한다**
  (`domain/recover/packet.py:143-147`) — 의도적 중단이 "정체"로 읽힌다.
  ADR-0025·ADR-0032의 `cancelled` 행이 Phase 7 시한을 무처분 도과했다.
- **canonical Stage 저장이 아직 없다 — 처분 완료, 도입은 Phase 6.** Entry
  Contract들의 "현재 Stage가 X다" 조건은 전 Stage에서 미강제이며, 실질
  보증은 각 진입의 Gate 재계산이다. upstream 대조
  ([CLI_UPSTREAM_FINDINGS §4](../research/CLI_UPSTREAM_FINDINGS.md)) 후
  [ADR-0037](../adr/0037-mission-record-and-canonical-stage.md)로
  결정했다(2026-08-08): mission record(current Stage 포함)는 합성
  계층(Phase 6 CLI) 소유로 도입하고, 저장된 Stage에 enforcement 지위를 주지
  않는다 — Gate 재계산이 계속 이긴다. Phase 6 구현 전까지 이 한계는 결함이
  아니라 결정된 상태다
  ([progress 0004](./0004_VERIFY_RECOVER_VERTICAL_SLICE.md) 질문 4 처분).

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

Phase를 완료로 선언하기 전에 아래 일곱 질문에 답하고, 답을 그 phase의
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
7. **시한 도과 점검** — **이 phase를 시한으로 지정한 보류·미확인 항목**이
   ADR·Open Questions에 남아 있는가? 남았다면 이행했거나 새 시한으로
   재지정했는가? *(실례: Phase 5를 시한으로 쓴 항목 7건 — rollback,
   resume/cancel, changed_files, 실패 분류 3종 — 이 전부가 무처분으로 Phase 5
   종료를 통과했고 2026-08-09 로드맵 대조에서야 발견됐다. 질문 4는 "표시가
   있는가"만 물어 "표시된 시한이 지났는가"를 놓친다.)*

최종 목표인 Phase 11까지 모든 구현 phase가 이 검토를 거친다. Phase 0은 문서
기반이라 대상이 아니다.

| Phase | 검토 상태 | 기록 |
|---|---|---|
| Phase 1 — Brief | 소급 충족 — 완료 당일 감사(ADR-0015·0016), 관측 대조에 따른 closure 소급(ADR-0020), 등록된 이탈은 ADR-0011과 ADR-0020 §5 | [progress 0001](./0001_BRIEF_VERTICAL_SLICE.md) |
| Phase 2 — Blueprint | **충족 (2026-08-08)** — 완료 선언 전 절차로 첫 수행. 계약 미달 1건 발견·수정(중복 AC, b00e0c2), 표시 누락 1건 추가(크기 제한), 미확인 이탈 1건 등록(previous_findings → ADR-0022) | [progress 0002](./0002_BLUEPRINT_VERTICAL_SLICE.md) |
| Phase 3 — Execute | **충족 (2026-08-08)** — Test Matrix 누락 2행 테스트 추가(2f951e2), ADR-0024 과장 정정, §10 미검사 조건 표 추가, telemetry schema 시점 정정(§9 → Phase 4 전), 재시도 정책 미확인 등록(ADR-0025) | [progress 0003](./0003_EXECUTE_VERTICAL_SLICE.md) |
| Phase 4 — Verify/Recover | **충족 (2026-08-08)** — 예산 리셋 테스트 추가(0186450), directive 저장 vs 파생 충돌 해소, exit_conditions 유예 재평가, canonical Stage 저장 부재 등록, Verify Gate 미검사 조건 표 신설. Gate·Matrix 전수 대조 포함 | [progress 0004](./0004_VERIFY_RECOVER_VERTICAL_SLICE.md) |
| Phase 5 — Runtime adapters | **충족 (2026-08-08)** — 낡은 약속 1건 갱신(도구 차단 시점), 근거 미인용 1건 보강(무도구 max-turns), 미표시 보류 1건 등재(workspace 밖 부작용). 잔여 3항목은 실수요 이연 후 2026-08-09 Phase 배치(7·11)로 재지정. **질문 7 미수행 — Phase 5를 시한으로 쓴 보류 7건이 무처분 통과** (2026-08-09 소급 처분) | [progress 0005](./0005_RUNTIME_ADAPTERS.md) |
| Phase 6 — `mcx` CLI | **충족 (2026-08-09)** — progress record 부재 자체가 첫 발견(0006 신설). 산문뿐이던 import 방향 계약을 검사로 승격(3 tests), ADR-0037 Verification 문장을 구현에 맞게 정정, §5의 upstream enum 국면 대조 무처분 도과를 Phase 10으로 재지정 | [progress 0006](./0006_MCX_CLI.md) |
| Phase 7 — MCP control surface | **충족 (2026-08-09)** — 로드맵 체크리스트 9항목이 이행 5·부분 2·미이행 2였음을 드러냈다. 미조립 부품 1건 수정(Recover 비동기 짝 — `recover dispatch`가 같은 `codex exec`를 돈다), 무처분 도과 3건 재지정(host 자기 도구 경로·승인 actor→Phase 8, cancelled 상태·resume→Phase 9), 미표시 보류 2건 등재(취소된 attempt, 재귀 경계), 미등록 이탈 1건 등록(서버가 사람에게 직접 묻지 않음, `upstream 미확인`) | [progress 0007](./0007_MCP_CONTROL_SURFACE.md) |
| Phase 8 — plugin 패키징 (합성 계층) | **충족 (2026-08-09)** — tool description이 이름의 반복이던 것을 검토에서 이행(CLI `help=` 파생, 24명령). 미이행 2건 재지정(stale write 재확인·host 자기 도구 경로 → Phase 9, 전자는 **발동 조건과 종료 조건을 함께 걸어** 무한 연기를 끊었다), 표시 없던 보류 1건 등록(skill 6종의 근거), 산문 강제 1건 확인(질문 형태 규칙) | [progress 0008](./0008_PLUGIN_COMPOSITION_LAYER.md) |
| Phase 9 — 실사용 진입 (brownfield·되돌리기) | **충족 (2026-08-10)** — 두 번의 도그푸딩이 결함 6건을 잡았고 전부 조사·테스트로는 드러나지 않았다. 가장 큰 소득은 개별 결함이 아니라 **셋이 같은 뿌리를 갖는다는 것** — *"upstream과 같다"고 적어 놓고 원문과 대조하지 않았다*(§1.3). ADR README에 절차 한 줄을 넣었다. 검토가 직접 잡은 것 1건 수정(`changed_files`를 만들어 놓고 표시하지 않았다), 미결 11건 처분(닫음 6·재지정 3·구현 1·해소 1, **무처분 통과 0**). Phase 5를 시한으로 쓴 마지막 항목(telemetry event 층)도 종결됐다 | [progress 0009](./0009_RECOVERY_LAYERS.md) |
| Phase 10 — Reflect/Evolve | **진행 중** — Reflect가 Brief를 대체함을 확인; 다음은 Gen 2+ 전체 연결 경로와 Hermes 사용 방식 조사 | — |
| Phase 11 — 병렬 실행 | 대기 | — |

## Update protocol

작업이 끝날 때마다 이 문서를 다음처럼 갱신한다.

1. 계획이 아니라 실제 완료 evidence를 확인한다.
2. 완료 checklist에 관련 test/commit/artifact를 연결한다.
3. 현재 HOLD/CLEAR 이유를 갱신한다.
4. 다음 한 개의 검증 가능한 목표를 지정한다.
5. Stage Guide와 구현이 다르면 차이를 숨기지 않는다.
6. Phase 완료를 선언하려면 먼저 위의 Phase 종료 검토를 수행하고 결과를
   progress record에 남긴다.
