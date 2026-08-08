# ADR 0031 — Recover v1 실패 packet과 재시도 계약

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 3 (Evidence over reasoning), [ADR-0024](./0024-execute-v1-execution-model.md) §3, [ADR-0028](./0028-verify-v1-mechanical-contract.md)
- Upstream evidence: [REPAIR_UPSTREAM_FINDINGS.md](../research/REPAIR_UPSTREAM_FINDINGS.md)

## Context

Execute v1은 실패한 AC를 상한 없이 동일 요청으로 재시도한다 — Guide
§11("실패했다고 곧바로 같은 prompt를 반복하지 않는다")과의 긴장이 progress
README 알려진 한계로 등록되어 있다. 그 해소가 Recover Stage다. 실패의 분류,
재시도 예산, 증거 전달, 정체 중단은 도메인 개념의 축이므로 구현 전에
고정한다.

upstream 사실 ([REPAIR_UPSTREAM_FINDINGS](../research/REPAIR_UPSTREAM_FINDINGS.md)):

- 실패 분류는 verifier가 매기는 6종이고, 분류→행동의 canonical 테이블이 있다
  (RETRY / ESCALATE_MODEL / REDISPATCH / ESCALATE_HUMAN / ALT_HARNESS) (§1~§2).
- `RETRY`는 "같은 dispatch, verifier feedback과 함께"다. 재시도 프롬프트에
  이전 실패 분류 + 오류 tail(500자) + 마지막 시도의 접근 전환 지시가 실린다.
  상한은 기본 2회 (§3).
- 동일 출력·오류의 해시 반복(3회)은 SPINNING으로 탐지되어 재시도를 중단한다.
  lateral 개입 예산은 1회다 (§4~§5).

## Decision

### 1. 실패 packet은 원천과 증거 참조로 구성된다

Recover의 입력은 "다시 해라"가 아니라 구조화된 실패다 (Guide §6). v1 필드 축:

```text
FailurePacket
  mission_id, blueprint_revision, ac_key     # lineage
  source                                     # 어느 층의 실패인가 (아래 §2)
  classification                             # BLOCKED | STALL | UNCLASSIFIED (아래 §3)
  error_excerpt                              # 마지막 오류/실패 이유 tail
  evidence_refs                              # attempt 번호, VerificationRun output_ref 등
  attempt_count                              # 이 AC의 소진된 시도 수
```

정확한 필드 이름과 serialization은 구현 slice에서 Guide §6의 목록과 대조해
확정한다.

### 2. 실패의 원천은 관측된 층으로 구분한다

v1의 실패 원천 네 가지 — 각각 이미 구현된 기록에서 결정적으로 파생된다:

| source | 파생 원천 | 기본 routing (Guide §5) |
|---|---|---|
| `EXECUTION_FAILED` | Execute attempt의 실패 기록 | 교정 후 재실행 |
| `MECHANICAL_FAILED` | `VerificationRun` 실패 (artifacts/exit/assertion/timeout) | 교정 후 Verify |
| `SEMANTIC_NOT_SATISFIED` | verdict 불충족 | 교정 후 Verify |
| `ESCALATION_PENDING` | verdict `uncertainty > 0.3` | v1은 사용자 결정 (`HOLD`) |

Specification gap(요구 결정 누락·모순)은 Recover work가 아니다 — Brief/
Blueprint로 route한다 (Guide §4.1·§5). upstream의 BAD_SPEC bounce와 같은 축.

### 3. 분류는 결정적으로 인식 가능한 두 가지만 v1에 둔다

- **`BLOCKED`** — 권한·도구·env의 hard precondition. upstream의 결정적
  인식(패턴 + bounded metadata 순회, fail-closed)을 채택한다. 행동은
  `ESCALATE_HUMAN` 대응 — 권한을 우회하지 않고 `HOLD`로 사용자 결정을
  요청한다 (Guide §4.5).
- **`STALL`** — 같은 AC의 연속 실패에서 오류 해시가 동일하게 반복(임계
  **3회**, upstream SPINNING 채택)되면 같은 재시도는 무의미하다. v1 행동은
  `HOLD`다 — upstream의 처방(REDISPATCH 재분해, lateral 전환)은 분해·lateral
  부재로 보류.
