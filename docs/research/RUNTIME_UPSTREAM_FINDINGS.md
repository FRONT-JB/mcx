# Runtime Upstream Findings — adapter protocol과 Codex 실행 계약

> Checked: 2026-08-08; stream 경계 재확인: 2026-08-11. Baseline:
> `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
> (`~/.claude/plugins/marketplaces/ouroboros`).<br>
> Scope: [Open Questions §7](./OPEN_QUESTIONS.md)(protocol method·capability·
> timeout/cancel/resume·backend 분리)과 Phase 5 첫 adapter 계약의 재료.<br>
> Evidence level: 별도 표기 없으면 **Verified** (소스 확인).

## 1. 두 protocol의 분리 — LLMAdapter와 AgentRuntime

upstream은 text 완성과 자율 실행을 **별개 protocol**로 둔다.

- **`LLMAdapter`** (`providers/base.py:123`) — `complete(...)`. 질문 생성·
  채점·판정 같은 단발 텍스트 작업의 port.
- **`AgentRuntime`** (`orchestrator/adapter.py:983`) — 실행 runtime의 port:
  `runtime_backend`(canonical 이름), `capabilities`, `llm_backend`(비실행 LLM
  작업에 쓸 backend 이름 — runtime이 자기 완성 backend를 지명), 
  `working_directory`, `permission_mode`, `execute_task`(**async generator** —
  정규화된 `AgentMessage` 스트림) + **`execute_task_to_result`**(수집된 최종
  결과 하나 — 단발 소비자용) (`:983-1057`).

같은 backend가 양쪽을 각각 구현한다 — `codex_cli_adapter.py`(완성)와
`orchestrator/codex_cli_runtime.py`(실행)는 별개 파일이다.

## 2. Capability는 선언적 플래그다 (`adapter.py:898-918`)

`RuntimeCapabilities`: `skill_dispatch` / `targeted_resume` /
`structured_output`(구조화 JSONL 이벤트 vs 평문 stdout). 목적이 주석에
명시된다 — "backend 차이를 암묵적 silent degradation에서 orchestrator가
분기할 수 있는 명시적 metadata로" — **backend 이름 검사보다 capability
플래그 분기를 선호**하라.

## 3. Codex 완성 호출 — `codex exec` 단발 (`providers/codex_cli_adapter.py`)

- 명령 구성 (`:414-451`): `codex exec` + `--json`(JSONL 이벤트) +
  `--skip-git-repo-check` + `-C <cwd>`(작업 디렉토리) +
  `--output-last-message <path>`(최종 메시지를 파일로) + 권한 인자 +
  `--output-schema <path>`(구조화 출력 스키마!) +
  `-c model_reasoning_effort=<level>`.
- **프롬프트는 항상 stdin이다** — ARG_MAX 한계 회피 (`:417` 주석).
- transient 재시도: 공용 패턴 코어 채택 (`:56-61`), 완성(부작용 없음)이라
  전체 재시도가 안전하다.

## 4. 권한은 공용 sandbox enum이 소유하고 Codex 플래그로 매핑된다

`codex_permissions.py`: 3단 모드 → `SandboxClass` → Codex 고유 플래그.

| 모드 | SandboxClass | Codex 인자 |
|---|---|---|
| `default` | READ_ONLY | `--sandbox read-only` |
| `acceptEdits` | WORKSPACE_WRITE | `--full-auto` |
| `bypassPermissions` | UNRESTRICTED | (sandbox·승인 게이트 제거) |

의미는 sandbox enum이 소유하고 Codex 플래그는 파생이다 — "Codex-side
behavior stays consistent and is derived from the same sandbox" (`:5-8`).
Codex CLI에 **도구 단위 allowlist 전달은 없다** — 경계는 sandbox 클래스
수준이다.

## 5. Codex 실행 runtime — thread 기반 resume과 정합 검증

`orchestrator/codex_cli_runtime.py`:

- 실행도 `codex exec`이고, 재개는 `codex exec resume <thread-id>` — JSONL
  이벤트의 thread id가 session identity다 (`:242`, `:430`).
- resume 정합 검증이 무겁다: 선택된 CLI 바이너리의 **bytes 해시 + 버전**을
  기록해 재개 시 대조하고 (`:507-511`), 모델 없는 자동 재개가 저장된 모델을
  조용히 바꾸지 못하게 막는다 (`:326`, `:494`). `_max_resume_retries = 3`.
- stall 기준은 실행 스트림의 **침묵 900초** (RUN_UPSTREAM_FINDINGS의
  `STALL_TIMEOUT_SECONDS`, `evidence/runtime_metadata.py:76`) — 총 실행
  시간이 아니라 마지막 신호 이후 시간이다.

## 6. MCP의 방향 구분 — 주 경로는 제어 표면, 그러나 실행 통로도 실재한다

> **2026-08-09 정정.** 원래 제목은 "MCP는 실행 통로가 **아니라** 제어
> 표면이다"였고, 아래 1번은 "코어가 실행할 때는 MCP가 아니라 subprocess다"라고
> 단정했다. **이 일반화는 거짓이다** — upstream은 코어가 MCP **클라이언트**가
> 되어 worker를 구동하는 backend를 실제로 등록해두고 있다(`codex_mcp`). 조사
> 당시 본 것은 `codex`/`claude` backend 두 개뿐이었고, 그 둘이 subprocess인 것을
> backend 축 전체로 넓혀 쓴 것이 오류다. 아래 4번을 추가하고 전모는 §12에 쓴다.

도그푸딩에서 관찰되는 "MCP로 codex와 통신"은 **기본 경로에서는 반대 방향**이다
— worker 실행이 아니라 제어다. 네 경로를 구분해야 한다.

1. **코어 → worker (실행, 기본)**: 기본 backend가 작업을 실행할 때는 MCP가
   아니라 **subprocess**다 — `codex exec`를 직접 띄운다 (§3, §5.
   `codex_cli_adapter.py:3` "shells out to `codex exec`",
   `codex_cli_runtime.py`). 이는 `codex`·`claude`·`opencode` backend에 한해
   참이며, backend 축 전체의 성질이 아니다 (4번).
2. **host → 코어 (제어)**: 도그푸딩에서 보이는 MCP 통신 — host CLI 세션
   (Claude/Codex/OpenCode 안의 skill 계층)이 **ouroboros의 MCP 서버**
   (`ouroboros_evaluate` 등)를 호출한다. worker와의 통신이 아니라
   ouroboros를 조작하는 표면이다.
3. **예외 — plugin 위임**: OpenCode bridge plugin이 호출 세션 안에 로드된
   경우에만, MCP handler가 실행하지 않고 `_subagent` envelope을 돌려줘
   **host가 자기 runtime으로 실행**하게 위임한다. 그 외 모든 runtime에서는
   "실제 in-process 실행 경로를 돌려야 한다"고 명시되어 있다
   (`mcp/tools/subagent.py:793-805`).
4. **코어 → worker (실행, MCP)**: `codex_mcp` backend에서는 코어가 **MCP
   클라이언트**가 되어 `codex mcp-server`의 `codex`/`codex-reply` 툴을 호출한다
   — 1번과 방향이 같고 전송만 MCP다. 기본값이 아니며 별도 backend 이름으로
   선택해야 한다. 상세는 §12.

Mission Control 대응: 1은 [ADR-0033](../adr/0033-first-runtime-adapter-contract.md)
(우리 Codex adapter — 같은 subprocess 축), 2는 Phase 7 MCP control surface
([ADR-0007](../adr/0007-mcp-is-control-surface.md) — 같은 배치), 3은
[Open Questions §8](./OPEN_QUESTIONS.md)(host 직접 작업 경로), 4는
[Open Questions §7](./OPEN_QUESTIONS.md)(leader-driven 실행 모델 채택 여부)의
결정 재료다.

## 7. 완성(text) 경로 — `--output-schema`와 재시도 (2026-08-08 후속)

- **구조화 출력**: JSON Schema를 임시 파일로 쓰고 `--output-schema <path>`로
  전달한다. **Codex는 strict shape를 요구한다** — 모든 property가
  `required`에 있어야 하고 `additionalProperties: false`. 열린 map은
  `{key, value}` 배열로 재작성 후 복원한다
  (`codex_cli_adapter.py:238-273` `_normalize_schema_for_codex`).
- **결과는 `--output-last-message` 파일에서 읽는다** — schema가 있으면 그
  내용이 곧 구조화 JSON이다 (`:895-940`).
- **재시도**: 완성은 부작용이 없으므로 전체 재시도가 안전하다 — transient
  패턴만, 최대 3회, `2**attempt` 지수 backoff. **timeout은 재시도하지
  않는다** (`:1215-1245`).
- **semantic 평가자의 시스템 프롬프트** (`agents/semantic-evaluator.md`):
  "You are a rigorous software evaluation assistant" + JSON exact format 강제
  + 필드 의미 정의 + 통과 기준(“ac_compliance = true, score >= 0.8,
  uncertainty <= 0.3”) — VERIFY findings §6의 스키마·임계와 일치한다.
- 완성 명령에는 `--ephemeral`(세션 미보존) 옵션이 있다 (`:437-438`).

## 8. 실물 스모크 결과 (2026-08-08, codex-cli 0.146.1)

> Evidence level: **Verified by execution** — 사용자 승인 하에 실제 codex를
> 실행했다 (완성 1회, 실행 2회, semantic 판정 2회).

확인된 가정: stdin 프롬프트, `--json` JSONL, `thread.started`/`thread_id`
이벤트(실물 thread id가 `native_session_id`로 기록됨), `--output-last-message`,
`--output-schema` strict 왕복(스키마 그대로의 JSON 반환), `-C` workspace 경계
(파일이 지정 위치에만 생성됨), `--sandbox read-only|workspace-write`.

불일치 2건 — 발견 즉시 정정:

1. **`--full-auto`가 exec에 없다** (0.146.1). upstream의 권한 매핑은 이
   플래그를 쓰지만 실물 exec의 어휘는 `--sandbox read-only |
   workspace-write | danger-full-access`다 → adapter를
   `--sandbox workspace-write`로 정정 (ADR-0033 정정 노트).
2. **semantic 평가 요청에 workspace가 없었다** — 평가자가 엉뚱한 디렉토리를
   검사하고 정직하게 `satisfied: false`("검증 명령을 재현할 수 없다")를
   반환했다. `SemanticEvaluationRequest.workspace` 필수 필드 추가 + 완성
   엔진에 `-C` 전달로 정정 (ADR-0034 정정 노트). 정정 후 재실행에서
   평가자가 workspace 안에서 명령을 직접 재현하고 파일 크기까지 검사해
   확신 있는 판정을 반환했다.

### 8.1 Codex-only 도그푸딩에서 확인한 긴 JSONL 경계 (2026-08-11)

> Evidence level: **Observed + Verified** — 로컬 codex-cli 0.147.0 실물 실패와
> pinned source 직접 대조.

Brief closure audit의 병렬 Codex 호출 중 단일 JSONL event가 Python asyncio
`StreamReader`의 기본 64 KiB line limit를 넘었다. mcx의 text adapter가
`readline()`으로 읽다가 `ValueError: Separator is found, but chunk is longer
than limit`로 중단되었다. 같은 `readline()`을 쓰던 execution adapter도 같은
잠재 결함을 가졌다.

pinned upstream은 이 입력을 이미 별도 경계로 다룬다.

- `providers/codex_cli_stream.py:21-26,36-85,143-232` — 16 KiB fixed chunk로
  incremental UTF-8 decode·newline 분리하며, newline 없는 line buffer는
  50 MiB에서 fail closed 한다.
- `orchestrator/codex_cli_runtime.py:157,2076-2098` — Codex가 asyncio 기본
  limit보다 큰 JSONL event를 낼 수 있다고 명시하고 위 reader를 사용한다.

따라서 mcx도 Codex text·execution adapter에서 `readline()`을 제거하고 같은
50 MiB 상한의 bounded chunk reader를 공유한다. 이는 event 의미나 Runtime
계층을 바꾸는 divergence가 아니라 누락된 upstream transport guard의 복원이다.

### 8.2 workspace 없는 text lane의 cwd 누출 (2026-08-11)

> Evidence level: **Observed + Verified** — Codex-only Brief closure 실물과
> pinned `providers/codex_cli_adapter.py:110-126,367-395` 직접 대조.

upstream `CodexCliLLMAdapter`는 `cwd`가 없으면 `os.getcwd()`를 채택하고 모든
완성 명령에 `-C self._cwd`를 넣는다. mcx Codex adapter도 명시 workspace가
없을 때 `-C`를 생략해 부모 프로세스 cwd를 상속했다. 그 결과 저장소 조사 권한이
없는 Brief closure lane이 우연히 mcx 저장소를 읽고, 실제 mission workspace의
파일이 없다고 잘못 차단했다.

mcx의 Brief 계약은 질문·closure lane이 저장소를 직접 조사하지 않고 선별된
context만 본다는 의도적 경계다 (Brief Guide §4.3, ADR-0004). 따라서 workspace가
없는 Codex text 호출은 호출마다 빈 임시 cwd를 만들어 `-C`로 고정한다. 실제
작업물을 봐야 하는 semantic evaluator처럼 workspace를 명시한 호출은 기존대로
그 경로를 읽기 전용으로 본다. upstream의 기본 cwd 상속과 다른 점은
[ADR-0011 §7](../adr/0011-brief-deliberate-divergences.md#7-다른-adr에서-결정된-차이--등록-링크)에
등록한다.

## 9. 조사하지 않은 것

- ~~OpenCode runtime의 상세 계약 (`opencode_runtime.py`)~~ — **§11에서 조사
  완료** (2026-08-08 후속). 이 줄은 2026-08-09까지 남아 있던 낡은 표기다.
- `AgentMessage`의 정확한 필드와 이벤트 정규화 규칙 — 스트리밍 도입 시.
- **`ClaudeAgentAdapter`의 전송 방식** (기본 `runtime_backend="claude"`가 쓰는
  runtime) — §12.2 표에서 미조사로 남았다. 우리 텍스트 lane은 `claude -p`
  단발이고(§10) 이 adapter는 실행 lane이라 축이 다르다.
- **leader-driven worker pool의 상세 계약** — `LeaderDrivenWorkerRuntime`의
  spawn/resume 계약, 세션 풀 수명, 실패 시 재배치 규칙. Open Questions §7의
  실행 모델 결정이 이 조사를 요구하면 그때 수행한다 (§12.5).

## 10. Claude 텍스트 backend 조사 (2026-08-08 후속)

사용자 확정 방향(claude가 brief·blueprint·verify 판정 담당)의 재료.
upstream 근거는 `providers/claude_code_adapter.py`, 로컬 실물은 claude CLI
**2.1.226** (스모크 2회, **Verified by execution**).

### upstream `ClaudeCodeAdapter` (Verified — 소스)

- 전송: SDK가 있으면 SDK, 없으면 **CLI print 모드 fallback** —
  `claude -p --output-format json [--model M] [--append-system-prompt S]
  [--permission-mode P] [--tools T --allowedTools T] --max-turns N
  [--strict-mcp-config --setting-sources ""]`, 프롬프트는 stdin (`:643-707`).
- **`--tools ""`가 도구 카탈로그 자체를 비운다** — `--allowedTools`는 권한
  프롬프트 억제일 뿐이라 둘 다 필요 (`:697-702`). interview/PM/QA 호출자는
  `allowed_tools=[]` + `strict_mcp_config=True`로 만들어 재귀·도구를 차단.
- semantic 평가는 **"20-turn read-only envelope"** (`:665-668` docstring).
- 격리: `--strict-mcp-config --setting-sources ""` — MCP 재발견과 setting
  source(프로젝트 지침·agents·plugins·hooks) 상속을 뿌리에서 차단 (`:705-713`).
- timeout: **총 시간 600s** (`_CLI_DEFAULT_TIMEOUT_SECONDS`, `:108`) —
  print 모드는 끝에 한 번 보고하므로 침묵 기준이 성립하지 않는다.
- envelope: stdout이 JSON 하나 — `result`(문자열)·`is_error`·`subtype`·
  `session_id`·`usage`. 비JSON stdout은 CLI 자체 실패(auth·flag)로 stderr가
  진단 (`:770-790`).
- 구조화 출력: **"CLI path does not reliably honor json_schema"** (`:458`,
  2.1.220 시점) → 스키마를 프롬프트에 싣고 `extract_json_payload`로 추출,
  prose면 `_MAX_JSON_RETRIES = 3` 재질의 (`:71`, `:849-909`).
- transient 재시도는 JSON 강제와 별도 층 (`:912` 이후).

### 로컬 claude CLI 2.1.226 (Verified by execution — 스모크 2회)

upstream이 우회했던 지점이 그 사이 1급 지원이 되었다.

- **`--json-schema <inline JSON>` 플래그가 존재**하고, 응답 envelope에
  **`structured_output` 필드로 스키마 적합 객체가 파싱되어 담긴다**
  (`result`에는 같은 내용의 문자열). 스모크: 무도구 봉투에서 왕복 성공.
- `--tools "" --allowedTools "" --max-turns 1 --strict-mcp-config
  --setting-sources ""` 전부 실플래그 (`--tools`·`--max-turns`는 --help에
  없지만 동작 — upstream 관찰과 일치). 무도구 + `--max-turns 1`에서도
  구조화 출력이 내부 도구 턴으로 처리되어 `num_turns 2`로 성공.
- read-only 봉투 스모크: `--tools "Read Glob Grep"` + cwd=workspace에서
  평가자가 파일을 실제로 읽고(응답 evidence에 파일 내용 인용) 스키마 적합
  판정을 반환. `permission_denials: []` — headless에서 권한 프롬프트 없이
  동작. 호출당 비용 관측: $0.016~0.022 (haiku).
- envelope에 `total_cost_usd`·`permission_denials`·`num_turns`가 있어
  비용·봉투 위반 관측이 공짜다.

### Mission Control 함의 (Claude 엔진)

- 스키마 강제는 프롬프트 삽입이 아니라 `--json-schema` + `structured_output`
  소비로 간다 — codex `--output-schema`와 같은 위치의 CLI측 검증이므로
  upstream의 prose 재질의(3회)는 불필요해진다. 결정은
  [ADR-0036](../adr/0036-claude-text-lane-contract.md).
- 구현 후 실물 확인 (스모크 3번째 호출): 실제 `ClaudeCompletion` +
  `PromptedSemanticEvaluator`로 배열 필드를 포함한 실제 VERDICT_SCHEMA가
  왕복했고, 평가자가 read-only 봉투 안에서 Grep(-o)으로 증거를 직접 세어
  인용하며 satisfied/score 1.0, uncertainty 0.0을 반환했다.

## 11. OpenCode 실행 runtime 조사 (2026-08-08 후속)

사용자 처분(OpenCode까지 Phase 5에서 구현, 용도는 대부분 종반의 부수
작업)의 재료. **괄호 안 용도 전제는 2026-08-09에 철회됐다** — upstream은
OpenCode를 Execute 하네스로 배치한다 (아래 "Mission Control 함의" 정정). upstream 근거는 `orchestrator/opencode_runtime.py`와
`orchestrator/opencode_event_normalizer.py`, 로컬 실물은 opencode CLI
**1.18.15** (`--help` 확인, 실행 스모크는 미수행).

### upstream `OpenCodeRuntime` (Verified — 소스)

- 명령: `opencode run --pure --format json
  [--dangerously-skip-permissions] [--model provider/model] [--session ID]`
  — **프롬프트는 argv가 아니라 stdin** (ARG_MAX 회피, OpenCode가 비TTY
  stdin을 자동 감지) (`:469-524`, `:477-480`).
- **`--pure`가 외부 플러그인을 끈다** — ouroboros-bridge가 subprocess 안에서
  이중 dispatch하는 것을 막는 명시적 격리 (`:497-503`). 우리의 재귀 금지
  (ADR-0004)와 같은 자리.
- 권한: 기본 `permission_mode="bypassPermissions"` →
  `--dangerously-skip-permissions` (`:503-510`). sandbox 모드 개념은 없다 —
  경계는 cwd(작업 디렉토리)다.
- timeout: **2단** — 첫 출력까지 120s(`_startup_output_timeout_seconds`),
  이후 출력 간 유휴 600s(`_stdout_idle_timeout_seconds`) (`:188-192`).
- 이벤트: JSONL, `type` 필드로 dispatch — `text` 이벤트의 `part.text`가
  assistant 텍스트 블록, session id는 이벤트 최상위 `sessionID`
  (normalizer `:10`, `:199`; runtime `:718-729`).
- resume은 `--session <id>`/`--continue`, 자식 세션(subagent)도 네이티브
  지원 — 전부 우리 v1 범위 밖 (ADR-0033 §6 보류 유지).
- 완성(LLMAdapter) 쪽도 같은 전송이다: `providers/opencode_adapter.py` —
  `opencode run --format json` 단발 (§로컬 확인만, 우리는 텍스트 어댑터를
  만들지 않는다).

### 로컬 opencode CLI 1.18.15 (`--help` 확인)

- `--format json`·`--pure`·`--session`·`--model provider/model`·`--agent`
  전부 존재.
- **`--dangerously-skip-permissions`가 help에 없다** — 대신
  `--auto`("auto-approve permissions that are not explicitly denied
  (dangerous!)")가 있다. codex `--full-auto` 부재와 같은 패턴의 드리프트
  후보 — 실행 스모크에서 확인 필요.
- **`--dir`** — "directory to run in" — codex `-C`의 대응물이 생겼다.
  upstream은 cwd로만 경계를 줬지만 로컬은 명시 플래그가 있다.

### upstream은 OpenCode를 언제 쓰는가 (Verified — 소스·문서)

**workflow 로직이 자동으로 OpenCode를 고르는 시점은 없다 — 언제나 사용자
구성의 결과다.** 세 가지 진입로가 전부다.

1. **host일 때 (권장 경로)** — 사용자가 OpenCode 세션 안에서 ouroboros를
   구동하면, `_subagent` envelope을 내는 도구들(`ouroboros_qa`,
   `ouroboros_lateral_think` 등)이 OpenCode 네이티브 **Task pane으로 병렬
   fan-out**된다 — "one child session per subagent, parallel multi-persona
   dispatch" (`docs/runtime-guides/opencode.md` §1). 병렬 부수 작업이라는
   용도의 upstream 실물이 바로 이것이다.
2. **worker 실행 backend로 구성했을 때 (fallback, headless/CI)** —
   `runtime_backend: opencode` 또는 `ouroboros setup --runtime opencode`.
   9종 동급 backend 목록의 하나이며, 문서가 명시하는 자리는 "CLI-driven
   workflows, batch runs, 세션 없는 환경"이다 (같은 문서 §2).
3. **stage별 라우팅** — `runtime_profile.stages`가 닫힌 stage 어휘
   (`interview`/`execute`/`evaluate`/`reflect`)별로 다른 backend를
   지정하고 `default`가 fallback이다 (`config/models.py:480-541`).
   "특정 단계만 다른 runtime"은 upstream에 이미 1급 구성 표면이 있다.

포지셔닝: multi-provider(로컬 모델 포함) 접근이 존재 이유이고, frontier
모델 사용을 권장한다 (guide "Model recommendation").

### Mission Control 함의

> **2026-08-09 정정 — 전제가 틀렸다.** 아래 첫 항목은 "사용자 의도가
> upstream 용법과 정합한다"고 적었으나, 같은 날 `orchestrator_stage.py`를
> 읽고 **upstream이 OpenCode를 Execute 하네스로 배치**함을 확인했다
> (`:1-20` — interview=Codex, **execute=OpenCode/OMX**, evaluate=Claude Code,
> reflect=Hermes). 즉 "OpenCode = 종반 부수 작업"은 upstream 사실이 아니라
> 2026-08-08 시점의 사용자 의도였고, 이 문서가 그것을 upstream 용법과
> 정합한다고 기술한 것은 과대 해석이었다. ①(host 병렬 fan-out)은 사용자가
> **OpenCode를 host로 쓸 때**의 이야기이지 mcx가 OpenCode를 worker로 부를
> 때가 아니다.
>
> 사용자 결정(2026-08-09)은 upstream 방향 채택이다 — Execute의 backend를
> codex/opencode로 갈아끼우는 구조를 [ADR-0039](../adr/0039-stage-runtime-routing-table.md)가
> 연다. 실물 adapter는 이연(로컬 모델 성능).

- ~~사용자 의도(2026-08-08, "대부분 마지막 단계에서 다른 용도·병렬")는
  upstream 용법과 정합한다~~ — 위 정정 참조. 남는 사실은 ③(stage별 라우팅)이
  upstream의 1급 구성 표면이라는 것이고, 우리 대응물이 ADR-0039다.
- 실행 adapter의 구현 시점은 **이연**(ADR-0003 note 3). 구현 시
  스모크 확인 대상: stdin 프롬프트 자동 감지, `--auto`의 실효(권한 프롬프트
  없이 완주), `--dangerously-skip-permissions` 수용 여부(기록용), `text`
  이벤트·`sessionID` 필드 형태의 1.18.15 실물.

## 12. runtime × backend 두 축과 leader-driven worker pool (2026-08-09 후속)

> Evidence level: **Verified** — 소스 확인. Baseline `9486c78`.<br>
> 계기: "backend를 codex↔opencode로 바꾸는 게 MCP 기능이냐"는 질문. 확인 결과
> §6의 일반화가 틀렸고 그 정정을 여기에 쓴다.

### 12.1 축은 두 개다 — backend(무엇)와 runtime(어떻게 구동)

`orchestrator/adapter.py:798-806` (`SubagentOrchestration` docstring):

> "This is a property of the **(runtime × backend) PAIR** … NOT of the backend
> name alone. The same backend can present different modes under different
> runtimes: `codex` driven by `codex exec` is INTERNAL, but the same `codex`
> driven as `codex mcp-server` … is EXTERNAL_LEADER_DRIVEN."

### 12.2 등록된 이름은 vendor가 아니라 vendor×전송이다

`backends/factory_registry.py`와 `orchestrator/runtime_factory.py:72-130`:

| 등록 이름 | `llm_backend` | 실제 전송 | 계열 |
|---|---|---|---|
| `claude` (기본값) | `claude_code` | `ClaudeAgentAdapter` — **미조사** | — |
| `codex` | `codex` | `codex exec` 서브프로세스 | INTERNAL |
| **`codex_mcp`** | **없음** | **`codex mcp-server`를 MCP로 호출** | EXTERNAL_LEADER_DRIVEN |
| `claude_mcp` | **없음** | `claude -p --resume` 서브프로세스 | EXTERNAL_LEADER_DRIVEN |
| `opencode` | `opencode` | `opencode run --pure` 서브프로세스 | subprocess 고정 |

두 가지를 함께 읽어야 한다.

- `*_mcp` 접미사는 **전송 이름이 아니라 계열 이름**이다. `claude_mcp`의 전송은
  MCP가 아니라 `claude -p --resume`다 (`runtime_factory.py:107-120`). 이 계열에서
  실제로 MCP를 쓰는 것은 **`codex_mcp` 하나뿐**이다.
- MCP 구동 변종에는 `llm_backend`가 **없다** — 텍스트 lane이 아니라 **실행
  lane에만** 존재한다.

### 12.3 재사용되는 것은 worker pool 골격이고 vendor마다 다른 것은 transport다

`orchestrator/worker_runtime.py:1-15`:

> "ouroboros is the LEADER and drives an addressable, resumable worker session
> DIRECTLY — it spawns a session, holds its native id, and continues it across
> turns. … a provider becomes a worker pool by supplying a thin
> `LeaderDrivenWorkerTransport` (spawn + resume), not a bespoke runtime."

codex의 transport가 MCP(`codex`/`codex-reply` + `threadId`), claude의 transport가
`--resume`(`session_id`)다. 오케스트레이션 두뇌(ParallelExecutor / AgentProcess /
EventStore)는 둘 다에서 그대로다.

### 12.4 기본값과 한계 — MCP 구동은 기본도 아니고 완성형도 아니다

- 기본 `runtime_backend`는 **`"claude"`**다. 해석 순서는 `OUROBOROS_AGENT_RUNTIME`
  → `OUROBOROS_RUNTIME` → `config.yaml orchestrator.runtime_backend` → 하드코딩
  `"claude"` (`config/loader.py:651-658`).
- `codex mcp-server` 세션은 **프로세스 귀속**이다. 동시성 안전을 위해
  spawn-per-call을 택했기 때문에 다른 프로세스의 `codex-reply`는 "Session not
  found"를 돌려준다. 그래서 이 transport는 **단발 턴만** 네이티브로 지원하고,
  견고한 다중 턴 resume은 영속 연결 풀이 필요한 **upstream 자신의 후속 과제**다
  (`codex_mcp_runtime.py:1-26`, 2026-06-21 검증 기록).
- 대조: `codex exec resume`과 `claude -p --resume`은 디스크 영속이라 프로세스를
  넘겨 재개된다.

### 12.5 Mission Control 함의

- 우리 실행 모델은 **단발**이다 — `codex exec` 한 번이 AC 하나
  ([ADR-0033](../adr/0033-first-runtime-adapter-contract.md)). upstream의 `codex`
  backend와 같은 축이고, leader-driven / MCP 구동 변종의 **대응물은 없다**.
- 실행 모델과 세션 재개 표현은 되돌리기 비싼 축이므로 "필요해지면 재평가"로
  넘기지 않고 미결로 등록한다 → [Open Questions §7](./OPEN_QUESTIONS.md).
- **backend 이름 축은 이미 정렬되어 있다.** 우리 `codex_cli`
  (`ExecutionRuntime.backend`)는 vendor가 아니라 vendor×전송이며, upstream이
  `codex`와 `codex_mcp`를 별개 키로 등록한 것과 같은 결이다.
  [ADR-0039](../adr/0039-stage-runtime-routing-table.md)의 backend 키 공간은 이
  근거 위에 선다.

## 13. Spawn/transport 실패의 표면 — upstream error event와 v1 예외 경계 (2026-08-23)

Issue #5의 재현 조건은 Codex 실행 파일이 없는 상태에서 subprocess spawn이
`FileNotFoundError`를 내는 것이다. 다음은 pinned baseline
`Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943`의 확인 결과다.

- `src/ouroboros/orchestrator/worker_runtime.py:283-325`는 worker turn의
  transport 예외를 정상 `result`와 구별되는 `data.subtype = "error"`와
  `error_type`을 가진 `AgentMessage(type="result")`로 내보낸다. 즉 예외를
  성공으로 합치지 않고 worker 경계의 terminal error로 바꾼다.
- `src/ouroboros/cli/commands/dispatch.py:179-187`는 result의
  `tool_error` 또는 `subtype == "error"`를 관찰하면 CLI exit code를 1로
  바꾼다.
- upstream에는 우리 `AttemptStatus`와 동일한 durable `DISPATCHED` 모델이 이
  호출 경로에 없다. 따라서 **error event/exit 1 경계는 채택**하되, 실행 전
  durable-first와 Recover 자동 재시도 차단은 우리 ADR-0024 상태 모델로
  표현한다.

우리의 deliberate mapping은 다음과 같다.

1. Codex execution/text adapter가 실제 `create_subprocess_exec`의 `OSError`를
   `RuntimeUnavailableError`로 감싼다. `which` 선행 검사는 하지 않는다.
2. ExecuteService는 이 예외를 `EXECUTION_FAILED` 또는 Coordinator 실패로
   저장하지 않고 다시 올린다. 이미 저장한 attempt는 `DISPATCHED`로 남으므로
   Gate는 `HOLD`하고 Recover packet은 생성하지 않는다.
3. process가 시작된 뒤의 non-zero exit와 timeout은 upstream의 worker/runtime
   failure와 같은 별도 관찰 경로이므로 기존 outcome 계약을 유지한다.

Evidence level: **Verified** (pinned source); 우리 mapping은
[ADR-0057](../adr/0057-runtime-spawn-failure-boundary.md)의 Accepted decision.

## Mission Control 함의

결정은 [ADR-0033](../adr/0033-first-runtime-adapter-contract.md)(port 분리
확정, Codex 우선 순서, 첫 실행 adapter 계약)에 있다.
