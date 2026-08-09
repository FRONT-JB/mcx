# ADR 0040 — Secret redaction의 경계와 두 프로필

- Status: Accepted
- Date: 2026-08-09
- Constitutional basis: [ADR-0007](./0007-mcp-is-control-surface.md) (MCP는 제어 표면),
  [ADR-0027](./0027-telemetry-layers-and-v1-schema.md) (Telemetry 층 분리)
- Upstream evidence: [SECURITY_UPSTREAM_FINDINGS](../research/SECURITY_UPSTREAM_FINDINGS.md)
- 진입 조건 해소: Phase 7 (MCP control surface) — [Open Questions §9](../research/OPEN_QUESTIONS.md)

## Context

secret redaction은 원래 Phase 5 시한이었고 **무처분 도과**했다. 2026-08-09
사용자 결정으로 **Phase 7 진입 조건**으로 재지정됐다 — 상태와 Telemetry가 MCP로
host 세션에 나가기 전에 확정해야 한다.

조사 전 우리 가정은 "MCP로 나가기 전에 한 겹 가린다"였다. **upstream은 네
지점에 서로 다른 코드로 둔다** — 입력 한도(`core/security.py`),
로깅(`observability/logging.py`), 저장 거부(`orchestrator/workflow_lifecycle.py`),
MCP 출력 마스킹(`mcp/resources/handlers.py`). 한 겹만 만들면 upstream보다 얇다.

우리 표면 실측(2026-08-09)에서 드러난 것:

- 원시 출력이 **두 곳**에 있다 — `outputs/verify_output_*.txt`(전문)과 상태
  문서의 `output_tail`(2000자 발췌).
- 실행 실패 발췌 `error`도 같은 성질이다 (codex 합류 출력의 tail).
- `state/current_mission`만 **0644**였다 — "0600이 유일한 방어"라는 기존 기술이
  전부 참이 아니었다.

## Decision

### 1. 프로필은 둘이고 섞지 않는다

| 프로필 | 가리는 것 | 걸리는 곳 |
|---|---|---|
| **저장** (`redact_credentials`) | 자격증명만 | 상태 문서에 들어가는 발췌 |
| **host** (`redact_for_host`) | 자격증명 + 로컬 경로 | host 대화로 나가는 payload |

**저장 프로필이 경로를 남기는 이유가 이 ADR의 핵심 제약이다.** 상태 문서의
`error` 발췌는 Recover를 거쳐 `PreviousFailure.error_excerpt`로 **worker에게
전달된다** (`recover_service.py:123`). 어느 파일이 실패했는지 모르는 worker는
같은 실패를 반복한다 — 경로를 지우면 Recover의 존재 이유가 무너진다.

반대로 host 프로필은 경로를 지운다. host 대화는 로컬 디렉터리 구조를 알 필요가
없다. upstream도 같은 자리에서 경로를 지운다 — 밖으로 나가는 interview event의
오류 텍스트에 `[redacted path]` (`authoring_handlers.py:1015-1070`).

### 2. lifecycle 기록은 마스킹이 아니라 **거부**다

명령 원장은 프롬프트·원시 출력을 담을 수 없다. 마스킹해서 저장하는 것이 아니라
**쓰기가 예외로 실패**한다 (`RedactionError`).

blocklist는 자격증명만이 아니다 — `prompt`, `raw_prompt`, `stdout`, `stderr`,
`raw_output`이 `api_key`와 같은 등급이다. upstream의 이름이 이유를 말한다:
**replay-unsafe**. 무엇이 들어올지도 크기도 통제되지 않는 값은 그 자리에 있으면
안 된다.

접미사 규칙(`_prompt`, `_stdout`, `_secret` …)이 `worker_prompt` 같은 합성
이름을 잡는다.

### 3. 강제는 호출이 아니라 경계에서 한다

**"부르면 되는 함수"로 두지 않는다.** 새 호출자가 조용히 빠뜨리기 때문이다.
upstream이 raw `BaseEvent` append를 `PersistenceError`로 막은 것과 같은 규율이다
(`event_store.py:1474-1494`):

