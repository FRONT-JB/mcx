# ADR 0005 — Evidence over reasoning

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Telemetry determines progress

## Context

코딩 agent의 자연어 완료 보고는 실제 build, test, 동작, Acceptance Criterion
충족을 보장하지 않는다. 같은 모델이 작업과 승인까지 맡으면 자기 보고가 자기
검증으로 변한다.

## Decision

Stage 진행과 Mission 완료는 구조화된 Telemetry를 참조하는 Gate만 결정한다.

- worker claim은 보조 context이며 독립 증거가 아니다.
- Execute 완료와 Verify 완료를 분리한다.
- mechanical evidence를 semantic judgment보다 먼저 사용한다.
- AC별 verdict는 evidence reference를 가져야 한다.
- evidence가 누락·손상·불명확하면 낙관적으로 성공 처리하지 않고 HOLD한다.
- Gate decision 자체도 이유, policy version, evidence refs를 남긴다.

## Consequences

### Positive

- 완료 판정이 재현 가능하고 감사 가능하다.
- 실패를 다음 Recover attempt의 정확한 입력으로 사용할 수 있다.
- Runtime 또는 모델을 바꿔도 같은 Gate 원칙을 적용한다.

### Cost

- command output, observation, artifact를 저장하고 redaction해야 한다.
- 모든 요구사항을 자동 검증할 수 없으므로 uncertainty와 사용자 판단 경로가 필요하다.
- 검증이 실행보다 별도 비용을 가진다.

## Rejected alternatives

- Flight Controller가 `done=true`를 반환하면 완료한다.
- 테스트 통과 하나로 모든 AC를 승인한다.
- 의미 평가 모델의 높은 confidence를 실제 evidence 대신 사용한다.

## Verification

- worker claim만 있는 결과는 Verify에서 HOLD한다.
- mechanical failure는 semantic 요약으로 성공 처리되지 않는다.
- MISSION COMPLETE decision은 모든 필수 AC evidence를 참조한다.

