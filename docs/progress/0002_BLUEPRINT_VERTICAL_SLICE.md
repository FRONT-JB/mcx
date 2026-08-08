# Progress 0002 — Blueprint Vertical Slice

- Status: COMPLETE
- Started: 2026-08-07
- Completed: 2026-08-08
- Scope owner: Blueprint Stage core implementation

## Goal

Brief를 승인 가능한 불변 Seed revision으로 변환하고, Execute 진입 Gate가
채점·승인된 현재 revision을 요구하게 한다.

## Inputs

- [Blueprint Guide](../06_BLUEPRINT.md) — Draft contract
- [SEED_UPSTREAM_FINDINGS.md](../research/SEED_UPSTREAM_FINDINGS.md)
- ADR-0017(schema), 0018(생성 계약), 0019(QA 루프), 0021(상태·revision),
  0022(divergence 등록부)

## In scope

- Blueprint domain: spec(AC identity·승인 기록), assembly(범위 검사),
  qa(정책·판정 기계), state(revision 이력·채점 기록·승인), gate(Execute 진입)
- Application: 생성, 채점(허용 검사가 위임 호출보다 먼저), 수정, 승인, Gate 조회
- Adapter: 파일 기반 durable state (revision·QA·승인 단일 문서)
- deterministic test double로 실행 가능한 test suite

## Out of scope

- 실제 생성기·채점자 text backend 어댑터 (Phase 5)
- 수정 후보 제시·채택 surface (Phase 6·7)
- Fact Resolver (B-004)
- Execute Stage 자체 (Phase 3)

## Deliverables

- [x] `domain/blueprint/spec.py` — AC 내용 digest identity, 중복 계약 거부,
  `BlueprintApproval` (Phase 2 초기 + 종료 검토 수정)
- [x] `domain/blueprint/assembly.py` — 결정적 범위 검사와 lineage 조립
- [x] `domain/blueprint/qa.py` — versioned 정책, 최선 시도 추적, 루프 판정
- [x] `domain/blueprint/state.py` — revision 이력, 채점 허용 규칙, 승인 바인딩
- [x] `domain/blueprint/gate.py` — Execute 진입 판정과 Stage 전이
- [x] `application/blueprint_service.py` + `ports.py` 확장
- [x] `adapters/persistence/file_blueprint_repository.py`
- [x] unit + integration test suite (137건)

## Exit criteria

- [x] 생성 → 채점 → 수정 → 재채점 → 승인 → Gate가 파일 저장소를 거쳐
  end-to-end로 돈다 (결정적 fake 기준).
- [x] 승인이 채점된 현재 revision에 바인딩되고 revise가 승인을 무효화한다.
- [x] 채점 예산(상한 5회)이 프로세스 재시작을 건너 유지된다.
- [x] Execute 진입 Gate가 승인된 현재 revision과 현재 Brief revision 일치를
  요구한다.
- [x] 저장 실패가 전이 성공으로 보고되지 않는다.
- [x] 범위 밖 초안(발명된 제약, 누락된 Non-goal)이 저장 전에 거부된다.
- [x] mypy, ruff, ruff-format이 통과한다.

## Verification evidence

```text
Commits: a94d0c7 (ADR-0021·0022) → 709f9ec (구현) → 12018fe (progress)
         → b00e0c2 (종료 검토 수정: 중복 AC 거부)
Tests: 331 passed
  tests/unit/domain/blueprint/test_spec.py       30
  tests/unit/domain/blueprint/test_assembly.py   13
  tests/unit/domain/blueprint/test_qa.py         27
  tests/unit/domain/blueprint/test_state.py      23
  tests/unit/domain/blueprint/test_gate.py        8
  tests/unit/adapters/persistence/…blueprint…    10
  tests/unit/application/test_blueprint_service…  22
  tests/integration/test_blueprint_flow.py        4
mypy: Success (26 source files)
ruff check / ruff format --check: 통과
Blueprint 구현: 1,398 lines
```

