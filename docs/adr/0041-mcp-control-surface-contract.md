# ADR 0041 — MCP control surface 계약

- Status: Accepted (사용자 승인 2026-08-09; §1·§4·§7은 구현이 드러낸 사실로 개정,
  Phase 10 Evolve surface 2026-08-10 추가)
- Date: 2026-08-09
- Constitutional basis: [ADR-0007](./0007-mcp-is-control-surface.md) (MCP는 제어 표면),
  [ADR-0038](./0038-mcx-cli-surface-contract.md) §1 (CLI/MCP 공유 경계),
  [ADR-0040](./0040-secret-redaction-boundaries.md) (host 프로필)
- Upstream evidence: [MCP_UPSTREAM_FINDINGS](../research/MCP_UPSTREAM_FINDINGS.md)
- 해소 대상: [Open Questions §8](../research/OPEN_QUESTIONS.md) 미결 6건,
  §7의 "Mission replay·resume 최소 보장" (Phase 7로 재지정된 항목)

## Context

[04_MCP](../04_MCP.md) 머리말이 *"tool 이름·schema·transport는 구현 전 ADR과
통합 테스트로 확정한다"*고 못박았다. 이 ADR이 그 확정이다.

조사에서 전제 하나가 뒤집혔다 — [MCP findings §4](../research/MCP_UPSTREAM_FINDINGS.md):
upstream에서 CLI와 MCP의 **공유 지점은 `mcp/tools/`의 handler**이고 CLI가
그것을 부른다 (`cli/commands/qa.py:16`). 우리는 둘 다 `application/`을 부른다.
행동은 정렬이지만 층이 다르다.

## Decision

### 1. tool은 CLI 명령과 1:1이다 — 등록된 divergence

이름은 `mcx_<stage>_<verb>`다 (`mcx_brief_ask`, `mcx_execute_next`,
`mcx_verify_gate`, `mcx_status`). 접두사가 전역에 하나인 것은 upstream
정렬이다(`ouroboros_`) — host의 도구 목록에서 출처가 이름만으로 구분된다.

**upstream은 1:1이 아니다**(MCP 전용 tool이 있고 CLI는 얇은 부분집합).
우리가 1:1인 이유는 우리 CLI가 이미 application operation과 1:1이기 때문이다
(ADR-0038 §1). 두 번째 어휘를 발명하면 parity를 검사할 대상이 사라진다.

**층위 divergence를 여기 등록한다.** 공유 지점이 upstream은 MCP handler,
우리는 **CLI의 ``dispatch``** 다. 대가는 upstream의 tool 계층 변경을 그대로
따라갈 수 없다는 것이고, 이득은 MCP를 제거해도 CLI가 선다는 것이다.

> **2026-08-09 개정 (구현이 드러낸 사실).** 초안은 "둘 다 application service를
> 부른다"고 썼으나, 그렇게 하면 arg→service 매핑이 **두 벌**이 된다 — parity를
> 테스트로 쫓아다녀야 하는 상태다. 실제 구현은 더 강하다:
>
> - tool 목록과 입력 스키마를 ``build_parser()``에서 **파생**한다. 손으로 적는
>   목록이 없으므로 CLI에 명령을 더하면 tool이 따라오고, 인자 검증도 argparse가
>   그대로 한다. 어긋날 자리가 구조적으로 없다.
> - 호출도 같은 ``dispatch``를 지난다 — mission record 전이·명령 원장·호출
>   계수·Stage 라우팅이 **같은 코드**로 일어난다.
> - 따라서 ``mcp/``가 ``cli/``에 의존한다. 방향은 하나다 — CLI는 MCP 없이 서야
>   하고, 그것을 ``test_import_direction.py``가 지킨다. upstream은 정확히 반대
>   방향이며(CLI가 MCP handler를 부른다) 그 뒤집힘이 이 divergence다.
> - 그래서 진입점은 ``mcx mcp serve``가 아니라 **별도 실행 파일 ``mcx-mcp``** 다.
>   CLI에 붙이면 두 표면이 서로를 물어 순환이 된다.

### 2. exit code는 envelope의 두 필드로 나뉜다 — HOLD는 오류가 아니다

