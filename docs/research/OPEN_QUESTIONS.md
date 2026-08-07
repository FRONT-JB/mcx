# Open Research and Design Questions

이 목록은 모르는 것을 감추지 않고 구현 전에 검증하기 위한 backlog다.

상태 표기:

- `[ ]` 조사 전
- `[-]` 조사 중
- `[x]` 근거와 결정 문서까지 반영

---

## 0. 현재 우선순위 — Phase 1 (Brief vertical slice)

2026-08-07 Phase 0 검토 후 우선순위화했다. Phase 1 착수 전에는 아래 항목만
조사하고, 나머지 섹션은 해당 Phase 직전에 조사한다.

1. §1 Upstream baseline 중 Brief 관련 항목
   - `pyproject.toml`과 package 경계 기록
   - `ooo interview` 종료 Gate end-to-end 추적
   - `ambiguity <= 0.2`와 user-controlled completion의 reconcile
   - completion candidate streak와 user approval 호출 경로
   - answer provenance enum과 requirement authority 규칙
   - LICENSE와 copied code notice 재확인 (구현 직전)
2. §2 Brief decisions 전체

2026-08-07: 1번 항목의 근거 수집이 완료되어
[INTERVIEW_UPSTREAM_FINDINGS.md](./INTERVIEW_UPSTREAM_FINDINGS.md)에
기록했고, §2 결정은 ADR-0009/0010/0011과 `05_BRIEF.md`에 반영되어 닫혔다.
§1의 Brief 관련 항목은 upstream test 조사(Phase 1 test case 설계 직전)와
LICENSE 재확인(코드 복사 직전)만 남아 `[-]`로 유지한다.

---

## 1. Upstream baseline

- [-] baseline commit의 `pyproject.toml`과 package 경계를 기록한다.
- [-] `ooo interview` skill, MCP handler, CLI path의 실제 종료 Gate를 end-to-end로 추적한다.
- [-] architecture의 `ambiguity <= 0.2`와 current source의 user-controlled completion을 reconciliate한다.
- [-] completion candidate streak와 user approval의 실제 호출 경로를 확인한다.
- [-] answer provenance enum과 requirement authority 규칙을 확인한다.
- [ ] Seed 생성 → QA → repair → approval path를 실제 handler/test로 추적한다.
- [ ] Seed field와 immutability/revision behavior를 source/test에서 확인한다.
- [ ] Run이 AC를 atomic-first로 시도하고 분해하는 정확한 조건을 확인한다.
- [ ] executed-unverified에 대응하는 upstream state/event를 확인한다.
- [ ] Evaluation pipeline의 current short-circuit와 consensus trigger를 tests로 확인한다.
- [ ] Repair, resilience, evolve, seed repair의 경계를 비교한다.
- [ ] Codex/OpenCode Runtime의 cancellation/resume/error normalization을 비교한다.
- [ ] MCP authoring handler와 execution handler의 recursive dispatch guard를 확인한다.
- [ ] pinned commit의 LICENSE와 copied code notice 요구를 구현 직전에 재확인한다.

---

## 2. Brief decisions

2026-08-07에 ADR-0009/0010/0011로 결정했다.

- [x] Greenfield/Brownfield를 v1에서 구분할지 결정한다. → 정책 자리만 예약, 탐색 단계는 유예 (ADR-0011)
- [x] source provenance의 canonical categories를 결정한다. → authority 2값 + source 별도 축 (ADR-0010)
- [x] clarity dimension과 score 방향을 결정한다. → dimension은 clarity(높을수록 명확), canonical metric은 ambiguity (ADR-0009)
- [x] score threshold, minimum rounds, stability streak의 관계를 결정한다. → 네 조건 모두 필요 (ADR-0009)
- [x] user approval을 command/state 중 어디에 기록할지 결정한다. → revision에 묶인 1급 상태 (ADR-0011)
- [x] 질문 생성 실패와 빈 응답 fallback을 정의한다. → 재개 조건을 명시한 HOLD, terminal status는 Lifecycle 소관 (05_BRIEF §15)
- [x] initial context size와 prompt compaction policy를 정의한다. → 한도 초과 시 요약 round, 기본값 3500자 (05_BRIEF §10 Step 1)
- [x] codebase fact를 누가 어떤 read-only capability로 수집할지 결정한다. → 별도 Fact Resolver 역할 유지 (ADR-0011)
- [x] **closure 감사를 Brief Gate에 도입할지, 어떤 형태로 할지 결정한다.**
      → 3-lane 전부 재구성해 Core에 도입 (사용자 결정 2026-08-08,
      [ADR-0020](../adr/0020-brief-closure-audit.md)). closer의 verdict가
      gate, advisory 두 lane은 HIGH만 차단, 합성은 결정적 도메인 코드.
      계약 문장은 upstream 원문, ambiguity 점수 비전달은 등록된 divergence.

