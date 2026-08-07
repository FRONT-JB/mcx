# ADR 0013 — Brief durable state baseline

- Status: Proposed
- Date: 2026-08-07
- Constitutional basis: Principle 7 (Durable state over conversation memory), §14 (Mission State와 Artifacts)
- Upstream evidence: `bigbang/interview.py` `save_state`/`load_state`, `state_dir`

## Context

Constitution §14는 저장 기술을 정하지 않고 의미적 계약만 요구한다. 세션을 닫아도
다시 읽을 수 있을 것, 상태 변경의 원인과 이전 상태를 추적할 수 있을 것, 저장
실패를 성공적 전이로 가장하지 않을 것.

upstream baseline이 Interview에 사용하는 방식:

- `~/.ouroboros/data/interview_<id>.json` 단일 파일에 전체 상태를 직렬화
- 읽기·쓰기 모두 file lock으로 보호하고 blocking I/O는 thread로 오프로드
- owner-only 권한으로 기록하고 durability 미확인 시 경고 로그
- 저장 실패는 `Result.err`로 반환하며 예외를 삼키지 않음
- HITL 같은 이벤트는 별도 SQLite event store에 best-effort로 기록

[Brief Guide](../05_BRIEF.md) §8.1은 upstream에 없는 요구를 추가한다. 수정은
revision을 올리고 이전 값을 감사 가능하게 남겨야 하며, 승인은 정확한 revision을
참조해야 한다.

## Decision

Phase 1의 durable state는 **Mission별 단일 JSON 문서**로 시작한다.

### 1. 저장 단위와 위치

- Brief 상태 전체를 Mission 단위 문서 하나로 저장한다.
- 경로는 설정으로 주입하며 기본값은 사용자 홈 아래 mcx 전용 디렉터리다.
  테스트는 항상 임시 디렉터리를 주입한다.
- 파일 권한은 owner-only로 생성한다.

### 2. Revision 표현

문서는 현재 상태와 함께 이전 revision의 스냅샷을 보존한다. 별도 revision 파일을
만들지 않는다.

- Brief 하나의 크기는 파일 하나에 담기에 충분하다.
- revision 이력이 같은 문서 안에 있으면 승인·Gate decision이 참조하는 revision을
  단일 읽기로 검증할 수 있다.
- 문서가 커지는 문제가 실제로 발생하면 그때 분리한다.

### 3. 쓰기 계약

- 임시 파일에 쓴 뒤 원자적으로 교체한다. 부분 기록된 문서가 남지 않는다.
- 동시 접근은 file lock으로 직렬화한다.
- 저장 실패는 예외를 삼키지 않고 명시적 실패 결과로 반환한다. 호출자는 이를
  전이 실패로 처리한다 ([Brief Guide](../05_BRIEF.md) §15).
- stale revision에 기반한 갱신은 거부한다.

### 4. Port 경계

도메인과 정책은 저장 방식을 알지 못한다. application 계층이 repository port를
통해서만 상태를 읽고 쓴다. port는
[ADR-0012](./0012-python-toolchain-and-layout.md)의 실행 모델에 따라 `async`로
정의하며, Phase 1의 파일 구현은 그 안에서 동기 I/O를 호출한다. 저장 매체를
바꾸어도 port 시그니처는 유지된다.

Phase 1 테스트는 인메모리 구현과 실패를 재현하는 구현으로 동작한다
([Brief Guide](../05_BRIEF.md) §17.1).

### 5. 이번 결정의 범위 밖

- Telemetry event stream의 저장소는 정하지 않는다. Phase 1의 Telemetry는 Brief
  문서 안의 구조화된 기록으로 충분하며, 별도 event store는 Execute가 Runtime
  결과를 다루기 시작하는 시점에 결정한다.
- SQLite, event sourcing, checkpoint는 v1 baseline이 아니다. 채택하려면 해결하려는
  구체적 문제와 함께 이 ADR을 대체하는 새 ADR이 필요하다.

## Consequences

### Positive

- 외부 의존성 없이 durable state 요구를 만족한다.
- 사람이 파일을 열어 상태를 읽을 수 있어 초기 디버깅과 학습에 유리하다.
- revision 이력이 한 문서에 있어 승인·Gate 참조 검증이 단순하다.
- port 경계 덕분에 저장 기술 교체가 도메인을 바꾸지 않는다.

### Cost

- Mission 간 조회(예: 전체 Mission 목록의 조건 검색)가 비효율적이다. v1 범위에
  그런 조회가 없다.
- revision을 누적하므로 문서가 단조 증가한다.
- 동시성 보장이 file lock 수준이며 다중 프로세스 환경에서 한계가 있다.

## Rejected alternatives

- **처음부터 SQLite + event sourcing**: Constitution §14가 요구하는 것은 의미이지
  특정 DB가 아니다. Phase 1에 필요한 조회 패턴이 없고, §17이 금지하는 선제적
  복잡도다.
- **revision마다 별도 파일**: 파일 수가 늘고, 승인이 참조하는 revision을 검증할 때
  여러 파일을 읽어야 한다.
- **최신 상태만 저장하고 이력 폐기**: [Brief Guide](../05_BRIEF.md) §8.1 규칙 3과
  승인 stale 처리를 구현할 수 없다.
- **저장 실패를 로그만 남기고 진행**: Appendix A 9번 위반.

## Verification

- 프로세스를 종료하고 다시 시작해도 Brief를 이어갈 수 있다
  ([Brief Guide](../05_BRIEF.md) §17의 B-019).
- 저장 실패를 주입하면 `CLEAR`가 기록되지 않는다 (B-016).
- stale revision 갱신이 최신 상태를 덮어쓰지 않는다 (B-017).
- 승인이 참조한 revision을 이후에도 조회할 수 있다 (B-014).
- 도메인 테스트가 파일시스템 없이 실행된다.
