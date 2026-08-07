# ADR 0015 — 요구사항 후보를 하나의 모델로 다룬다

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 10 (Reconstruct before improve), Principle 3 (Evidence over reasoning), §17 (Scope와 Reasoning Discipline)
- Upstream evidence: [INTERVIEW_UPSTREAM_FINDINGS.md](../research/INTERVIEW_UPSTREAM_FINDINGS.md) §5.5

## Context

[Brief Guide](../05_BRIEF.md) §13.1은 `CLEAR` 조건에 Non-goals 기록, material
conflict 부재, material assumption 해결, material unresolved decision 부재를
**각각 별도 항목으로** 나열했다. 구현은 이 중 하나(`UnresolvedItem`)만 가지고
있었고 나머지 셋은 어떤 코드 경로로도 만들 수 없었다.

Non-goal을 구현하기 전에 upstream을 확인한 결과, upstream은 넷을 별도 개념으로
두지 않는다. `core/requirement_candidate.py`의 **`RequirementCandidate` 하나**에
축이 붙는다.

| 축 | 값 | 우리 문서의 대응 |
|---|---|---|
| `section` | goal, constraint, existing_constraint, acceptance_criterion, ontology, evaluation_principle, exit_condition, **non_goal**, context | Non-goals |
| `resolution` | confirmed, needs_confirmation, **unknown**, **conflicting** | 미해결, 충돌 |
| `content_source` | user_stated, reference_derived, **model_inferred**, repo_observed | 가정 |
| `confirmation_authority` | user, repo_evidence, none | — |
| `required` | bool | material |

또한 `evaluate_promotion()`은 ambiguity score와 **무관하게** 진행을 막는 결정적
정책이며(`requirement_candidate.py:338-430`), Seed 생성 직전에 호출된다
(`mcp/tools/authoring_handlers.py:1469-1474`). 이것이 §11.5 "score 단독 종료
금지"가 upstream에서 구현된 자리다.

네 개의 평행 구조를 만들면 upstream이 하나로 푸는 것을 재발명하게 되고, 이후
대조가 불가능해진다.

## Decision

### 1. `RequirementCandidate` 하나로 통합한다

`UnresolvedItem(description, is_material)`을 제거하고 upstream과 같은 축을 갖는
`RequirementCandidate`로 대체한다. 축의 이름과 값 집합은 upstream을 그대로
따른다.

Brief v1이 실제로 만드는 section은 goal, constraint, existing_constraint,
acceptance_criterion, non_goal, context다. 나머지 세 값(ontology,
evaluation_principle, exit_condition)은 Blueprint가 Seed를 구성할 때 쓰며, 어휘를
잘라내면 이후 단계에서 축이 갈라지므로 지금 포함한다.

### 2. 승격 정책을 결정적 정책으로 재구성한다

`evaluate_promotion()`을 도메인 순수 함수로 둔다. 판정 순서는 upstream과 같다.

1. `conflicting` → `required`와 무관하게 `BLOCK`
2. `unknown` → required면 `BLOCK`, 아니면 `OMIT`
3. `confirmed`가 아님 → required면 `BLOCK`, 아니면 `OMIT`
4. 확인 권위 부족 → required면 `BLOCK`, 아니면 `OMIT`
5. 그 외 `PROMOTE`

4번이 [ADR-0010](./0010-answer-provenance-and-requirement-authority.md)의 원칙이
규칙으로 강제되는 자리다. 저장소 증거는 `context`와 `existing_constraint`에만
스스로 들어갈 수 있고, goal·constraint·non_goal·성공 조건이 되려면 사용자 확인이
필요하다.

필수가 아닌 후보를 조용히 버리지 않고 `OMIT`으로 이유와 함께 남기는 것도
upstream과 같다. 왜 이 진술이 다음 Stage에 가지 않았는지 설명할 수 있어야 한다.

### 3. Gate가 승격 blocker를 읽는다

`GateBlockingCondition.MATERIAL_UNRESOLVED_ITEM`을 `UNPROMOTABLE_REQUIREMENT`로
바꾸고, blocker의 detail에 판정 이유와 대상 section을 담는다. clarity 점수와
독립적으로 성립하는 두 번째 관문이라는 성질이 유지된다.

### 4. Divergence — 파생 read model이 아니라 primary state로 기록한다

