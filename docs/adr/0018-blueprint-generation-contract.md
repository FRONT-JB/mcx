# ADR 0018 — Blueprint 생성 계약: 무엇을 위임하고 무엇을 결정적으로 확인하는가

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 6 (Scope는 hard boundary), Principle 3 (Evidence over reasoning), §17
- Upstream evidence: [SEED_UPSTREAM_FINDINGS.md](../research/SEED_UPSTREAM_FINDINGS.md) §6

## Context

[ADR-0016](./0016-brief-handoff-projection.md)이 Blueprint의 입력을,
[ADR-0017](./0017-blueprint-schema-baseline.md)이 출력을 고정했다. 남은 것은 그
사이의 변환이다.

upstream의 흐름은 `SeedGenerator.generate` (`bigbang/seed_generator.py:1719`)에
있다.

1. ambiguity threshold gate (`:1770`)
2. `initial_context_summary_missing` 확인
3. `build_requirement_distillation(state)` — 결정적 후보 도출
4. `apply_requirement_distillation` — 결정적 승격 판정. blocker가 있으면 중단
5. `_extract_requirements(state)` (`:1981`) — **LLM 호출 한 번**,
   `role="seed_generation"`. 파싱 실패 시 명확화한 프롬프트로 **한 번 재시도**
6. `_parse_extraction_response` — 결정적 파싱과 검증

즉 upstream은 **결정적 관문 → 모델 1회 → 결정적 검증**이다. 파싱 계층은
2,637줄 파일의 대부분을 차지하며, POSIX 셸 추적기와 중복 JSON 키 거부까지 갖는다
— 모델 출력이 필드 경계를 넘나드는 실패를 실제로 겪었다는 증거다.

Mission Control의 상황은 하나 다르다. handoff가 이미 goal/constraints/non_goals/
success_criteria로 나뉘어 있다([ADR-0015](./0015-requirement-candidate-model.md)의
결과). upstream은 대화 원문에서 전부 추출하지만 우리는 **이미 칸이 나뉜 입력**을
받는다. 따라서 모델에게 남는 일이 더 작다.

## Decision

### 1. 위임하는 것은 "성공 조건의 구체화" 하나다

생성기의 일은 `success_criteria` 문장에 **확인 계약**을 붙이는 것이다. "목록 맨
위에 새 댓글이 보인다"에서 `verify_command`, `expected_artifacts`,
`output_assertion`을 뽑는 데는 판단이 필요하다.

goal 문장의 정리도 위임한다. 나머지(제약, Non-goal)는 사용자가 정한 경계이므로
구체화 대상이 아니다.

### 2. 생성기에 handoff의 칸만 전달한다

`BlueprintGenerationRequest`는 goals, constraints, non_goals, success_criteria,
context만 담는다. **대화 원문, 관찰 사실 본문, revision 이력을 넘기지 않는다.**

생성기가 대화를 다시 읽을 수 있으면 Brief에서 합의되지 않은 것을 요구사항으로
되살릴 수 있고, 그것이 handoff를 둔 이유를 없앤다.

`context`는 예외다. 관찰된 현재 상태는 요구사항이 아니라 **성공 조건을 확인
가능하게 만드는 재료**다 — 어떤 명령으로 무엇을 확인할지 정하려면 지금 무엇이
있는지 알아야 한다.

### 3. 초안은 lineage를 담지 않는다

`BlueprintDraft`에는 mission_id도 revision도 brief_revision도 없다. 조립 단계가
handoff에서 가져온다. 생성기가 revision을 정할 수 있으면 **승인 대상이 어느
Brief에서 나왔는지를 모델이 주장하게 된다.**

### 4. 범위 검사는 결정적이다 — Scope는 hard boundary

`check_scope`가 모델을 부르지 않고 판정한다.

