# ADR 0049 — 실행 중 진행 관측: 정규화는 두고 event store는 두지 않는다

- Status: **Accepted** (사용자 결정 2026-08-10 — 세 안 중 (b))
- Date: 2026-08-10
- Constitutional basis: [ADR-0003](./0003-runtime-neutral-core.md) (Core는
  Runtime-neutral), [ADR-0040](./0040-secret-redaction-boundaries.md)
  (redaction 경계), [ADR-0041](./0041-mcp-control-surface-contract.md) §4·§5
  (원장에서 유도한다 · 관측은 설치되어야 한다)
- Upstream evidence: [EVENT_LAYER findings](../research/EVENT_LAYER_UPSTREAM_FINDINGS.md)
- 해소 대상: [ADR-0027](./0027-telemetry-layers-and-v1-schema.md) §3의
  *"canonical event 층 + 스트리밍 생산자"* — Phase 5 시한 무처분 도과분

## Context

로드맵 항목은 이유를 둘로 적었다: 긴 실행의 진행 표시, 그리고
*"`changed_files`가 같은 생산자를 요구한다"*.

**둘째는 이미 거짓이 됐다.** `changed_files`는
[ADR-0048](./0048-changed-files-collection.md)로 확정됐고 생산자는
`git status` 한 번이다. event는 한 줄도 쓰이지 않았다.

그리고 조사가 첫째마저 뒤집었다 — **upstream에서 진행 표시는 event 층의
소비자가 아니다** (findings §3). `leaf_dispatcher.py:549`의 콘솔 출력은 event
store를 읽지 않고 같은 루프에서 정규화 결과를 직접 찍는다. event append와 화면
출력은 나란한 두 동작이지 생산자–소비자가 아니다.

즉 이름 하나가 **성격이 다른 두 층**을 가리고 있었다 (findings §1).

| | upstream 실물 | 성격 |
|---|---|---|
| 정규화 | `ProjectedRuntimeMessage` | 순수 변환, 저장 없음 |
| 저장 | `BaseEvent` + `EventStore` | SQLite 영속 계층 |

## Decision

### 1. 정규화 층을 둔다 — vendor JSONL을 backend-neutral 한 줄로

`RuntimeActivity`. upstream `ProjectedRuntimeMessage`의 축을 받되 필드는
**우리 소비자가 요구하는 것만** 둔다 — 지금 소비자는 화면 표시와 job 답변
둘이고, 둘 다 *"어떤 도구로 무엇을"* 이면 답이 된다.

```text
RuntimeActivity
  kind    # "tool"
  tool    # codex item type 그대로
  detail  # 한 줄 (마스킹·절단 완료)
```

**도구 이름을 다시 짓지 않는다.** upstream은 item type을 자기 어휘로 옮기지만
그 매핑의 근거를 확인하지 못했다 — 확인하지 않은 것을 발명으로 메우지 않는다.
codex의 item type(`command_execution`·`file_change`·`mcp_tool_call`·
`web_search`, findings §2)을 그대로 싣는다.

**두 번째 Runtime(OpenCode)이 오면 이 자리에서 흡수한다.** upstream이 vendor
이벤트 이름을 집합으로 접는 자리와 같다 (`runtime_message_projection.py:20-48`).

### 2. `item.started`만 싣는다 — `item.completed`는 싣지 않는다

upstream은 둘 다 투영한다. 목적이 다르기 때문이다 — upstream은 deliver gate가
**도구 완료를 증명**해야 해서 쌍이 필요하다 (`codex_cli_runtime.py:179-181`).

우리 목적은 *"지금 무엇을 하는가"* 이고, 그 답은 시작이다. 둘 다 실으면 줄이
두 배가 되고 마지막 줄이 *"방금 끝난 것"* 이 되어 질문에 어긋난다.

**등록된 divergence.** 발동 조건은 *"도구 완료 여부가 판정 재료로 필요해지는
것"* 이며, 그때는 우리도 쌍이 필요하다.

### 3. **event store를 두지 않는다** — 소비자가 없다

