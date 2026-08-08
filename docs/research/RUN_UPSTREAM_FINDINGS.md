# Run Upstream Findings — 진입 경로와 Telemetry provenance

> Checked: 2026-08-08. Baseline: `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
> (`~/.claude/plugins/marketplaces/ouroboros`).<br>
> Scope: [Open Questions §4](./OPEN_QUESTIONS.md)의 굵은 항목 — Execute 진입
> 경로 단일성과 Telemetry provenance — 에 한정한다. **Run Stage 전체 조사가
> 아니다.** work derivation, dependency, capability scope 조사는 Phase 3
> 시작 시 수행한다.
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

## 6. 조사하지 않은 것

- evaluate(Verify) 경로가 채점 전에 실행 lineage의 존재를 요구하는지 —
  [Open Questions §5](./OPEN_QUESTIONS.md)의 결정 재료이며 Phase 4 전에
  조사한다.
- work derivation(AC tree), dependency readiness, capability scope — Run
  Stage 본 조사(Phase 3 시작 시).
- `runtime` handle 직렬화(`to_persisted_dict`)의 정확한 필드 목록.

## Mission Control 함의

결정은 [ADR-0023](../adr/0023-execute-entry-and-provenance.md)에 있다. 요약:
upstream의 실패는 "관문이 있는 계층(skill)이 결과를 소유하지 않고, 결과를
소유한 계층(core)이 관문을 갖지 않는" 배치에서 왔다 (§12.3). Mission Control은
Brief·Blueprint에서 이미 관문을 state를 소유하는 application 계층에 두었으므로
(ADR-0011 Div.1, ADR-0019 §1), Execute도 같은 배치를 따르고 provenance를
선언 필드로 고정한다.
