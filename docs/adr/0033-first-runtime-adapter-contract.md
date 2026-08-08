# ADR 0033 — Runtime port 분리 확정과 첫 concrete adapter 계약

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: [ADR-0003](./0003-runtime-neutral-core.md) (Runtime-neutral Core), [ADR-0004](./0004-stage-scoped-minimum-capability.md), [ADR-0024](./0024-execute-v1-execution-model.md) §6
- Upstream evidence: [RUNTIME_UPSTREAM_FINDINGS.md](../research/RUNTIME_UPSTREAM_FINDINGS.md)

## Context

Phase 0~4가 결정적 fake 위에서 다섯 Stage의 규칙을 검증했다. Phase 5는 그
fake 자리에 실제 backend를 끼운다. 어느 port부터, 어느 backend부터, 어떤
호출 계약으로 — 셋 다 axis 결정이므로 구현 전에 고정한다.

upstream 사실 ([RUNTIME_UPSTREAM_FINDINGS](../research/RUNTIME_UPSTREAM_FINDINGS.md)):

- text 완성(`LLMAdapter`)과 자율 실행(`AgentRuntime`)은 별개 protocol이고,
  같은 backend가 양쪽을 각각 구현한다 (§1).
- capability는 backend 이름 검사가 아니라 선언적 플래그다 (§2).
- Codex 호출은 `codex exec` 단발 — 프롬프트 stdin, `--json`, `-C <cwd>`,
  `--output-last-message`, 권한은 공용 sandbox enum → Codex 플래그 파생 (§3~§4).
- 실행 stall은 총 시간이 아니라 침묵 900초 기준, resume은 thread id +
  무거운 정합 검증이다 (§5).

## Decision

### 1. 두 port의 분리를 확정한다 — 이미 우리 구조다

위임 text port들(질문 생성기, 채점자, semantic 평가자 등)과
`ExecutionRuntime`은 별개로 유지한다. upstream의 LLMAdapter/AgentRuntime
분리와 같은 축이며, 하나의 backend(Codex)가 양쪽 adapter를 각각 갖는다.
실행 runtime이 자기 완성 backend를 지명하는 `llm_backend` 축은 라우팅
결정이 생기는 시점(둘째 adapter 이후)으로 보류한다.

### 2. 첫 concrete adapter는 Codex의 ExecutionRuntime이다

순서: **Codex 실행 adapter → Codex text backend(위임 port들) → OpenCode**.
근거 — 실행 adapter가 가장 많은 등록 보류(capability 차단, timeout,
previous_failure 렌더링)의 실체화 지점이고, upstream 대조물이 가장 두껍다
(`codex_cli_runtime.py` + 권한 정책 + CLI 정책). Gemini는 v1 제외 그대로다
(ADR-0003).

### 3. 첫 adapter는 단발 실행이다 — 스트리밍·resume은 보류

`ExecutionRuntime.execute` 시그니처(요청 → outcome 하나)를 유지한다.
upstream도 단발 소비자용 `execute_task_to_result`를 protocol에 둔다 — 우리
v1은 그 축에서 시작한다. 스트리밍(`AgentMessage` 스트림)은 event 층
(ADR-0027 §3)과 함께, resume은 upstream의 정합 검증(바이너리 해시·모델
고정)과 대조해 별도 ADR로 도입한다.

### 4. Codex 실행 adapter의 호출 계약

- **호출**: `codex exec`, 프롬프트는 **stdin**(ARG_MAX 회피 — upstream 관례
  채택), `--json`, `-C <envelope.workspace>`, `--skip-git-repo-check`,
  `--output-last-message <임시 파일>`.
- **workspace가 처음으로 실제 강제된다** — `-C`가 envelope.workspace를 실행
  프로세스의 경계로 만든다.
- **권한**: upstream 3단 매핑을 채택하되 v1 기본은 `WORKSPACE_WRITE`
  (`--full-auto`) 하나다 — Execute 기본 권한 정책(Guide §5: 쓰기는 workspace
  안, commit/push 금지)과 대응한다. `UNRESTRICTED`(bypass)로 가는 경로는
  만들지 않는다 — 사용자 승인 없는 권한 상향 금지 (ADR-0004).

  > **2026-08-08 스모크 정정**: 실물 codex-cli 0.146.1의 `exec`에는
  > `--full-auto`가 없다 — 같은 의미의 `--sandbox workspace-write`를 직접
  > 지정한다 ([RUNTIME_UPSTREAM_FINDINGS §8](../research/RUNTIME_UPSTREAM_FINDINGS.md)).
  > 의미(WORKSPACE_WRITE 고정, bypass 없음)는 그대로다.
- **envelope.allowed_tools의 강제 수준**: Codex CLI에는 도구 단위 allowlist
  전달이 없다 — v1 강제는 sandbox 클래스까지이고, 도구 목록은 기록·전달용으로
  남는다. ADR-0024 §6의 "전달·기록까지"에서 "sandbox 경계까지"로 한 단계
  좁혀진 것이며, 도구 단위 차단은 그것을 지원하는 runtime에서 도입한다
  (아래 보류 표).