## Phase 종료 검토

[progress README](./README.md)의 여섯 질문에 대한 답이다. 이 검토가 처음으로
완료 선언 **전에** 절차로 수행되었다 (Phase 1은 소급이었다).

### 1. 구조 검사 — 각 방어가 막는 결함

| 방어 | 막는 결함 | 위치 |
|---|---|---|
| AC 내용 digest key | 목록 위치 기반 식별이 증거를 잘못 상속 | `spec.py` key |
| 중복 계약 거부 | Verify 증거가 어느 항목 것인지 판정 불가 | `spec.py` validator — **이 검토에서 발견·수정 (b00e0c2)** |
| `output_assertion`은 명령 요구 | 아무것도 확인 안 하면서 확인 수단이 있어 보이는 AC | `spec.py` validator |
| 승인 기록의 점수-표시 일관성 | 미달 명세가 통과로 기록 | `spec.py` `BlueprintApproval` validator |
| 범위 검사 | 승인 안 된 경계가 명세에 실림 | `assembly.py` `check_scope` |
| 채점 허용 규칙 | 상한 우회(재시작 포함), 통과 재채점, FAIL 후 루프 지속 | `state.py` `ensure_qa_allowed` — 위임 호출 **전에** 검사 |
| 미채점 승인 거부 | QA 근거 없는 승인 기록 | `state.py` `approve` |
| revision 연속성 validator | 승인·채점 기록이 가리키는 revision 소실 | `state.py` |
| Gate blocker | 승인 없는/오래된 revision의 Execute 진입, Brief 변경 후 진행 | `gate.py` |
| 단일 문서 원자 교체 + sequence | 승인만 유실된 상태의 CLEAR 오인, 조용한 덮어쓰기 | `file_blueprint_repository.py` |

산문·프롬프트로만 막는 계약과 그 기록 위치: 생성기의 제약·Non-goal 원문 보존
프롬프트 의존(progress README 알려진 한계), AC 의미 품질은 quality bar 문장
(ADR-0019 §4), **§7.2의 문자열/배열 크기 제한은 미구현** — 이 검토에서 확인해
progress README 알려진 한계에 추가했다. Non-goal↔AC 모순의 결정적 검사도 없다
— QA quality bar(내부 일관성 항목) 소관이며 채점자 어댑터가 붙어야 동작한다.

### 2. 부품/단계 구분

end-to-end로 돈다 — `test_blueprint_flow.py` 4건이 생성 → 채점(REVISE) → 수정
→ 재채점(PASS) → 승인 → Gate `CLEAR` → `Stage.EXECUTE` 전이를 실제 파일
저장소로 잇고, 프로세스 재시작(저장소 재생성) 후 승인과 채점 예산이 유지됨을
확인한다. progress README의 Phase 2 `[x]` 항목을 구현과 대조했고 과장된 체크는
없었다. 단, "돈다"의 기준은 결정적 fake다 — 실제 LLM 생성기·채점자는 Phase 5.

### 3. 미등록 이탈

검토에서 하나 발견: **직전 채점 지적의 전달 방식**(`QaRequest.previous_findings`
— 마지막 채점의 지적만 전달). upstream skill 루프는 대화 안에 있어 전체 이력이
암묵적으로 전달되는데 성문 규정을 확인하지 못했다 → ADR-0022 미확인 표에
등록했다. 그 외 구현 규칙(저장 형태, revision 정책, 승인 점수 귀속, 채점 허용
규칙)은 ADR-0021·0022에 기등록 상태였다.

### 4. 표시 없는 보류

06 §18 미해결 항목, ADR-0022 Deferrals·미확인 표, progress README 알려진 한계를
대조했고 서로 모순 없다. 이 검토에서 추가된 표시: 크기 제한 미구현(질문 1),
previous_findings 미확인(질문 3).

### 5. 계약 문장 원문 여부

