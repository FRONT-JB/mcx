# ADR 0053 — 병렬 Execute는 durable stage와 Coordinator 재검증으로 연다

- Status: Accepted (사용자 결정 2026-08-10 — ADR-0052의 upstream coordinator
  경로 선택)
- Date: 2026-08-10
- Constitutional basis: §7 Evidence over reasoning, §17 Scope와 Reasoning
  Discipline, [ADR-0004](./0004-stage-scoped-minimum-capability.md),
  [ADR-0024](./0024-execute-v1-execution-model.md),
  [ADR-0045](./0045-worktree-isolation-contract.md),
  [ADR-0052](./0052-parallel-execution-introduction-gate.md)
- Upstream evidence:
  [PARALLEL_EXECUTION_UPSTREAM_FINDINGS](../research/PARALLEL_EXECUTION_UPSTREAM_FINDINGS.md)

## Context

ADR-0052는 shared worktree 병렬 실행을 열기 전에 conflict authority를 고르도록
했다. 사용자는 두 경로 중 **upstream coordinator 경로**를 선택했다.

같은 날 설치된 Codex CLI를 격리된 저장소에서 관측한 결과도 계약에 영향을
준다.

- 편집 도구로 파일을 만들면 같은 절대 경로를 담은 `file_change`가
  `item.started`와 `item.completed`에 나온다.
- 셸 리다이렉션으로 파일을 만들면 `command_execution`만 나오고
  `file_change`는 나오지 않는다.
- 공식 Codex 문서는 `codex exec --json`이 상태 변화별 JSONL을 출력한다고만
  보장하고 개별 item payload schema는 보장하지 않는다.

따라서 worker별 `file_change`가 겹칠 때만 Coordinator를 부르면 **관측되지 않은
셸 write를 충돌 없음으로 오판**한다. 구체적으로 AC-1이 `printf > config.toml`,
AC-2가 편집 도구로 같은 파일을 바꾼 경우, AC-1의 writer identity가 사라져
AC-2만 쓴 것으로 보인다.

## Decision

### 1. 새 표면은 `mcx execute stage`이고 `execute next`는 유지한다

`mcx execute next`의 선언 순서 단일-AC 계약은 바꾸지 않는다. 병렬 경로는
`mcx execute stage --max-workers N`으로 명시한다.

- `--max-workers`를 생략하면 effective concurrency는 1이다.
- 2 이상을 명시한 호출만 실제 fan-out을 허가한다.
- unknown backend의 암묵 기본값도 1이다. 명시값은 stage run에 durable하게
  기록한다.
- 한 stage 안에 기계적 success contract가 없는 AC가 하나라도 있으면 그 stage는
  effective concurrency 1로 내린다. Coordinator 뒤 settled workspace를 독립
  재검사할 수 없기 때문이다.

기존 명령의 의미를 조용히 바꾸지 않으면서 upstream의 “stage 순차, stage 안
병렬” 축을 드러내는 최소 추가다.

### 2. plan은 승인된 Blueprint revision 전체에 고정한다

dependency analyzer는 현재 승인된 Blueprint의 AC content key 전체를 한 번에
받아 각 AC의 direct dependency를 반환한다. 현재 Blueprint에는 structured
dependency metadata가 없으므로 v1 parallel plan의 비어 있지 않은 신호는 LLM
분석이다. 응답은 다음을 모두 만족해야 한다.

- 현재 revision의 AC key가 정확히 한 번씩 등장한다.
- dependency는 현재 revision의 다른 AC key만 가리킨다.
- self edge·중복 edge가 없다.
- 결정적 topological stage를 만들 수 있고 cycle이 없다.

하나라도 어기거나 분석 호출이 실패하면 병렬 plan을 만들지 않고 `HOLD`한다.
upstream의 “분석 실패 → 모든 AC가 한 level” fallback은 이식하지 않는다
(ADR-0025 divergence).

검증된 dependency와 계산된 stage, analyzer backend, Blueprint revision을
immutable plan으로 저장한다. 같은 revision에서는 재분석하지 않는다. 새 revision은
새 plan을 만들며 이전 plan과 stage run은 역사로 남는다.

upstream은 active execution adapter의 LLM backend로 analyzer를 만든다. mcx는
text generation과 workspace-write execution을 분리한 기존 Runtime 경계를
유지해 Execute의 text routing lane을 사용한다
([ADR-0039 amendment](./0039-stage-runtime-routing-table.md)). analyzer backend는
plan에 기록한다.