## 3. Blueprint decisions

- [x] Seed schema의 필수/선택 필드를 결정한다. → 방향 필드(goal, constraints,
      non_goals, acceptance_criteria)와 lineage만, `extra="forbid"`
      ([ADR-0017](../adr/0017-blueprint-schema-baseline.md))
- [x] Non-goal과 Constraint의 validation rule을 정의한다. → 그대로 옮겨야
      하며 추가·누락은 결정적 범위 검사가 거부
      ([ADR-0018](../adr/0018-blueprint-generation-contract.md))
- [x] AC quality rubric과 QA 통과 policy를 결정한다. → quality bar 문장 +
      0.90/0.40/최대 5회 ([ADR-0019](../adr/0019-blueprint-qa-loop.md))
- [x] Seed revision ID와 parent lineage를 결정한다. → 1부터 연속 정수
      revision, `brief_revision`으로 lineage, 전체 revision 보존
      ([ADR-0021](../adr/0021-blueprint-state-and-revisions.md) §2)
- [-] approval actor와 approval evidence를 결정한다. → evidence는
      `BlueprintApproval`(statement + QA 근거,
      [ADR-0019](../adr/0019-blueprint-qa-loop.md) §8)로 확정. actor
      identity와 승인 UX는 surface(Phase 6·7)에서 결정한다.
- [ ] user-edited YAML을 지원할지 결정한다.
- [x] schema/ontology를 v1에 포함할지 결정한다. → 제외. upstream 필드 5개
      (ontology_schema 등)는 v1 미포함으로 기록
      ([ADR-0017](../adr/0017-blueprint-schema-baseline.md) Cost)

## 4. Execute decisions

- [ ] work item의 canonical 이름과 schema를 결정한다.
- [ ] atomic-first size 판단과 분해 한도를 정의한다.
- [ ] dependency graph와 ready calculation을 정의한다.
- [ ] 첫 concrete Runtime Adapter 순서를 결정한다.
- [ ] workspace/file scope 표현을 결정한다.
- [ ] required idempotency의 exact key, scope, retention, duplicate result semantics를 정의한다.
- [ ] parallel execution 도입 Gate를 정의한다.
- [ ] **Execute 진입 경로가 하나임을 무엇이 보장하는지, Telemetry가 "무엇이
      이 작업을 만들었는가"를 기록하는지 결정한다.** upstream 관측에서
      Stage→Runtime 바인딩이 orchestrator 밖 경로에서 조회되지조차 않았다
      ([SEED_UPSTREAM_FINDINGS §12.3](./SEED_UPSTREAM_FINDINGS.md)). 계층
      경계에 해당하므로 Execute 구현 **시작 전에** 정한다.

## 5. Verify decisions

- [ ] project-specific mechanical command 발견 방식을 결정한다.
- [ ] command allowlist와 custom command 승인 정책을 결정한다.
- [ ] semantic verdict schema와 uncertainty 표현을 결정한다.
- [ ] UI/API/CLI observation adapter의 우선순위를 결정한다.
- [ ] conditional consensus를 v1에 포함할지 결정한다.
- [ ] workspace snapshot/revision 검증 방식을 결정한다.
- [ ] **Execute Telemetry 없이 나타난 작업을 Verify가 CLEAR할 수 있는지
      결정한다.** AC가 통과해도 그 작업을 무엇이 만들었는지 기록이 없으면
      완료 선언의 근거가 비어 있다
      ([SEED_UPSTREAM_FINDINGS §12.3](./SEED_UPSTREAM_FINDINGS.md)).

## 6. Recover decisions

- [ ] failure taxonomy enum을 결정한다.
- [ ] Recover Stage activation과 RecoveryDirective의 exact serialization을 정의한다.
- [ ] retry budget과 progress signal을 결정한다.
- [ ] identical failure/oscillation 탐지 방식을 결정한다.
- [ ] rollback 지원 범위를 결정한다.
- [ ] blocked/cancelled/unrecoverable 상태를 결정한다.

