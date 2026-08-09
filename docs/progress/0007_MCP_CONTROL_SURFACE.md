# Progress 0007 — Phase 7: MCP control surface 종료 검토

- 일시: 2026-08-09
- 범위: secret redaction 경계(진입 조건), MCP tool 표면 29개(CLI 24 + 비동기 3 +
  job 2), stdio transport, 취소 마커와 runtime 관측, `mcx-mcp` 진입점
- Evidence: [ADR-0040](../adr/0040-secret-redaction-boundaries.md)·
  [ADR-0041](../adr/0041-mcp-control-surface-contract.md),
  commits 5e479cf·186fcc4, 718 tests,
  [MCP findings](../research/MCP_UPSTREAM_FINDINGS.md),
  [SECURITY findings](../research/SECURITY_UPSTREAM_FINDINGS.md)
- 상태: **Phase 7 COMPLETE (2026-08-09).** 검토가 잡은 6건은 §2에서 처분했다 —
  1건은 코드 수정, 5건은 등록·재지정이다.

> **로드맵 체크리스트 9항목 중 3항목이 미이행인 채로 Phase 7이 "구현 완료"로
> 기록돼 있었다** ([README](./README.md) Phase 종료 검토 표). 이 검토의 가장 큰
> 소득은 그 셋을 이름으로 부른 것이다 — 비동기 짝 하나 누락, 재귀 경계 부재,
> `cancelled` 상태 미이행.

## 1. 일곱 질문에 대한 답

### 1.1 구조 검사 — 각 방어가 막는 결함

| 방어 | 막는 결함 |
|---|---|
| tool 목록·스키마를 `build_parser()`에서 파생 | CLI에 명령을 더할 때 tool이 조용히 빠져 두 표면의 어휘가 갈린다 |
| 호출이 CLI와 같은 `dispatch`를 지남 | arg→service 매핑이 두 벌이 되어 mission record 전이·원장·호출 계수·Stage 라우팅이 표면마다 달라진다 |
| exit 2 → `is_error=false` | host가 HOLD를 실패로 읽어 재시도로 뒤집으려 한다 (판정은 재시도로 바뀌지 않는다) |
| `mission`을 스키마 수준에서 필수로 | 서버가 "현재 mission"을 기억하면, host가 mission을 바꾼 뒤 이전 mission에 쓴다 |
| `--state-dir`를 표면에서 제외 | host가 상태 루트를 골라 한 미션이 두 저장소로 쪼개진다 |
| import 방향 — `cli → mcp` 금지 | MCP를 제거하면 CLI가 무너진다 |
| import 방향 — `mcp → application` 직접 호출 금지 | 두 표면의 동작이 갈린다 (파리티를 테스트로 쫓아야 하는 상태) |
| envelope 조립 지점 **하나**에 `redact_for_host` | 자격증명·로컬 절대경로가 host 대화로 나간다 |
| `on_sequence` 훅으로 실제 sequence 수령 | 동시 호출에서 접수증이 **다른 명령의** job id를 준다 |
| 취소 마커를 runtime이 관측 | 마커만 디스크에 쓰이고 프로세스는 계속 돈다 (upstream이 실제로 깬 지점 — `tools/background.py:16-26`) |
| 빈 `content` 금지 (structured의 JSON fallback) | host가 결과를 읽지 못한다 |
| job 어휘 5종을 원장에서 유도 | job 저장소와 원장이 두 진실이 된다 |
| lifecycle 기록의 replay-unsafe 키 **거부** | prompt·stdout·stderr가 마스킹된 척 저장되어 원장이 재현 위험을 나른다 |

**산문으로만 막고 있는 계약 1건을 발견했다.**
[ADR-0004](../adr/0004-stage-scoped-minimum-capability.md)의 *"delegated
worker는 Mission Control을 재귀 호출하지 않는다"* 는 실행 lane에 강제가 없다 —
§2.2에 등록하고 "알려진 한계"에 올렸다.

### 1.2 부품/단계 구분

