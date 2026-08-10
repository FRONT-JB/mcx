# upstream 병렬 실행 조사 — shared worktree의 안전 장치와 durable stage

- 조사일: 2026-08-10
- Baseline: `~/.claude/plugins/marketplaces/ouroboros` @
  `9486c78575a0332e9b84d93ef5832985291d7943` (v0.50.8)
- Evidence level: **Verified — pinned source + focused tests**
- 재현: dependency analyzer 전체 + 실제 batch fan-out + 실패 의존 차단 focused
  tests, **22 passed**
- 조사 이유: Phase 11의 병렬 실행 도입 Gate는 실행 모델·상태 축·공유 worktree를
  함께 바꾸는 되돌리기 비싼 결정이다. 단순히 `gather()`를 붙일 수 있는지보다
  upstream이 동시 파일 변경을 어떻게 수습하고, 실패와 checkpoint를 어느
  경계에서 닫는지를 먼저 확인했다.

---

## 1. 결론

upstream의 병렬 실행은 다음 묶음이다.

```text
structured signal ∪ LLM dependency inference
→ deterministic topological stages
→ same-stage AC bounded fan-out in one shared worktree
→ per-worker Write/Edit telemetry로 충돌 탐지
→ conflict가 있으면 별도 Level Coordinator AI가 검토·수정
→ settled workspace 재검증
→ level checkpoint
```

**병렬 dispatch만 떼어낼 수 없다.** 특히 shared worktree 안전은 실행 전의 완전한
파일 분리 증명이 아니라, 실행 뒤의 worker별 변경 Telemetry와 변경 권한이 있는
Coordinator를 포함한다.

현재 mcx에는 두 핵심 부품이 없다.

1. `ExecutionOutcome`에는 worker별 변경 파일이 없고 Codex JSONL도 thread id와
   진행 표시만 소비한다.
2. AC attempt와 1:1이 아닌 level 단위 충돌을 검토·수정하는 Coordinator 역할과
   그 durable authority가 없다.

따라서 현재 상태에서 AC 여러 개를 같은 worktree에 fan-out하면 파일 충돌을
발견하거나 수습할 근거가 없다. Phase 11 Gate의 현재 결과는 **HOLD**다.

## 2. plan: 의존 추론과 ready 계산은 서로 다른 층이다

`dependency_analyzer.py:371-438`은 구조화 신호와 LLM 결과를 합집합으로 만든다.
LLM 호출이 실패하면 구조화 신호만 남긴다. `:645-712`의 ready 계산은 그 결과를
결정적 토폴로지 level로 바꾸고 `serial_only` AC를 단독 stage로 분리한다.

구조화 신호는 다음을 포함한다.

- 명시적 prerequisite·dependency reference
- `parallel_safe=false` 같은 직렬화 metadata
- 공유 runtime resource claim. 같은 resource에 write 충돌이 있으면 선언 순서
  edge를 추가한다 (`dependency_analyzer.py:462-528`).

하지만 일반 `AcceptanceCriterionInput`은 `_normalize_specs`에서 내용만 가진
`ACDependencySpec`으로 바뀐다 (`:440-459`). 현재 Seed 생성 경로가 dependency나
resource metadata를 생산하지 않는다는 기존
[RUN findings §8.1](./RUN_UPSTREAM_FINDINGS.md)의 결론과 일치한다. 일반 경로에서
실질적인 dependency 신호는 LLM 추론이고, 그 prompt는 **논리적 선후관계**만 묻지
실제 write set을 약속하지 않는다 (`:233-260`).

순환 처리도 안전 기본값은 아니다. 토폴로지 ready가 비면 경고 뒤 남은 AC를 같은
level로 넣는다 (`:671-685`). mcx가 순환을 `HOLD`로 다루기로 한 기존 divergence는
유지해야 한다 (ADR-0025).

## 3. dispatch: stage는 순차, stage 안 AC는 동시다

`parallel_executor.py:4270-4506`은 stage를 순서대로 돌고, 한 stage의 batch는
task group에 AC별 task를 함께 넣는다 (`:3771-3921`). 결과 배열은 입력 AC 순서로
미리 만들기 때문에 실제 완료 순서와 무관하게 identity가 유지된다.