upstream에서 event store를 읽는 것은 넷이고 (findings §4) **셋이 우리에게
없다**: TUI, auto listeners, replay/resume. 넷째인 job 상태는
[ADR-0041](./0041-mcp-control-surface-contract.md) §4가 이미
**원장에서 유도**하기로 정했다.

지금 event store를 도입하면 그 ADR이 명시적으로 기각한 형태 —
*"같은 사실의 두 번째 저장소"* — 가 생긴다.

**등록된 divergence.** 발동 조건은 위 셋 중 하나가 생기는 것이며, 현실적으로는
**resume**이 가장 가깝다.

### 4. 원장이 비워 둔 칸 하나는 채운다 — 진행 꼬리

원장은 **명령 단위**다. 답하지 못하는 질문이 정확히 하나 있다:
*"한 명령이 도는 **동안** 그 안에서 무슨 일이 일어나는가."*

화면 출력만으로는 이 칸이 안 채워진다. MCP 백그라운드 job에는 볼 화면이 없고,
나중에 물으면 원장은 `running`까지만 안다.

`<state>/progress_<mission_id>_<sequence>.jsonl` — 원장·취소 마커와 같은
이름 규칙이다. **job 하나에 파일 하나**이며 `job_id`가 그대로 좌표다.

**두 번째 저장소가 아니다.** 원장이 담는 사실(명령의 시작·끝·결과)을 하나도
중복하지 않는다. 담는 것은 원장에 없는 축 하나뿐이다.

### 5. 관측은 **설치되어야 한다** — ambient contextvar

[ADR-0041](./0041-mcp-control-surface-contract.md) §5의 취소와 같은 배치이며,
같은 모듈 형태를 쓴다 (`cancellation.py` ↔ `progress.py`).

adapter는 *"누가 왜 보는지"* 를 모른다. `record(activity)`만 부르고, 설치된
싱크가 없으면 **아무 일도 일어나지 않는다** — 기존 동작이 한 글자도 바뀌지
않는다.

싱크를 설치하는 자리는 원장 구간을 여는 자리(`dispatch`)다. 그래야 sequence가
정해져 있고, 원장과 진행 꼬리의 생명주기가 어긋나지 않는다.

### 6. 진행 줄에 저장 프로필을 **생성 시점에** 건다

detail은 도구 입력에서 온다 — `curl --api-key=…`, `export TOKEN=…`가 그대로
지나갈 수 있는 자리다. 새 저장 표면이므로
[ADR-0040](./0040-secret-redaction-boundaries.md) §3의 규율을 받는다:
**"부르면 되는 함수"로 두지 않는다.**

`RuntimeActivity` 생성 시점에 마스킹·절단이 일어난다 — 아무도 부르지 않아도
지나간다. `ExecutionAttempt`·`VerificationRun`과 같은 방식이다.

절단 한도 200자. 원시 출력은 **애초에 싣지 않는다** — 도구 이름과 입력 한 줄뿐이며,
이것이 원장의 replay-unsafe 거부(§2)와 이 파일이 갈리는 지점이다.

### 7. stall 판정은 **이번에 바꾸지 않는다**

upstream은 도구 호출이 liveness를 증명한다고 보고 시한을 갱신한다
(`RC6`, findings §6). 우리는 출력 바이트의 침묵으로 본다.

정규화가 생겼으므로 이제 좁힐 수 있지만 **하지 않는다.** 판정을 조이면
오탐이 곧 **돌고 있는 프로세스를 죽이는 것**이고, 그 방향의 변경은 실사용
관측 없이 할 일이 아니다. 두 기준의 값은 이미 같다(900초).

**미결로 등록한다** (§미결).

## Consequences

### Positive

- 10분짜리 실행이 무엇을 하는지 보인다. 지금은 죽은 건지 도는 건지 알 방법이
  없다.
- MCP job이 `running` 너머를 답한다 — *"방금 무엇을 시작했는가"*.
- 두 번째 Runtime이 올 자리가 생겼다 (§1). 지금은 codex JSONL을 아는 코드가
  adapter 안에만 있다.
