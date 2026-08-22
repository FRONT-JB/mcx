# ADR 0057 — Runtime spawn 실패의 표면 경계

- Status: Accepted
- Date: 2026-08-23
- Related issue: #5

## Context

Codex 실행 파일이 PATH에 없으면 `asyncio.create_subprocess_exec`가
`FileNotFoundError`를 낸다. 기존 ExecuteService의 넓은 예외 정규화는 이 오류를
`EXECUTION_FAILED` attempt로 저장하고 `execute next`를 exit 0으로 끝냈다. 그러면
실행이 시작되지 않은 환경 오류가 worker 작업 실패로 보이고 Recover가 같은 환경에서
재시도할 수 있다.

이 동작은 다음 계약과 충돌한다.

- dispatch 전 attempt를 durable하게 남긴다 (ADR-0024 §4).
- 결과를 모르면 `DISPATCHED`를 유지하고 낙관적으로 `CLEAR`하지 않는다
  (ADR-0024 §4, `docs/07_EXECUTE.md` §13).
- Runtime executable이 없으면 Execute를 멈추고 Runtime 설정을 보완한다
  (`docs/07_EXECUTE.md` §11).

Pinned upstream `Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943`도
worker transport 예외를 정상 결과와 구분된 `result` event의 `subtype: error`로
내보내고(`src/ouroboros/orchestrator/worker_runtime.py:283-325`), CLI는 그
subtype을 보고 exit 1로 수렴한다(`src/ouroboros/cli/commands/dispatch.py:179-187`).
우리 v1에는 해당 event stream을 직접 저장하는 모델이 없으므로, 같은 경계를
application port 예외로 표현한다.

## Decision

1. `application.ports`에 `RuntimeUnavailableError`를 둔다. 실행 파일 이름을
   보존하고 사람이 읽는 메시지에 basename을 포함하며, adapter의 원래 `OSError`는
   cause로 유지한다.
2. Codex execution/text adapter는 실제 `create_subprocess_exec` 호출에서
   `OSError`를 `RuntimeUnavailableError`로 감싼다. 별도 `which` preflight는 두지
   않는다. 실제 spawn이 환경과 실행 권한의 source of truth이고, preflight 뒤에도
   실행 파일이 사라질 수 있기 때문이다.
3. ExecuteService는 이 예외를 순차 worker, parallel worker, Coordinator 경로에서
   다시 올린다. 일반 Runtime 예외와 `succeeded=False` outcome의 기존 정규화는
   유지한다.
4. Runtime이 시작되기 전이므로 실패 attempt/coordination result를 새로 기록하지
   않는다. durable-first 순서에 따라 순차·parallel worker attempt는
   `DISPATCHED`에 남고, Coordinator는 `COORDINATOR_DISPATCHED`에 남는다. 따라서
   Execute Gate는 `HOLD`이고, `DISPATCHED`는 Recover failure packet으로 파생되지
   않아 자동 재시도 대상이 아니다.
5. CLI 공통 오류 경계는 이 예외를 exit 1로 반환한다. 메시지에는 `codex` 같은
   실행 파일 이름이 포함된다. text completion도 같은 예외를 그대로 표면화하여
   transient 문자열 재시도에 넣지 않는다.

## Consequences

- 환경에 Codex가 없을 때 성공처럼 보이는 exit 0과 가짜 `EXECUTION_FAILED`가
  사라진다.
- `DISPATCHED`가 “dispatch는 durable했지만 process start/result가 관찰되지 않은
  상태”라는 의미를 유지한다. operator는 Runtime을 고친 뒤 상태를 확인해야 하며,
  자동으로 같은 prompt를 재호출하지 않는다.
- 실행 파일 권한 거부 등 spawn 단계의 다른 `OSError`도 같은 환경 가용성 경계로
  표면화된다. process가 실제로 시작된 뒤의 non-zero exit, timeout, parsing 실패는
  기존 outcome/adapter error 계약을 따른다.

## Rejected alternatives

- `shutil.which` 기반 선행 진단: 실제 spawn과 중복되고 TOCTOU 창을 남긴다.
- 모든 예외를 `EXECUTION_FAILED`로 저장: 실행 전 환경 오류를 worker 실패로
  오분류하고 Recover 재시도를 유발한다.
- 새 attempt 상태 `RUNTIME_UNAVAILABLE` 추가: 현재 `DISPATCHED`의 결과 불명 및
  durable-first 의미만으로 Gate HOLD와 자동 재시도 차단을 표현할 수 있어 상태 축을
  늘리지 않는다.

## Verification

- missing `codex` execution adapter가 `RuntimeUnavailableError`와 `codex`를
  표면화하는 단위 테스트
- missing `codex` text adapter가 같은 예외를 재시도 없이 표면화하는 단위 테스트
- sequential Execute가 attempt를 `DISPATCHED`로 남기고 예외를 올리는 테스트
- parallel Execute가 worker failure로 저장하지 않고 예외를 올리는 테스트
- CLI `execute next`가 exit 1을 반환하는 테스트
- full pytest/coverage, mypy, ruff, format 및 CI
