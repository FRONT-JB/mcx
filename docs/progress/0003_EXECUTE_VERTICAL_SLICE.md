# Progress 0003 — Execute Vertical Slice

- Status: COMPLETE
- Started: 2026-08-08
- Completed: 2026-08-08
- Scope owner: Execute Stage core implementation

## Goal

승인된 Blueprint의 AC를 bounded 실행 계약으로 바꿔 순차 실행하고,
executed-unverified 상태와 `CLEAR — Clear for Verify` Gate를 결정적 Runtime으로
검증한다.

## Inputs

- [Execute Guide](../07_EXECUTE.md) — Draft contract (§6·§7·§13·§14는 v1 확정 표시)
- [RUN_UPSTREAM_FINDINGS.md](../research/RUN_UPSTREAM_FINDINGS.md) §1~§9
- ADR-0023(진입 경로·provenance), 0024(v1 실행 모델), 0025(divergence 등록부)

## In scope

- Execute domain: state(attempt 이력·provenance 강제·열린 attempt 규칙),
  plan(선언 순서의 다음 AC 선택), gate(Verify 진입 판정)
- Application: ports 확장(`ExecuteRepository`, `ExecutionRequest/Outcome`,
  `ExecutionRuntime`), `ExecuteService`(진입 확인 → 지속 우선 dispatch →
  결과 기록 → Gate)
- Adapter: 파일 기반 durable state (`execute_<mission_id>.json`)
- deterministic runtime test double로 실행 가능한 test suite

## Out of scope

- concrete Runtime adapter, capability 실제 차단, timeout/cancel/resume (Phase 5)
- telemetry event/report/bundle schema ([Open Questions §9](../research/OPEN_QUESTIONS.md) — Phase 4 진입 전 §5와 함께)
- AC 분해, dependency 파생, 병렬 실행 (ADR-0025 등록 보류)
- Verify handoff와 mechanical verification (Phase 4)
- `mcx execute` CLI (Phase 6)

## Deliverables

- [x] `domain/execute/state.py` — attempt 상태 셋, provenance 선언 필드,
  열린 attempt 하나·실패 중단 규칙, 결과-상태 일관성 재검증
- [x] `domain/execute/plan.py` — 선언 순서의 결정적 다음 AC 선택
  (revision 스코프, 실패 AC 재선택)
- [x] `domain/execute/gate.py` — `evaluate_execute_gate`
  (ATTEMPT_OPEN / CRITERION_UNEXECUTED / CRITERION_FAILED)
- [x] `application/execute_service.py` + `ports.py` 확장
- [x] `adapters/persistence/file_execute_repository.py`
- [x] unit + integration test suite (57건)

## Exit criteria

- [x] 승인된 Blueprint → 순차 dispatch → 결과 기록 → `CLEAR — Clear for
  Verify`가 파일 저장소를 거쳐 end-to-end로 돈다 (결정적 fake 기준).
- [x] 지속이 dispatch보다 먼저다 — Runtime 호출 시점에 저장소에 `DISPATCHED`
  attempt가 이미 존재하고, 저장 실패 시 Runtime이 호출되지 않는다.
- [x] 실행 실패가 후속 AC를 막고, 같은 AC 재시도가 첫 순위가 되며, 새
  Blueprint revision이 차단을 해제한다.
- [x] provenance 네 항목이 없는 attempt는 생성 시점에 거부된다.
- [x] attempt 이력이 프로세스 재시작을 건너 유지되고, `DISPATCHED`로 남은
  attempt가 Gate에서 "결과 불명"으로 드러난다.
- [x] Brief가 도중에 바뀌면 dispatch도 Gate 판정도 진입에서 막힌다.
- [x] mypy, ruff, ruff-format이 통과한다.

## Verification evidence

```text
Commits: 9de92f0 (ADR-0023) → 71a4120 (Run 조사·ADR-0024/0025·07 계약)
         → 016c1b8 (구현) → 9798b40 (progress) → eb2f3d1 (research §8.1)
         → 2f951e2 (종료 검토 수정: 저장 실패 경로 테스트 2건)
Tests: 388 passed
  tests/unit/domain/execute/test_state.py               19
  tests/unit/domain/execute/test_plan.py                 5
  tests/unit/domain/execute/test_gate.py                 5
  tests/unit/adapters/persistence/…execute…              7
  tests/unit/application/test_execute_service.py        17
  tests/integration/test_execute_flow.py                 4
mypy: Success (32 source files)
ruff check / ruff format --check: 통과
Execute 구현: 686 lines
```

