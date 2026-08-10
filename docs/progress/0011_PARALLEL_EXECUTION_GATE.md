# Progress 0011 — Phase 11: 병렬 실행 도입 Gate

- 일시: 2026-08-10
- 범위: pinned upstream dependency plan·shared-worktree fan-out·실패 격리·
  Coordinator reconciliation·level checkpoint 재대조, 현재 mcx 계약 감사
- Evidence: [ADR-0052](../adr/0052-parallel-execution-introduction-gate.md),
  [PARALLEL_EXECUTION_UPSTREAM_FINDINGS](../research/PARALLEL_EXECUTION_UPSTREAM_FINDINGS.md),
  upstream focused tests **22 passed**, [DOGFOODING_0006](../research/DOGFOODING_0006.md)
- 상태: **Phase 11 IN PROGRESS. 병렬 implementation Gate `HOLD`.** 순차 실행은
  정상 운영 경로로 유지된다.

## 1. Gate 결과

병렬 실행은 단순한 application fan-out이 아니었다. upstream은 한 shared
worktree에서 workspace-write AC를 동시에 실행하고, worker별 Write/Edit
Telemetry로 충돌을 찾아 별도 Coordinator AI가 수정한 다음 settled workspace를
재검증한다.

현재 mcx에는 다음이 없다.

1. exact Blueprint revision·AC key 전체에 묶인 durable stage plan
2. 한 stage의 여러 open attempt를 첫 effect 전에 원자적으로 저장하는 상태
3. worker별 변경 파일 Telemetry
4. 충돌을 repair할 별도 Coordinator authority
5. partial stage crash에서 완료 작업을 중복 dispatch하지 않는 resume checkpoint
6. backend별 effective concurrency 계약

따라서 현재 코드에 병렬 dispatch를 추가하지 않았다. 이는 구현 실패가 아니라
ADR-0052가 정한 Gate의 검증 결과다.

## 2. upstream에서 채택·거부한 것

| 항목 | 처분 |
|---|---|
| structured ∪ LLM dependency → deterministic stage | 도입 시 기준으로 채택 |
| stage 순차, stage 안 bounded fan-out | 도입 시 기준으로 채택 |
| sibling 일반 실패 수집, dependent만 BLOCKED | 도입 시 기준으로 채택 |
| shared provider quota면 incomplete stage 전체 pause | 도입 시 기준으로 채택 |
| cycle이면 남은 AC를 같은 level로 실행 | 거부, `HOLD` divergence 유지 |
| analysis 실패면 모든 AC를 한 parallel level로 실행 | 거부, unknown은 순차/HOLD |
| per-worker trace + mutating Coordinator | 현재 안전 경로 후보, 사용자 결정 필요 |
| unknown CLI backend concurrency 기본 1 | 안전 기본값으로 채택 |

## 3. 실사용 증거가 바꾼 판단

DOGFOODING_0006의 Gen 2 Execute에서 AC 세 실행의 합산 `changed_files`는
`retry_policy.py`·`test_retry_policy.py` 두 개뿐이었다. 첫 worker가 전체 함수를
완성하고 다음 둘이 보강했다. 현재 기록은 worker별 write set을 담지 않아 exact
overlap을 확정할 수 없다. 순차 실행에서는 뒤 worker가 앞선 결과를 읽었지만, 같은
셋을 병렬로 보낼 때 파일 손실이 없다고 입증할 수도 없다.

즉 “AC 설명이 서로 다른 결과 분기이므로 독립”이라는 논리 판단만으로는 실제
파일 독립성이 성립하지 않았다. 이 관측 때문에 LLM dependency 추론 단독 허가를
Gate에서 제외했다.

## 4. 다음 한 개의 결정

Phase 11의 다음 목표는 **shared-worktree conflict authority를 고르는 것**이다.

- upstream 경로: worker write Telemetry + Coordinator Flight Controller의 bounded
  repair + settled workspace 재검증
- sequential 유지: Coordinator 역할과 AC attempt와 1:1이 아닌 level repair
  authority를 만들지 않고
  현재 v1에서 병렬 실행을 제외

현재 Codex CLI는 AC별 path write allowlist를 강제할 표면이 없어, runtime-enforced
disjoint scope는 당장 선택 가능한 제3안이 아니다. 이 결정을 내리기 전에는 batch
state나 concurrency 설정을 구현하지 않는다. conflict authority가 없으면 그
구조들은 실행 가능한 안전 경로 없이 남는 선행 구현이기 때문이다.

## 5. Phase 11 종료 전 남은 강제 fixture

Phase 10에서 넘겨받은 두 항목은 시한을 유지한다.

- targeted dirty-rollback fixture에서 실제 제거 파일 표시 확인
- 실제 Brief candidate trace에서 파생/수동 중복과 굵기 감사

Phase 11을 sequential 유지로 닫든 병렬을 구현해 닫든, 두 fixture를 실행하지 않고
`COMPLETE`로 표시하지 않는다.
