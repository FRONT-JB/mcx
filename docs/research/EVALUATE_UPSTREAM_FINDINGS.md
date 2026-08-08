# Evaluate Upstream Findings — lineage 요구와 telemetry 실물

> Checked: 2026-08-08. Baseline: `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
> (`~/.claude/plugins/marketplaces/ouroboros`).<br>
> Scope: [Open Questions §5·§9](./OPEN_QUESTIONS.md)의 결정 재료 —
> [RUN_UPSTREAM_FINDINGS §10](./RUN_UPSTREAM_FINDINGS.md)이 미조사로 남긴
> "evaluate가 채점 전에 실행 lineage의 존재를 요구하는지"와, telemetry
> event/report/bundle의 실제 구조.<br>
> Evidence level: 별도 표기 없으면 **Verified** (소스 확인).

## 1. evaluate 진입 경로 — 파이프라인은 셋, runner는 아니다

`EvaluationPipeline`(3단: mechanical → semantic → consensus,
`evaluation/pipeline.py`)의 호출자는 MCP evaluate tool
(`mcp/tools/evaluation_handlers.py`), evolve 루프(`evolution/loop.py`),
MCP server adapter 세 곳이다. **`OrchestratorRunner`는 평가 파이프라인을
부르지 않는다** — `ooo run`은 실행 직후 mechanical 증거 묶음만 직접 생성한다
(`cli/commands/run.py:40, :785` → §4).

## 2. evaluate는 실행 lineage를 요구하지 않는다 (§5의 답)

어느 층에도 "채점 대상이 기록된 실행에서 나왔는가"를 검사하는 gate가 없다.

- **입력 계약부터 문자열이다.** `EvaluationContext.execution_id`는 검증 없는
  식별자이고 `artifact`는 호출자 제공 텍스트다 (`evaluation/models.py:335-343`).
- **MCP 경로의 lineage 조회는 전부 best-effort다.** `execution_id`에는 MCP
  session id가 들어가고(`evaluation_handlers.py:758-759`), session 재구성은
  실패해도 `pass`(`:633-641` "Best-effort enrichment"), seed 파싱 실패도
  non-fatal(`:574-577`), 실행 주체 조회 `_resolve_executor_backend`는 문서화된
  best-effort다 — "Any failure returns `None` — evaluation then behaves exactly
  as before" (`:171-196`). 실행 이벤트가 하나도 없어도 평가는 그대로 진행된다.
- **닫힌 루프의 lineage는 검사가 아니라 배선이다.** evolve 루프는
  `evaluator(current_seed, execution_output)`으로 실행 단계의 출력을 직접
  넘긴다 (`evolution/loop.py:1943`). 구조상 성립할 뿐 어디에도 존재 검증이
  없고, 평가 실패는 경고 후 `evaluation_summary=None`으로 계속 진행한다
  (`:1947-1951`).
- **평가 결과 이벤트도 연결을 강제하지 않는다.** `evaluation.pipeline.completed`
  는 `aggregate_id=execution_id`로 남지만(`events/evaluation.py:242-251`), 그
  id가 실행 이벤트와 대응하는지 확인하는 코드는 없다.

함의: [SEED_UPSTREAM_FINDINGS §12.3](./SEED_UPSTREAM_FINDINGS.md)의 사고(경로
밖 작업이 평가·수용됨)는 이 배치의 직접 결과다. 열린 surface(MCP)는 임의
artifact 평가를 **의도적으로** 허용하는 형태이며, 기록 없는 작업을 걸러내는
것은 upstream 어디에도 없다.

## 3. 실행 중 telemetry — event store 라이브 append (§9 재료, event 층)

실행 스트림의 매 메시지가 `project_runtime_message`로 정규화되고
(`orchestrator/leaf_dispatcher.py:492`), 실행 **중에** event store로 직접
append된다.

- **이벤트 컬럼**: `id` / `type` / `timestamp` / `aggregate_type` /
  `aggregate_id` / `data`(JSON payload) / `consensus_id` / `event_version`
  (`events/base.py:62-92`). actor 컬럼 없음 —
  [RUN_UPSTREAM_FINDINGS §5]와 일치. "언제 시작·종료했는가"는 이벤트
  `timestamp`가 답한다.
- **lifecycle 이벤트 5종**: `execution.session.{started,resumed,recovered,
  completed,failed}` (`orchestrator/evidence/runtime_metadata.py:5-17`).
- **lifecycle payload 실물** (`orchestrator/ac_runtime_handle_manager.py:1386-1451`):
  ownership metadata(node/parent/root id, depth, path, ordinal 등 —
  RUN §7) + `ac_id` + **AC 원문**(`acceptance_criterion`) + `retry_attempt` +
  `attempt_number` + `execution_id` + session id 3종 + `server_session_id` +
  `runtime_backend` + **runtime handle 전체 직렬화**(`runtime`) + `success` +
  `result_summary` + `error` + `turn_id`/`turn_number` + `tool_catalog`.
- **스트림 중 이벤트**: `session.tool.called`(도구 호출마다), session progress
  (`leaf_dispatcher.py:525-542`).

## 4. mechanical 증거 — report 층의 실물 (§9 재료)

`evaluation/verification_artifacts.py` — "agent-authored final summary에
의존하는 대신" 저장소의 mechanical check를 직접 실행해 raw 출력을 보존하는
runtime-neutral 경로 (모듈 docstring). `ooo run`이 post-run에 직접 생성한다
(`cli/commands/run.py:785`).

- **`VerificationRunArtifact`** (`:34-48`): `check_type`, `command`,
  `exit_code`, `passed`, `timed_out`, `stdout_path`/`stderr_path`(보존 위치),
  `stdout_excerpt`/`stderr_excerpt`(head 500 / tail 2,000자 — `:27-28`),
  `final_outcome`.
- **`VerificationArtifacts`** (`:50-62`): 렌더된 `artifact`(QA judge용 요약) +
  `reference` + `artifact_dir` + `manifest_path` + **`changed_files`**(git
  기반) + `runs`(위 레코드들) + git 상태 가용성.
- 보존 위치는 `~/.ouroboros/artifacts` 파일 트리 + manifest (`:26`).

즉 §9의 "어떤 명령·exit code", "stdout/stderr는 어디에", "어떤 파일이
변경되었는가"의 upstream 대응물이 이 두 구조다.

## 5. 평가 입력 bundle (§9 재료)

`ArtifactBundle` — `files`(수집된 파일들) + `text_summary` + `total_chars`
(`evaluation/models.py:298-312`). working_dir 스캔으로 수집하며, MCP 경로는
호출자 artifact 텍스트를 파일(`.ouroboros_eval_artifact.md`)로 써서 collector가
줍게 한다 (`evaluation_handlers.py:690-707`). "semantic evaluator에게 agent
요약이 아니라 실제 소스를 준다"가 목적이다 (`models.py:301-302`).

## 6. 평가 자체의 이벤트

stage1/2/3 `started`/`completed`, `consensus.triggered`,
`evaluation.pipeline.completed` — `aggregate_type="evaluation"`,
`aggregate_id=execution_id`, payload에 `final_approved`/`highest_stage`/
`failure_reason` (`events/evaluation.py`).

## 7. RuntimeHandle 직렬화 (ADR-0025 미확인 항목 해소)

`to_persisted_dict` (`orchestrator/adapter.py:659-680`): `backend`, `kind`,
`native_session_id`, `cwd`, `approval_mode`, `metadata`. OpenCode는 재접속
가능한 최소형(위 6필드, metadata는 허용 키만), 그 외 backend는 `to_dict()`
전체다.

## 8. 조사하지 않은 것

- consensus(3단계) 내부의 reviewer 독립성 규칙 상세 — Phase 4 semantic 설계
  시 조사한다.
- `mechanical.toml`의 스키마와 detector의 명령 발견 규칙 — Phase 4 mechanical
  구현 시 조사한다 ([Open Questions §5](./OPEN_QUESTIONS.md) 첫 항목).

## Mission Control 함의

결정은 [ADR-0026](../adr/0026-verify-entry-requires-lineage.md)(§5 — upstream과
달리 Verify 진입이 Execute Gate `CLEAR`를 요구)과
[ADR-0027](../adr/0027-telemetry-layers-and-v1-schema.md)(§9 — 세 층의 소유·
시점과 report 층 v1 스키마)에 있다.
