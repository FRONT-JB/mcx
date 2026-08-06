# ADR 0002 — Approved Seed is immutable

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Specification before execution

## Context

긴 대화를 실행 중 계속 재해석하면 목표와 비범위가 모델마다 달라진다. 실행 중
에이전트가 Seed를 수정할 수 있으면, 실패한 구현에 맞춰 성공 기준을 바꾸는 일이
가능해지고 검증의 기준도 사라진다.

## Decision

승인된 Blueprint에 대응하는 Seed revision은 불변이다.

- 모든 Execute/Verify attempt는 하나의 Seed revision에 고정된다.
- 실행 중 발견한 요구사항 변경은 기존 revision을 수정하지 않는다.
- 변경은 새 Blueprint revision을 만들고 QA와 승인을 다시 거친다.
- 과거 attempt와 Gate는 당시 사용한 revision을 계속 참조한다.

불변성은 저장 객체를 절대 삭제하지 않는다는 뜻보다, **승인된 의미를 제자리에서
바꾸지 않는다**는 뜻이다.

## Consequences

### Positive

- 실행과 검증의 기준이 안정적이다.
- 어떤 요구사항으로 결과를 만들었는지 재현할 수 있다.
- scope drift와 요구사항 변경을 구분할 수 있다.
- 과거 결과가 새 요구사항 때문에 의미를 잃지 않는다.

### Cost

- 작은 문구 변경도 revision과 재승인 절차가 필요할 수 있다.
- revision lineage와 migration을 저장해야 한다.
- 잘못된 Seed를 실행 중 즉석 수정하는 편법을 허용하지 않는다.

## Rejected alternatives

- Seed YAML을 실행 중 직접 수정한다.
- Flight Controller가 유용하다고 판단한 요구사항을 자동 추가한다.
- Verify가 실패한 AC를 구현에 맞춰 완화한다.

## Verification

- 승인 revision을 직접 변경하려 하면 실패한다.
- 새 revision은 parent revision과 변경 이유를 가진다.
- Execute/Verify report가 정확한 revision을 참조한다.
- 새 revision 승인 전에는 실행이 재개되지 않는다.