SDK 없이 51개 MCP 테스트가 도는 것 자체가 §1(SDK는 `serve()` 안에만)의
검증이다. 실물 확인은 stdio 프로토콜 왕복이다 — `initialize` → `tools/list`
→ `mcx_brief_gate`가 `isError:false` + `_meta.result_type:"hold"`로 돌아오고,
`mcx_status`가 사람용 렌더를 싣는다.

**미조립 부품 1건을 여기서 잡았다.** 로드맵 항목은
*"long-running Execute/Verify/**Recover** job contract"* 인데 비동기 짝이 둘뿐
이었다. `recover dispatch`는 `RecoverService.dispatch_correction` →
`ExecuteService.dispatch_correction`으로 **`execute next`와 같은 `codex exec`**
를 돈다 — 길이가 같다. 짝이 없는 동안 host는 침묵 900초까지 블로킹된 채 job
id를 받지 못해 취소할 수단도 없었다. 고쳤다 (§2.1).

실 AI로 도는 MCP 경로의 관측은 **없다** — §1.6 참조.

### 1.3 미등록 이탈

ADR-0041이 자기 divergence를 인라인으로 등록하고 있다: 층위 뒤집힘(공유 지점이
upstream은 MCP handler, 우리는 CLI `dispatch`), tool 1:1(upstream은 아님),
job 어휘 5 vs 7, transport 1 vs 3, 별도 `JobManager` 미도입.

**새로 발견한 미등록 이탈 1건 — 차단 질문을 서버가 묻지 않는다.** Gate가 `HOLD`
일 때 우리는 `blocking_reasons`(closure 차단 질문이 접힌다 —
`domain/brief/gate.py:127`)를 **데이터로 돌려주고** host가 사람에게 중계하기를
기다린다. MCP 프로토콜의 서버→사용자 질의 수단을 쓰지 않는다는 뜻이며, 이유는
[04_MCP §1-4](../04_MCP.md)의 *"host 대화 session은 durable Mission의 identity나
저장소가 아니다"* 와 정렬하기 위해서다 — 서버가 사람에게 직접 물으면 그 답이
어느 mission의 것인지 서버가 기억해야 한다. 근거는 우리 쪽 문서이고 **upstream
대응물은 미확인**이라 그렇게 표시해 등록한다.

### 1.4 표시 없는 보류

ADR-0041이 미결 2건을 그 자리에 표시하고 있었다 — `job_wait`·disconnect 의미
(upstream도 미조사), 고아 attempt(`DISPATCHED` 잔해) 해소 경로.

**표시 없던 보류 2건을 발견해 같은 자리에 추가했다:**

1. **취소된 attempt가 실패와 구분되지 않는다.** ADR-0041은 프로세스 종료까지만
   정의하고 attempt 상태 어휘를 건드리지 않았다. 결과는 job 어휘
   (`cancel_requested`)와 도메인 attempt 상태가 어긋나는 것이다.
2. **worker의 재귀 호출 경계가 없다.** ADR-0041은 host→Core 방향만 정의했다.

### 1.5 계약 문장 원문 여부

Phase 7은 표면 계층이라 vendor에게 보내는 계약 문장을 새로 만들지 않았다 —
프롬프트와 SUCCESS CONTRACT 블록은 Phase 5 산출물 그대로다. 번역·의역으로
계약을 깎은 지점 없음.

**다만 이 질문이 인접한 결함 하나를 드러냈다.** MCP에서 **tool description은
계약에 가깝다** — host LLM은 그것만 읽고 어느 도구를 부를지 고른다. 현재
description은 `f"mcx {stage} {verb}"`, 즉 **도구 이름의 반복**이라 정보가 0이다
(파생 원천인 CLI 하위 파서 대부분이 `help=`를 갖고 있지 않다). 지금 문제가 되지
않는 이유는 호출자가 순서를 아는 사람이기 때문이며, 그 전제가 깨지는 곳이
바로 Phase 8(합성 계층)이다. §2.5로 등록했다.

### 1.6 관측 대조

**MCP 경로의 실 AI 관측이 없다.** 도그푸딩 0001~0003은 전부 CLI 경로이고, Phase
7 산출물의 확인은 stdio 프로토콜 왕복과 LLM-free 경로까지다. 이것은 결함이
아니라 관측 공백이며, 여기 명시해 다음 Phase가 "관측된 것"으로 오해하지 않게
한다. Phase 8이 skill 계층으로 host를 실제로 운전시키므로 그때 첫 관측이 생긴다.

