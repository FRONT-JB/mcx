# Upstream Concept Mapping

> Baseline: `Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943`<br>
> Checked: 2026-08-07

Mission Control v1은 Ouroboros 전체를 축소 복사하지 않는다. 사용자가 중요하게
본 specification-first Workflow, Stage Gate, 최소 capability, Runtime 분리,
Telemetry 기반 진행을 작은 Python 시스템으로 재구성한다.

## Primary sources

- [Ouroboros repository at baseline](https://github.com/Q00/ouroboros/tree/9486c78575a0332e9b84d93ef5832985291d7943)
- [Architecture](https://github.com/Q00/ouroboros/blob/9486c78575a0332e9b84d93ef5832985291d7943/docs/architecture.md)
- [CLI reference](https://github.com/Q00/ouroboros/blob/9486c78575a0332e9b84d93ef5832985291d7943/docs/cli-reference.md)
- [Codex runtime guide](https://github.com/Q00/ouroboros/blob/9486c78575a0332e9b84d93ef5832985291d7943/docs/runtime-guides/codex.md)
- [OpenCode runtime guide](https://github.com/Q00/ouroboros/blob/9486c78575a0332e9b84d93ef5832985291d7943/docs/runtime-guides/opencode.md)
- [Interview source](https://github.com/Q00/ouroboros/blob/9486c78575a0332e9b84d93ef5832985291d7943/src/ouroboros/bigbang/interview.py)
- [Ambiguity source](https://github.com/Q00/ouroboros/blob/9486c78575a0332e9b84d93ef5832985291d7943/src/ouroboros/bigbang/ambiguity.py)
- [Seed source](https://github.com/Q00/ouroboros/blob/9486c78575a0332e9b84d93ef5832985291d7943/src/ouroboros/core/seed.py)
- [License](https://github.com/Q00/ouroboros/blob/9486c78575a0332e9b84d93ef5832985291d7943/LICENSE)

위 링크는 모두 baseline commit에 고정되어 있어 이후 `main`이 바뀌어도 이 문서의
관찰을 재현할 수 있다.

---

## 1. Product and command mapping

| Mission Control | Internal term | Ouroboros surface/concept | Evidence | Mission Control decision |
|---|---|---|---|---|
| Mission Control | Workflow control plane | specification-first engine / orchestrator | Session-confirmed + Verified | Accepted baseline |
| `mcx` | CLI | `ooo` skill surface + `ouroboros` terminal CLI | Session-confirmed + Verified | Accepted baseline |
| `mcx brief` | Interview | `ooo interview`, Big Bang interview | Session-confirmed + Verified | Accepted baseline |
| `mcx blueprint` | Seed | `ooo seed`, Seed generation | Session-confirmed + Verified | Accepted baseline |
| `mcx execute` | Run | `ooo run`, orchestrated execution | Session-confirmed + Verified | Accepted baseline |
| `mcx verify` | Evaluate | `ooo evaluate`, evaluation pipeline | Session-confirmed + Verified | Accepted baseline |
| `mcx recover` | Repair | repair/resilience/evolve-related loops | Session-confirmed (name) + Inferred (upstream equivalence) | Accepted public command; exact upstream boundary TBD |
| Flight Controller | execution worker | AgentRuntime-backed worker/session | Session-confirmed + Inferred | Accepted baseline |
| Telemetry | evidence/events/results | runtime events, evaluation evidence, event store | Session-confirmed + Inferred | Accepted baseline |
| `CLEAR` / `HOLD` | Stage Gate | upstream gates/thresholds/results | Session-confirmed + Inferred | Accepted baseline |

Recover는 upstream 단일 command와 완전히 같은 개념이라고 가정하지 않는다.
Seed repair, execution retry, resilience, evaluation feedback 중 어떤 동작을 v1에
포함할지는 [Recover Guide](../09_RECOVER.md)와 Lifecycle에서 명시한다.

---

## 2. Brief / Interview

### Verified upstream observations

현재 `bigbang/interview.py`에서 직접 확인한 내용:

- iterative requirement clarification을 위한 persistent `InterviewState`가 있다.
- question과 response를 round로 저장한다.
- ambiguity score와 breakdown을 상태에 저장한다.
- answer provenance를 저장하고 재분류한다.
- tool-less interviewer prompt는 정확히 하나의 Socratic question을 요구한다.
- 그 prompt는 파일, command, repository, API, tool, 외부 시스템 탐색을 금지한다.
- goal, constraints, success criteria, context clarity 차원을 사용한다.
- 문서/코드 안에 user-controlled closure와 score-based candidate logic이 함께 존재한다.

### Important discrepancy to resolve

공식 architecture 문서는 `ambiguity <= 0.2`를 Big Bang Gate로 설명한다. 반면
현재 interview source는 “Users control when to stop”을 명시하고, 최소 round,
score persistence, completion candidate streak 등 더 복잡한 종료 의미를 가진다.

따라서 Mission Control은 아직 `0.2`를 헌법 값으로 고정하지 않는다. baseline
commit의 실제 handler/skill/test까지 추적해 다음을 분리해야 한다.

- score가 질문 종료를 **추천**하는 조건
- interview state를 completed로 바꾸는 조건
- 사용자가 Seed-ready를 승인하는 조건
- low ambiguity가 여러 round 유지되어야 하는지

**2026-08-07 해소됨** — 위 네 질문은 baseline source 추적으로 분리 확인했다.
`0.2`는 machine gate(overall threshold + per-dimension floor + streak 2)의
입력이고, 완료는 surface별로 CLI 사용자 Confirm / MCP qualify+streak /
skill Acceptance Guard + Restate 사용자 확인이 겹겹이 결정한다. file:line
근거는 [INTERVIEW_UPSTREAM_FINDINGS.md](./INTERVIEW_UPSTREAM_FINDINGS.md)
§2–§4에 있다.

### Mission Control target

> Evidence: Session-confirmed. Decision: Accepted baseline. Exact score, threshold,
> minimum-round, and stability policy remain TBD in
> [Open Questions](./OPEN_QUESTIONS.md#2-brief-decisions).

- 한 번에 하나의 집중 질문
- user decision / code fact / research / assumption의 출처 구분
- score는 Gate input이지만 유일한 권위가 아님
- explicit user approval
- 질문 생성 역할에 write/Shell/Git/browser/MCP 권한 없음

---

## 3. Blueprint / Seed

### Verified upstream observations

현재 architecture와 `core/seed.py`는 Seed를 실행의 불변 specification으로
설명한다. architecture가 명시한 핵심 필드는 Goal, Constraints, Acceptance
Criteria, Ontology Schema, Exit Conditions다. 일반 흐름에서 interview가 Seed를
생성한다.

### Mission Control target

> Evidence: Session-confirmed + Inferred. Decision: approved revision immutability is
> Accepted baseline in [ADR-0002](../adr/0002-approved-seed-is-immutable.md); exact
> Seed schema and QA policy remain TBD.

- Goal
- Constraints
- Non-goals
- Acceptance Criteria
- Exit Conditions
- source Brief/Interview와 decision provenance
- QA/refinement/approval
- 승인 뒤 in-place mutation 금지, revision lineage 사용

Non-goals와 revision UX의 정확한 upstream 대응은 추가 조사한다.

---

## 4. Execute / Run

### Verified upstream observations

현재 architecture는 다음을 설명한다.

- orchestration과 concrete Runtime의 분리
- Acceptance Criteria tree와 dependency-aware execution
- normalized agent messages/runtime handles/task result
- runtime factory와 여러 adapters
- execution과 evaluation의 별도 영역

현재 문서에서 확인한 관련 경로:

```text
src/ouroboros/orchestrator/adapter.py
src/ouroboros/orchestrator/runtime_factory.py
src/ouroboros/orchestrator/runner.py
src/ouroboros/orchestrator/parallel_executor.py
src/ouroboros/orchestrator/codex_cli_runtime.py
src/ouroboros/orchestrator/opencode_runtime.py
```

### Mission Control target

> Evidence: Session-confirmed + Inferred. Decision: Runtime separation, bounded work,
> minimum capability, and evidence-first progress are Accepted baselines in
> [ADR-0003](../adr/0003-runtime-abstraction.md),
> [ADR-0004](../adr/0004-stage-scoped-minimum-capability.md), and
> [ADR-0005](../adr/0005-evidence-over-reasoning.md). Exact work schema and any
> parallel execution policy remain TBD.

- 승인 Seed revision binding
- AC에 추적되는 bounded work
- v1 순차 실행 baseline
- capability-scoped dispatch
- executed-but-unverified 상태
- Runtime-neutral result/Telemetry
- 필요성이 입증된 뒤에만 병렬 실행과 recursive decomposition

---

## 5. Verify / Evaluate

### Verified upstream observations

현재 architecture는 progressive evaluation을 세 층으로 설명한다.

1. mechanical checks
2. semantic verification
3. 조건부 multi-model consensus

관련 경로:

```text
src/ouroboros/evaluation/pipeline.py
src/ouroboros/evaluation/mechanical.py
src/ouroboros/evaluation/semantic.py
src/ouroboros/evaluation/consensus.py
src/ouroboros/evaluation/trigger.py
```

문서에는 coverage, semantic score, drift, uncertainty, consensus trigger에 대한
구체 수치가 있지만 Mission Control 값으로 자동 채택하지 않는다.

### Mission Control target

> Evidence: Session-confirmed + Inferred. Decision: evidence-first verification and
> separation from execution are Accepted baselines in
> [ADR-0001](../adr/0001-workflow-before-runtime.md) and
> [ADR-0005](../adr/0005-evidence-over-reasoning.md); exact verdict schema and
> escalation policy remain TBD.

- mechanical first
- AC별 semantic verdict와 evidence
- actual behavior observation
- no self-approval
- missing evidence는 HOLD
- conditional escalation은 별도 정책으로 격리

---

## 6. Recover / Repair and resilience

### Verified upstream observations

현재 architecture는 stagnation을 반복, 진동, no-drift, diminishing returns로
분류하고 lateral personas를 선택하는 구조를 설명한다. session replay, agent
respawn, escalation 같은 복구 메커니즘도 문서화되어 있다.

관련 경로:

```text
src/ouroboros/resilience/stagnation.py
src/ouroboros/resilience/lateral.py
src/ouroboros/persistence/checkpoint.py
```

### Mission Control target

> Evidence: Session-confirmed + Inferred. Decision: bounded correction followed by
> mandatory re-verification is an Accepted baseline in
> [ADR-0008](../adr/0008-bounded-recovery.md); taxonomy and retry numbers remain TBD.

- failure taxonomy
- failed AC + expected/observed + reproduction + evidence packet
- bounded attempt history
- progress signal과 no-progress 감지
- specification gap은 Brief/Blueprint로 routing
- 교정 뒤 Verify 필수

v1은 persona panel 전체보다 deterministic failure classification과 bounded retry를
먼저 구현한다.

---

## 7. Runtime

### Verified upstream observations

현재 architecture와 runtime guides는 Workflow가 `AgentRuntime` protocol을 통해
concrete backend를 사용하며, adapter가 native event를 공통 message/handle/result로
정규화한다고 설명한다.

- Codex adapter는 Codex CLI를 session-oriented Runtime으로 감싼다.
- OpenCode adapter는 provider 생태계와 session-aware execution을 제공한다.
- Runtime마다 tool, permission, streaming semantics가 다르며 feature parity는
  보장되지 않는다고 명시한다.
- CLI reference는 authoring LLM backend와 run-handoff Runtime을 구분한다.

### Mission Control target

> Evidence: Session-confirmed + Verified. Decision: Runtime-neutral Core and initial
> Codex/OpenCode direction are Accepted baselines in
> [ADR-0003](../adr/0003-runtime-abstraction.md); exact protocol and adapter order
> remain TBD. Gemini is Excluded from v1.

- execution Runtime과 text-generation backend 분리
- Codex와 OpenCode 초기 지원 방향
- OpenCode local model / provided agent capability 차이 표현
- Gemini 제외
- adapter conformance tests
- native event와 normalized Telemetry 연결

---

## 8. MCP

### Verified upstream observations

현재 architecture는 Ouroboros가 MCP server와 client 양쪽 역할을 제공한다고
설명한다. CLI reference는 `mcp serve`와 authoring/execution handler의 관계를
설명하며, host/runtime/mode에 따라 in-process authoring과 runtime handoff가
다를 수 있음을 보여준다.

### Mission Control target

> Evidence: Session-confirmed + Verified. Decision: MCP as a control surface over the
> shared application boundary is an Accepted baseline in
> [ADR-0007](../adr/0007-mcp-is-control-surface.md); exact tool and transport schemas
> remain TBD.

Mission Control v1은 우선 MCP **server/control surface**에 집중한다.

- host가 Brief/Blueprint/Execute/Verify/Recover command/query를 호출
- Core가 durable Mission state와 Gate를 소유
- execution은 Runtime Adapter를 통해 별도 worker에 dispatch
- client disconnect와 Mission cancel을 구분
- CLI와 동일 application boundary 사용
- delegated worker의 recursive Mission Control call 차단

외부 MCP server의 tool을 execution capability로 소비하는 client/hub 기능은 핵심
흐름을 검증한 뒤 별도 RFC로 평가한다.

---

## 9. Persistence and Telemetry

### Verified upstream observations

현재 architecture는 append-only SQLite event store, replay, checkpoint, audit trail을
설명한다.

2026-08-07 baseline 조사에서 확인한 사실: upstream은 저장 대상을 **매체별로
분리**한다. Interview 상태는 JSON 파일이고, 실행 이벤트·세션 guard·brownfield
등록부는 SQLite(`ouroboros.db`)이며, workflow checkpoint는 별도 JSON 파일이다.
append-only 이벤트 스트림만으로는 동시 전이 선점을 막지 못해 compare-and-set
guard 테이블을 함께 둔다. 상세는
[PERSISTENCE_UPSTREAM_FINDINGS.md](./PERSISTENCE_UPSTREAM_FINDINGS.md)에 있다.

### Mission Control target

> Evidence: Session-confirmed + Inferred. Decision: durable Mission state and
> traceable Gate/attempt evidence are Accepted baselines; file store, SQLite, and
> event sourcing remain Proposed alternatives pending an ADR.

헌법이 요구하는 것은 특정 DB가 아니라 다음 의미다.

- chat session 밖의 durable Mission state
- attempt와 Gate의 추적 가능성
- 실패 evidence 보존
- resume 가능한 identity
- 원본 event와 normalized Telemetry 연결

Event sourcing/SQLite를 v1에 그대로 채택할지는 Architecture ADR로 결정한다.

---

## 10. What we intentionally do not copy first

다음은 upstream에 존재하더라도 Mission Control의 첫 vertical slice에 필수라고
간주하지 않는다.

- PAL/model cost router
- full Double Diamond execution
- dependency-aware parallel workers
- full event sourcing/checkpoint compression
- rich TUI/dashboard
- many Runtime backends
- plugin ecosystem
- multi-model consensus by default
- lateral persona system 전체
- secondary TODO loop

제외 이유는 가치가 없어서가 아니라 Core invariant를 검증하기 전에 complexity를
늘리지 않기 위해서다.

---

## 11. License note

baseline에서 확인한 upstream `LICENSE`는 MIT이며 copyright notice와 permission
notice를 copies 또는 substantial portions에 포함하도록 요구한다.

Mission Control은 현재 문서와 동작을 재구성하는 단계다. 원본 코드를 직접
복사하거나 상당 부분 포팅하기 전에는 다음을 수행한다.

- pinned commit의 LICENSE 재확인
- copied/derived 파일 목록 기록
- 필요한 copyright/permission notice 보존
- `THIRD_PARTY_NOTICES.md` 또는 적절한 고지 방식 결정

이 문단은 법률 자문이 아니라 프로젝트의 추적·고지 체크리스트다.