## 7. Runtime decisions

- [ ] Runtime protocol method와 streaming shape를 결정한다.
- [ ] text-generation backend port를 execution Runtime과 어떻게 분리할지 결정한다.
- [ ] capability descriptor와 mismatch semantics를 정의한다.
- [ ] native event 보존과 normalized Telemetry 연결 방식을 정의한다.
- [ ] timeout/cancel/resume contract를 정의한다.
- [ ] OpenCode local/provider/agent mode를 capability로 어떻게 표현할지 결정한다.

## 8. MCP and CLI decisions

- [ ] MCP tool 하나가 한 Stage command와 1:1인지 command/query를 분리할지 결정한다.
- [ ] request/response schema와 error envelope를 정의한다.
- [ ] host session, Mission ID, Runtime handle 전달 규칙을 정의한다.
- [ ] async job/polling/notification 방식을 결정한다.
- [ ] disconnect, cancel, timeout의 의미를 분리한다.
- [ ] CLI와 MCP parity test 전략을 정의한다.
- [ ] plugin 설치·발견·설정 UX를 결정한다.
- [ ] **MCP host가 자기 편집 도구로 작업하고 Verify만 호출하는 경로를 어떻게
      다룰지 결정한다.** host는 에이전트이며 `mcx` 도구와 자기 도구를 동시에
      갖는다 — upstream에서 실제로 발생한 조건이다
      ([SEED_UPSTREAM_FINDINGS §12.3](./SEED_UPSTREAM_FINDINGS.md)).
      [ADR-0004](../adr/0004-stage-scoped-minimum-capability.md)는 worker가
      위로 탈출하는 것만 막고 이 방향을 덮지 않는다.
- [ ] **upstream이 CLI를 얇게 둔 이유를 조사한다 (Phase 6 시작 전).**
      `ooo seed` CLI는 QA·승인 없이 생성·저장만 한다 — 이것이 의도(스크립트
      가능성, LLM 비용 회피)인지 우연(skill 계층이 먼저 진화)인지에 따라
      `mcx blueprint`가 그 use case를 부수는지가 갈린다. Principle 10 —
      이유를 모른 채 다르게 가지 않는다.
- [ ] **`mcx` CLI의 대화형 지점을 결정한다.** QA EXHAUSTED에서의 사용자
      선택, 수정 후보 채택, HOLD의 exit code, 비대화형 모드 지원 여부.
      upstream skill 계층은 대화 안에 있어 이 질문들이 없었으므로 **대조
      불가능한 신규 영역**이다 — 여기서의 작은 판단들이 누적 divergence가
      되지 않도록 결정을 ADR로 묶는다. 단, QA 우회 플래그(`--skip-qa` 류)는
      선택지가 아니다 — [ADR-0019](../adr/0019-blueprint-qa-loop.md) §1이
      죽인 surface 간 비대칭을 재생산한다.

## 9. Persistence and Telemetry decisions

기초 조사는 [PERSISTENCE_UPSTREAM_FINDINGS.md](./PERSISTENCE_UPSTREAM_FINDINGS.md)에
있다. Brief 범위의 baseline은 ADR-0013에서 결정했고, 나머지는 Phase 3(Execute)
설계 직전에 확정한다.

- [-] file store, SQLite, event sourcing 중 v1 baseline을 결정한다. (Brief 범위는 ADR-0013으로 결정, 실행 이벤트는 Phase 3)
- [ ] atomic state transition과 crash recovery 요구를 정의한다.
- [ ] Telemetry event/report/bundle schema를 결정한다.
- [ ] retention, redaction, output-size 정책을 결정한다.
- [ ] Mission replay와 resume의 최소 보장 수준을 결정한다.

---

## Definition of resolved

질문은 답변 문장 하나가 생겼다고 완료되지 않는다. 다음을 모두 만족해야 한다.

- primary source 또는 재현 가능한 실험 근거가 있다.
- Mission Control에 채택할지 말지 결정했다.
- 중요한 결정이면 ADR이 있다.
- 관련 Architecture/Stage Guide가 갱신되었다.
- 검증할 테스트 또는 acceptance condition이 있다.