- 그 외는 **`UNCLASSIFIED`** — 분류 없이도 원천(§2)과 증거로 재시도는
  가능하다. upstream 6종 중 나머지(FABRICATION, SCOPE_CREEP, EVIDENCE 계열)는
  verifier의 구조화 증거 계약 위의 분류라 v1 대응물이 없다 —
  [ADR-0032](./0032-recover-deliberate-divergences.md) 보류 등록.

### 4. 재시도 예산은 AC당 2회이고 Recover가 소유한다

upstream `ac_retry_attempts` 기본값 채택. 예산의 의미: 같은 AC에 대한 교정
재시도(원래 실행 이후의 재실행)가 2회를 넘으면 `HOLD` — 사용자 결정 없이
계속하지 않는다. 예산은 blueprint revision이 바뀌면 리셋된다(새 계약은 새
작업이다 — ADR-0024 §3의 차단 해제와 같은 축).

### 5. 재시도는 실패 증거를 가지고 간다

교정 재시도의 실행 요청은 upstream `_build_ac_retry_prompt`의 세 요소와
정렬한다: (1) 실패 분류, (2) 마지막 오류 tail(500자 한도), (3) **마지막
시도에는** "같은 접근을 반복하지 말라"는 전환 지시. 이를 위해
`ExecutionRequest`에 선택 필드(`previous_failure`)를 추가한다 — 첫 실행에는
없고, Recover 경로에서만 채워진다. Execute의 동일 요청 무한 재시도 한계가
이 지점에서 해소된다.

### 6. Recover Gate는 MISSION COMPLETE를 선언하지 않는다

Recover의 `CLEAR`는 "교정이 실행되었고 재검증할 준비가 되었다"이며 목적지는
Verify다 (Guide §11). 완료 선언은 여전히 Verify Gate만 한다. 진입은 다른
Stage와 같은 배치 — Execute Gate 또는 Verify Gate의 `HOLD`가 근거이고, 그
근거 없이 Recover가 시작되지 않는다.

## Consequences

### Positive

- "같은 prompt 무한 반복" 한계가 예산(2회)·증거 전달·동일 실패 중단(3회)의
  세 겹으로 닫힌다 — 전부 upstream 값이다.
- 실패 packet이 Verify 증거(output_ref, verdict reasoning)를 참조하므로,
  교정이 추측이 아니라 기록 위에서 시작된다.
- BLOCKED가 결정적으로 인식되어, 권한 문제를 재시도로 문지르는 낭비가 없다.

### Cost

- UNCLASSIFIED가 넓다 — 세밀한 분류(FABRICATION 등)는 Phase 5 verifier
  실체화 전까지 없다.
- STALL·예산 소진의 출구가 `HOLD`뿐이다 — lateral 전환·재분해·모델 승급 같은
  자동 처방이 없어 사람이 개입해야 한다.

## Rejected alternatives

- **upstream 6종 분류를 그대로 채택**: v1에는 그 분류를 매길 verifier 증거
  계약이 없다. 매길 수 없는 분류는 UNCLASSIFIED를 세분화한 장식이 된다.
- **재시도 예산을 mission 전체 공유로**: upstream은 AC 단위다. mission 공유
  예산은 한 AC의 소진이 무관한 AC의 교정을 막는다.
- **동일 실패 중단을 생략**: 예산 2회 안에서도 같은 오류의 기계적 반복은
  낭비이며, upstream이 SPINNING으로 탐지하는 것을 우리가 생략할 이유가 없다.
- **Recover가 Blueprint를 자동 수정**: Guide §5가 금지한다 — 요구 변경은
  재승인 경로다 (ADR-0002).

## Verification

- 실행·검증·판정 실패 각각에서 FailurePacket이 결정적으로 파생된다.
- 같은 AC의 교정 재시도가 2회를 넘으면 `HOLD`하고, 새 revision이 예산을
  리셋한다.
- 재시도 요청에 이전 실패 분류와 오류 tail이 실리고, 마지막 시도에 전환
  지시가 붙는다.
- 동일 오류 해시 3회에서 재시도가 중단된다.
- BLOCKED 인식 시 재시도 없이 `HOLD`한다.
- Recover의 `CLEAR`가 MISSION COMPLETE로 해석되는 경로가 없다.
