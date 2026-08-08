# ADR 0036 — Claude 텍스트 lane: 판정·생성은 Claude, 실행은 Codex

- Status: Accepted
- Date: 2026-08-08
- 근거 조사: [RUNTIME_UPSTREAM_FINDINGS §10](../research/RUNTIME_UPSTREAM_FINDINGS.md)
  (upstream `providers/claude_code_adapter.py` + 로컬 claude CLI 2.1.226 스모크)

## Context

사용자 확정 방향 (2026-08-08): **텍스트 lane(Brief 질문·채점·감사, Blueprint
생성·QA, Verify semantic 판정)은 Claude가, 실행(Execute worker, Recover
교정)은 Codex가 담당한다.** ADR-0003이 v1 Runtime을 Codex/OpenCode로 잡아
두었으므로 이는 명시적 범위 변경이다 — 단, 변경되는 축은 **LLMAdapter(텍스트
완성)뿐**이고 AgentRuntime(실행) 축은 불변이다. upstream도 두 축을 별개
protocol로 두고 vendor를 독립적으로 고른다 (ADR-0033 §1, findings §1).

upstream에는 Claude 어댑터가 이미 있다 (`claude_code_adapter.py`). 다만
upstream이 "CLI는 json_schema를 신뢰할 수 없다"며 프롬프트 삽입 + prose
재질의로 우회한 지점은, 로컬 2.1.226에서 `--json-schema` + envelope의
`structured_output` 필드로 1급 지원이 되었다 (findings §10 — Verified by
execution).

## Decision

### 1. vendor 범위: LLMAdapter 축에 Claude를 추가한다 (ADR-0003 변경)

실행 축은 그대로 Codex(+OpenCode 예정)다. 텍스트 lane의 기본 조립은
Claude, Codex 텍스트 어댑터는 대체 구성으로 유지한다(스모크·도그푸딩
0001로 검증된 경로를 버리지 않는다).

### 2. 프롬프트 클래스는 vendor 중립이다 — 엔진만 vendor별

upstream 정렬: persona(프롬프트)는 vendor 중립이고 LLMAdapter만 vendor별이다.
위임 port 7종의 프롬프트+변환 클래스는 `Prompted*`로 개명하고, 완성 엔진
계약 `CompletionEngine`(`complete_json(prompt, schema, workspace)`)을
Protocol로 분리한다. `CodexCompletion`과 `ClaudeCompletion`이 이를 구현한다.
프롬프트 문장(upstream 영어 원문 계약 포함)은 한 벌만 존재한다 — vendor마다
프롬프트가 갈라지면 계약 문장의 원문 대조가 두 배로 깨지기 쉽다.

### 3. ClaudeCompletion 엔진 계약

- 명령: `claude -p --output-format json --json-schema <inline schema>
  --strict-mcp-config --setting-sources ""` + 도구 봉투(§4), 프롬프트는
  stdin (upstream CLI fallback과 동일 전송).
- 모델은 생성자 주입(`model: str | None`), 기본은 CLI 기본 모델.
- 출력: envelope의 `structured_output`을 1급으로 소비한다. `is_error`,
  0이 아닌 exit code, `structured_output` 부재·비객체는 전부 예외다 —
  조용히 성공으로 해석하지 않는다 (ADR-0034 §4와 동일 규칙).
- **prose 재질의 없음** — upstream의 `_MAX_JSON_RETRIES=3`은 CLI측 스키마
  검증이 없던 시절의 보상책이다. `--json-schema`가 그 자리를 대신한다.
  등록된 divergence (근거: findings §10).
- timeout: **총 시간 600s** (upstream `_CLI_DEFAULT_TIMEOUT_SECONDS` 채택).
  codex 엔진의 침묵 900s와 다른 이유: print 모드는 끝에 한 번 보고하므로
  침묵 기준이 성립하지 않는다. 의도적 비대칭으로 등록.
- 재시도: transient 패턴만, 최대 3회, 2^n backoff (ADR-0034 §3과 동일 축 —
  패턴 목록은 두 엔진이 공유한다).

### 4. 도구 봉투 — 권한은 도구 카탈로그로 강제한다

codex의 sandbox 모드 대응물은 claude에서 도구 카탈로그다 (upstream 정렬):

| 모드 | 플래그 | 사용처 |
|---|---|---|
| 무도구 | `--tools "" --allowedTools "" --max-turns 8` | workspace 없는 role 전부 (질문·채점·감사·생성·QA) |
| 관찰 | `--tools "Read Glob Grep" --allowedTools 동일 --max-turns 20` + cwd=workspace | semantic 평가자 (upstream "20-turn read-only envelope" 정렬) |

> **정정 (2026-08-09, 도그푸딩 0003 — Verified by execution).** 무도구
> 봉투는 원래 `--max-turns 1`이었고 근거로 upstream pairing
> (`evaluation/verification_artifacts.py:109` — "``allowed_tools=[]``
> paired with ``max_turns=1``")을 인용했다. 그러나 그 pairing은 upstream의
> **prose 재질의 lane**의 것이고, 우리가 채택한 `--json-schema` lane(§3의
> 등록된 divergence)은 구조화 출력이 내부 턴을 소비한다 — 0002에서
> `num_turns: 2` 관측(record 0005 §1.6), 0003에서 9-AC Blueprint QA 판정이
> `error_max_turns`로 2회 재현 실패. 무도구 상한을 **8**로 정정한다 —
> 실측 최소(2)의 4× 여유이면서 폭주 방지 상한은 유지. 재관측 시 조정하고,
> upstream 대응물이 없는 값이므로 이 note가 등록이다.

`--tools ""`가 카탈로그를 비우고 `--allowedTools`는 프롬프트 억제일 뿐이라
둘 다 넘긴다 (upstream `:697-702`). `--strict-mcp-config --setting-sources ""`
는 MCP 재발견과 프로젝트 지침·plugins·hooks 상속을 차단한다 — delegated
role의 Mission Control 재귀 금지(ADR-0004)가 플래그로 강제되는 지점이다.

### 5. 보류

- SDK 전송 (upstream 1순위) — CLI로 충분한 동안 도입하지 않는다.
- `permission_denials`·`total_cost_usd`의 telemetry 소비 — §9 layer 결정과
  함께.
- 실행(AgentRuntime) 축의 Claude adapter — 범위 밖 (사용자 구조에 없음).

## Cost

- 봉투가 프롬프트가 아니라 플래그로 강제되는 대신, 플래그 유효성이 CLI
  버전에 묶인다 (`--tools`·`--max-turns`는 --help에 없는 실플래그).
  conformance test가 명령 구성을 고정하고, 버전 상승 시 스모크로 재확인한다.
- 같은 프롬프트가 vendor에 따라 다른 품질을 낼 수 있다 — 도그푸딩으로
  관측하고, vendor별 프롬프트 분기는 관측 근거가 생기기 전에는 만들지
  않는다.

## Verification

- ClaudeCompletion conformance: 명령 구성(무도구/관찰 봉투), stdin 프롬프트,
  `structured_output` 왕복, `is_error`·exit·부재 처리, timeout 정리,
  transient만 재시도 — stub CLI로 고정.
- 프롬프트 클래스가 엔진 protocol만 요구함을 Claude/Codex 두 엔진 모두로
  고정하는 통합 테스트.