### 3. 한 stage의 attempt는 첫 Runtime effect 전에 한 번에 저장한다

실행할 ready AC 전부에 대해 attempt id를 먼저 할당하고, stage owner와 함께
Execute state 한 문서에 원자적으로 저장한 뒤 Runtime을 연다. 결과는 완료 순서가
아니라 `execution_id`로 해당 attempt에 결합하고, worker 하나가 끝날 때마다
durable하게 저장한다.

이 규칙 때문에 한 stage에는 여러 `DISPATCHED` attempt가 있을 수 있다. 기존
단일-AC `dispatch`는 계속 열린 attempt 하나만 허용하고, 복수 open은 durable
stage owner가 exact attempt 집합을 소유할 때만 유효하다.

### 4. worker 결과와 충돌 판정은 fail-closed다

각 worker attempt는 completed `file_change` 경로와 write Telemetry 상태를
기록한다.

- 같은 상대경로 writer가 둘 이상이면 exact conflict다.
- `command_execution`이 하나라도 있거나 terminal event가 없으면 write attribution이
  불완전하다.
- exact conflict가 있거나 attribution이 불완전하면 **stage Coordinator를 반드시
  실행**한다.
- exact conflict도 불완전성도 없을 때만 Coordinator를 생략한다.

경로는 workspace 안의 canonical 상대경로로 바꾼다. workspace 밖 경로·파싱
불능은 충돌 없음이 아니라 Telemetry 불완전이다.

upstream은 Write/Edit trace의 같은 파일 writer를 기준으로 Coordinator를 연다.
mcx는 실 Codex의 셸 write 비가시성을 관측했으므로, 불완전할 때 full-stage
Coordinator를 여는 쪽으로 더 보수적으로 간다. 이 차이는 ADR-0025에 등록한다.

### 5. Coordinator는 AC worker와 다른 stage authority다

Coordinator는 AC attempt가 아니다. 한 stage의 sibling 결과가 모두 닫힌 뒤
딱 한 번 열리는 별도 Flight Controller invocation이며 다음 입력만 받는다.

- 승인된 Goal, Constraints, Non-goals
- stage의 AC와 worker 결과
- exact conflict paths
- attribution이 불완전한 AC key
- 같은 mission worktree

권한은 충돌 수습과 stage AC의 공동 성립에 한정된다. 새 요구사항, 범위 확장,
Mission Control 재귀 호출, Verify `CLEAR` 선언은 금지한다. Coordinator attempt도
effect 전에 durable하게 기록하며 **stage당 1회**다. 결과 불명·실패 뒤 자동
재호출하지 않는다.

### 6. Coordinator 뒤 검사는 Verify가 아닌 settled revalidation이다

Coordinator가 실행됐으면 stage에서 실행에 성공한 AC의 승인된 mechanical
success contract를 settled workspace에서 다시 실행한다. artifact → command →
output assertion 순서는 Verify와 같지만 결과의 의미는 다르다.

- 이 검사는 뒤 stage에 손상된 workspace를 넘기지 않는 Execute 안전 장치다.
- `EXECUTED_UNVERIFIED`를 Verify 통과로 바꾸지 않는다.
- Verify evidence store·semantic verdict·proven checkpoint를 만들지 않는다.
- 하나라도 실패하면 stage는 `HOLD`이고 후속 stage를 dispatch하지 않는다.

최종 `MISSION COMPLETE` 권한은 계속 Verify Gate에만 있다.

### 7. 실패와 crash는 완료 작업을 다시 실행하지 않는다

일반 worker 실패는 이미 시작한 sibling을 취소하지 않는다. 다음 stage에서는
실패 AC에 의존한 AC만 `BLOCKED`로 계산하고, 성공 branch에만 의존한 ready AC는
계속 실행할 수 있다. `BLOCKED`는 실제 dispatch attempt가 아니므로 attempt를
만들지 않는다.

예외는 shared provider quota/rate-limit이다. 한 worker 결과가 `429`, `rate
limit`, `quota`, `usage limit`로 정규화되면 아직 끝나지 않은 sibling process를
정리하고 stage를 미완료 `HOLD`로 남긴다. 이미 저장된 sibling 결과는 보존하되
stage reconciliation·후속 dispatch는 하지 않는다. 이는 일반 AC 결함이 아니라
stage 전체가 공유하는 실행 자원 실패이기 때문이다. 취소된 sibling의
`DISPATCHED`는 결과 불명으로 남아 자동 재실행되지 않는다.

재개 권위는 durable plan + stage owner + exact attempt id다.