| CLI exit | `is_error` | `result_type` | 뜻 |
|---|---|---|---|
| 0 | `false` | `complete` | 정상 수행 |
| 2 | **`false`** | `hold` | 명령은 정상 수행, 판정이 부정 |
| 1 | `true` | `error` | 예외·계약 위반·진입 차단 |

**exit 2를 `is_error=true`로 보내면 host가 재시도를 건다.** Gate `HOLD`는
"실패"가 아니라 "사용자 결정이 필요함"이고, 재시도로 뒤집히지 않는다. 이
구분은 ADR-0038 §3이 CLI에서 세운 것과 같은 축이며, upstream이 오류를 예외가
아니라 **플래그**로 표현하기에 그대로 옮길 수 있다
([findings §7](../research/MCP_UPSTREAM_FINDINGS.md)).

`structured_content`에는 CLI `--json`이 내보내는 것과 **같은 payload**를
싣는다. `content`에는 사람이 읽는 렌더(= `mcx status`의 사람용 화면과 같은
함수)를 싣는다. 두 표면이 같은 데이터의 두 렌더가 되도록.

### 3. Mission id는 인자이며 host session에서 유추하지 않는다

`mission_id`는 모든 tool의 필수 인자다. CLI의 `current_mission` 포인터
대응물을 MCP에 두지 않는다 — [04_MCP §1-4](../04_MCP.md)가 *"host 대화
session은 durable Mission의 identity나 저장소가 아니다"*라고 이미 규정했다.
host가 두 mission을 오가는 동안 서버가 "현재"를 기억하면 잘못된 mission에
쓴다.

### 4. 비동기는 장기 명령에만 두고, job 기록은 **원장을 재사용한다**

장기 명령은 넷이다 — `execute next`(`codex exec`, 침묵 900초까지),
`recover dispatch`(**같은 `codex exec`**), `verify semantic`(AC 수만큼의 완성
호출), `blueprint evolve`(Wonder + Reflect, 정상 2 primary calls). 이 넷에만
비동기 짝을 둔다:

```
mcx_blueprint_evolve /  mcx_start_blueprint_evolve
mcx_execute_next     /  mcx_start_execute_next
mcx_recover_dispatch /  mcx_start_recover_dispatch
mcx_verify_semantic  /  mcx_start_verify_semantic
mcx_job_status  ·  mcx_cancel_job
```

> **2026-08-09 정정 (Phase 7 종료 검토).** 초안과 첫 구현은 "장기 명령은
> 둘"이라고 적었다. 사실이 아니다 — `recover dispatch`는
> `RecoverService.dispatch_correction` → `ExecuteService.dispatch_correction`
> 으로 **`execute next`와 같은 실행 runtime**을 돈다. 짝이 없는 동안 host는
> 침묵 900초까지 블로킹된 채 job id를 받지 못해 취소할 수단도 없었다. 길이는
> 명령 이름이 아니라 실행 경로가 정한다는 것을 검사로 고정했다
> (`test_every_command_that_drives_the_execution_runtime_has_a_start_pair`).

**새 JobManager를 만들지 않는다.** 명령 원장이 이미 job 기록이다 — 짝 없는
`start`가 "진행 중"이고 `end`가 결과다 (ADR-0038 §6.1 a). `job_id`는
`<mission_id>#<sequence>`이며 원장의 sequence가 그대로 쓰인다.

upstream은 별도 `JobManager`와 event store를 쓰지만
([findings §5·§6](../research/MCP_UPSTREAM_FINDINGS.md)), 우리는 durable
상태가 파일이고 원장이 이미 같은 사실을 담는다. **중복 진실을 만들지 않는
것이 이 결정의 이유다** — ADR-0037이 "저장된 Stage vs Gate 재계산"에서 겪은
문제를 되풀이하지 않는다.

