# Event Layer Upstream Findings — canonical event 층과 스트리밍 생산자

> Checked: 2026-08-10. Baseline: `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
> (`~/.claude/plugins/marketplaces/ouroboros`).<br>
> Scope: Phase 5 시한을 무처분 도과한
> [ADR-0027](../adr/0027-telemetry-layers-and-v1-schema.md) §3 —
> *"canonical event 층 + 스트리밍 생산자"*.<br>
> Evidence level: 별도 표기 없으면 **Verified** (소스 확인).

## 0. 조사가 뒤집은 것 — 로드맵의 두 근거 중 하나는 이미 소멸했다

Phase 9 로드맵은 이 항목을 여기 둔 이유를 둘로 적었다:

> *"실사용에서야 긴 실행의 진행 표시가 실수요가 되고, 바로 위 `changed_files`가
> **같은 생산자를 요구한다**"*

**두 번째는 더 이상 참이 아니다.** `changed_files`는 2026-08-09에
[ADR-0048](../adr/0048-changed-files-collection.md)로 확정·구현됐고, 생산자는
event가 아니라 `git status --porcelain=v1 -z` 한 번이다
(`adapters/workspace/changes.py`). event 층은 한 줄도 쓰이지 않았다.

즉 이 항목을 지탱하는 근거는 **진행 표시 하나만** 남았다. 그리고 §3이 그
하나마저 event 층을 요구하지 않는다는 것을 upstream 실물로 보여준다.

## 1. upstream에 층은 **둘**이고, 이름 하나가 둘을 가리고 있었다

*"canonical event 층"* 이라는 우리 이름은 upstream에서 서로 다른 두 물건에
대응한다. 이것을 분리하지 않으면 하나를 이유로 다른 하나를 짓게 된다.

| 우리가 부르던 것 | upstream 실물 | 성격 | 위치 |
|---|---|---|---|
| **정규화(projection)** | `ProjectedRuntimeMessage` | 순수 변환. 저장하지 않는다 | `orchestrator/runtime_message_projection.py:52-73` |
| **저장(event store)** | `BaseEvent` + `EventStore` | 영속 계층. SQLite | `events/base.py:62-92`, `persistence/event_store.py:574` |

### 1.1 정규화 — vendor 메시지를 backend-neutral 형태로

```text
ProjectedRuntimeMessage  (frozen, slots)
  message_type      # tool / tool_result / system / …
  content
  tool_name, tool_input, tool_result
  thinking
  runtime_signal, runtime_status
  runtime_metadata
  .is_tool_call     # message_type == "tool" and tool_name is not None
  .is_tool_result
```

docstring이 존재 이유를 말한다 — *"Backend-neutral projection used by workflow
state and event emitters."* (`:53`)

vendor별 이벤트 이름을 **집합으로** 흡수한다 (`:20-48`) —
`session.started`/`thread.started`를 같은 신호로 접고,
`result.completed`/`run.completed`/`turn.completed` 등 5종을 완료 하나로 접는다.
Codex의 `thread.started`와 OpenCode의 `session.started`가 같은 자리에 있는 것이
이 층의 몫이다.

### 1.2 저장 — 이벤트 소싱 테이블

```text
BaseEvent
  id, type, timestamp, aggregate_type, aggregate_id,
  data(JSON), consensus_id, event_version
