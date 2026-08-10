# Progress 0011 — Phase 11: 병렬 실행 도입 Gate

- 일시: 2026-08-10
- 범위: pinned upstream dependency plan·shared-worktree fan-out·실패 격리·
  Coordinator reconciliation·level checkpoint 재대조, 현재 mcx 계약 감사
- Evidence: [ADR-0052](../adr/0052-parallel-execution-introduction-gate.md),
  [ADR-0053](../adr/0053-parallel-coordinator-execution-contract.md),
  [PARALLEL_EXECUTION_UPSTREAM_FINDINGS](../research/PARALLEL_EXECUTION_UPSTREAM_FINDINGS.md),
  upstream focused tests **22 passed**, [DOGFOODING_0007](../research/DOGFOODING_0007.md)
- 자동 검증: **1056 passed**, Ruff·mypy·`git diff --check` 통과, MCP tool 33개 실측
- 상태: **Phase 11 COMPLETE.** upstream Coordinator 경로의 구현·대표 실경로·
  이월 fixture가 모두 검증됐다. 순차 `execute next`도 정상 운영 경로로 유지된다.

## 1. Gate 결과

병렬 실행은 단순한 application fan-out이 아니었다. upstream은 한 shared
worktree에서 workspace-write AC를 동시에 실행하고, worker별 Write/Edit
Telemetry로 충돌을 찾아 별도 Coordinator AI가 수정한 다음 settled workspace를
재검증한다.

Gate 최초 판정 당시 mcx에는 다음이 없었다.

1. exact Blueprint revision·AC key 전체에 묶인 durable stage plan
2. 한 stage의 여러 open attempt를 첫 effect 전에 원자적으로 저장하는 상태
3. worker별 변경 파일 Telemetry
4. 충돌을 repair할 별도 Coordinator authority
5. partial stage crash에서 완료 작업을 중복 dispatch하지 않는 resume checkpoint
6. backend별 effective concurrency 계약

따라서 단순 병렬 dispatch를 먼저 추가하지 않았다. 이 초기 `HOLD` 뒤 사용자가
Coordinator 경로를 선택했고, 위 여섯 항목을 ADR-0053의 한 vertical slice로
구현했다.

## 2. upstream에서 채택·거부한 것

| 항목 | 처분 |
|---|---|
| structured ∪ LLM dependency → deterministic stage | 도입 시 기준으로 채택 |
| stage 순차, stage 안 bounded fan-out | 도입 시 기준으로 채택 |
| sibling 일반 실패 수집, dependent만 BLOCKED | 도입 시 기준으로 채택 |
| shared provider quota면 incomplete stage 전체 pause | 도입 시 기준으로 채택 |
| cycle이면 남은 AC를 같은 level로 실행 | 거부, `HOLD` divergence 유지 |
| analysis 실패면 모든 AC를 한 parallel level로 실행 | 거부, unknown은 순차/HOLD |
| per-worker trace + mutating Coordinator | **사용자 채택·구현 완료** |
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

## 4. 사용자 결정과 다음 검증 목표

사용자는 2026-08-10 **upstream Coordinator 경로**를 선택했다.

exact 계약은 [ADR-0053](../adr/0053-parallel-coordinator-execution-contract.md)이
소유한다. 기존 `execute next`는 유지하고, 새 `execute stage`에서 durable plan,
grouped attempts, bounded fan-out, write Telemetry, Coordinator, settled
revalidation을 한 vertical slice로 구현한다.

실 Codex 관측에서 셸 리다이렉션 write가 `file_change`를 남기지 않았다. 따라서
exact 파일 overlap뿐 아니라 command event·terminal 누락도 full-stage Coordinator를
여는 fail-closed trigger로 확정했다. fake vertical slice와 공통 파일 conflict+
독립 AC 대표 brownfield 도그푸딩이 실제 concurrency·Coordinator·Verify lineage를
모두 입증했다.

## 5. Phase 11 종료 전 남은 강제 fixture

Phase 10에서 넘겨받은 두 항목을 targeted fixture로 닫았다.

- [x] targeted dirty-rollback fixture — 실제 제거 3경로가 결과와 CLI에 표시됨
- [x] actual Brief candidate trace — 굵은 원문 후보 유지, exact 파생/수동 중복은
  기존 candidate number를 포함한 명시적 오류로 거부

## 6. 최종 실경로 evidence

`DOGFOODING_0007`은 `requested_workers=3`, `effective_workers=3`의 실제 Codex
worker를 같은 worktree에서 실행했다. 두 worker의 `retry_policy.py` exact overlap과
세 worker의 incomplete write attribution이 Coordinator를 열었고, 별도 Coordinator
1회 뒤 세 settled revalidation이 통과했다. 독립 Verify는 mechanical 3/3,
semantic 3/3, checkpoint `6065f76`, `MISSION COMPLETE`로 닫혔다.

사전 예상 8회 대비 실측은 성공 8회+실패 1회였다. 추가 1회는 기본 Claude 주간
한도 `HOLD`이며, 지원되는 Codex text routing으로 같은 미션을 재개했다. 기본
Claude 재시험 가능 시각은 실물 메시지 기준 2026-08-13 12:00 Asia/Seoul이다.

다음 한 개의 검증 가능한 목표는 사용자 승인 하의 v1 release-readiness 감사다.
