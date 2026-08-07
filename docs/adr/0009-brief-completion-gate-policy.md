# ADR 0009 — Brief completion gate policy

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 2 (Workflow before model), Principle 3 (Evidence over reasoning), Principle 5 (No self-approval)
- Upstream evidence: [INTERVIEW_UPSTREAM_FINDINGS.md](../research/INTERVIEW_UPSTREAM_FINDINGS.md) §2–§4

## Context

[Brief Guide](../05_BRIEF.md) §11은 종료 threshold, dimension floor, stability
streak, 최소 round를 모두 미확정으로 남겨 두었다. Constitution §25도 이 항목의
결정 위치를 “Brief Stage Guide / ADR”로 지정했다.

[UPSTREAM_MAPPING](../research/UPSTREAM_MAPPING.md) §2는 upstream architecture
문서의 `ambiguity <= 0.2`와 source의 “user controls when to stop” 사이에 충돌이
있다고 기록했다. baseline commit
`9486c78575a0332e9b84d93ef5832985291d7943` 조사 결과 둘은 충돌이 아니라 서로
다른 층이었다.

- machine gate: overall threshold + dimension floor + stability streak + minimum
  rounds
- human gate: surface별 사용자 확인 (CLI Confirm, MCP `done`, skill 계층의
  Acceptance Guard와 목표 재진술)

또한 upstream MCP handler는 조건 충족 시 **사용자 신호 없이 interview를 자동
완료**한다. 승인은 그 위 skill 계층이 담당한다. Mission Control에는 그 상위
계층이 없으므로 같은 동작을 그대로 옮기면 Appendix A 불변 조건 7번(“사용자 승인
없이 Blueprint로 진행하지 않는다”)이 깨진다.

## Decision

Brief의 질문 루프 종료 조건과 Gate를 다음과 같이 확정한다.

### 1. 종료 후보 조건 (네 가지 모두 필요)

| 조건 | 초기 기본값 |
|---|---|
| overall ambiguity threshold | `<= 0.20` |
| dimension minimum floor | goal `0.75`, constraint `0.65`, success criteria `0.70`, context `0.60`(brownfield) |
| stability signal | 연속 `2`회 |
| minimum rounds | `3` |

metric은 ambiguity(낮을수록 명확, `0.0`~`1.0`)이고 dimension은 clarity(높을수록
명확)로 평가하며 `ambiguity = 1 − Σ(clarity × weight)`로 집계한다. weight는
greenfield `0.40/0.30/0.30`, brownfield `0.35/0.25/0.25/0.15`다.

### 2. 종료 후보는 `CLEAR`가 아니다

네 조건 충족의 효과는 **질문 루프 중단과 승인 요청 자격**이다. upstream의
자동 완료 지점은 Mission Control에서 승인 요청 시점으로 매핑한다. Gate `CLEAR`는
사용자 승인과 [Brief Guide](../05_BRIEF.md) §11.5의 hard condition을 함께
평가한 뒤에만 가능하다.

### 3. 값은 versioned policy로 주입한다

threshold, floor, weight, streak, minimum round는 prompt의 magic number가 아니라
정책 객체로 주입하고, 저장된 평가는 사용한 policy version을 참조한다. 초기
기본값은 upstream 값을 채택하지만 domain test가 각 조건의 경계를 독립적으로
검증한다.

### 4. 부수 정책

- 최소 round 도달 전에는 clarity 평가를 수행하지 않는다. 미평가와 미통과를
  상태에서 구분한다.
- 평가 실패는 낮은 ambiguity로 해석하지 않고 결과 없음으로 기록하며 stability
  signal을 초기화한다.
- Brief가 material하게 변경되거나 `CLEAR` 이후 재개되면 저장된 평가와 stability
  signal을 함께 무효화한다.
- stability signal은 durable 저장 성공 후에만 사용자에게 보고한다.

## Consequences

### Positive

- 종료 조건이 재현 가능하고 경계 테스트가 가능하다.
- dimension floor가 가중 평균의 상쇄 효과를 막는다.
- stability signal이 단발성 평가 변동에 의한 조기 종료를 막는다.
- upstream과 같은 구조를 사용하므로 동작 차이를 직접 비교할 수 있다.
- 자동 완료를 승인 요청으로 매핑해 헌법 불변 조건을 유지한다.

### Cost

- 조건이 네 개라 “왜 아직 안 끝나는가”를 사용자에게 설명할 책임이 커진다.
- stability signal 때문에 최소 한 번의 추가 평가 round가 필요하다.
- upstream 기본값이 Mission Control의 질문 품질에 맞지 않으면 재조정이 필요하다.

## Rejected alternatives

- **overall threshold만 사용**: 한 dimension이 무너져도 다른 dimension의 높은
  점수가 이를 가린다.
- **stability signal 없이 단일 평가로 종료**: LLM 평가의 분산 때문에 우연히 낮게
  나온 한 번의 결과로 종료된다.
- **수치를 계속 TBD로 두고 구현 시작**: 구현 편의로 숨은 default가 생기며,
  Constitution §25가 금지한다.
- **upstream처럼 사용자 신호 없이 자동 완료**: Mission Control에는 승인을
  담당하는 상위 계층이 없어 불변 조건 7번을 위반한다.

## Verification

- 각 조건의 경계값을 독립적으로 검증하는 domain test가 존재한다
  ([Brief Guide](../05_BRIEF.md) §17의 B-027~B-030, B-034~B-036).
- dimension floor 미달 시 overall threshold를 통과해도 종료 후보가 되지 않는다.
- 최소 round 전에는 평가 dispatch가 발생하지 않는다.
- 네 조건을 충족해도 승인 없이는 `CLEAR`가 기록되지 않는다.
- policy version이 저장된 평가 결과에서 조회된다.