- 일부 worker 결과가 저장됐고 나머지가 `DISPATCHED`면 완료 worker를 다시
  실행하지 않으며, 결과 불명 worker도 자동 재실행하지 않고 `HOLD`한다.
- 모든 worker 결과가 저장됐지만 reconciliation 전이면 저장된 결과에서 충돌
  판정을 재개한다.
- Coordinator가 `DISPATCHED`로 남으면 side effect가 불명확하므로 자동 재호출하지
  않고 `HOLD`한다.
- Coordinator 결과까지 저장됐으면 read-only settled revalidation은 다시 실행할
  수 있다.

이는 “가능한 것은 계속”보다 “같은 write를 두 번 적용하지 않음”을 우선한다.

### 8. Execute stage state와 Verify git checkpoint를 섞지 않는다

parallel plan·stage run·Coordinator·settled revalidation은 Execute JSON state의
재개 authority다. git commit을 만들지 않는다. 입증된 git checkpoint는 계속
Verify round 뒤 ADR-0046 경계에서만 만든다.

## Consequences

### Positive

- AC 여러 개가 한 worktree에서 실제로 동시에 실행될 수 있다.
- worker 완료 순서와 무관하게 결과가 exact attempt에 붙는다.
- 명시적 파일 겹침뿐 아니라 Codex JSONL이 보지 못한 셸 write도 Coordinator
  review를 건너뛰지 않는다.
- worker 실패가 독립 branch 전체를 불필요하게 막지 않는다.
- crash 뒤 완료 작업을 중복 dispatch하지 않는다.

### Cost

- dependency plan은 Blueprint revision당 AI 1회다.
- 병렬 stage에서 exact conflict 또는 불완전 Telemetry가 있으면 Coordinator AI
  1회가 추가된다. 일반적인 worker가 테스트 명령을 실행하면 보수 규칙상 대개
  Coordinator가 열린다.
- Coordinator 뒤 mechanical success contract를 다시 실행하므로 실행 시간이
  추가된다.
- 결과 불명 worker나 결과 불명 Coordinator는 자동 재실행하지 않아 사람의
  복구 결정이 필요하다.

AI 호출 추정은 `1 dependency plan + AC worker 수 + conflict stage 수`다.
Verify semantic 호출은 별도 Stage 비용으로 AC 수만큼 더한다.

## Rejected alternatives

- **기존 `execute next`의 의미를 stage 실행으로 변경** — 기존 자동화가 호출 한
  번에 side effect 하나라는 계약을 잃는다.
- **file_change overlap만 Coordinator 실행** — 셸 write 실측에서 false negative가
  확인됐다.
- **모든 stage를 무조건 Coordinator 실행** — 안전하지만 파일 편집만 있고 exact
  disjoint가 입증된 stage도 AI 호출을 강제한다. 불완전성 또는 충돌을 trigger로
  한정한다.
- **worker별 worktree** — ADR-0045와 upstream shared-worktree 모델을 뒤집고 새
  merge authority를 요구한다.
- **Coordinator 결과를 Verify evidence로 사용** — 자기 작업의 자기 승인이고
  `Executed is not verified` 경계를 무너뜨린다.
- **crash 뒤 `DISPATCHED` worker 자동 재실행** — 이미 적용된 write를 다시
  적용할 수 있다.

## Verification

- plan exact binding·unknown·duplicate·cycle contract tests
- grouped attempts가 Runtime 호출보다 먼저 한 save에 들어가는 integration test
- 실제 concurrent fake의 max active worker가 2 이상인 test
- sibling 실패·dependent BLOCKED·independent branch 지속 test
- quota failure가 실행 중 sibling process를 정리하고 incomplete stage를 HOLD하는 test
- completed `file_change` 중복과 command-only uncertainty가 Coordinator를 여는 test
- Coordinator effect 전 durable record, 1회 상한, 실패/unknown HOLD test
- settled revalidation 실패가 후속 stage와 Execute Gate를 막는 test
- partial crash에서 completed worker를 재호출하지 않는 test
- 공통 파일 conflict + 독립 AC를 함께 둔 representative brownfield dogfood와
  최종 Verify lineage

**결과 (2026-08-10): 전부 통과.** 1056개 전체 suite와 실제
[DOGFOODING_0007](../research/DOGFOODING_0007.md)이 worker 3개,
`retry_policy.py` conflict, Coordinator 1회, settled revalidation 3/3,
독립 mechanical·semantic Verify 3/3, `MISSION COMPLETE`를 입증했다.
