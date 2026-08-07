# ADR 0014 — Brief 상태의 동시 쓰기 보호와 두 개의 버전 축

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 5 (User authority), Principle 7 (Durable state over conversation memory), Appendix A 8·16
- Upstream evidence: [PERSISTENCE_UPSTREAM_FINDINGS.md](../research/PERSISTENCE_UPSTREAM_FINDINGS.md) §9
- Amends: [ADR-0013](./0013-brief-durable-state-baseline.md) §3의 "stale revision에 기반한 갱신은 거부한다"

## Context

[ADR-0013](./0013-brief-durable-state-baseline.md) §3은 쓰기 계약 네 항목을
나열했다. 임시 파일 원자적 교체, file lock 직렬화, 저장 실패를 삼키지 않기,
그리고 **"stale revision에 기반한 갱신은 거부한다"**.

앞의 세 항목은 upstream 근거가 있다. 네 번째는 없다. ADR-0013의 Context는
upstream이 하는 일을 다섯 줄로 정리하면서 동시성 제어를 언급하지 않았고,
`:22-24`에서 "`05_BRIEF.md` §8.1은 upstream에 없는 요구를 추가한다"고 명시하면서
revision 증가와 승인 바인딩만 열거하고 이 항목은 빼놓았다. 근거 있는 항목 셋
사이에 근거 없는 항목 하나가 같은 형식으로 놓였다.

이 요구는 실제로는 더 이른 시점에 들어왔다. Stage Guide를 작성한 commit
`e731865`가 Entry Contract, §14.1, §15 error table, §17 B-017, §17.1 test double
다섯 자리에 동시에 기록했으며, 이는 Brief upstream 조사(`a2cb097`)보다 앞선다.
조사 결과를 계약에 반영한 commit `9886877`은 stale 관련 줄을 하나도 건드리지
않았다 — **그 줄들이 미확인 상태라는 표시가 없었기 때문이다.**

한편 Phase 1 구현은 `revision` 하나로 두 가지 판정을 하려다 모순에 부딪혔다.
답변 대기 질문은 저장되어야 하지만(세션이 끊겨도 같은 질문으로 재개) 요구사항을
바꾸지 않으므로 승인을 무효화해서는 안 된다. 저장소가 "revision이 올라야
저장한다"고 요구하면 두 조건을 동시에 만족할 수 없다. 통합 테스트가 이를 잡았고
구현은 축을 둘로 나눴으나, 그 결정 역시 upstream과 대조되지 않았고 어떤 계약
문서에도 반영되지 않았다.

### upstream이 이 문제를 겪지 않는 이유

upstream은 축을 나눠서 푸는 것이 아니라 **문제를 만들지 않는다**
([PERSISTENCE_UPSTREAM_FINDINGS](../research/PERSISTENCE_UPSTREAM_FINDINGS.md) §9).

- interview state 저장은 last-write-wins다. version precondition도 충돌 분기도
  없다.
- 답변 대기 질문 저장은 `rounds`와 `updated_at`만 건드리고 완료 신호를 손대지
  않는다.
- 유일한 정수 `requirement_input_revision`은 파생 캐시 무효화용이며 승인이나
  완료를 가리키지 않는다. 승인이 참조하는 version stamp 자체가 없다.

## Decision

### 1. stale write 거부를 유지한다 — upstream과의 의도적 차이

**upstream**: interview state 저장에 동시 쓰기 보호가 없다. 두 경로가 같은
상태에서 출발해 각자 저장하면 나중 쓰기가 앞 쓰기를 조용히 삼킨다.

**Mission Control**: 저장된 것보다 앞서지 않는 쓰기를 거부한다.

**근거**: upstream은 승인을 특정 버전에 묶지 않으므로 이 보호 없이도 모순이
없다. Mission Control은 [ADR-0011](./0011-brief-deliberate-divergences.md)
Divergence 2로 **승인을 정확한 revision에 바인딩**했다. 그 조건에서 lost update가
발생하면 다음이 성립한다.

```
경로 A의 답변이 유실 → 저장된 내용은 경로 B의 것
승인은 "revision N을 승인함"으로 여전히 유효
그러나 revision N의 실제 내용에는 사용자가 답한 것 하나가 빠져 있다
```

승인은 유효한데 승인한 내용이 아닌 것이 다음 Stage로 넘어간다. 이는 Appendix A
8번이 막으려는 상황 자체이며, 승인을 revision에 묶은 결정이 lost update를
전제하지 않고서는 성립하지 않는다. 즉 이 보호는 Divergence 2의 **짝**이지 독립적인
추가 기능이 아니다.

### 2. 버전 축을 둘로 나눈다

