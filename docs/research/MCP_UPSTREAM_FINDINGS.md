# MCP Upstream Findings — server 구조·tool 표면·비동기 job

> Checked: 2026-08-09. Baseline: `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
> (`~/.claude/plugins/marketplaces/ouroboros`).<br>
> Scope: [Open Questions §8](./OPEN_QUESTIONS.md) — tool 1:1 여부, request/response
> schema와 error envelope, host session·Mission ID 전달, async job/polling,
> disconnect·cancel·timeout, CLI/MCP parity.<br>
> Evidence level: 별도 표기 없으면 **Verified** (소스 확인). tool 목록은
> **Verified by execution** — 이 세션의 MCP 클라이언트가 노출하는 실물이다.

## 1. SDK는 adapter 뒤에 있다 — 우리 port/adapter 배치와 같은 축

upstream은 자기 **protocol 층**을 따로 두고 (`mcp/server/protocol.py`:
`ToolHandler`, `MCPToolDefinition`, `MCPToolResult`), MCP SDK v2 `MCPServer`에
붙이는 것은 `mcp/server/adapter.py` 하나다. tool handler는 SDK를 모른다.

핸들러 시그니처가 `Result`를 돌려준다 — 예외가 아니라 값이다:

```
ToolHandlerFunc = Callable[[dict], Awaitable[Result[MCPToolResult, MCPServerError]]]
```

**Mission Control 함의**: [ADR-0007](../adr/0007-mcp-is-control-surface.md)의
"MCP는 inbound adapter"와 정합한다. SDK 의존은 adapter 하나에 가둘 수 있다.

## 2. transport는 셋이다

`adapter.py:213` — `stdio`, `sse`, `streamable-http`. 문자열로 받아
`validate_transport()`가 정규화·검증한다(알 수 없으면 `ValueError`).

## 3. tool 이름은 handler가 소유하고 registry가 모은다

이름은 각 handler의 `definition` 속성에 리터럴로 있다 (예:
`evaluation_handlers.py:420` `name="ouroboros_evaluate"`). `ToolRegistry`가
등록·조회·호출을 맡는다 (`tools/registry.py`).

접두사는 `ouroboros_`로 전역에 하나다 — host의 도구 목록에서 출처가 이름만으로
구분된다.

## 4. tool은 CLI 명령과 1:1이 **아니다**

두 가지가 확인된다.

**(a) MCP에만 있는 것이 있다.** `ooo evaluate` CLI 명령은 **존재하지 않는다**.
`cli/commands/`의 전부는 auto·cancel·cleanup·codex·config·detect·dispatch·
harness·init·job·mcp·mcp_doctor·plugin·pm·qa·resume·run·seed·setup·status·
tui·uninstall·workflow_ir·zcode다. evaluate는 MCP tool과 `ooo auto` 안에서만
호출된다.

**(b) 공유 구현이 `mcp/tools/`에 있고 CLI가 그것을 부른다.** 방향이 우리
예상과 반대다:

- `cli/commands/qa.py:16` → `from ouroboros.mcp.tools.qa import QAHandler`
- `cli/commands/auto.py:76` → `from ouroboros.mcp.tools.evaluation_handlers import LateralThinkHandler`

즉 upstream에서 "표면은 공유 핸들러에 위임한다"([CLI findings §2](./CLI_UPSTREAM_FINDINGS.md))의
**공유 핸들러가 MCP tool handler**다. CLI가 얇은 이유가 여기 있다.

**Mission Control 함의 — 등록해야 할 층위 차이.**
[ADR-0038](../adr/0038-mcx-cli-surface-contract.md) §1은 "CLI와 MCP가 같은
application service와 같은 composition을 공유"한다고 했고, 그 자리에 "upstream
정렬: 표면은 공유 핸들러 위임"이라고 적었다. **행동은 정렬이지만 공유 지점의
층이 다르다** — upstream은 `mcp/tools/`, 우리는 `application/`. 우리 배치가
MCP를 지우고도 CLI가 서는 반면 upstream은 그렇지 않다. Phase 7 ADR에서
divergence로 등록한다.

## 5. 비동기는 **tool 쌍 + job 조회 tool**이다

같은 작업에 동기·비동기 두 tool이 있다. 이 세션의 MCP 클라이언트가 노출하는
실물 목록(Verified by execution):

| 동기 | 비동기(fire-and-forget) |
|---|---|
| `ouroboros_evaluate` | `ouroboros_start_evaluate` |
| `ouroboros_execute_seed` | `ouroboros_start_execute_seed` |
| `ouroboros_evolve_step` | `ouroboros_start_evolve_step` |
| `ouroboros_auto` | `ouroboros_start_auto` |
| `ouroboros_ralph` | `ouroboros_start_ralph` |

조회·제어는 별도 tool이다: `ouroboros_job_status`, `ouroboros_job_result`,
`ouroboros_job_wait`, `ouroboros_cancel_job`, `ouroboros_cancel_execution`.

`Start*` 핸들러는 전부 같은 4단 파이프라인을 지난다 (`tools/background.py:1-33`):

1. `allocate_job_id()` — job id를 **먼저** 확보한다.
2. `should_cancel()` 사전 가드 — 큐에서 취소된 job은 시작하지 않고 terminal
   *cancelled*를 돌려준다.
3. `run_with_agent_process(process_id=…, cancel_key="mcp_job:{job_id}")` —
   실행을 취소 마커에 묶는다.
4. `start_job(…)` — 큐에 넣고 snapshot을 돌려준다.

이 헬퍼가 만들어진 이유가 기록되어 있다: 두 핸들러가 `process_id`/`cancel_key`
없이 감싸는 바람에 **"재시작 후에도 보이는 취소" 계약이 조용히 깨져 있었다.**
취소 마커는 디스크에 쓰였는데 그 프로세스가 그것을 관측할 수 없었다.

## 6. job 상태 어휘는 일곱이다

`mcp/job_manager.py:47-57`:

```
queued, running, cancel_requested, completed, failed, cancelled, interrupted
```

`cancel_requested`와 `cancelled`가 **분리**되어 있고, `interrupted`가 따로
있다 — 요청된 취소, 실제로 취소됨, 그리고 (프로세스 죽음 등으로) 중단됨이
서로 다른 사실이다.

`JobSnapshot`은 `job_id`, `job_type`, `status`, `message`, `created_at`,
`updated_at`, `cursor`(스트리밍 위치), `links`(session/execution/lineage id)를
담는다.

## 7. 응답 envelope

`mcp/types.py:363-382` `MCPToolResult`:

- `content` — text/image/resource 항목들 (사람이 읽는 자리)
- `is_error: bool` — 오류를 **예외가 아니라 플래그**로 표현
- `meta: JSONObject` — 부가 정보 (host_action 같은 지시가 여기 실린다)
- `structured_content` — MCP 스펙의 `structuredContent`. 기계가 읽는 payload.
  주석의 예시가 그대로 §12의 사실과 맞물린다 — `codex mcp-server`의 `codex`
  호출이 `{"threadId": …}`를 여기 돌려준다
- `result_type: str = "complete"` — 완료가 아닌 결과(job 접수 등)를 구분

## 8. 서버에 보안 계층이 따로 있다

`mcp/server/security.py`: 인증(`none`/`api_key`/`bearer_token`)과 tool 단위
권한(`read`/`write`/`execute`/`admin`), 입력 검증, rate limiting.

**Mission Control 함의**: 우리 v1은 로컬 stdio 단일 사용자라 인증 대응물이
필요한지가 결정 사항이다. 권한 축은 [ADR-0004](../adr/0004-stage-scoped-minimum-capability.md)
(Stage별 최소 capability)와 다른 축이다 — 그것은 worker의 권한이고 이것은
호출자의 권한이다.

## 9. 조사하지 않은 것

- `MCPServerError` 계층과 오류가 host에게 보이는 정확한 형태.
- host session id·project dir가 요청에서 어떻게 전달되는지
  (`mcp/server/project_dir.py`는 존재만 확인).
- resource(URI) 표면의 전체 목록. redaction만
  [SECURITY findings §5](./SECURITY_UPSTREAM_FINDINGS.md)에서 확인했다.
- `ouroboros_job_wait`의 대기 상한과 disconnect 시 동작.
- CLI/MCP parity test가 upstream에 있는지.

## 10. Mission Control 결정 재료

[Open Questions §8](./OPEN_QUESTIONS.md)의 미결에 대응시키면:

| 미결 | upstream 사실 | 우리가 정해야 할 것 |
|---|---|---|
| tool 1:1 여부 | 1:1 아님. MCP 전용 tool이 있고 CLI가 MCP 핸들러를 부름 | 우리는 CLI 24명령이 이미 있다 — tool을 그 위에 1:1로 얹을지, 묶을지 |
| request/response schema | `MCPToolResult`(content·is_error·meta·structured_content·result_type) | 우리 exit code 0/1/2를 무엇으로 옮길지 — 특히 **HOLD(2)는 오류가 아니다** |
| host session·Mission ID | `JobLinks`에 session/execution/lineage id | `--mission` 대응물과 `current_mission` 포인터의 MCP 대응 |
| async job | 동기·비동기 tool 쌍 + job 조회 tool 4개, 상태 7종 | 우리 명령 중 장기인 것은 execute·verify semantic. 쌍을 둘지 |
| disconnect/cancel/timeout | `cancel_requested`≠`cancelled`≠`interrupted`, 취소 마커는 디스크 | 우리 원장의 "짝 없는 start"와 같은 축 — 통합할지 |
| CLI/MCP parity | 미조사 (§9) | parity test 전략 |