`BLUEPRINT_QUALITY_BAR`가 한국어 번역인 것은 ADR-0019 §4에 등록된 알려진
위험이다(재발 아님 — 어댑터 도입 시 재평가 조건 포함). Phase 2 신규 코드에
문장이 곧 계약인 다른 지점은 없다 — Gate·상태의 규칙은 모두 결정적 코드이고,
예외 메시지는 계약 문장이 아니다.

### 6. 관측 대조

[SEED_UPSTREAM_FINDINGS §12](../research/SEED_UPSTREAM_FINDINGS.md)의 관측과
모순되는 규칙 없음: QA 동점은 축별 평균으로 판정(관측 채택, ADR-0019 §5),
첫 생성은 정확히 한 번(`BlueprintAlreadyExistsError`), QA 수정본이 store로
돌아간다(upstream 관측과 의도적으로 다른 지점 — ADR-0019 §1 등록,
`revise`가 저장을 거침).

## Test Matrix 대응

`docs/06_BLUEPRINT.md` §14 기준. 각 행을 테스트 이름이 아니라 assertion과
대조했다.

| 상태 | 행 |
|---|---|
| 덮음 | Entry(CLEAR 없음, stale Brief revision), Generation(valid draft), Structure(duplicate AC — b00e0c2로 수정 후), Refinement(issue 해결, 반복 종료), QA loop(동점, 상한 마지막 통과), Approval 4행 전부, Mutation, Persistence |
| 부분 | Intent(발명 요구사항 — 제약·Non-goal은 결정적 거부, AC 내용의 발명은 미추적: ADR-0018 Cost), Scope(Non-goal을 AC에 포함 — 결정적 검사 없음, QA 소관), AC quality 2행(구조는 드러냄, 의미 판정은 채점자 어댑터 필요: ADR-0019 §4) |
| 대상 없음 | Generation(malformed output — 구조화 port 사용, text backend는 Phase 5), Structure(broken dependency — AC dependency 미모델, §18 open decision), Traceability(source ref schema 미정, §18), Revision(downstream evidence는 Phase 3·4) |

Property invariants: 승인 revision 불변·approval identity 일치·serialization만으로
승인 불가·QA output ≠ GateDecision은 덮음. "Execute attempt가 approved revision
참조"는 Phase 3 대상.

§16 Implementation checklist 중 특기 사항 — "exact content identity를 approval에
연결했다"는 content hash가 아니라 **불변 revision 이력 + revision 번호 바인딩 +
단일 문서 원자성**으로 성립한다. 승인이 가리키는 revision의 내용은 frozen
tuple에 보존되어 사후 변경이 불가능하므로 번호가 곧 내용을 고정한다. content
hash는 §18 open decision으로 남는다(최선 시도 채택 절차가 내용 동일성 판정을
요구할 때 확정).

## 미완료 항목의 처분

- **AC quality validation의 의미 판정** — Phase 5(실제 어댑터)로 이관. Phase 1과
  같은 기준이다: Brief도 결정적 fake로 완료했고 실제 백엔드는 Runtime adapter
  단계다. 구조 검사 부분(중복·빈 goal·output_assertion)은 이번 slice에서 충족.
- **수정 후보 제시·채택 surface** — Phase 6·7 소관 (progress README에 기명시).
  application 진입점(`revise`)은 구현되어 surface가 붙을 자리가 있다.

## 이번 검토가 잡은 것

1. **중복 AC 계약 미검사** — Stage Guide §7.2가 요구하는 결정적 검사가 구현에
   없었다. 검토 질문 1(구조 검사)의 Test Matrix 대조에서 발견, b00e0c2로 수정.
2. **크기 제한 미구현이 어디에도 표시되지 않았다** — §7.2 항목인데 알려진
   한계에 없었다. 추가했다.
3. **previous_findings 전달의 upstream 근거 부재** — ADR-0022 미확인 표에 등록.