관측과 모순되는 규칙은 없다. 오히려 관측이 설계를 이긴 항목이 하나 있다 —
upstream이 취소 마커를 디스크에 쓰고도 실행 프로세스가 그것을 볼 수 없어 계약이
조용히 깨진 사례(`tools/background.py:16-26`)를 근거로 우리는 관측을 runtime에
넣었고, **실물 프로세스를 띄워 종료되는 것**까지 테스트로 고정했다
(`test_a_cancel_request_terminates_the_running_process`). 관측기가 없을 때 기존
침묵 동작이 한 글자도 바뀌지 않는 것도 함께 고정했다.

### 1.7 시한 도과 점검

Phase 7을 시한으로 지정한 항목 전수:

| 항목 | 처분 |
|---|---|
| [Open Questions §9](../research/OPEN_QUESTIONS.md) secret redaction (**진입 조건**) | **이행** (ADR-0040, 5e479cf) |
| [00_MISSION_CONTROL](../00_MISSION_CONTROL.md) §25 — MCP tool 목록·transport 세부 | **이행** (ADR-0041 §1·§7) |
| [Open Questions §8](../research/OPEN_QUESTIONS.md) MCP/CLI 결정 6건 | **5건 이행, 1건 부분** — disconnect·`job_wait` 대기 상한은 열려 있다 (upstream도 미조사) |
| [Open Questions §8](../research/OPEN_QUESTIONS.md) — host가 자기 편집 도구로 작업하고 Verify만 호출하는 경로 | **무처분 도과.** 시한은 [ADR-0023](../adr/0023-execute-entry-and-provenance.md)과 [ADR-0026](../adr/0026-verify-entry-requires-lineage.md)이 건 *"Phase 7 전"* 이었다 — 시작 전에 결정했어야 할 항목이 시작도 끝도 지나갔다. **새 시한 Phase 8** (host를 실제로 운전시키는 층) |
| [Open Questions §7](../research/OPEN_QUESTIONS.md) Mission replay·resume 최소 보장 | **부분 이행** — 취소는 닫혔다(ADR-0041 §5, 실물 종료 테스트). **resume 미이행**, DISPATCHED 잔해 미이행. 새 시한은 아래 두 행 |
| [ADR-0033](../adr/0033-first-runtime-adapter-contract.md) §6 resume | **미이행 → 재지정 Phase 9** (worktree·checkpoint와 같은 자리 — 중단 지점 복구는 되돌리기 층과 함께여야 의미가 있다) |
| [ADR-0033](../adr/0033-first-runtime-adapter-contract.md) §6 cancel | **이행** |
| [ADR-0003](../adr/0003-runtime-abstraction.md), [00_MISSION_CONTROL](../00_MISSION_CONTROL.md) §25 — 스트리밍·resume·cancel | **cancel만 이행.** 스트리밍은 event 층(Open Questions §9)이 소유하며 시한 미배치 — 그 사실을 여기 남긴다 |
| [ADR-0025](../adr/0025-execute-deliberate-divergences.md)·[ADR-0032](../adr/0032-recover-deliberate-divergences.md) `cancelled` attempt 상태 | **미이행 → 재지정 Phase 9.** 오작동을 확인했다 (§2.3) |
| [ADR-0025](../adr/0025-execute-deliberate-divergences.md) resume/cancel 계약 **조사** | **cancel만 조사됨** (MCP findings §5·§9). resume 조사는 위 재지정에 합류 |
| [ADR-0014](../adr/0014-brief-concurrent-write-protection.md), [05_BRIEF](../05_BRIEF.md) B-017 — stale write 재확인 경로 | **미이행 → 재지정 Phase 8.** 그리고 Phase 7이 그 전제조건을 실제로 만들었다 (§2.4) |
| [ADR-0019](../adr/0019-blueprint-qa-loop.md) §7·[ADR-0021](../adr/0021-blueprint-state-and-revisions.md) — QA revision 제시 표면 | **재료 이행, 행위 미이행 → 재지정 Phase 8.** `mcx_blueprint_qa`가 지적을, `mcx_blueprint_revise`가 진입점을 준다. 없는 것은 *"host가 그것을 하라"* 는 지시이며 그것이 skill 계층 내용이다 |
| [Open Questions §3](../research/OPEN_QUESTIONS.md), [ADR-0038](../adr/0038-mcx-cli-surface-contract.md) §7 — approval actor(host 대리 승인) | **무처분 도과 → 재지정 Phase 8.** MCP는 승인 tool을 열었으나 "누가 승인했는가"는 여전히 기록되지 않는다. host 에이전트가 부르면 사용자 승인과 구분되지 않는다 |
| [09_RECOVER](../09_RECOVER.md) — 장기 실행 job의 승인 기록 재평가 (directive 저장) | **재평가 수행, 결론 무변경.** 장기 job이 생겼지만 승인은 여전히 별도 동기 명령(`approve`)이고 job이 승인을 만들지 않는다 — 재평가를 촉발한 조건이 성립하지 않았다 |
| [SEED findings](../research/SEED_UPSTREAM_FINDINGS.md) — 취소 경로("우리 취소 경로는 Phase 7이다") | **이행** |
| [MCP findings](../research/MCP_UPSTREAM_FINDINGS.md) — import 방향 divergence를 Phase 7 ADR에 등록 | **이행** (ADR-0041 §1) |
| 로드맵 — recursion/security tests | **미이행 → §2.2** |

