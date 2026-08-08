# Run Upstream Findings — 진입 경로, provenance, work 파생

> Checked: 2026-08-08. Baseline: `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
> (`~/.claude/plugins/marketplaces/ouroboros`).<br>
> Scope: §1~§6은 [Open Questions §4](./OPEN_QUESTIONS.md)의 굵은 항목(진입
> 경로·provenance), §7~§10은 같은 날 후속 조사(work 파생·dependency·capability
> — Execute 첫 slice의 재료)다.
> Evidence level: 별도 표기 없으면 **Verified** (소스 확인).

## 1. Stage→Runtime 바인딩 테이블 — 닫힌 enum과 3단 해석 규칙

`orchestrator_stage.py`가 바인딩 테이블 primitive다.

- Stage는 **닫힌 enum** 4개: interview / execute / evaluate / reflect. 멤버
  추가는 정당화가 필요한 명시적 PR이다 (`:44-56`). per-handler 항목(qa_judge
  등)이 테이블로 번지는 것을 의도적으로 막는다 — 그런 것은 AgentProcess
  내부 소관이라고 명시한다 (`:14-18`).
- 해석 규칙은 모듈 docstring에 고정되어 있다 (`:23-31`):
  `stages.get(stage)` → `default` → 현재 orchestrator runtime_backend.
- config 검증은 fail-fast다. 알 수 없는 stage key는 로드 시 거부되고
  (`config/models.py:525-538`), config 파일이 존재하는데 로드에 실패하면
  기본값으로 조용히 넘어가지 않고 예외를 올린다 — "operator의 라우팅 실수가
  조용히 fallback runtime으로 재라우팅되면 안 된다"
  (`auto/runtime_routing.py:55-66` 주석).

**조회 지점은 세 곳이다**: `ooo auto`(`auto/runtime_routing.py:76`), MCP 서버
adapter(`mcp/server/adapter.py:1707`), config loader의 LLM 완성 fallback
(`config/loader.py:1696`). 즉 테이블은 **호출된 파이프라인 안에서만** 읽힌다.

## 2. Python 쪽 실행 진입은 OrchestratorRunner로 수렴한다

`OrchestratorRunner`의 진입점: `cli/commands/run.py`(`ooo run`),
`mcp/tools/execution_handlers.py`(MCP execute job), auto 파이프라인. Python
프로세스 안에서 AC를 실행하는 두 번째 경로는 없다.

[§12.3의 우회](./SEED_UPSTREAM_FINDINGS.md)는 Python 안의 두 번째 경로가
아니라 **Python 밖**이다 — host 세션(skill 계층)이 자기 편집 도구로 작업하면
orchestrator 프로세스가 아예 뜨지 않으므로, 코어의 어떤 코드도 실행되지
않는다. 코어가 자기 코드로 이 우회를 탐지하는 것은 구조적으로 불가능하다.
남는 방어선은 "코어를 거치지 않은 작업은 ledger에 아무 기록이 없다"는 사실
뿐인데, upstream에는 그 부재를 검사하는 gate가 없다 (§5 참조).

## 3. 경로 안에서의 바인딩 강제 — AC 실행 capsule

경로 안은 느슨하지 않다. `ac_execution_capsule.py`가 AC 하나당 실행 경계를
강제한다 (`:820-870`).

- 새 capsule은 provider 세션 연속성 식별자를 **상속할 수 없다** — fresh
  capsule에 native_session_id 등이 있으면 ValueError.
- 재개(resume)는 같은 AC attempt로만 가능하고, 재개된 handle은
  workspace·backend·approval mode가 capsule의 권한과 일치해야 한다.
  `expected_backend` 불일치는 "runtime handle backend disagrees with the AC
  capsule authority"로 거부된다 (`:851-852`).
- handle metadata에 capsule fingerprint가 박히고, 다른 capsule의 fingerprint가
  있으면 거부된다 (`:858-860`).

## 4. Telemetry provenance — 경로 안에서는 기록된다, payload로

`ac_runtime_handle_manager.py`의 `_emit_ac_runtime_event`가 AC 단위 lifecycle
이벤트(`execution.session.started/resumed/completed/failed`)를 지속하며,
payload에 다음이 들어간다:

- **`runtime_backend`** — 실행한 backend 이름 (`runtime_handle.backend`)
- **`runtime`** — runtime handle 전체의 직렬화 (`to_persisted_dict()`)
- `ac_id`, `acceptance_criterion`(원문), `semantic_ac_key`(identity metadata
  경유), `execution_id`, `session_scope_id`/`session_attempt_id`,
  `retry_attempt`/`attempt_number`, `success`/`result_summary`/`error`
- 성공 시 `execution.ac.completed` 이벤트를 추가로 남긴다.

control 계열 session-signal 이벤트도 `runtime_backend`를 bounded correlation
으로 담는다 (`events/session_signal.py:46-73`).

**단, 전부 payload 안이다.** events 테이블 스키마에는 actor/runtime 컬럼이
없다 — 컬럼은 id, aggregate_type, aggregate_id, event_type, payload(JSON),
timestamp, consensus_id뿐이다 (`persistence/schema.py:34-63`). provenance는
스키마 계약이 아니라 emitter의 관례다.

## 5. 경로 밖 작업을 잡는 장치는 없다

persistence의 guard 테이블들(`session_terminal_guards`,
`session_start_guards`, `ac_acceptance_guards`, `lineage_advancement_claims` —
`persistence/schema.py:66-140`)은 전부 **경로 안의 경쟁 상태**(터미널 전이
CAS, 시작 경쟁, 최종 수용 one-winner)를 직렬화한다. "수용되는 작업에는 실행
이벤트가 있어야 한다"는 검사는 어디에도 없다.

이것이 §12.3 관측의 소스 측 확인이다: config는 매핑을 알고, orchestrator는
호출될 때 매핑을 읽고, 세션은 매핑의 존재를 모른다. 세 계층 중 누구도 "실행이
경로 밖에서 일어났다"를 알 수 없으며, 경고도 Telemetry도 Gate도 없다.

## 7. Work 파생 — 실행 단위는 AC 자체다

seed의 `acceptance_criteria` 목록이 곧 작업 목록이다. AC 하나가 실행 capsule
하나로 dispatch되며(§3), 별도의 "task" 개념으로 변환되지 않는다. 실행 내용은
seed에서 만든 system prompt(전략은 `task_type`으로 선택,
`runner.py:500-507`)와 AC 문장, 그리고 도구 목록이다.

**분해(decomposition)는 기본 경로가 아니라 예외 경로다.**

- 트리거는 두 곳뿐이다 — `PREFLIGHT`(실행 전 평가)와 `BOUNCE`(실패 후,
  원인 enum: TOO_BIG/BAD_SPEC/ENVIRONMENT/MODEL/UNKNOWN)
  (`decomposition_policy.py:73-117`).
- 처분은 ATOMIC / SPLIT / UNKNOWN / ESCALATED. 즉 upstream의 기본 가정은
  "AC는 그대로 실행 가능"이고, 분해는 판정을 거친 예외다 — 우리
  [Execute Guide](../07_EXECUTE.md) §6.2의 atomic-first가 이것이다.
- 한도는 상수로 고정: 자식 2~5개, 라이브 깊이 기본 2, durable replay 한도
  깊이 4(최대 780 노드), repair 1회
  (`decomposition_policy.py:19-32`, `decomposition_limits.py`).
- 분해된 자식은 parent/root node id로 원 AC에 추적된다
  (`evidence/runtime_metadata.py`의 ownership metadata 키:
  `parent_node_id`, `root_ac_index`, `node_id` 등).

## 8. Dependency — 선언 ∪ LLM 추론, ready는 결정적 토폴로지

`dependency_analyzer.py` (902줄). 두 신호를 합집합한다.

- **선언(구조) 신호**: AC metadata의 `depends_on`/`blocked_by`/`requires` 류
  키, `provides` alias, 공유 runtime 자원 claim(write 충돌 시 직렬화)
  (`:24-56`).
- **LLM 추론 pass**: adapter가 있으면 AC 문장들에서 의존을 추론해 선언 신호에
  **더한다**. LLM 실패는 분석 실패가 아니다 — `structured_fallback`으로
  선언 신호만으로 진행한다 (`:408-424`).

ready 계산은 결정적이다 (`_compute_execution_levels`, `:645-687`):
in-degree 0인 노드들이 한 level이 되는 토폴로지 워크. **순환이 발견되면 hard
fail이 아니라 경고 후 남은 전부를 같은 level로 실행한다** (`:672-678`).
serial-only 제약(metadata 플래그, 자원 write 충돌)은 level을 쪼개 자기만의
stage를 만든다. AC가 하나면 분석 없이 단일 level이다 (`:397-400`).

실행 계획은 `StagedExecutionPlan` — stage의 순차 나열이고 stage 안은 병렬
가능(`ExecutionStage.is_parallel`).

### 8.1 병렬성 구분은 Seed 생성 시점이 아니라 Run 시점이다

"AC를 만들 때 병렬 가능 여부를 구분하는가"를 확인한 결과 — **아니다**.
Seed 쪽에는 그 축이 아예 없고, 구분은 전부 Run 시점 파생이다.

- **AC 스키마에 dependency·병렬 필드가 없다.** `AcceptanceCriterionSpec`의
  필드는 description / semantic_ac_key / verify_command / expected_artifacts /
  output_assertion / investment 전부다 (`core/seed.py:452-476`). metadata
  dict도 없다. pydantic 기본 동작(extra ignore)이라 seed YAML의 AC dict에
  `depends_on`을 손으로 써넣어도 파싱 시 조용히 소실된다.
- **Seed 생성 프롬프트도 요구하지 않는다.** seed-architect의 AC 출력 계약은
  `description`/`verify`/`artifacts`/`expect` 4필드 고정이고
  (`agents/seed-architect.md` §3), granularity contract가 이유를 명시한다 —
  "deciding means is the execution engine's work at runtime, and it decides
  them better with the outcome in hand than with your guess at the path".
  순서·경로의 사전 계획을 Seed의 일에서 의도적으로 제외한 것이다.
- **위 선언(구조) 신호 채널은 seed 경로에서 생산자가 없다.** runner는
  `seed.acceptance_criteria`를 그대로 넘기고 (`runner.py:10343`),
  `_normalize_specs`가 metadata를 빈 채로 감싼다
  (`dependency_analyzer.py:458`). `ACDependencySpec`을 analyzer 밖에서
  만드는 곳은 src 전체에 없다. 즉 `depends_on`/serial 류 metadata 키는
  API로는 존재하지만 v0.50.8의 Seed→Run 경로에서는 **실효 신호가 Run 시점
  LLM 추론 + 토폴로지 계층화뿐**이다.

## 9. Capability scope — dispatch 계약의 digest 바인딩

dispatch마다 넘어가는 것: prompt, **tools 목록**, system prompt, workspace
(`cwd`), approval mode (`leaf_dispatcher.py:363-380`,
`adapter.py RuntimeHandle`). 상한 상수: 전략 도구 256개, 허용 도구 1,024개
등 (`runner.py:224-229`).

`authority_scope`는 권한 목록 자체가 아니라 **권한을 낳는 모든 입력의 sha256
fingerprint**다 — base_scope + dispatch_contract + execution_policy
(`ac_execution_capsule.py:79-95`). capsule에 digest로 박혀 재개 시 불일치를
거부하는 데 쓰인다(§3). 프롬프트에 싣지 않는 context는
`ACContextReference`(workspace/seed/dependency/artifact/gate 5종)로 참조만
전달하고, 예산이 고정되어 있다 — 참조 256개, context 12,000자
(`ac_execution_capsule.py:30-33`, `:117-130`).

## 10. 조사하지 않은 것

- evaluate(Verify) 경로가 채점 전에 실행 lineage의 존재를 요구하는지 —
  [Open Questions §5](./OPEN_QUESTIONS.md)의 결정 재료이며 Phase 4 전에
  조사한다.
- `runtime` handle 직렬화(`to_persisted_dict`)의 정확한 필드 목록.
- decomposition의 SPLIT 판정을 실제로 누가 내리는지(LLM 프롬프트 계약)와
  preflight 평가의 기준 — 분해를 도입할 때 조사한다.
- `ooo run`의 재개(resume)·취소 계약 — Runtime adapter(Phase 5)에서 조사한다.

## 11. 후속 조사 (2026-08-09) — `executed_unverified` 실물과 라우팅 대상

[Open Questions §1](./OPEN_QUESTIONS.md)에 미조사로 남아 있던 두 항목을
닫는다. Evidence level: **Verified** (소스 확인).

### 11.1 `executed_unverified`는 upstream에 실재한다

우리 슬로건("Executed is not verified")과 `EXECUTED_UNVERIFIED` 상태의
upstream 대응물이 확인되지 않은 채 Phase 3을 지나갔었다. 실물은 두 곳이다.

- `mcp/job_manager.py:249-258` `_run_only_verification_meta` — docstring이
  목적을 그대로 말한다: *"Metadata that keeps execution completion separate
  from formal evaluation."* 필드는 `evaluated: False`,
  `verification_status: "executed_unverified"`,
  `formal_evaluation_required: True`, `next_step: "ooo evaluate <session_id>"`.
- `auto/pipeline.py:4650-4676` — 산출물 결과를 orchestration status와 **분리**
  분류한다: `complete_unverified` / `complete_verified` /
  `partial_artifact_generated`. docstring: *"This companion value prevents
  final renderers from implying completion."*

**함의**: 축은 정렬이다 — 실행 완료와 형식 평가의 분리, 그리고 "다음 단계는
evaluate"라는 지시까지 같다. 차이는 두 가지이며 둘 다 우리 쪽이 더 강하다.

| 축 | upstream | Mission Control |
|---|---|---|
| 표현 지위 | job 메타데이터·렌더링 힌트 (status는 별도로 authoritative) | Attempt의 1급 상태 (ADR-0023) |
| 미평가 작업의 차단 | 없음 — evaluate는 lineage를 요구하지 않는다 (§5, EVALUATE findings §2) | Verify 진입이 Execute Gate `CLEAR`를 요구 (ADR-0026, 등록된 divergence) |

### 11.2 §1 라우팅 테이블은 실행뿐 아니라 LLM 완성도 라우팅한다

§1의 조회 지점 세 곳 중 `config/loader.py`의 성격을 확정했다
(`:1685-1707`). 해석 순서는 `explicit_backend` → per-stage
(`runtime_profile.stages`) → `runtime_profile.default` → legacy
`llm.backend`/env override → orchestrator default agent runtime이며, 주석이
*"Per-stage routing stays authoritative"*라고 못박는다.

`auto/runtime_routing.py:40-43`은 반대편을 말한다 — `--runtime` override는
*"one explicit runtime drives both **authoring and execution**"*.

**함의**: upstream은 **stage 하나에 backend 하나**이고, 그 backend가 그
stage의 텍스트 생성과 실행을 모두 맡는다. 우리처럼 한 Stage 안에서 텍스트
lane(Claude)과 실행 lane(Codex)을 다른 vendor로 쪼개는 구조는 upstream에
대응물이 없다 — [ADR-0039](../adr/0039-stage-runtime-routing-table.md)에
divergence로 등록했다.

## Mission Control 함의

결정은 [ADR-0023](../adr/0023-execute-entry-and-provenance.md)에 있다. 요약:
upstream의 실패는 "관문이 있는 계층(skill)이 결과를 소유하지 않고, 결과를
소유한 계층(core)이 관문을 갖지 않는" 배치에서 왔다 (§12.3). Mission Control은
Brief·Blueprint에서 이미 관문을 state를 소유하는 application 계층에 두었으므로
(ADR-0011 Div.1, ADR-0019 §1), Execute도 같은 배치를 따르고 provenance를
선언 필드로 고정한다.