- **session**: JSONL 이벤트의 thread id를 `native_session_id`로 기록한다 —
  provenance의 실행 주체 항목이 실제 값을 갖는다 (ADR-0023 §3).
- **timeout**: 총 시간 한도가 아니라 **출력 침묵 900초** — upstream stall
  기준 채택. 초과 시 process group 종료 후 실패 outcome (Verify runner와
  같은 기법).
- **adapter 자체 재시도 없음**: 실행은 부작용이 프로세스 시작 직후부터
  가능하므로 "side effect 전 transport 실패"를 입증할 수 없다 — 실패는
  outcome으로 반환하고 재시도는 Recover의 것이다 (Execute Guide §11).
  완성(text) adapter는 부작용이 없으므로 upstream처럼 transient 재시도를
  가질 수 있다 — 그 계약은 text backend ADR에서.

### 5. 프롬프트 조립은 adapter의 일이고, 계약 블록은 upstream과 정렬한다

`ExecutionRequest`의 구조화 필드(방향·AC 성공 계약·previous_failure)를
프롬프트로 렌더링하는 것은 Core가 아니라 adapter다 — Core는 runtime-neutral
을 유지한다 (ADR-0003). 렌더링 규칙: 성공 계약 블록과 실패 전달 블록은
upstream의 대응 블록(선언 계약 제시 + "Prior failure classification" +
오류 tail + 전환 지시)과 정렬하고, 계약 문장은 **영어 원문**으로 둔다
(ADR-0020 §4와 같은 이유 — 문장이 곧 계약인 곳에 번역을 두지 않는다).

### 6. 보류 등록

| 항목 | upstream | 시점 |
|---|---|---|
| 스트리밍 이벤트(`AgentMessage`)와 event 층 | `execute_task` async generator | ADR-0027 §3과 함께 |
| resume (`codex exec resume` + 정합 검증) | thread id, 바이너리 해시·모델 고정, 재시도 3 | **Phase 7** (2026-08-09 사용자 결정 — MCP 장기 실행 job 계약과 한 묶음) — 도입 시 §5 대조 |
| 도구 단위 allowlist 차단 | Codex에 없음 (sandbox 수준) | 그것을 지원하는 runtime 도입 시 |
| cancel | 존재 | **Phase 7** (2026-08-09 사용자 결정 — 장기 실행 job 계약과 함께). 스트리밍은 별개 축(event 층)으로 분리 |
| capability 선언 플래그(`RuntimeCapabilities` 대응) | 3플래그 | 둘째 adapter(OpenCode)에서 차이가 실제로 생길 때 |
| `--output-schema` 구조화 출력 | 존재 | text backend adapter에서 |

## Consequences

### Positive

- fake 자리에 실제 실행이 끼워져도 Core는 한 줄도 바뀌지 않는다 —
  runtime-neutral의 첫 실증.
- envelope.workspace가 기록에서 실제 경계(-C + sandbox)가 된다.
- provenance의 native_session_id가 실제 값을 갖는다.

### Cost

- 도구 단위 allowlist는 여전히 강제되지 않는다 — sandbox 클래스가 근사한다.
- 단발 실행이라 진행 관찰·취소가 없다 — 침묵 900초까지 기다린다.
- Codex CLI의 플래그가 바뀌면 adapter가 깨진다 — conformance test가 CLI
  실물 없이도 명령 구성을 고정해야 한다.

## Rejected alternatives

- **text backend부터**: 실행이 이 시스템의 핵심 가치이고, 보류가 가장 많이
  걸린 지점이다. text는 부작용이 없어 뒤로 미뤄도 위험이 쌓이지 않는다.
- **스트리밍부터**: 소비자(event 층, 진행 표시)가 아직 없다 — 발생 경로
  없는 계약은 장식이다.
- **권한 3단을 전부 노출**: bypass 경로는 사용자 승인 없는 권한 상향의
  문이다. 필요해지면 그때 승인 절차와 함께 연다.
- **프롬프트 조립을 Core에**: vendor 세부(블록 형식, 언어)가 adapter 경계
  안에 있어야 Core가 runtime-neutral로 남는다.

## Verification

- Codex adapter가 `ExecutionRuntime` port만 구현하고 Core 변경이 없다.
- 명령 구성이 계약대로다(stdin 프롬프트, `--json`, `-C`, `--full-auto`,
  `--output-last-message`) — CLI 실물 없이 검증 가능해야 한다.
- thread id가 native_session_id로 기록된다.
- 침묵 timeout 초과 시 process group이 정리되고 실패 outcome이 반환된다.
- adapter가 스스로 재시도하지 않는다 — 같은 요청의 재실행은 호출자 기록에만
  존재한다.
- bypass 권한으로 가는 코드 경로가 없다.