> **2026-08-09 개정 (구현).** 접수증이 job id를 **추측하지 않는다.**
> ``dispatch``에 ``on_sequence`` 훅을 두어 원장 구간이 열린 실제 sequence를
> 받은 뒤 접수증을 돌려준다. 추측하면 동시 호출에서 다른 명령의 id를 준다.
>
> 비동기 짝의 실제 이름은 ``mcx_start_execute_next``와
> ``mcx_start_verify_semantic``이다 — 초안의 "execute dispatch"는 CLI에 없는
> 이름이었다(실제 명령은 ``execute next``). 스키마는 동기 tool의 것을 그대로
> 쓴다.

`job_wait`는 도입하지 않는다. host가 폴링하면 되고, 대기 상한·disconnect
의미는 upstream에서도 미조사다(findings §9).

### 5. 상태 어휘는 다섯이고 취소는 **디스크 마커**다

원장에서 유도한다 — 별도 저장 없음:

| 상태 | 원장에서 어떻게 아는가 |
|---|---|
| `running` | 짝 없는 `start` |
| `completed` | `end` + `exit_code == 0` |
| `hold` | `end` + `exit_code == 2` |
| `failed` | `end` + `exit_code == 1` |
| `cancel_requested` | 취소 마커 파일 존재 + 짝 없는 `start` |

upstream의 일곱(`queued`·`interrupted` 포함)에서 둘이 빠진다. `queued`가 없는
이유는 우리가 큐를 두지 않기 때문이고(명령은 즉시 시작한다), `interrupted`가
없는 이유는 **짝 없는 `start` 자체가 그 사실**이기 때문이다 — 프로세스가 죽어도
원장이 남는다.

취소는 `<state-dir>/state/cancel_<mission>_<sequence>` 마커다.
**`CodexExecutionRuntime`이 이 마커를 관측해야 한다** — upstream이 정확히 이
지점에서 계약을 조용히 깼다: 취소 마커는 디스크에 쓰였는데 실행 프로세스가
그것을 볼 수 없었다 (`tools/background.py:16-26`). 우리 runtime은 이미 침묵
timeout에서 process group을 정리하므로 종료 수단은 있다. 마커 폴링을 같은
루프에 붙인다.

### 6. 응답 직렬화에 host 프로필을 건다

[ADR-0040](./0040-secret-redaction-boundaries.md) §5가 예약한 자리다.
`redact_for_host`를 **envelope 조립 지점 하나**에 걸어, 자격증명과 로컬 경로가
host 대화로 나가지 않게 한다. 원시 출력 본문은 싣지 않고 `output_ref`만
내보낸다 (§4).

### 7. transport는 stdio 하나다

upstream은 셋을 지원하지만(`stdio`·`sse`·`streamable-http`), v1은 로컬 단일
사용자다. **SDK는 optional extra다** (`mission-control[mcp]`) — core 의존성은
`pydantic` 하나로 유지하고(ADR-0012), import는 `serve()` 안에서 지연된다.
SDK가 없어도 `mcx` CLI와 tool 표면 테스트가 그대로 선다. **인증 계층을 도입하지 않는 근거가 이것**이다 — 원격 transport가
없으면 호출자는 이미 로컬 사용자다. 원격을 열면 인증이 선행 조건이며,
그때 upstream의 `AuthMethod`/`Permission` 축과 대조한다.

### 8. parity는 구조와 판정 둘 다 검사한다

- **구조**: MCP 모듈이 `application`을 직접 부르지 않는다 — 부르기 시작하면
  두 표면의 동작이 갈린다. CLI가 `mcp`를 import하지 않는다(한 방향). tool
  목록이 CLI 명령 집합과 정확히 같다. 셋 다 import 방향 검사다.
- **판정**: 같은 상태에 대해 `mcx_*_gate` tool과 CLI `gate` 명령이 같은
  `CLEAR`/`HOLD`와 같은 blocking reasons를 낸다.

## Consequences

### Positive

- host가 `mcx`를 부르는 방법이 CLI와 같은 어휘다 — 문서·테스트가 두 벌이 되지
  않는다.
- HOLD가 오류로 보이지 않아 host가 무의미한 재시도를 걸지 않는다.
- job 진실이 하나다(원장). 새 저장소·새 상태 기계가 없다.

### Cost

- tool 25개 + 비동기 4개·job 2개가 host 도구 목록에 올라간다. upstream도 비슷한 규모라
  (약 35) 이례적이지 않지만, host의 컨텍스트를 그만큼 쓴다.
