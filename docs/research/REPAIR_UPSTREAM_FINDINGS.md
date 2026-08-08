# Repair Upstream Findings — 실패 분류, 회복 정책, 증거 전달

> Checked: 2026-08-08. Baseline: `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
> (`~/.claude/plugins/marketplaces/ouroboros`).<br>
> Scope: [Open Questions §6](./OPEN_QUESTIONS.md)(failure taxonomy, retry
> budget, 동일 실패 탐지)과
> [ADR-0025](../adr/0025-execute-deliberate-divergences.md) 미확인 항목(실패
> 증거 전달) — Recover 첫 slice 계약의 재료.<br>
> Evidence level: 별도 표기 없으면 **Verified** (소스 확인).

## 1. 실패 분류 — verifier가 매기는 6종 (`orchestrator/failure_taxonomy.py:28-56`)

`FailureClass`: `EVIDENCE_MISSING`(증거 레코드 생성 실패) /
`EVIDENCE_FORM_MISMATCH`(작업은 했으나 증거 형태가 계약을 입증 못함) /
`FABRICATION_SUSPECTED`(존재하지 않는 파일·심볼 주장) / `SCOPE_CREEP`(AC에서
이탈) / `STALL`(재시도가 도움될 것 같지 않음) / `BLOCKED`(도구·권한·env 등
hard precondition).

- 분류 주체는 **verifier**다 — 실패한 leaf의 자기 보고가 아니다.
- `BounceCause`(TOO_BIG/BAD_SPEC/…)와 **의도적으로 분리**되어 있다 — 분해
  트리거와 실패 분류는 다른 축이다 (`decomposition_policy.py:105-110` 주석).
- `BLOCKED`만은 결정적으로도 인식한다 — 권한/도구/env 패턴 정규식과 provider
  metadata의 bounded 순회, 한도 초과 시 fail-closed로 BLOCKED
  (`failure_taxonomy.py:92-169`).

## 2. 분류→행동 정책 테이블 (`failure_taxonomy.py:172-254`)

`RecoveryAction` 5종과 canonical 매핑:

| FailureClass | 행동 | 근거 (소스 주석) |
|---|---|---|
| EVIDENCE_MISSING | `RETRY` | verifier feedback이 이미 누락 필드를 지목한다 |
| EVIDENCE_FORM_MISMATCH | `RETRY` | 계약에 맞는 증거 형태로 재시도 |
| FABRICATION_SUSPECTED | `ESCALATE_MODEL` | 상위 tier로 — self-grounding이 강한 모델 |
| SCOPE_CREEP | `REDISPATCH` | AC를 더 쪼개 단일 산출물로 |
| STALL | `REDISPATCH` | "같은 prompt 반복 재시도는 도움이 안 된다" |
| BLOCKED | `ESCALATE_HUMAN` | harness가 자동으로 채울 수 없는 전제 |

`RETRY`는 "**같은 dispatch, verifier의 feedback과 함께**"로 정의된다 (`:176`).
`REDISPATCH_ALT_HARNESS`(같은 AC를 **다른 vendor runtime**에) — 단일 vendor
harness는 할 수 없는 meta-harness 고유 수단 (`:179-184`).

## 3. 실패 증거는 재시도 프롬프트에 실린다 (`parallel_executor.py:10565-10599`)

`_build_ac_retry_prompt`의 세 요소:

1. **이전 실패 분류** — "### Prior failure classification".
2. **마지막 오류 tail** — redact 후 마지막 500자.
3. **마지막 시도에만**: lateral "접근 전환" directive — "이전 시도들이 위처럼
   실패했다; 같은 접근은 동작하지 않는다".

재시도 상한은 `ac_retry_attempts`(실제 run 경로 기본 **2**,
[VERIFY_UPSTREAM_FINDINGS §2](./VERIFY_UPSTREAM_FINDINGS.md)). 이로써
ADR-0025 미확인 행("실패 증거 전달")이 완전히 해소된다.

## 4. 정체(stagnation) 탐지 — 4패턴, 해시 기반 (`resilience/stagnation.py`)

| 패턴 | 의미 | 기본 임계 |
|---|---|---|
| SPINNING | 동일 출력/오류의 반복 (해시 일치) | 3회 |
| OSCILLATION | A→B→A→B 진동 | 2사이클 |
| NO_DRIFT | 출력은 있으나 진전 없음 | 3 |
| DIMINISHING_RETURNS | 개선 폭 지속 감소 | 3 |

탐지는 출력·오류 문자열의 해시 비교로 결정적이며, 결과는 confidence +
evidence dict를 담는다 (`:58-100`, `:260-292`).

## 5. RecoveryPlanner — 개입 예산 1회의 lateral 전환 (`resilience/recovery.py`)

- 행동 3종: `CONTINUE` / `INJECT_LATERAL_DIRECTIVE` / `STAGNATED`(terminal).
- **개입 예산 기본 1회** (`max_interventions=1`, `:64`) — 소진 시 STAGNATED.
- directive는 프롬프트 블록이다: 패턴·persona·이유를 명시하고 "실패한 경로를
  반복하지 말라. 같은 작업을 전략만 바꿔 계속하라. AC를 전진시키는 구체적
  patch 또는 검증 step을 내라" (`:100-112`).
- persona는 패턴별로 선택하며 이미 쓴 persona는 배제한다 — 같은 처방의
  반복을 막는다.

## 6. 조사하지 않은 것

- evolution 루프의 repair phase 상세(wonder/reflect와의 관계) — 진화 루프
  자체가 v1 범위 밖이므로 필요 시 조사한다.
- rollback/worktree 복구 (`core/worktree.py`) — rollback 결정(§6) 시 조사한다.
- lateral persona의 상세 계약 — lateral 도입 시 조사한다.

## Mission Control 함의

결정은 [ADR-0031](../adr/0031-recover-v1-failure-and-retry-contract.md)(실패
packet·회복 정책·예산)과
[ADR-0032](../adr/0032-recover-deliberate-divergences.md)(Recover divergence
등록부)에 있다.
