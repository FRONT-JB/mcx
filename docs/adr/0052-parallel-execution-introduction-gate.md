# ADR 0052 — 병렬 실행 도입 Gate: unknown을 독립으로 간주하지 않는다

- Status: Accepted
- Date: 2026-08-10
- Constitutional basis: §7 Evidence over reasoning, §17 Scope와 Reasoning
  Discipline, [ADR-0004](./0004-stage-scoped-minimum-capability.md),
  [ADR-0024](./0024-execute-v1-execution-model.md),
  [ADR-0045](./0045-worktree-isolation-contract.md)
- Upstream evidence:
  [PARALLEL_EXECUTION_UPSTREAM_FINDINGS](../research/PARALLEL_EXECUTION_UPSTREAM_FINDINGS.md)
- 해소 대상: [Execute Guide](../07_EXECUTE.md) §17의 *병렬 실행을 도입할 Gate*

## Context

Phase 11의 목표는 여러 AC를 동시에 실행하는 것이다. 현재 Execute는 mission당
열린 attempt 하나, 선언 순서의 AC 하나, 같은 mission worktree 하나를 전제로 한다.
병렬화는 application의 loop만 바꾸는 일이 아니라 attempt cardinality·실패
전파·resume authority·공유 파일 충돌을 함께 바꾼다.

pinned upstream을 다시 확인한 결과 병렬 안전은 다음 묶음이었다.

- LLM과 구조화 신호로 dependency stage를 만든다.
- 같은 stage의 workspace-write AC를 실제로 동시에 실행한다.
- worker별 Write/Edit Telemetry로 같은 파일 writer를 찾는다.
- 충돌이 있으면 별도 Level Coordinator AI가 workspace를 검토·수정한다.
- settled workspace를 다시 검증한 뒤 level checkpoint를 남긴다.

현재 mcx는 worker별 write Telemetry와 Coordinator authority가 모두 없다. 최근
brownfield 도그푸딩에서도 AC 세 실행의 합산 변경은 파일 두 개에 집중됐고, 첫
worker가 전체 함수를 만든 뒤 후속 worker들이 경계를 보강했다. worker별 write
set은 기록되지 않아 exact overlap은 확정할 수 없다. 바로 그 상태에서 fan-out만
도입하면 늦은 write가 앞선 변경을 잃어도 판정할 근거가 없다.

## Decision

### 1. Gate를 확정하고 현재 결과를 `HOLD`로 판정한다

병렬 실행 구현은 아래 조건을 **모두** 충족하기 전까지 시작하지 않는다. 현재
결과는 `HOLD`이며 ADR-0024의 선언 순서 순차 실행이 계속 규범이다.

| 조건 | `CLEAR` evidence |
|---|---|
| plan authority | exact Blueprint revision·AC content key 전체에 바인딩된 immutable stage plan. 중복·누락·unknown dependency 없음 |
| cycle handling | 순환이면 `HOLD`. upstream처럼 남은 AC를 같은 level로 바꾸지 않음 |
| shared-write safety | 아래 §2의 conflict authority 하나가 구현·테스트됨 |
| attempt durability | 한 stage의 모든 `DISPATCHED` attempt와 plan을 첫 Runtime effect 전에 원자적으로 저장하고 결과를 attempt id로 결합 |
| crash/resume | 일부 sibling 완료·일부 결과 불명 상태에서 완료 작업을 중복 dispatch하지 않는 replay authority |
| failure isolation | 이미 시작한 sibling 결과는 수집하고, 실패에 의존한 AC만 `BLOCKED`; 무관한 ready AC는 계속함 |
| bounded fan-out | backend별 effective concurrency를 1 이상으로 명시할 때만 동시 실행. unknown backend 기본은 1 |
| evidence ordering | Execute stage checkpoint와 Verify proven git checkpoint를 구분하고, 병렬 worker 주장을 `CLEAR`로 사용하지 않음 |
| real-path proof | 공유 파일 충돌과 독립 AC를 함께 포함한 brownfield dogfood에서 상태·파일·Verify lineage를 실제로 검증 |

### 2. LLM dependency 추론만으로 병렬을 허가하지 않는다

dependency는 논리적 선후관계를 설명하지만 실제 write set의 경계가 아니다. 모델이
“독립”이라고 답하거나 AC 설명에 다른 파일명이 보이는 것만으로 같은 worktree
동시 쓰기를 허가하지 않는다.

shared-write safety를 충족하는 방법은 둘 중 하나를 별도 ADR로 확정해야 한다.

1. **upstream coordinator 경로** — worker별 write Telemetry, 충돌 탐지, 별도
   Coordinator Flight Controller의 bounded repair, settled workspace 재검증.
