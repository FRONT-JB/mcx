# Runtime Upstream Findings — adapter protocol과 Codex 실행 계약

> Checked: 2026-08-08. Baseline: `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
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

## 6. MCP는 실행 통로가 아니라 제어 표면이다 — 방향 구분

도그푸딩에서 관찰되는 "MCP로 codex와 통신"은 **반대 방향**이다 — worker
실행이 아니라 제어다. 세 경로를 구분해야 한다.

1. **코어 → worker (실행)**: Python 코어가 작업을 실행할 때는 MCP가 아니라
   **subprocess**다 — `codex exec`를 직접 띄운다 (§3, §5.
   `codex_cli_adapter.py:3` "shells out to `codex exec`",
   `codex_cli_runtime.py`).
2. **host → 코어 (제어)**: 도그푸딩에서 보이는 MCP 통신 — host CLI 세션
   (Claude/Codex/OpenCode 안의 skill 계층)이 **ouroboros의 MCP 서버**
   (`ouroboros_evaluate` 등)를 호출한다. worker와의 통신이 아니라
   ouroboros를 조작하는 표면이다.
3. **예외 — plugin 위임**: OpenCode bridge plugin이 호출 세션 안에 로드된
   경우에만, MCP handler가 실행하지 않고 `_subagent` envelope을 돌려줘
   **host가 자기 runtime으로 실행**하게 위임한다. 그 외 모든 runtime에서는
   "실제 in-process 실행 경로를 돌려야 한다"고 명시되어 있다
   (`mcp/tools/subagent.py:793-805`).

Mission Control 대응: 1은 [ADR-0033](../adr/0033-first-runtime-adapter-contract.md)
(우리 Codex adapter — 같은 subprocess 축), 2는 Phase 7 MCP control surface
([ADR-0007](../adr/0007-mcp-is-control-surface.md) — 같은 배치), 3은
[Open Questions §8](./OPEN_QUESTIONS.md)(host 직접 작업 경로)의 결정 재료다.

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

## 9. 조사하지 않은 것

- OpenCode runtime의 상세 계약 (`opencode_runtime.py`) — 두 번째 adapter
  도입 시 조사한다.
- `AgentMessage`의 정확한 필드와 이벤트 정규화 규칙 — 스트리밍 도입 시.

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

## Mission Control 함의

결정은 [ADR-0033](../adr/0033-first-runtime-adapter-contract.md)(port 분리
확정, Codex 우선 순서, 첫 실행 adapter 계약)에 있다.