- 원장 재사용은 job 개념을 mission에 묶는다 — mission 없는 작업은 job이 될 수
  없다. 현재 그런 작업은 없다.
- 취소 마커 관측을 runtime에 넣는 것은 [ADR-0033](./0033-first-runtime-adapter-contract.md)의
  adapter 계약 변경이다. **이 ADR의 가장 위험한 항목이며 별도 검증이 필요하다.**

## Rejected alternatives

- **tool을 묶어 수를 줄인다** (`mcx_brief`에 verb 인자) — host가 인자로 분기해야
  하고, 잘못된 verb가 런타임 오류가 된다. 24개가 목록에서 스스로 설명하는 편이
  낫다.
- **upstream처럼 MCP handler에 공유 구현을 둔다** — MCP를 제거하면 CLI가 무너진다.
  우리는 CLI가 먼저 있었고 그것이 이미 application을 부른다.
- **tool 목록을 손으로 적는다** — CLI에 명령을 더할 때 조용히 빠진다. 파서에서
  파생하면 빠질 수가 없다.
- **별도 JobManager 도입** — 진실이 둘이 된다(원장과 job 저장소). upstream은
  event store가 이미 있어 비용이 없지만 우리는 새로 만드는 것이다.
- **비동기를 전 명령에 도입** — 짧은 명령까지 두 벌이 되고 host가 어느 쪽을 쓸지
  매번 판단해야 한다.
- **v1에 인증 도입** — stdio 로컬에서 호출자는 이미 로컬 사용자다. 방어가 아니라
  의식이 된다.

## Verification

- exit 2를 내는 명령의 tool 결과가 `is_error=false`, `result_type="hold"`다.
- `structured_content`가 CLI `--json`과 같은 payload다 (같은 입력, 같은 mission).
- `mission_id` 없이 호출하면 거부된다 — 서버가 "현재 mission"을 기억하지 않는다.
- 짝 없는 `start`가 `mcx_job_status`에서 `running`으로 보인다.
- `mcx_start_blueprint_evolve`가 동기 tool과 같은 schema로 접수되고 실제 원장
  sequence를 job id로 돌려준다.
- 프로세스를 죽인 뒤에도 그 job이 사라지지 않고 `running`으로 남는다.
- 취소 마커를 쓰면 실행 중인 `codex exec`가 종료되고 attempt가 실패로 닫힌다.
- MCP 응답에 로컬 절대 경로와 자격증명이 없다.
- handler 모듈이 application 밖의 로직을 갖지 않는다 (import 방향 검사).
- 같은 상태에서 tool과 CLI가 같은 Gate 결과·같은 blocking reasons를 낸다.

## 미결로 남기는 것

- **`job_wait`와 disconnect 의미** — upstream도 미조사다(findings §9). host
  폴링으로 시작하고, 실수요가 생기면 그때 대조한다.
- **고아 attempt(`DISPATCHED` 잔해) 해소 경로** — Open Questions §7의 잔여이며
  이 ADR이 덮지 않는다. 취소는 "실행 중"을 끝내지만, 이미 고아가 된 attempt는
  별도 진입점이 필요하다.
- **취소된 attempt가 실패와 구분되지 않는다** (Phase 7 종료 검토에서 확인).
  이 ADR은 프로세스 종료까지만 정의하고 attempt 상태 어휘를 건드리지 않았다.
  결과는 §5의 job 어휘(`cancel_requested`)와 도메인 attempt 상태가 어긋나는
  것이다 — 상세와 시한은 [ADR-0025](./0025-execute-deliberate-divergences.md)·
  [ADR-0032](./0032-recover-deliberate-divergences.md)의 `cancelled` 행.
- **worker의 재귀 호출을 막는 경계가 실행 lane에 없다** — 이 ADR은 host→Core
  방향만 정의하고 Core→worker→Core 방향을 다루지 않았다.
  [Open Questions §8](../research/OPEN_QUESTIONS.md)에 등록했고 시한은 Phase 8
  이다(그 Phase가 `mcx-mcp`를 host·worker 설정에 등록해 경로를 실제로 연다).