## 2. 검토가 잡은 것

### 2.1 `recover dispatch`에 비동기 짝이 없었다 — 고침

로드맵 항목이 이름으로 Recover를 부르는데 `LONG_RUNNING`에는 둘뿐이었다.
`recover dispatch`가 `execute next`와 같은 `codex exec`를 돈다는 것을 실행
경로로 확인하고 `mcx_start_recover_dispatch`를 추가했다. ADR-0041 §4의
*"장기 명령은 둘이다"* 를 정정했다.

길이를 **명령 이름이 아니라 실행 경로**가 정한다는 것을 검사로 고정했다
(`test_every_command_that_drives_the_execution_runtime_has_a_start_pair`) —
같은 누락이 다시 생기면 테스트가 잡는다.

### 2.2 worker의 재귀 호출을 막는 경계가 실행 lane에 없다 — 등록, 결정 필요

[ADR-0004](../adr/0004-stage-scoped-minimum-capability.md)는 *"delegated worker가
Mission Control을 재귀 호출하지 않는다"* 를 요구하고, 로드맵은 Phase 7에
`recursion/security tests`를 배치했다. **둘 다 강제가 없다.**

lane별 실측:

| lane | 격리 | 실물 |
|---|---|---|
| 텍스트 (Claude) | 있다 | `--strict-mcp-config --setting-sources ""` + `--tools ""` (ADR-0036) |
| 실행 (Codex) | **없다** | `build_command()`는 `--json --skip-git-repo-check -C --output-last-message --sandbox workspace-write`뿐 |

즉 `codex exec` worker는 `~/.codex/config.toml`을 그대로 상속한다. 거기에
`mcx-mcp`가 등록되어 있으면 worker가 Mission Control을 호출할 수 있고, ADR-0004의
금지가 깨진다. **그 등록을 하는 것이 정확히 Phase 8(plugin 패키징)이다** — 지금
도달 불가인 이유는 방어가 아니라 우연이다.

upstream 대조 (baseline `9486c78`): upstream의 `codex exec` 명령에도 MCP 차단
플래그는 없다. 대신 `_build_command`가 `--profile`을 *"the worker-isolation
boundary"* 로 명시해 쓴다 (`orchestrator/codex_cli_runtime.py`) — **우리에게 없는
축이다.** 우리 쪽 후보 레버는 `codex exec --ignore-user-config`인데 이것은
사용자 모델·프로필 설정까지 함께 떨어뜨려 도그푸딩 구성을 바꾼다.