## Phase 종료 검토

[progress README](./README.md)의 여섯 질문에 대한 답이다.

### 1. 구조 검사 — 각 방어가 막는 결함

| 방어 | 막는 결함 | 위치 |
|---|---|---|
| provenance 필수 선언 필드 | "무엇이 이 작업을 만들었는가"에 답 못하는 기록 (ADR-0023 §3) | `state.py` `ExecutionAttempt` |
| 결과-상태 일관성 validator + `record_result`의 명시적 재검증 | 실패인데 이유 없음, 성공인데 오류, dispatch 전 결과 — `model_copy`가 validator를 우회하는 경로 포함 | `state.py` |
| 번호 연속·마지막만 열림 validator | 시도 번호 검증 불능, 결과 없는 시도 위에 쌓인 기록 | `state.py` |
| `OpenAttemptError` | 동시 attempt로 결과 귀속 불명 | `state.py` `dispatch` |
| `HaltedByFailedCriterionError` | 실패한 산출물 위에 쌓기 (같은 revision, 같은 AC 재시도는 허용) | `state.py` `dispatch` |
| revision 스코프 선택·판정 | 이전 revision 실행 결과의 자동 재사용 | `plan.py`, `gate.py` |
| Gate blocker 셋 | 결과 불명·미실행·실패 상태의 낙관적 `CLEAR` | `gate.py` |
| 진입 확인이 모든 일보다 먼저 | 승인 없는/stale Blueprint·바뀐 Brief 위의 실행과 판정 | `execute_service.py` `_cleared_blueprint` |
| 지속이 dispatch보다 먼저 | "아무도 모르는 작업" (upstream §12.3 관측) — **저장 실패 경로는 이 검토에서 테스트 추가 (2f951e2)** | `execute_service.py` |
| runtime 예외 → `EXECUTION_FAILED` 기록 | 예외로 증발하는 실패 | `execute_service.py` |
| `AllCriteriaExecutedError` | 전부 실행된 상태의 dispatch가 조용한 no-op이 되는 것 | `execute_service.py` |
| bounded request (대상 AC 하나만) | 전체 명세 전달이 유도하는 범위 밖 작업 | `execute_service.py` `_request` |
| 단일 문서 원자 교체 + sequence | 부분 기록, 조용한 덮어쓰기 | `file_execute_repository.py` |

산문·프롬프트로만 막는 계약과 그 기록 위치: capability envelope의 실제 차단
없음(ADR-0024 §6 명시, ADR-0025 보류 — fake runtime이 `allowed_tools`를 무시해도
탐지 없음), **Execute Guide §10 CLEAR 조건 중 3건(변경 artifact 추적, Runtime
events·명령 결과 보존, Verify 충분 입력)은 Gate가 검사하지 않는다** — 이
검토에서 확인해 progress README에 "강제되지 않는 것" 표로 추가했다.

### 2. 부품/단계 구분

end-to-end로 돈다 — `test_execute_flow.py` 4건이 Brief CLEAR → Blueprint 승인
→ 순차 실행 → 실패·재시도 → Gate를 실제 파일 저장소로 잇고, 프로세스
재시작(저장소 재생성) 후 attempt 이력이 유지됨을 확인한다. "돈다"의 기준은
결정적 fake다 — 실제 Runtime은 Phase 5. [Execute Guide](../07_EXECUTE.md) §14
기준 Slice 1·2가 완료됐고, Slice 3(concrete adapter)은 Phase 5, Slice 4(CLI)는
Phase 6, Slice 5(Verify handoff)는 Phase 4 소관이다. progress README의 Phase 3
checklist는 `[x]` 하나(work derivation)뿐이고 나머지는 `[-]`로 v1 범위와
잔여를 구분해 기록했다 — 과장된 체크 없음.

### 3. 미등록 이탈

검토에서 하나 발견: **실행 실패 후 같은 AC 재시도의 정책** — 우리 v1은 상한
없이 동일 요청을 재시도하며(실패 증거 전달 없음), upstream의 bounce/repair가
재시도를 어떻게 제한하고 실패 증거를 어떻게 전달하는지 미조사다 → ADR-0025
미확인 표에 등록했다. 함께 확인한 것: 오늘의 [RUN_UPSTREAM_FINDINGS
§8.1](../research/RUN_UPSTREAM_FINDINGS.md) 조사(Seed 생성 시점에 병렬성 구분
없음)는 ADR-0024 §3의 근거("우리 Blueprint AC에는 선언 신호로 읽을 metadata가
없다")를 강화하는 일치이지 이탈이 아니다. 그 외 v1 축소(분해·dependency·병렬·
timeout·capability 차단·context 예산)는 ADR-0025에 기등록 상태였다.