**upstream**: 후보 목록은 `RequirementDistillation`이라는 **파생 read model**이다.
LLM이 대화를 읽고 만들어 내며, `InterviewState`에 캐시로 얹혀 내용 지문과
`requirement_input_revision`이 맞지 않으면 load 시 폐기된다
(`core/requirement_candidate.py:269-275`, `bigbang/interview.py:344-356`).

**Mission Control v1**: 후보를 대화에서 distill하지 않고 상태에 직접 기록한다.
`BriefService.record_candidate`와 `resolve_candidate`가 진입점이다.

**근거**: distillation은 LLM 호출과 프롬프트와 캐시 무효화를 함께 요구하며,
질문 루프를 돌리는 데 필요한 것이 아니라 Blueprint에 넘길 때 필요해지는 것이다.
Constitution §17("현재 Stage와 승인 범위가 요구하지 않는 작업을 미리 수행하지
않는다")에 따라 유예한다.

되돌리기 비싼 축(section, resolution, content_source, confirmation_authority,
required)은 이 결정에서 upstream과 일치한다. 유예한 것은 "누가 목록을
채우는가"뿐이며, distillation port를 도입할 때 **모델을 바꾸지 않고** 채우는
주체만 바뀐다.

### 5. Evidence lineage는 도입하지 않는다

upstream의 `evaluate_promotion`은 첫 단계에서 `validate_candidate_lineage`로
후보가 참조하는 evidence의 유효성을 검사한다. Mission Control에는 evidence 객체가
없으므로 이 단계를 구현하지 않는다. `RequirementEvidence`와 `evidence_ids`는
Blueprint의 근거 추적과 함께 다룬다.

후보 식별자도 upstream의 검증된 문자열 `candidate_id` 대신 `number` ordinal을
쓴다. `candidate_id`의 용도가 evidence 교차 참조이고 그 대상이 없기 때문이며,
`BriefRound.number`와 같은 규약이다.

## Consequences

### Positive

- §13.1의 CLEAR 조건 네 개(Non-goals, 충돌, 가정, 미해결)가 하나의 모델에서
  동시에 강제된다.
- 미해결 후보를 application 경계에서 만들 수 있게 되어, 승인 외 Gate 차단 사유가
  실제 사용 경로에서 도달 가능해졌다.
- 관찰이 요구사항이 되는 것을 막는 규칙이 원칙이 아니라 승격 판정으로 강제된다.
- 축과 값 집합이 upstream과 같아 이후 대조가 성립한다.

### Cost

- `UnresolvedItem`을 쓰던 기존 계약·테스트를 수정해야 했다.
- 후보 하나에 축이 다섯 개라 `UnresolvedItem` 두 필드보다 기록 시 입력이 많다.
- Brief v1이 만들지 않는 section 값 세 개가 열거형에 존재한다.
- evidence lineage 검사가 빠져 있어 upstream 정책의 첫 단계가 재현되지 않는다.

## Rejected alternatives

- **`non_goals: tuple[str, ...]` 필드 추가**: 가장 작은 변경이지만 upstream이
  하나로 푸는 것을 네 개의 평행 구조로 재발명한다. 충돌과 가정을 나중에 추가하면
  차이가 더 벌어진다.
- **distillation까지 지금 재구성**: 가장 충실하지만 Phase 1 범위를 넘는다. 축은
  이미 일치하므로 나중에 붙여도 모델이 바뀌지 않는다.
- **`required` 대신 `is_material` 유지**: 문서 용어와 맞지만 upstream 축 이름과
  갈라진다. 산문에서는 "material"을 계속 쓰고 필드명만 upstream을 따른다.
- **Brief가 쓰지 않는 section 값 제거**: 어휘를 잘라내는 것은 upstream과의 차이를
  만드는 일이며, Blueprint에서 다시 확장하면 그 시점의 값 집합이 upstream과
  일치하는지 재확인해야 한다.

## Verification

- 충돌은 `required`와 무관하게 차단된다 ([Brief Guide](../05_BRIEF.md) §17의 B-009).
- 필수 미해결은 차단되고 선택 미해결은 이유와 함께 생략된다 (B-007).
- 저장소 증거만으로 goal·constraint·non_goal·성공 조건을 확정할 수 없다 (B-006).
- 미해결 후보를 use case 경계에서 만들면 Gate가 실제로 `HOLD`한다.