```

`EventStore`는 SQLAlchemy Core + aiosqlite다 (`event_store.py:574-580`).
`to_db_dict`가 저장 직전 `sanitize_event_data_for_persistence`로 `raw_*`,
`subscribed_*`, `event_payload*` 계열 키를 **재귀적으로 제거**한다
(`base.py:15-58`) — 우리 [ADR-0040](../adr/0040-secret-redaction-boundaries.md)
§2의 replay-unsafe 거부와 같은 축이며, upstream 쪽은 거부가 아니라 삭제다.

## 2. 스트리밍 생산자의 실물 — 메시지 루프가 하는 일 여섯

`orchestrator/leaf_dispatcher.py:470-560`. 런타임 메시지 하나마다:

1. **상태 누적** — `state.messages.append`, `message_count`, 실행 카운터
2. **heartbeat** — 30초마다 (`HEARTBEAT_INTERVAL_SECONDS = 30.0`,
   `evidence/runtime_metadata.py:77`). 메시지 흐름에 얹어 보낸다
   (*"RC1: Emit heartbeat piggybacking on message flow"*)
3. **정규화** — `projected = project_runtime_message(message)`
4. **이벤트 append** — `session.tool.called`(도구 호출마다),
   session progress(조건부), lifecycle(세션 id를 처음 알게 된 순간 1회)
5. **콘솔 출력** — `console.print(f"{indent}[yellow]{label} → {tool_detail}")`
6. **stall 시한 갱신** — 도구 호출이면 deadline을 밀어준다
   (*"RC6: Tool invocations prove liveness"*)

진행 이벤트의 발행 조건 (`parallel_executor.py:7713-7729`):

```python
message.is_final or messages_processed % 10 == 0 or projected.is_tool_call
or projected.thinking is not None or message.type == "system"
or runtime_backend == "opencode" or projected.is_tool_result
```

전량이 아니다 — **도구 호출·사고·최종·10건마다**로 솎아낸다.

## 3. **진행 표시는 event 층의 소비자가 아니다** — 이 조사의 결론

§2의 5번을 다시 본다. 콘솔 출력은 `_event_store`를 **읽지 않는다.** 같은
루프 안에서 `projected`를 직접 포맷해 찍는다. event append(4번)와 화면
출력(5번)은 **나란히 있는 두 동작**이지 생산자–소비자가 아니다.

`ooo run`도 마찬가지다 — `cli/commands/run.py`에서 `EventStore`는 **생성해
아래로 넘겨주는 대상**일 뿐(`:668-730`), 이벤트를 되읽어 표시하는 코드가 없다.

함의: **긴 실행의 진행 표시를 얻는 데 event 저장 층은 필요하지 않다.**
필요한 것은 §1.1의 정규화와 §2의 루프 훅이다.

## 4. 그럼 event store는 누가 읽는가 — 네 소비자, 우리에겐 셋이 없다

전수 확인(`event_store.{replay,query_events,get_events_after,…}` 호출부):

| 소비자 | 무엇을 위해 | 우리에게 |
|---|---|---|
| **TUI** (`tui/app.py:493`) | rowid 커서로 폴링해 HUD 갱신 | **없다** (TUI 없음) |
| **MCP job_manager** (`job_manager.py` 10여 곳) | 비동기 job의 상태·진행 | **다른 방식으로 있다** — §5 |
| **auto/listeners** (`listeners.py:319`) | Ralph job 이벤트를 auto 상태로 미러 | **없다** (auto 없음) |
| **replay/resume** (`agent_process.py:404`) | 스냅샷 재구성 | **없다** (resume 미도입) |
| trace_export (`auto/trace_export.py:169`) | 사후 추출 | 없다 |

## 5. 우리 job 상태는 이미 **원장에서 유도**한다 — upstream의 event 소비를 대체하는 자리

upstream이 `job_manager`에서 이벤트를 되읽어 만드는 것을, 우리는 명령 원장에서
유도한다 ([ADR-0041](../adr/0041-mcp-control-surface-contract.md), `mcp/jobs.py`):
짝 없는 `start`가 `running`, `end`의 exit code가 결과다.

즉 §4의 두 번째 행은 **이미 답이 있는 자리**이며, 그 답은 "event store를
두지 않는다"였다. 지금 event store를 도입하면 같은 사실의 두 번째 저장소가
생긴다 — ADR-0041 §4가 명시적으로 기각한 형태다.

**다만 원장이 답하지 못하는 것이 하나 있다**: 한 명령이 도는 **동안** 그 안에서
무슨 일이 일어나는가. 원장은 명령 단위이고, 그 안은 비어 있다.

## 6. stall 판정의 근거가 다르다 — upstream은 정규화, 우리는 바이트

| | upstream | mcx |
|---|---|---|
| 기준 | 도구 호출이 liveness를 증명 → deadline 갱신 (`leaf_dispatcher.py:549-553`) | 마지막 **출력 바이트** 이후 침묵 (`codex_execution_runtime.py:204-227`) |
| 값 | `STALL_TIMEOUT_SECONDS = 900.0` | `SILENCE_TIMEOUT_SECONDS = 900.0` (채택) |
| heartbeat | 30초 | **없다** |

값은 같고 **판정 재료가 다르다.** 우리 기준은 더 느슨하다 — 의미 없는 출력이
계속 나오면 실제로는 멈춰 있어도 살아 있다고 본다. 반대로 upstream 기준은
도구를 부르지 않는 긴 사고 구간을 stall로 오인할 수 있어 `is_final`·메시지
흐름도 함께 본다.

이 차이는 **정규화 층이 생기면 좁힐 수 있다** — 지금은 `thread.started` 외의
JSONL을 파싱하지 않으므로 도구 호출을 알 방법이 없다.

## 7. 우리 현황 — 배관은 있고 통로가 없다

`adapters/runtime/codex_execution_runtime.py:204-232`:

```python
line = await asyncio.wait_for(process.stdout.readline(), timeout=poll)
...
text = line.decode("utf-8", errors="replace")
output_tail = (output_tail + text)[-_OUTPUT_TAIL_CHARS:]
native_session_id = self._thread_id_from(text) or native_session_id
```

**이미 한 줄씩 읽고 있다.** 매 JSONL 이벤트를 손에 쥐고서 `thread.started`
하나만 꺼내고 나머지를 버린다. §2의 루프와 같은 자리이며, 빠진 것은
정규화(§1.1)와 내보낼 통로다.

`src/`에 event 타입은 여전히 없다 (2026-08-09 확인, 재확인 2026-08-10).

## 8. 미확인

- **upstream이 진행 표시를 event 소비로 옮길 계획이 있는지** — 코드에는 없다.
  콘솔 출력과 event append가 나란한 것이 의도인지 잔재인지는 소스로 판단할 수
  없다. `upstream 미확인`.
- **`event_version`의 실제 마이그레이션 사례** — 필드는 있으나 버전 1 외의
  값을 쓰는 코드를 찾지 못했다. 스키마 진화가 실제로 일어난 적이 있는지는
  이력 조사가 필요하다.
- **heartbeat 30초의 근거** — 상수 주석은 *"Heartbeat emission interval"*
  뿐이다. 값의 유래는 소스에 없다.
