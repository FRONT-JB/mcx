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

---

## 1. Upstream baseline

- [ ] baseline commit의 `pyproject.toml`과 package 경계를 기록한다.
- [ ] `ooo interview` skill, MCP handler, CLI path의 실제 종료 Gate를 end-to-end로 추적한다.
- [ ] architecture의 `ambiguity <= 0.2`와 current source의 user-controlled completion을 reconciliate한다.
- [ ] completion candidate streak와 user approval의 실제 호출 경로를 확인한다.
- [ ] answer provenance enum과 requirement authority 규칙을 확인한다.
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

- [ ] Greenfield/Brownfield를 v1에서 구분할지 결정한다.
- [ ] source provenance의 canonical categories를 결정한다.
- [ ] clarity dimension과 score 방향을 결정한다.
- [ ] score threshold, minimum rounds, stability streak의 관계를 결정한다.
- [ ] user approval을 command/state 중 어디에 기록할지 결정한다.
- [ ] 질문 생성 실패와 빈 응답 fallback을 정의한다.
- [ ] initial context size와 prompt compaction policy를 정의한다.
- [ ] codebase fact를 누가 어떤 read-only capability로 수집할지 결정한다.

## 3. Blueprint decisions

- [ ] Seed schema의 필수/선택 필드를 결정한다.
- [ ] Non-goal과 Constraint의 validation rule을 정의한다.
- [ ] AC quality rubric과 QA 통과 policy를 결정한다.
- [ ] Seed revision ID와 parent lineage를 결정한다.
- [ ] approval actor와 approval evidence를 결정한다.
- [ ] user-edited YAML을 지원할지 결정한다.
- [ ] schema/ontology를 v1에 포함할지 결정한다.

## 4. Execute decisions

- [ ] work item의 canonical 이름과 schema를 결정한다.
- [ ] atomic-first size 판단과 분해 한도를 정의한다.
- [ ] dependency graph와 ready calculation을 정의한다.
- [ ] 첫 concrete Runtime Adapter 순서를 결정한다.
- [ ] workspace/file scope 표현을 결정한다.
- [ ] required idempotency의 exact key, scope, retention, duplicate result semantics를 정의한다.
- [ ] parallel execution 도입 Gate를 정의한다.

## 5. Verify decisions

- [ ] project-specific mechanical command 발견 방식을 결정한다.
- [ ] command allowlist와 custom command 승인 정책을 결정한다.
- [ ] semantic verdict schema와 uncertainty 표현을 결정한다.
- [ ] UI/API/CLI observation adapter의 우선순위를 결정한다.
- [ ] conditional consensus를 v1에 포함할지 결정한다.
- [ ] workspace snapshot/revision 검증 방식을 결정한다.

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

## 9. Persistence and Telemetry decisions

- [ ] file store, SQLite, event sourcing 중 v1 baseline을 결정한다.
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