| 항목 | 규칙 | 이유 |
|---|---|---|
| 제약 추가 | 거부 | 승인받지 않은 경계가 생긴다 |
| 제약 누락 | 허용 | 범위를 넓히지 않는다. Blueprint QA가 다룰 문제다 |
| Non-goal 추가 | 거부 | 위와 같다 |
| Non-goal 누락 | **거부** | 승인된 경계가 사라지고, 만드는 쪽이 그 범위까지 만든다 |
| 수용 기준 없음 | 거부 | 완료를 증거로 선언할 수 없다 |
| 빈 goal | 거부 | — |

제약 누락과 Non-goal 누락을 다르게 다루는 것이 이 표의 핵심이다. 제약을 덜
싣는 것은 **더 좁게** 만드는 것이지만, Non-goal을 빠뜨리는 것은 **더 넓게**
만드는 것이다. "하지 않기로 한 일"의 목록에서 항목이 사라지면 그 일이 다시
범위에 들어온다.

수용 기준은 내용 일치를 요구하지 않는다. 문장을 다시 쓰거나 하나를 여럿으로
쪼개는 것이 생성기의 일이기 때문이다. **존재만** 요구한다.

### 5. 범위를 벗어나면 거부하고 경고로 남기지 않는다

`assemble_blueprint`가 `BlueprintScopeError`를 올린다. 경고로 남기고 진행하면
초안이 승인 화면에 올라가고, 그 순간 사용자는 그것을 **Brief에서 합의한
내용으로 읽는다.**

### 6. 재시도 정책은 아직 정하지 않는다

upstream은 파싱 실패 시 명확화한 프롬프트로 한 번 재시도한다. Mission Control은
Phase 2의 이 단계에서 재시도를 도입하지 않는다 — 범위 위반과 파싱 실패는 다른
실패이며, 무엇을 재시도하고 무엇을 사용자에게 돌려줄지는 Blueprint QA 루프와
함께 정해야 한다.

## Consequences

### Positive

- 승인된 범위를 벗어난 명세가 승인 화면에 도달하지 않는다.
- 모델에게 남는 일이 작아 실패 표면이 좁다.
- 위임 경계가 시그니처로 강제된다 — 생성기는 대화를 볼 수 없다.
- lineage를 모델이 주장할 수 없다.

### Cost

- 제약과 Non-goal의 **문자열 완전 일치**를 요구하므로, 생성기가 표현을 다듬으면
  범위 위반으로 거부된다. 이는 의도한 엄격함이지만 생성 프롬프트가 원문을 그대로
  옮기도록 지시해야 한다.
- 수용 기준의 traceability를 강제하지 않는다. 성공 조건과 무관한 AC를 만들어도
  범위 검사를 통과한다 (아래 한계).
- upstream의 방어적 파싱 계층이 없다. 구조화된 출력을 port 타입으로 요구하므로
  Phase 2 범위에서는 필요하지 않지만, 실제 어댑터가 붙을 때 재평가한다.

## Rejected alternatives

- **범위 위반을 경고로 기록하고 진행**: 승인 화면에 오르는 순간 합의된 내용으로
  읽힌다.
- **수용 기준도 handoff 문장과 일치를 요구**: 구체화 자체가 불가능해진다. 하나의
  성공 조건이 여러 AC가 되는 정상 경로를 막는다.
- **생성기에 대화 원문 전달**: handoff를 둔 이유를 없앤다.
- **제약 누락도 거부**: 범위를 넓히지 않는 변화까지 막으면 생성기가 판단할 여지가
  사라지고, 실제로는 중복 제약을 합치는 정상 동작도 막힌다.
- **upstream의 재시도를 지금 복제**: 무엇을 재시도할지가 QA 루프 설계에 달려
  있어 지금 정하면 근거 없는 확정이 된다.

## Verification

- 초안이 handoff에 없는 제약이나 Non-goal을 담으면 거부된다.
- 승인된 Non-goal을 빠뜨린 초안이 거부된다.
- 수용 기준이 없는 초안이 거부된다.
- lineage가 초안이 아니라 handoff에서 온다.
- 수용 기준의 표현이 handoff와 달라도 통과한다.