### 4. 표시 없는 보류

세 건 발견, 전부 이 검토에서 표시했다.

1. **telemetry schema의 시점 문구 불일치** — [Open Questions
   §9](../research/OPEN_QUESTIONS.md)("Phase 3 설계 직전"), ADR-0023 §3·Cost·
   Verification("Phase 3 설계에서"), ADR-0025 미확인 표("Phase 3 시 확인")가
   전부 Phase 3을 가리키는데 Phase 3은 event/report/bundle 스키마를 결정하지
   않았다. 처분은 아래 [§9 Required Telemetry 대조](#9-required-telemetry-대조)
   — 결격이 아니라 시점 정정이며, 세 문서 모두 dated 정정을 남겼다.
2. **고아 열린 attempt의 해소 진입점 없음** — 결과 저장 실패나 크래시 후
   `DISPATCHED`로 남은 attempt는 Gate가 드러내지만, 그것을 해소(늦은 결과 기록,
   실패 처리)할 application 진입점이 없어 mission이 멈춘다. resume(Phase 5
   미확인)과 Recover(Phase 4) 전까지의 v1 한계로 progress README에 표시했다.
3. **ADR-0024 Verification의 과장 1건** — "AC가 해당 revision에 존재하지
   않으면 거부된다"는 어느 계층도 수행하지 않는 존재 검증을 주장했다. 단일
   생성 경로가 승인된 Blueprint에서 AC를 선택하므로 경로상 발생 불가이고, 경로
   밖 기록의 탐지는 ADR-0023 §2가 명시적으로 약속하지 않는다 — 문구를 실제
   계약으로 정정했다.

### 5. 계약 문장 원문 여부

Phase 3 신규 코드에 문장이 곧 계약인 지점은 없다 — 순서·상태·Gate 규칙은 모두
결정적 코드이고, 예외 메시지는 계약 문장이 아니며, Runtime에 보내는 프롬프트는
아직 없다(`ExecutionRequest`는 구조화된 필드만 담고, 프롬프트 조립은 Phase 5
adapter 소관 — 그때 이 질문을 다시 적용한다).

### 6. 관측 대조

[SEED_UPSTREAM_FINDINGS §12.3](../research/SEED_UPSTREAM_FINDINGS.md)의 관측
(config 매핑을 우회한 host 직접 작업, 기록 없음)이 이 slice의 배치를 정했다 —
단일 use case 경로, 지속이 dispatch보다 먼저, 기록의 부재가 판정 가능
(ADR-0023). 오늘의 upstream 소스 재확인([RUN_UPSTREAM_FINDINGS
§8.1](../research/RUN_UPSTREAM_FINDINGS.md))과 모순되는 규칙 없음. 실행 경로의
도그푸딩 전사는 아직 없으며, concrete adapter(Phase 5)에서 `ooo run` 관측과
대조한다.

## §9 Required Telemetry 대조

[Execute Guide](../07_EXECUTE.md) §9의 열한 질문에 현재 attempt 기록이 답할 수
있는지 — 이번 검토에 지정된 항목이다.

| §9 질문 | 현재 기록 | 답? |
|---|---|---|
| 어떤 Mission과 Seed revision | `mission_id` + `blueprint_revision` | 답함 |
| 어떤 AC | `ac_key` (내용 digest) | 답함 |
| 어떤 Runtime과 session/handle | `runtime_backend` + `native_session_id` | 답함 (session은 Runtime이 돌려준 경우) |
| 어떤 capability와 workspace scope | `envelope` (workspace + allowed_tools) | 답함 (기록까지 — 강제는 Phase 5) |
| 언제 시작하고 종료 | — | **답 못함** (Clock 미도입) |
| 어떤 파일/artifact 변경 | — | **답 못함** |
| 어떤 명령과 exit code | — | **답 못함** |
| stdout/stderr·artifact 위치 | — | **답 못함** |
| 완료·실패 이유 | `result_summary` / `error` | 답함 (요약 수준) |
| 누락·파싱 실패 이벤트 | — | **답 못함** (event 층 자체가 없음. 단 결과 불명은 `DISPATCHED`로, runtime 예외는 `error`로 드러남) |
| Verify가 확인해야 할 것 | — | 부분 (attempt에는 없음 — `ac_key` lineage로 Blueprint의 `verify_command`에 도달 가능) |

**미답 항목의 처분: Phase 3 결격이 아니라 [Open Questions
§9](../research/OPEN_QUESTIONS.md) 결정 대기이며, 시한은 Phase 4 진입 전이다.**
근거는 셋이다.

1. §9 자신이 세 층(raw observation → canonical event → domain evidence)을
   conceptual baseline으로, exact schema를 TBD로 명시한다. Phase 3 목표(AC 기반
   bounded work와 executed-unverified 상태 검증)는 스키마 없이 충족된다.
2. 미답 내용(시각, artifact, 명령 결과, 이벤트)은 결정적 fake에 발생 경로가
   없다 — 명령을 실행하지 않으므로 exit code가 존재할 수 없다. 발생 경로 없는
   필드는 테스트할 수 없고, 테스트되지 않은 계약은 장식이다 (ADR-0024 기각
   사유와 같은 논리).
3. 스키마의 소비자는 Verify·Recover다. evaluate가 실행 lineage를 요구하는지
   (§5, RUN_UPSTREAM_FINDINGS §10 미조사)를 모른 채 지금 확정하면 upstream
   근거 없는 발명이 된다.

단, 이 처분이 성립하려면 두 가지가 함께 있어야 한다 — Gate가 이 공백을 아는
척하지 않을 것(progress README "강제되지 않는 것" 표), 그리고 결정 시한이
고정될 것(다음 목표). 둘 다 이 검토에서 반영했다.

## Test Matrix 대응

[Execute Guide](../07_EXECUTE.md) §13 기준. 각 행을 테스트 이름이 아니라
assertion과 대조했다.

| 상태 | 행 |
|---|---|
| 덮음 | Entry(승인 Seed 없음), Binding(오래된 revision — Brief·Blueprint Gate 재확인), Dispatch(정상 결과 → executed-unverified), Sequence(실패 후 후속 거부), Attempt 3행 전부(저장 실패 — **이 검토에서 테스트 추가 (2f951e2)**, 결과 불명 재개, 열린 attempt 거부), Telemetry(provenance 누락 거부) |
| 부분 | Runtime(process 시작 실패 — runtime 예외를 `EXECUTION_FAILED`로 기록. system failure의 별도 분류는 event schema와 함께), Idempotency(열린 attempt 1개 규칙까지 — exact key schema는 §17 미정) |
| 대상 없음 (v1) | Capability(차단 없음 — Phase 5), Scope(drift 탐지 없음 — Phase 5), Runtime(timeout — 발생 경로 없음), Telemetry(command result 누락 — command result 개념이 §9 schema 대기), Dependency·Decomposition(미도입 — ADR-0025 보류), Cancellation·Retry 2행(transport retry — Phase 5), Recursion(fake에 호출 경로 없음 — Phase 5·7) |

## 미완료 항목의 처분

- **telemetry event/report/bundle schema** — Phase 4 진입 전, §5와 함께 결정
  (위 §9 대조). OPEN_QUESTIONS §9·ADR-0023·ADR-0025에 시점 정정 기록.
- **capability 차단·concrete adapter·timeout/cancel/resume** — Phase 5
  (ADR-0025 보류, §14 Slice 3).
- **dependency 파생·분해·병렬** — 등록된 보류 (ADR-0025). 도입 시 upstream
  한도·모델과 대조.
- **재시도 상한과 실패 증거 전달** — Recover(Phase 4) 전에 upstream 정책 조사
  (ADR-0025 미확인 표, 이 검토에서 등록).

## 이번 검토가 잡은 것

1. **§13 Test Matrix 두 행이 assertion 없이 행으로만 존재** — "dispatch 전 저장
   실패"와 "결과 수신 전 종료 후 재개". 테스트 2건 추가로 수정 (2f951e2).
2. **ADR-0024 Verification의 존재 검증 과장** — 실제 계약(단일 경로 + 탐지
   비약속)으로 정정.
3. **§10 CLEAR 조건 3건이 검사되지 않는데 미표시** — progress README에
   "강제되지 않는 것" 표 추가.
4. **telemetry schema 시점 문구 불일치** — 세 문서가 Phase 3을 가리킴. 시점
   정정 + 다음 목표로 고정.
5. **같은 AC 재시도 정책의 upstream 근거 부재** — ADR-0025 미확인 표에 등록,
   v1 동작(상한 없음, 동일 요청)은 알려진 한계로 표시.
6. **고아 열린 attempt의 해소 진입점 없음** — 알려진 한계로 표시 (Phase 4
   Recover·Phase 5 resume에서 다룸).