도구 목록에 `Edit`·`Bash`가 있다는 이유로 batch를 순차화하지 않는다. source는
cross-AC safety가 `LevelCoordinator`의 file-conflict guard와 provider runtime에
있다고 명시한다 (`:3909-3917`). focused test도 `Read`·`Edit`·`Bash`가 모두 있는
두 AC의 최대 동시 실행 수가 2임을 고정한다
(`test_parallel_executor.py:6741-6814`).

즉 **workspace-write worker를 실제로 동시에 띄우는 것이 upstream 동작**이다.
AC마다 worktree를 만들지 않는다는 ADR-0045의 기존 조사와도 일치한다.

## 4. 충돌: 실행 전에 막는 것이 아니라 실행 뒤 Coordinator가 수습한다

`coordinator.py:827-867`은 같은 level의 `ACExecutionResult.messages`에서
`Write`/`Edit` tool call을 모아, 파일 하나에 writer가 둘 이상이면
`FileConflict`를 만든다. `parallel_executor.py:4718-4803`은 충돌이 있으면 별도
Coordinator runtime을 열어 review를 수행한다. 이 Coordinator는 실제 workspace를
바꿀 수 있고, 바뀌었다면 최종 success contract를 settled workspace에서 다시
검증한다 (`:4744-4789`, `:4896` 이후).

구체적 실패 장면은 이렇다.

```text
AC-1 worker: retry_policy.py의 429 branch를 수정
AC-2 worker: 같은 함수의 Retry-After parsing을 수정
둘 다 시작 시점 파일을 읽고 각자 전체 함수를 다시 씀
→ 늦게 끝난 write가 먼저 끝난 write를 덮을 수 있음
→ worker 둘의 "완료"만 모으면 손실을 알 수 없음
→ worker별 Write/Edit trace로 겹침을 찾고 Coordinator가 settled file을 복구
```

이 장면은 순전히 가상인 위험도 아니다. mcx의 실제
[DOGFOODING_0006](./DOGFOODING_0006.md)에서는 AC 세 실행의 **합산**
`changed_files`가 `retry_policy.py`와 `test_retry_policy.py` 두 개뿐이었고, 첫
worker가 전체 함수를 완성한 뒤 다음 둘이 경계를 보강했다 (`:145-164`). 다만 현재
Telemetry에는 worker별 write set이 없어 “셋 모두 같은 파일을 썼다”고 확정할 수
없다. exact attribution이 불가능하다는 사실 자체가 현재 Gate blocker다. 순차
실행에서는 뒤 worker가 settled workspace를 읽을 수 있었지만, 같은 셋을 병렬로
보내면 위 충돌 경로를 배제할 증거가 없다.

## 5. 실패: 이미 시작한 sibling은 모으고, 실패 의존자만 막는다

일반 실행 예외는 task group 전체를 취소하지 않고 해당 AC의 실패 결과로 바꾼다
(`parallel_executor.py:3886-3907`, `:4513-4606`). 다음 stage에서 실패 AC에
의존한 AC는 `BLOCKED`가 되고, 그 실패와 무관한 AC는 계속 실행한다
(`:4300-4321`). focused test는 다음 결과를 고정한다.

```text
Stage 1: AC-1 FAILED, AC-2 SUCCEEDED
Stage 2: AC-3 depends on AC-1 → BLOCKED
         AC-4 depends on AC-2 → SUCCEEDED
```

예외는 공유 provider quota pause다. 한 sibling이 quota 경계를 만나면 아직 끝나지
않은 sibling을 취소하고 stage 완료·checkpoint를 남기지 않는다 (`:3878-3904`,
`:4608-4618`). 이것은 일반 AC 실패와 전체 실행 자원 실패가 다른 축이라는 뜻이다.

## 6. durability: plan과 level 완료가 재개 권위다