이는 [ADR-0033](../adr/0033-first-runtime-adapter-contract.md) adapter 계약의
변경이자 실행 모델 축이라 **구현 중 임의 확정하지 않는다.** Open Questions §8에
등록하고 시한을 Phase 8로 지정했다 — 결정 대상은 "profile 축을 들여올 것인가,
`--ignore-user-config`로 끊을 것인가"다.

### 2.3 취소된 attempt가 실패와 구분되지 않는다 — 오작동 확인

취소는 프로세스를 죽이고 `ExecutionOutcome(succeeded=False, error="cancelled by
request; the process group was terminated")`로 attempt를 닫는다. 여기까지는
ADR-0041 Verification의 서술과 일치한다. 문제는 그 `error`가 **상수 문자열**이라는
점이다.

`domain/recover/packet.py:143-147`은 최근 `stall_threshold`(3)개 attempt의 오류
해시가 하나로 모이면 `STALL`로 분류한다. 따라서 **같은 AC를 세 번 취소하면
Recover가 "정체"로 판정해 중단한다** — 사용자가 의도적으로 멈춘 것을 runtime이
막힌 것으로 읽는다. `BLOCKED` 패턴 검사도 같은 문자열을 본다.

[ADR-0025](../adr/0025-execute-deliberate-divergences.md)·
[ADR-0032](../adr/0032-recover-deliberate-divergences.md)가 `cancelled` 상태를
Phase 7 시한으로 등록해 두었으나 이행되지 않았다. 새 시한 **Phase 9** — 되돌리기
층(rollback·checkpoint)이 "중단된 작업을 어떻게 되돌리는가"를 같은 자리에서
정하기 때문이다.

### 2.4 stale write 재확인이 미이행인데, Phase 7이 그 전제조건을 만들었다

[ADR-0014](../adr/0014-brief-concurrent-write-protection.md) §15는 *"동시 writer가
실제로 생기는 Phase 7에서 구현한다"* 고 적었다. Phase 7은 그 조건을 실제로
만들었다 — `mcx_start_*`가 백그라운드 task로 도는 동안 host는 다른 tool을 부를 수
있고, 둘 다 같은 `dispatch`와 같은 저장소를 지난다. **조건은 성립했고 구현은
없다.**

현재 동작: `StaleWriteError`가 envelope에서 `is_error=true`와 예외 이름으로
나간다. 조용한 유실이 아니라 큰 실패이므로 ADR-0014의 핵심 방어(덮어쓰기 금지)는
지켜지고, 미달인 것은 *"최신 question과 revision을 제시해 재확인"* 이다. 새 시한
**Phase 8** — host가 그 재확인을 사람에게 중계하는 층이다.

### 2.5 tool description이 도구 이름의 반복이다

`f"mcx {stage} {verb}"`가 전부다. host LLM이 29개 도구 중 무엇을 부를지 고르는
유일한 근거인데 정보가 없다. 파생 원천인 CLI 하위 파서가 `help=`를 갖고 있지
않은 것이 원인이므로, 고치는 자리도 파서다(고치면 CLI `--help`도 같이 좋아진다).
시한 **Phase 8** — 그 Phase가 "host가 순서를 스스로 안다"를 목표로 하므로 이
결함이 그때 1급 장애가 된다.

### 2.6 로드맵 체크리스트가 미이행을 담은 채 "구현 완료"로 기록돼 있었다

9항목 중 이행 5, 부분 2, 미이행 2였다. [README](./README.md)의 Phase 종료 검토
표는 *"조사·설계·구현 완료"* 라고만 적고 있었다. 표를 실제 상태로 갱신했다.

## 3. 다음 Phase 진입 조건

Phase 8(plugin 패키징 = 합성 계층)의 선행은 **"무엇이 skill 소유이고 무엇이 Core
소유인가"의 경계 ADR**이다 ([Open Questions §8](../research/OPEN_QUESTIONS.md)).
이 검토가 그 ADR이 답해야 할 항목 5개를 구체적으로 채웠다 — §2.2 재귀 경계,
§2.4 재확인 중계, §2.5 tool description, QA revision 제시, host 대리 승인의
actor. 다섯 전부가 "Core가 재료를 주고 skill이 행위를 한다"의 경계에 걸려 있다.
