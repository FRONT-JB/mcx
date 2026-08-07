# Progress 0001 — Brief Vertical Slice

- Status: COMPLETE
- Started: 2026-08-07
- Completed: 2026-08-07
- Scope owner: Brief Stage core implementation

## Goal

첫 구현을 Brief에 필요한 최소 Core로 제한하고, 질문 loop와 `CLEAR`/`HOLD` Gate를
외부 Runtime 없이 검증한다.

## Inputs

- [Brief Guide](../05_BRIEF.md) — Active contract
- [INTERVIEW_UPSTREAM_FINDINGS.md](../research/INTERVIEW_UPSTREAM_FINDINGS.md)
- ADR-0009(종료 조건), 0010(answer authority), 0011(의도적 차이),
  0012(toolchain·실행 모델), 0013(durable state)

## In scope

- Brief domain: round 축적, revision/sequence, answer authority, clarity 정책,
  Gate 판정, Stage 전이
- Application: 질문 dispatch, 답변 기록, 승인, clarity 평가, Gate 조회
- Adapter: 파일 기반 durable state
- deterministic test double로 실행 가능한 test suite

## Out of scope

- Fact Resolver, assumption/conflict 모델, handoff 객체
- Runtime Adapter와 실제 도구 차단
- Telemetry와 Gate decision 저장
- CLI, MCP surface

## Deliverables

- [x] `domain/brief/provenance.py` — authority와 requirement input 투영
- [x] `domain/brief/state.py` — round, revision/sequence, 승인, 평가 보관
- [x] `domain/brief/clarity.py` — versioned policy와 종료 후보 네 조건
- [x] `domain/brief/gate.py` — `CLEAR`/`HOLD` 판정과 Brief 전이
- [x] `domain/stage.py`, `domain/errors.py`
- [x] `application/ports.py` — repository, question generator, clarity assessor
- [x] `application/brief_service.py` — use case 조율
- [x] `adapters/persistence/file_brief_repository.py`
- [x] unit + integration test suite

## Exit criteria

- [x] 질문 loop가 외부 Runtime 없이 deterministic double로 끝까지 돈다.
- [x] 종료 후보 네 조건이 각각 독립적으로 검증된다.
- [x] 승인이 revision에 바인딩되고 material 변경이 승인을 무효화한다.
- [x] material 변경이 평가와 stability signal을 함께 무효화한다.
- [x] 저장 실패가 전이 성공으로 보고되지 않는다.
- [x] 프로세스가 끊긴 뒤 다른 인스턴스가 상태를 이어받는다.
- [x] Brief에서 나가는 경로가 `CLEAR` → Blueprint 하나뿐이다.
- [x] mypy strict, ruff, ruff-format이 통과한다.

## Verification evidence

```text
Commit range: 8659f99..980e8a5 (구현 7 commit)
Tests: 140 passed
  tests/unit/domain/brief/test_provenance.py    11
  tests/unit/domain/brief/test_state.py         24
  tests/unit/domain/brief/test_clarity.py       23
  tests/unit/domain/brief/test_gate.py          15
  tests/unit/domain/brief/test_transition.py     9
  tests/unit/adapters/persistence/…             19
  tests/unit/application/test_brief_service.py  33
  tests/integration/test_brief_flow.py           6
mypy --strict: Success: no issues found in 23 source files
ruff check: All checks passed
ruff format --check: 58 files already formatted
Source: 1,333 lines / Tests: 1,953 lines
```

### Test Matrix 대응

`docs/05_BRIEF.md` §17 기준으로 이번 slice가 덮은 행:

> 이 표는 2026-08-07 감사에서 **정정되었다.** 최초 기록은 20개 행을 "덮음"으로
> 주장했으나, 각 행을 테스트 이름이 아니라 실제 assertion과 대조한 결과 7개가
> 과장이었고 4개는 덮었는데 누락되어 있었다.

| 상태 | 행 |
|---|---|
| 덮음 | B-001, B-012, B-013, B-014, B-016, B-025, B-027, B-028, B-029, B-030, B-031, B-034, B-035, B-036 |
| 부분 | 아래 표 참조 |
| 미착수 | B-004~B-007, B-009, B-018, B-020~B-024, B-026, B-037~B-039 |

부분 커버리지의 정확한 경계:

| 행 | 실제 상태 |
|---|---|
| B-002 | dispatch당 1회와 최소 context는 검증. 도구 부재는 Protocol 형태일 뿐 강제·검증되지 않는다 (`ports.py`가 명시). |
| B-003 | 반환 타입이 질문 하나만 담는 구조적 제한. 한 문자열 안의 다중 질문은 미탐지. |
| B-008 | question, answer, authority, revision은 연결. **`source`는 미구현**이며 authority는 knowledge kind가 아니다(§5.2에서 직교 축으로 규정). 5개 요소 중 2개 미달. |
| B-010 | 정책이 결정의 근거로 쓰이고 version이 판정에 기록되는 것은 검증. **주입 가능성은 미검증** — `greenfield_v1()` 외의 정책을 만드는 테스트가 없어, threshold를 코드에 박아도 테스트가 통과한다. |
| B-011 | HOLD와 signal 초기화는 검증. 오류 Telemetry 없음. |
| B-015 | 판정은 되나 근거 reference 저장 없음. |
| B-017 | 쓰기 거부는 검증. **재확인 요청은 미구현**([ADR-0014](../adr/0014-brief-concurrent-write-protection.md) §3). 행의 문자 그대로의 시나리오(무효화된 질문에 대한 늦은 답변)는 답변에 질문 identity가 없어 탐지 불가. |
| B-019 | 재개는 검증. runtime도 timeout도 없어 발동 조건 자체가 미검증. |
| B-032 | 저장된 값을 재해석하지 않는 것은 검증. 소비자 모듈이 하나뿐이라 "여러 소비자"는 미표현. |
| B-033 | 투영은 검증. 시스템이 사용자를 대신해 기본값을 확정하는 코드 경로가 없어, 행이 말하는 분류 자체는 수행되지 않는다. |

Lifecycle 시나리오는 L-S01, L-B02, L-B04를 Brief 관점에서 덮었다. 추가로
L-A02(저장 실패 후 Stage 불변)와 L-A03(같은 state version에서의 동시 전이)이
각각 use case·persistence 계층에서 덮여 있다. L-B01은 Non-goal을 미해결 항목으로
표현했을 때만 근사적으로 덮이며, Non-goal 개념 자체가 없으므로 미착수로 둔다.

## 이번 slice에서 설계가 바뀐 지점

구현이 문서보다 늦게 발견한 것이다. 최초 기록은 이들이 "문서에 반영되었거나
한계로 남았다"고 서술했으나 **1번은 둘 다 아니었다.** 어느 계약 문서에도 없었고
한계 목록에도 없었다. 2026-08-07 감사에서 정정했다.

1. **revision과 sequence의 분리.** `revision` 하나가 "내용 버전"과 "쓰기 순서"를
   겸하면서, 질문을 던지는 것처럼 요구사항을 바꾸지 않는 저장이 승인을 무효화하는
   모순이 생겼다. 통합 테스트가 잡았고 두 축으로 나눴다.
   **그러나 이 결정은 upstream과 대조되지 않았고 어떤 계약 문서에도 없었다.**
   재조사 결과 upstream에는 쓰기 순서 축도 stale write 거부도 없으며, 모순의
   근원은 축을 하나로 쓴 것이 아니라 upstream에 없는 거부를 도입한 것이었다.
   결정과 근거는 [ADR-0014](../adr/0014-brief-concurrent-write-protection.md),
   계약은 [Brief Guide](../05_BRIEF.md) §8.1 규칙 3에 있다.
2. **Gate가 평가를 인자로 받지 않는다.** 평가와 signal을 상태에 저장하면서, Gate가
   따로 받으면 지난 revision의 평가를 현재 상태에 붙일 수 있다는 점이 드러났다.
   상태에서 읽도록 바꿔 §8.1 규칙 7을 구조로 만들었다.
3. **평가 호출과 Gate 조회의 분리.** 한 함수가 평가하고 판정하면 판정을 다시
   요청하는 것만으로 stability signal이 올라 upstream #405 회귀가 다시 열린다.
   `assess_clarity`와 `decide_gate`를 나눴다.

이 세 항목은 progress note가 아니라 divergence register에 있어야 했다. 현재
등록 상태는 [ADR-0011](../adr/0011-brief-deliberate-divergences.md) §7·§8에 있다.

## Gate

```text
COMPLETE — Brief vertical slice verified by tests.
```

Phase 2 진입 전에 [Project Progress](./README.md)의 "현재 구현의 알려진 한계"를
검토한다. 특히 handoff 객체(B-026)는 Blueprint의 입력 계약이므로 Phase 2 첫
작업에서 함께 정한다.