runner는 재개 시 dependency analysis를 다시 하지 않고 이미 durable한 plan을
재사용한다 (`runner.py:10325-10329`). 분석 실패의 일반 fallback은 모든 AC를
dependency 없는 한 level로 만드는 것인데 (`:10345-10359`), 이는 mcx의
fail-closed 원칙과 맞지 않는다. mcx에서는 분석 불능을 독립성 증거로 바꾸지
않아야 한다.

executor는 level이 모두 끝나고 conflict reconciliation까지 지난 뒤 다음을 한
checkpoint에 저장한다 (`parallel_executor.py:4803-4869`).

- completed level 수
- AC별 status·retry count·outcome
- failed/blocked set
- 다음 level에 넘길 context
- workspace identity와 Coordinator 재검증 상태

현재 mcx의 git checkpoint는 Verify round 뒤의 **입증 커밋**이다(ADR-0046).
upstream의 위 checkpoint는 Execute 중간의 **재개 권위**다. 이름이 같아도 목적이
다르며, 병렬 도입에는 새 git commit이 아니라 durable stage/batch state가 필요하다.

## 7. concurrency 기본값을 그대로 복사해도 Codex는 동시에 돌지 않는다

upstream의 requested worker 기본값은 3이지만, CLI runtime처럼 provider 한도가
알려지지 않은 backend(`codex`, `opencode` 등)는 기본 effective concurrency를
1로 제한한다 (`backend_limits.py:350-372`, `docs/config-reference.md:181-186`).
사용자가 `OUROBOROS_MAX_CONCURRENCY`로 명시해야 실제 fan-out이 열린다.

따라서 `max_parallel_workers=3` 하나만 복사하면 Phase 11 목표인 “여러 AC를
동시에 실행”은 Codex adapter에서 실현되지 않는다. backend별 한도와 명시적 override,
quota 전체 실패 처리가 한 계약으로 와야 한다.

## 8. 현재 mcx와의 정확한 간극

| 축 | upstream | 현재 mcx | Gate 판단 |
|---|---|---|---|
| plan | dependency graph + durable stages | 선언 순서의 다음 AC 하나 | plan authority 없음 |
| write conflict | worker별 Write/Edit trace + mutating Coordinator | outcome에 파일 trace 없음, Coordinator 없음 | **HOLD** |
| open work | stage의 여러 AC | mission당 `DISPATCHED` 하나만 허용 | grouped attempt state 필요 |
| failure | sibling 수집, dependent만 BLOCKED | 최신 실패가 다른 모든 AC를 중단 | dependency가 먼저 필요 |
| resume | durable plan + completed level checkpoint | 열린 attempt 하나는 결과 불명 | batch replay authority 없음 |
| concurrency | requested 3, backend cap 적용 | 동시 worker 설정 없음 | backend limit 계약 필요 |
| git checkpoint | 별도 평가/commit 정책 | Verify round 뒤 proven commit | 그대로 유지 가능 |

`asyncio.gather(dispatch_next(...))`는 이 간극을 하나도 닫지 않는다. 첫 호출들이
동일 state를 읽고, 단일-open invariant와 optimistic save에서 경합하며, 그 전에
Codex가 같은 파일을 이미 바꿀 수 있다. 이것은 성능 개선이 아니라 상태·파일
손상 경로다.

## 9. Gate에 남길 선택

true parallel을 열 수 있는 검증 가능한 안전 경로는 둘뿐이다.

1. **upstream 경로 채택**: worker별 write Telemetry → 충돌 탐지 → 별도
   Coordinator Flight Controller의 bounded repair → settled workspace 재검증.
2. **실행 전 강제 격리**: AC별 write scope를 실제 runtime에서 차단하고 서로
   disjoint임을 입증. LLM의 파일 예상이나 prompt 지시는 강제가 아니므로 해당하지
   않는다.

두 번째는 현재 Codex CLI의 workspace-write sandbox가 AC별 path allowlist를
제공하지 않아 바로 구현할 수 없다. 첫 번째는 upstream에 있지만 Coordinator
역할·추가 호출 비용·AC attempt와 1:1이 아닌 level repair authority를 새로
확정해야 한다.
결정 전까지 현재 순차 실행은 유지한다.