2. **runtime-enforced disjoint scope** — AC별 write scope를 Runtime이 실제로
   차단하고 stage 안 scope가 서로 겹치지 않음을 결정적으로 증명.

prompt 지시나 LLM 파일 예측은 2번의 “강제”가 아니다. 현재 Codex CLI adapter의
workspace-write sandbox에는 AC별 path allowlist 표면이 없으므로 2번은 현재
구현 가능 경로가 아니다.

### 3. unknown은 parallel-safe가 아니다

다음은 전부 병렬 실행 `HOLD` 또는 순차 fallback이다.

- dependency analysis 실패·불완전 응답
- plan의 AC 누락·중복·현재 revision 불일치
- 순환 dependency
- conflict authority 없음
- backend concurrency 한도 미확인
- crash 뒤 stage owner·완료 population을 재구성할 수 없음

upstream은 dependency analysis 자체가 실패하면 모든 AC를 한 parallel level로
만든다. mcx는 반대로 간다. **알 수 없음을 독립성 증거로 바꾸지 않는다.** 이
차이는 ADR-0025 divergence register에 등록한다.

### 4. mission worktree와 Verify checkpoint는 유지한다

AC별 worktree를 만들지 않는다. upstream도 parallel AC가 한 session worktree를
공유하고, ADR-0045가 이미 같은 격리 단위를 확정했다. AC별 worktree는 별도 merge
정책을 새로 만들고 앞 stage 결과 가시성을 끊는다.

ADR-0046의 checkpoint도 바꾸지 않는다. 그것은 Verify round 뒤 입증된 변경을
커밋하는 경계다. 병렬 실행이 요구하는 것은 Execute 중간의 durable stage state이지
AC별 git commit이 아니다.

### 5. 단순 fan-out은 금지한다

기존 `dispatch_next`를 여러 coroutine에서 부르거나, 각 호출의 저장을 따로 한 뒤
Runtime을 동시에 여는 구현은 Gate를 통과하지 못한다. 한 호출이 다른 호출의
state를 덮어쓰거나 optimistic save에서 실패할 때 이미 worker가 파일을 바꾼 뒤일
수 있기 때문이다.

## Consequences

### Positive

- 성능 개선이 durable lineage와 shared worktree를 조용히 깨지 않는다.
- 병렬 도입에 필요한 실제 최소 묶음이 명시되어, `gather()` 수준의 부분 구현을
  완료로 오인하지 않는다.
- cycle·analysis failure·backend unknown이 모두 fail-closed다.
- 현재 sequential Execute와 Phase 9의 worktree/checkpoint 계약은 변경 없이
  계속 쓸 수 있다.

### Cost

- Phase 11 목표인 실제 동시 실행은 아직 달성되지 않았다.
- upstream coordinator 경로를 고르면 worker Telemetry와 conflict repair용 추가
  Runtime 호출이 필요하다. conflict가 있는 level마다 최소 1회가 추가되고,
  settled workspace 재검증도 뒤따른다.
- coordinator를 도입하지 않으면 현재 Codex CLI 경계에서는 write AC를 안전하게
  병렬화할 방법이 없어 순차 실행을 유지해야 한다.

## Rejected alternatives

- **모든 미실행 AC를 한 번에 fan-out** — dependency 분석 실패 시 upstream이
  쓰는 fallback이지만, conflict guard가 없는 mcx에서는 unknown을 독립으로
  오판한다.
- **LLM이 독립이라고 한 AC만 fan-out** — logical dependency와 write conflict는
  다른 질문이며 Runtime enforcement가 없다.
- **AC description의 파일명으로 분리** — 실제 worker가 공통 helper·test·config를
  건드리는 것을 막지 못한다.
- **AC별 worktree** — ADR-0045의 mission 단위 격리와 upstream shared-worktree
  모델을 뒤집고 새 merge authority를 요구한다.
- **worker 완료 메시지로 충돌 없음 판정** — Telemetry 없는 reasoning이며
  ADR-0005 위반이다.

## Verification

- pinned upstream focused tests 22개가 dependency level·resource 직렬화·실제
  batch fan-out·실패 의존 차단을 재현했다.
- current source audit가 single-open attempt, one-AC service, change Telemetry 없는
  Runtime outcome을 확인했다.
- DOGFOODING_0006의 합산 변경이 파일 둘에 집중되고 후속 worker가 앞선 결과를
  보강한 실제 경로를 overlap-risk evidence로 사용했다. worker별 write attribution
  부재는 안전 증거가 아니라 Gate blocker로 기록했다.
- 문서·ADR에는 Phase 11 implementation `HOLD`가 표시되고, 코드에는 병렬
  dispatch 경로를 추가하지 않는다.
