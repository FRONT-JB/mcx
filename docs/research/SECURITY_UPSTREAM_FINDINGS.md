# Security Upstream Findings — secret redaction과 노출 경계

> Checked: 2026-08-09. Baseline: `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
> (`~/.claude/plugins/marketplaces/ouroboros`).<br>
> Scope: [Open Questions §9](./OPEN_QUESTIONS.md)의 secret redaction — **Phase 7
> 진입 조건**. 상태·Telemetry가 MCP로 host 세션에 나가기 전에 무엇을 가리는가.<br>
> Evidence level: 별도 표기 없으면 **Verified** (소스 확인).

## 1. upstream은 redaction을 한 겹으로 두지 않는다

한 개의 "redact()" 함수가 아니라 **역할이 다른 네 지점**이 있다. 이것이 이
조사의 가장 중요한 결과다 — 우리가 "MCP 나가기 전에 가린다" 한 겹만 만들면
upstream보다 얇다.

| 지점 | 파일 | 하는 일 |
|---|---|---|
| 입력 한도 | `core/security.py` | 외부 입력 크기 상한 (DoS 방지) |
| 로깅 | `observability/logging.py:56-60` | 로그 레코드의 민감 필드·값 마스킹 |
| **저장(구조)** | `orchestrator/workflow_lifecycle.py:49-80` | 특정 키를 **애초에 저장하지 못하게 거부** |
| **출력(MCP)** | `mcp/resources/handlers.py:24-80·521-575` | 나가는 event data를 패턴으로 마스킹 |

로깅용 마스커(`core/security.py`)와 MCP 경계 마스커(`mcp/resources/handlers.py`)는
**서로 다른 코드**다. 후자의 주석이 그 의도를 말한다 — *"Project event data
through a conservative MCP-resource redaction layer."* (`:528`)

## 2. 저장 층은 마스킹이 아니라 **거부**다

`WorkflowLifecycleEvent`는 replay-unsafe 키를 담으면 **모델 경계에서 예외**를
올린다 (`workflow_lifecycle.py:398`: *"Workflow lifecycle {name} must not
persist replay-unsafe key"*). 마스킹해서 저장하는 게 아니라 저장 자체를
막는다.

그리고 이 경계를 **우회할 수 없게 가드**가 걸려 있다. raw `BaseEvent`로
`aggregate_type="workflow_ir"`을 직접 append하면 `PersistenceError`다
(`event_store.py:1474-1494`):

> "a caller that constructs a raw `BaseEvent` … would bypass that redaction.
> Route lifecycle persistence exclusively through
> `append_workflow_lifecycle_event`."

**설계 교훈**: redaction을 "부르면 되는 함수"로 두면 안 부른 경로가 남는다.
upstream은 안 부르는 경로를 타입·예외로 막았다.

## 3. blocklist는 자격증명만이 아니다

`_REPLAY_UNSAFE_KEYS` (`workflow_lifecycle.py:49-70`) 전문:

```
api_key, apikey, auth_token, bearer_token, client_secret, credential,
credentials, password, private_key, prompt, raw_prompt, raw_stderr,
raw_stdout, raw_output, refresh_token, secret, stderr, stdout, token
```

접미사 규칙도 있다: `_api_key`, `_credential(s)`, `_password`, `_prompt`,
`_secret`, `_stderr`, `_stdout` …

**`prompt`·`stdout`·`stderr`·`raw_output`이 자격증명과 같은 등급이다.**
이유는 이름이 말한다 — replay-unsafe. 원시 출력과 프롬프트는 (a) 무엇이 들어
있을지 통제되지 않고 (b) 크기가 통제되지 않는다. 우리 [ADR-0027](../adr/0027-telemetry-layers-and-v1-schema.md)
§1이 "원문 출력은 상태 문서에 담지 않고 파일 참조와 발췌만"이라고 한 것과 **같은
축이지만, 우리는 발췌를 상태 문서에 남기고 upstream은 그 키 자체를 거부한다.**

## 4. 경로도 가린다

`mcp/tools/authoring_handlers.py:1015-1070`이 interview 실패 event의 오류
텍스트에서 **로컬 경로 모양 문자열을 제거**한다 (`[redacted path]`). POSIX
절대경로·`~/`·Windows 드라이브를 지우되, **URL은 보호했다가 되돌린다**
(`protect_url` → placeholder → 복원). `/api/`로 시작하는 경로는 예외로 남긴다.

docstring: *"Remove local path-shaped substrings from persisted interview event
text."*

즉 upstream이 가리는 것은 secret ⊃ 자격증명이 아니라 **{자격증명, 프롬프트,
원시 출력, 로컬 경로}**다.

## 5. 출력(MCP) 층의 규칙

`mcp/resources/handlers.py`:

- **필드명 기반** (`_is_secret_field_name`): 마지막 세그먼트가
  `secret`/`token`/`credential`/`password`/`key` 류면 값 전체를 `[redacted]`.
- **패턴 기반** (`_redact_secret_shaped_text`), 네 종류를 순서대로:
  1. CLI 플래그 — `--api-key=…`, `--token …`, `--password …`
  2. 라벨 — `api_key: …`, `secret = …`, `AWS_SECRET_ACCESS_KEY=…`
  3. `Bearer <값>`
  4. 고신뢰 형태 — `ghp_…`, `sk-…`, `AIza…`, `AKIA…`, JWT 3부 구조
- 재귀적으로 dict·list를 내려간다 (`:527-543`).

**고신뢰 패턴만 값 자체를 지운다.** 라벨·플래그가 붙지 않은 임의 문자열은
건드리지 않는다 — 과잉 마스킹으로 증거를 못 읽게 만드는 것을 피한 선택이다.

## 6. 우리 표면 실측 (2026-08-09)

무엇이 실제로 저장되고 무엇이 밖으로 나가는가. Phase 7에서 이 **전부**가 MCP
응답으로 host 대화에 들어갈 수 있다.

| 표면 | 담기는 것 | 현재 방어 |
|---|---|---|
| `state/brief_*.json` | `initial_intent`, 사용자 답변 원문, 질문·판정 | 0600 |
| `state/blueprint_*.json` | goal·constraints·AC·`verify_command` | 0600 |
| `state/execute_*.json` | attempt `error` (실행 실패 발췌) | 0600 |
| `state/verify_*.json` | `output_tail` (합류 출력 끝 2000자), `output_ref` | 0600 |
| `outputs/verify_output_*.txt` | 검증 명령 **합류 출력 전문** | 0600 |
| `state/journal_*.jsonl` | 명령 이름·소요·exit·backend별 호출 수 | 0600 |
| `state/mission_*.json` | **workspace 절대 경로** | 0600 |
| `state/current_mission` | mission id | **0644** ← 불일치 |
| `mcx status` stdout | intent, **차단 사유 원문**, workspace 경로 | 없음 |
| `mcx * --json` stdout | 위 + 상태 스냅샷 | 없음 |

세 가지가 눈에 띈다.

1. **원시 출력이 두 곳에 있다.** `outputs/`의 전문과 상태 문서의 2000자 발췌.
   upstream 기준으로 둘 다 replay-unsafe 등급이다. 검증 명령이 환경변수를
   덤프하거나 `curl -v`가 `Authorization` 헤더를 찍으면 그대로 들어온다.
2. **`error` 발췌도 같은 성질이다** — codex의 합류 출력 tail이다
   (`codex_execution_runtime.py`의 `_OUTPUT_TAIL_CHARS`).
3. **`current_mission`만 0644다.** 담긴 것은 mission id뿐이라 심각도는 낮지만,
   "0600이 유일한 방어"라는 [Open Questions §9](./OPEN_QUESTIONS.md)의 기술이
   전부 참은 아니라는 뜻이다.

## 7. 조사하지 않은 것

- MCP **tool 응답**(resource가 아닌)에 redaction이 걸리는지 — `mcp/tools/`
  전수는 보지 않았다. resource 층은 확인했다.
- `core/security.py`의 `sanitize_for_logging`이 실제로 호출되는 지점 전수.
  로깅 모듈이 `is_sensitive_field`/`is_sensitive_value`/`mask_api_key`를
  import하는 것까지만 확인했다.
- upstream이 사용자 답변(interview 본문)을 노출 경계에서 다루는 방식.

## 8. Mission Control 결정 재료

결정해야 할 축은 셋이며 [Open Questions §9](./OPEN_QUESTIONS.md)에 등록되어
있다. 각 축의 선택지와 대가는 Security ADR에서 확정한다.

1. **적용 지점** — 출력 경계만 / 저장 시점도 / upstream처럼 구조는 거부하고
   자유 텍스트는 출력 시 마스킹.
2. **대상 범위** — 자격증명만 / + 로컬 경로 / + 원시 출력 본문.
3. **우회 방지** — 부르면 되는 함수로 둘지, upstream처럼 안 부르는 경로를
   타입·예외로 막을지.