- ADR-0027 §3의 두 Phase 묵은 도과가 닫힌다 — **항목을 반으로 줄여서**가
  아니라 그 절반이 근거를 잃었음을 기록해서.

### Cost

- **진행 꼬리 파일이 쌓인다.** job마다 하나이고 지우는 경로가 없다.
  `mcx cleanup`은 worktree만 본다 (미결).
- `item.completed`를 안 실으므로 **도구가 끝났는지 알 수 없다** (§2). 마지막
  줄이 오래 그대로면 그 도구가 오래 걸리는 것인지 멈춘 것인지 구분되지 않는다 —
  그 구분은 stall 판정의 몫이고 §7이 미뤘다.
- detail이 200자에서 잘린다. 긴 명령은 뒷부분이 사라진다.
- 마스킹이 진행 줄에도 걸리므로 `foreign_key=…` 같은 도구 입력이
  `[redacted]`로 보일 수 있다 (REDACTION_FIELD_TRIAL §4와 같은 대가).

## Rejected alternatives

- **event store (SQLite) 도입** — 읽을 소비자가 없고, ADR-0041 §4가 기각한
  "같은 사실의 두 번째 저장소"가 된다 (§3).
- **화면 출력만, 저장 없음** — MCP 백그라운드 job에 화면이 없다. 원장이 비워
  둔 칸이 그대로 남는다 (§4).
- **원장에 진행 줄을 함께 쓰기** — 원장은 프롬프트·원시 출력을 담을 수 없고
  (ADR-0040 §2), 명령 단위 구간이라는 성질이 흐려진다.
- **`item.completed`도 싣기** — 우리 질문에 어긋난다 (§2).
- **도구 이름을 우리 어휘로 옮기기** — upstream 매핑의 근거를 확인하지
  못했다. 확인하지 않은 것을 발명으로 메우지 않는다 (§1).
- **stall 판정을 도구 호출 기준으로 교체** — 오탐이 프로세스를 죽인다 (§7).

## Verification

- `execute next`가 도는 동안 도구 호출이 화면에 한 줄씩 나온다.
- 같은 줄이 `progress_<mission>_<sequence>.jsonl`에 남고, 파일 권한은 0600이다.
- 싱크가 설치되지 않으면 adapter의 동작이 바뀌지 않는다 — 파일도 생기지 않는다.
- `item.started`만 줄이 된다. `item.completed`·`thread.started`는 되지 않는다.
- 도구가 아닌 item type(`agent_message` 등)은 줄이 되지 않는다.
- 깨진 JSONL 한 줄이 실행을 멈추지 않는다.
- **자격증명이 실린 도구 입력은 파일에도 화면에도 남지 않는다** — 아무도
  마스킹 함수를 부르지 않아도.
- detail이 200자를 넘지 않는다.
- job 조회가 마지막 진행 줄을 함께 답한다. 진행 파일이 없으면 그 자리가 비고,
  job 조회가 실패하지 않는다.

## 미결로 남기는 것

- **stall 판정을 정규화 기준으로 옮길 것인가** (§7). 실사용에서 침묵 기준이
  실제 stall을 놓치는 것이 관측되면 옮긴다. **시한 Phase 10 진입 시.**
- ~~**진행 꼬리의 정리**~~ → **닫음: 넣지 않는다** ([Phase 9 종료 검토](../progress/0009_RECOVERY_LAYERS.md) §3-11, 2026-08-10).
  미션 하나에 파일 15개, 합계 **60K** — 같은 상태 디렉터리의 worktree 52K,
  outputs 112K와 견줘 거슬리는 크기가 아니다. `mcx cleanup`에 넣지 않는 이유는
  그 명령의 계약이 *"작업이 사라지지 않는다"* 이고 **진행 기록은 작업이 아니라
  기록**이라 성격이 다르기 때문이다. **발동 조건**: 상태 디렉터리 크기가 실제로
  문제가 되면 outputs와 함께 본다.
- **resume이 오면 §3을 다시 본다** — event store를 읽는 소비자 중 우리에게
  가장 가까운 것이다. **시한 resume 계약 착수 시.**
