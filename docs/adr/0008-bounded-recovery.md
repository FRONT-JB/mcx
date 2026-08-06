# ADR 0008 — Recovery is evidence-driven and bounded

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Recovery uses failure evidence

## Context

에이전트 실패에 같은 prompt를 반복하면 비용과 시간이 늘고, 동일한 오류나 A/B
진동이 계속될 수 있다. 반대로 한 번 실패했다고 Mission 전체를 폐기하면 이미
얻은 evidence와 완료 작업을 잃는다.

## Decision

Recover는 실패 evidence를 입력으로 하는 새로운 bounded attempt다.

- 실패한 AC 또는 Gate condition을 식별한다.
- expected/observed 차이와 재현 정보를 포함한다.
- 실패와 관련된 최소 capability와 파일 scope만 연다.
- 이전 attempt를 덮어쓰지 않는다.
- retry budget과 progress signal을 가진다.
- 동일 실패 또는 무진전을 감지하면 전략을 바꾸거나 HOLD한다.
- 제품 결정/Seed 문제는 코드 수정으로 해결하지 않고 Brief/Blueprint로 보낸다.
- Recover 결과는 반드시 다시 Verify한다.

## Consequences

### Positive

- 실패가 다음 시도를 더 정확하게 만든다.
- 무한 루프와 범위 확장을 제한한다.
- Runtime failure, implementation failure, specification gap을 다르게 처리한다.
- 사용자에게 지금까지의 시도와 남은 선택지를 설명할 수 있다.

### Cost

- attempt lineage와 failure taxonomy를 저장해야 한다.
- progress 측정과 stagnation 감지가 필요하다.
- 자동 교정할 수 없는 경우 사람의 결정까지 멈춰야 한다.

## Rejected alternatives

- 실패 시 전체 Mission을 처음부터 다시 실행한다.
- 같은 prompt를 고정 횟수만큼 무조건 반복한다.
- 실패한 AC를 삭제하거나 기준을 낮춘다.
- retry 한도를 두지 않는다.

## Verification

- Recover packet이 source failure evidence를 참조한다.
- retry는 새로운 attempt ID를 가진다.
- budget 소진 시 추가 dispatch 없이 HOLD한다.
- 성공한 repair도 Verify 전에는 MISSION COMPLETE가 아니다.