> "a caller that constructs a raw `BaseEvent` … would bypass that redaction."

우리 강제 지점:

- `ExecutionAttempt.error`·`result_summary` — pydantic field validator. 생성되는
  모든 attempt가 지난다.
- `VerificationRun.output_tail`·`command` — 같은 방식.
- `MissionJournal._append` — 원장의 **유일한 쓰기 경로**. `open`·`close`가 둘 다
  여기를 지나므로 새 필드를 붙여도 가드를 우회할 수 없다.

### 4. 원시 출력 본문은 host로 내보내지 않는다

`outputs/verify_output_*.txt`의 전문은 로컬 증거다. host에게는 **참조
(`output_ref`)와 마스킹된 발췌(`output_tail`)만** 나간다. Phase 7 MCP 응답이
전문을 실으려면 이 ADR을 개정해야 한다.

### 5. 로컬 터미널은 host 표면이 아니다

`mcx`의 stdout·stderr에는 host 프로필을 걸지 않는다. 사용자가 곧 로컬
운용자이며, 자기 경로를 자기에게 가리는 것은 순손실이다. 저장 프로필은 이미
상태 문서에 걸려 있으므로 `status`가 보여주는 발췌는 자격증명이 지워진
상태다.

**Phase 7에서 MCP 응답에는 host 프로필을 건다.** 그 자리가 이 ADR이 대비하는
경계다.

## Consequences

### Positive

- 자격증명이 상태 문서에 저장되는 경로가 닫힌다 — 유출이 MCP 도입을 기다리지
  않는다.
- 원장이 프롬프트·원시 출력을 담을 수 없다는 것이 규약이 아니라 예외다.
- Phase 7은 `redact_for_host`를 응답 직렬화에 거는 것으로 끝난다 — 정책을 그때
  발명하지 않는다.

### Cost

- 저장 프로필이 자격증명을 지우므로 **원문 발췌는 `outputs/` 전문에만 남는다.**
  상태 문서만 보고 재현할 수 없는 실패가 생길 수 있다.
- 패턴 기반 마스킹은 라벨 없는 미등록 형태의 비밀을 놓친다. 고신뢰 형태로
  좁힌 것은 과잉 마스킹으로 증거를 못 읽게 만드는 쪽이 더 나쁘다는 판단이다
  (upstream과 같은 선택).
- 경로 판별이 문자열 모양에 기댄다. URL은 보호했다 복원하지만, 경로처럼 생긴
  비경로 문자열은 host 프로필에서 지워질 수 있다.

## Rejected alternatives

- **출력 경계에서만 마스킹** — 디스크에 원문이 남고, redaction을 안 부르는 새
  출력 경로가 생기면 조용히 샌다.
- **저장 시점에 전면 마스킹(경로 포함)** — Recover가 worker에게 넘길 실패
  발췌에서 경로가 사라져 "같은 prompt를 반복하지 않는다"(Guide §11)가 깨진다.
- **원장도 마스킹으로 처리** — 크기가 통제되지 않는 값이 원장을 오염시킨다.
  거부가 맞다.
- **로컬 stdout에도 host 프로필** — 운용자에게서 자기 경로를 가리는 순손실.

## Verification

- 고신뢰 형태(`ghp_`, `sk-`, `AIza`, `AKIA`, `xox`, JWT), 플래그(`--api-key=`),
  라벨(`SECRET=`), `Bearer`가 저장 프로필에서 지워진다.
- 평범한 오류 텍스트와 상대 경로는 저장 프로필이 건드리지 않는다.
- **저장 프로필은 절대 경로를 남기고 host 프로필은 지운다.**
- host 프로필에서 URL은 살아남고, 민감한 이름의 필드는 값 전체가 지워진다.
- `ExecutionAttempt`와 `VerificationRun`은 **아무도 호출하지 않아도** 생성
  시점에 마스킹된다.
- 원장은 replay-unsafe 키를 만나면 쓰지 않고 예외를 올리며, 그 키 이름을
  알린다. `calls`의 backend 이름 자리도 예외가 아니다.
- `state/current_mission`이 다른 상태 파일과 같은 0600이다.