| 축 | 의미 | 올라가는 시점 | 판정 대상 |
|---|---|---|---|
| `revision` | 내용 버전 | 요구사항에 영향을 주는 변경 | 승인이 현재 내용에 유효한가 |
| `sequence` | 쓰기 순서 | 상태가 바뀌는 모든 저장 | 이 쓰기가 저장된 것보다 앞서는가 |

- 답변 기록과 미해결 항목 추가는 둘 다 올린다.
- 질문 제시, clarity 평가 기록, 승인 기록은 `sequence`만 올린다. 셋 다
  요구사항을 바꾸지 않으므로 기존 승인의 의미를 바꿔서는 안 된다.
- 저장소의 거부 판정 기준은 `sequence`다.

한 축으로 유지하면 "저장되어야 하지만 승인을 무효화하면 안 되는 변경"을 표현할
수 없다. 두 요구를 하나의 정수에 얹은 것이 원래 결함이었다.

### 3. 충돌 시 호출자 계약 — Phase 1에서는 미완성이다

[Brief Guide](../05_BRIEF.md) §15는 stale 충돌에 "최신 question과 revision을
제시해 재확인"을 요구한다. Phase 1은 **탐지까지만 구현한다.** 저장소가
`StaleWriteError`를 올리고 application 계층은 이를 잡지 않는다.

이 상태를 계약 미달로 명시한다. 재확인 경로는 동시 writer가 실제로 존재하는
시점, 즉 MCP surface(Phase 7) 도입과 함께 구현한다. 조용한 유실 대신 큰 실패를
내는 것은 부분적 이득이지만 §15가 약속한 동작은 아니다.

### 4. 내용 지문(fingerprint)은 도입하지 않는다

upstream은 캐시 무효화에 카운터와 SHA-256 지문을 함께 쓴다
(`core/requirement_candidate.py:269-275`). Mission Control은 지문을 두지 않는다.
파생 캐시가 없고, `revision`이 가리키는 대상은 캐시가 아니라 승인이기 때문이다.
파생 read model을 도입하면 그때 재평가한다.

## Consequences

### Positive

- 승인 바인딩이 동시 쓰기 상황에서도 성립한다.
- 요구사항을 바꾸지 않는 저장(질문 제시, 평가 기록, 승인)이 승인을 무효화하지
  않는다.
- 두 축의 의미가 분리되어 각각 독립적으로 테스트할 수 있다.
- upstream과의 차이가 근거를 가진 결정으로 등록된다.

### Cost

- 상태에 정수가 둘이며 읽는 사람이 둘의 차이를 이해해야 한다.
- 저장할 때마다 사전 읽기가 한 번 발생한다.
- §15의 재확인 동작이 미구현으로 남는다 (위 Decision 3).
- upstream 대비 계약이 하나 늘어 1:1 대조가 이 지점에서 성립하지 않는다.
- 다중 프로세스에서의 보장 수준은 file lock의 한계를 넘지 않는다
  ([ADR-0013](./0013-brief-durable-state-baseline.md) Cost).

## Rejected alternatives

- **upstream처럼 last-write-wins**: 코드와 계약이 단순해지고 문서 작업도 더
  적다. 그러나 승인 바인딩과 짝이 맞지 않아 "유효한 승인 + 유실된 내용"을
  허용한다. 조용한 유실은 오류를 내지 않으므로 발견 자체가 어렵다.
- **단일 카운터 유지**: 원래 결함이다. 저장되어야 하지만 승인을 무효화하면 안
  되는 변경을 표현할 수 없다.
- **upstream식 decoupling만으로 해결**: upstream이 쓰는 방법이지만 우리 문제를
  풀지 못한다. `pose_question`은 이미 승인과 평가를 건드리지 않으며, 모순의
  원인은 저장소가 단조 증가를 요구한 것이었다.
- **`updated_at` 시각으로 판정**: Clock port가 없고, 시각 기반 판정은 같은
  밀리초 내 쓰기를 구분하지 못한다.
- **지금 제거하고 MCP 도입 시 재도입**: 기계장치 자체는 다시 넣기 쉽다. 그러나
  재도입을 잊으면 실패가 조용하고, 이미 작동하고 테스트된 보호를 지울 이유가
  현재 없다.

## Verification

- 저장된 것보다 앞서지 않는 쓰기가 거부되고 저장된 상태가 온전히 남는다
  ([Brief Guide](../05_BRIEF.md) §17의 B-017).
- 질문 제시가 저장되면서 `revision`을 올리지 않는다 (B-014와 함께).
- 승인 이후 답변이 들어오면 승인이 stale 처리된다 (B-014).
- §15의 재확인 경로는 Phase 7에서 구현하며 그 전까지 미달로 기록한다
  ([Project Progress](../progress/README.md)).
