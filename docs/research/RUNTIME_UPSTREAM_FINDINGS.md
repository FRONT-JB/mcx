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

## 6. 조사하지 않은 것

- OpenCode runtime의 상세 계약 (`opencode_runtime.py`) — 두 번째 adapter
  도입 시 조사한다.
- `AgentMessage`의 정확한 필드와 이벤트 정규화 규칙 — 스트리밍 도입 시.
- `--output-schema`의 스키마 형식 — text backend adapter(위임 port) 구현 시.

## Mission Control 함의

결정은 [ADR-0033](../adr/0033-first-runtime-adapter-contract.md)(port 분리
확정, Codex 우선 순서, 첫 실행 adapter 계약)에 있다.
