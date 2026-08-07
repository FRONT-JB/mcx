# ADR 0019 — Blueprint QA 루프

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 3 (Evidence over reasoning), Principle 5 (User authority), §6.5 (surface 간 동일 state)
- Upstream evidence: [SEED_UPSTREAM_FINDINGS.md](../research/SEED_UPSTREAM_FINDINGS.md) §8, §9, §10, §12

## Context

생성된 Blueprint를 그대로 승인 대상으로 올릴 수 없다.
[ADR-0018](./0018-blueprint-generation-contract.md)의 `check_scope`는 범위만
보고 품질을 보지 않는다 — 수용 기준이 측정 가능한지, 수단이 결과 자리에 섞였는지,
제약이 모호한 표현인지 판정하지 않는다.

upstream 조사에서 실제 강제 경로를 확인했다
([SEED_UPSTREAM_FINDINGS](../research/SEED_UPSTREAM_FINDINGS.md) §8~§10).
`skills/seed/SKILL.md`가 생성 직후 **필수 QA 루프**를 규정한다.

- 생성 직후 "do not present it as final yet"
- `pass_threshold: 0.90` — 일반 기준 0.80보다 엄격. 이유는 "seeds are
  structural specs and must be precise"
- 최대 5회, 최고 점수 시도를 "best attempt"로 추적
- 5회 후에도 통과하지 못하면 사용자에게 세 선택지 — 그대로 수락 / 최종 수정
  하나만 적용 후 수락 / 상위 Stage로 에스컬레이션. 6회째 반복은 금지
- 첫 생성은 정확히 한 번이고 이후 수정은 재생성이 아니라 직접 편집
- 수정은 자동 적용하지 않는다 — "No candidate is accepted by default"
- granularity 규칙이 quality bar 문자열에 그대로 들어 있다

Python core(`ooo seed` CLI)에는 이 루프가 없다. 이는 Brief에서 확인한
CLI/MCP/skill 3층 구조가 Seed에서 반복되는 것이며, 사람이 쓰는 경로의 가장 강한
관문은 항상 skill 계층에 있다.

**채점자는 이미 core에 있다.** 런타임 관측(§12)에서 QA는 MCP 도구
`ouroboros_qa` 호출로 수행됐다. 즉 skill이 갖는 것은 **루프 제어**이고 채점
자체는 core 계층이다. 따라서 아래 Decision 1이 옮기는 것은 루프이지 채점자가
아니다.

## Decision

### 1. QA 루프를 Core에 둔다

**upstream**: 루프가 skill 계층에 있고 CLI에는 없다.

**Mission Control**: application 계층에 두어 모든 surface가 같은 루프를 거친다.

**근거**: [ADR-0011](./0011-brief-deliberate-divergences.md) Divergence 1과 같다.
Constitution §6.5는 어느 창구로 들어오든 같은 canonical state를 요구한다.
upstream의 비대칭을 따르면 `mcx blueprint`로 만든 명세와 MCP로 만든 명세의 품질
기준이 달라진다. 이 비대칭은 Brief 종료 gate, Seed 진입 gate에 이어 **세 번째로**
확인된 것이므로 개별 예외가 아니라 일관된 대응이 필요하다.

이 근거는 원칙론이 아니다. 런타임 관측(§12)에서 skill이 QA로 고친 개정본이
**store에 돌아가지 않았다** — MCP에는 생성 직후 초안이 남았고 실행 엔진은
그것을 읽는다. 루프가 state를 소유하지 않는 계층에 있으면 실제로 이렇게 된다.

### 2. 정책 수치는 upstream 값을 그대로 쓴다

`pass_threshold = 0.90`, `fail_threshold = 0.40`, `max_iterations = 5`.

이 값들은 upstream이 실제 운용에서 정한 것이고, 우리가 다르게 정할 근거가 없다
(Constitution "upstream의 수치 예시를 임의로 바꾸지 않는다"). versioned policy로
주입하므로 근거가 생기면 새 버전으로 교체한다.

### 3. 채점자는 판정하지 않는다

`QaAssessment`는 점수와 지적 사항만 담고 **verdict를 담지 않는다.** 몇 점이면
통과인지는 `QaPolicy.verdict_for`가 정한다.

`QaRequest`에 통과 점수와 반복 상한을 전달하지 않는다. Brief의 clarity 평가와
같은 이유다 — 통과선을 알려 주면 그 선에 맞춰 점수를 조정할 여지가 생긴다.

`quality_bar`는 정책이 정한 문장으로 전달한다. 무엇이 좋은 명세인지를 채점자가
정하면 기준과 점수가 같은 곳에서 나온다.

### 4. 품질 기준에 granularity를 포함한다

`BLUEPRINT_QUALITY_BAR`가 upstream quality bar의 항목을 담는다 — 내부 일관성,
측정 가능한 수용 기준, 구체적인 제약, 필드 간 모순 없음, 그리고 **결과와 수단의
구분**.

granularity를 결정적 코드로 판정하지 않는 이유는 판정 자체가 문장을 형제 항목
옆에서 읽는 판단이기 때문이다. 단어 목록으로는 잡히지 않는다. upstream도 같은
이유로 quality bar에 두었다.

### 5. 최선의 시도를 따로 기억한다

반복마다 점수가 오르내린다(upstream 실사용 기록:
`0.81 → 0.87 → 0.88 → 0.87 → 0.88`). 따라서 마지막 시도가 최선이 아닐 수 있다.

- `best`는 최고 점수 시도다.
- **동점이면 축별 평균이 높은 쪽**이다. 축 평균까지 같으면 먼저 나온 것을
  유지한다.
- 상한에 도달했을 때 사용자에게 제시하는 것은 마지막이 아니라 `best`다.
- 점수 하락(`regressed`)을 상태로 노출한다. 사용자가 판단할 정보다.

**동점 규칙을 2026-08-08에 바꿨다.** 처음에는 "동점이면 먼저 나온 것 — 같은
점수면 덜 고친 쪽이 낫다"였다. 그 규칙은 upstream 근거 없이 우리가 만든 것이고,
이후 확보한 유일한 관측이 반대였다 (§12). 관측된 실행은 3회차와 5회차가 모두
0.88일 때 5회차를 채택하며 "차원별로는 이전 최고보다 낫다 — Correctness
0.85 → 0.90"을 근거로 들었다.

총점은 반올림 자리에서 같아지지만 축 점수는 다를 수 있고, 그때 총점만 보면
**실제로 더 나은 명세를 버린다.** 근거 없는 우리 규칙을 유지하는 것보다 관측된
동작을 따르는 편이 divergence를 줄인다.

> ⚠️ `skills/seed/SKILL.md`가 동점을 규정하는지는 **미확인**이다. 관측은 1회
> 실행의 판단일 수 있다. 확인 항목은
> [SEED_UPSTREAM_FINDINGS](../research/SEED_UPSTREAM_FINDINGS.md) §11에 있다.

### 6. 루프 종료 조건

| 상황 | 동작 |
|---|---|
| 통과 점수 | `DONE` — 승인 요청 단계로 |
| 실패 점수 | `ESCALATE` — 명세 수준 문제이므로 반복으로 해결하지 않는다 |
| 재작업 점수, 횟수 남음 | `CONTINUE` |
| 재작업 점수, 상한 도달 | `EXHAUSTED` — 최선의 시도로 사용자 결정 요청 |

**통과 판정이 상한 판정보다 앞선다.** 상한에 도달한 마지막 채점이 통과라면
통과다 — 횟수를 다 썼다는 이유로 합격을 취소하지 않는다.

### 7. 수정은 자동 적용하지 않는다

채점자는 지적과 제안만 반환하고 초안을 고치지 않는다. 무엇을 적용할지는 사용자가
정한다.

upstream의 "No candidate is accepted by default"와 같다. 자동 적용하면 사용자가
승인한 적 없는 명세가 승인 대상이 되고, 특히 **사용자가 이미 정한 값을 QA가
뒤집는** 경우를 사용자가 모르고 지나친다.

이 ADR은 적용 절차의 **경계**만 정한다. 후보를 어떻게 제시하고 선택받을지는
CLI/MCP surface(Phase 6·7)가 다룬다.

### 8. QA 결과는 승인 기록이 들고 있다

`BlueprintApproval`이 `qa_policy_version`, `qa_threshold`, `qa_best_score`,
`qa_iterations`, `accepted_below_threshold`를 담는다. **Blueprint 자체는 QA
결과를 담지 않는다.**

Blueprint는 방향이고 승인 이후 불변이다
([ADR-0002](./0002-approved-seed-is-immutable.md)). 점수를 Blueprint에 넣으면
채점 결과를 적는 것만으로 revision이 올라가고 재승인이 필요해진다 — 방향은
하나도 바뀌지 않았는데. 반면 승인 기록은 "누가 무엇을 보고 진행을 허락했는가"의
자리이고, 그 판단의 근거인 QA 결과가 여기 있는 것이 맞다.

`accepted_below_threshold`가 이 결정의 핵심이다. 임계 미달 수락(§6의
`EXHAUSTED` 경로)이 상태로 남지 않으면, 나중에 **"이 명세가 기준을 통과한
것인가, 사용자가 0.88에서 봐준 것인가"를 물을 방법이 없다.** 미달 명세에서
출발한 미션이 `MISSION COMPLETE`에 도달했을 때 그 사실이 어디에도 없으면 완료
선언의 근거가 비어 있다 ([ADR-0005](./0005-evidence-over-reasoning.md)).

`qa_threshold`를 정책 버전과 **함께** 저장한다. 버전만 있으면 오래된 승인을
읽을 때 정책 정의를 되짚어야 하고, 그 사이 정책 파일이 사라지면 기록이 해석
불가능해진다. 임계값이 함께 있으면 `accepted_below_threshold`가 기록 자체로
검증된다 — 실제로 model validator가 둘의 일관성을 강제한다.

upstream이 seed metadata에 같은 성격의 값을 남기는 것을 관측했으나(§12), 그
키들이 `SeedMetadata`에 선언된 것인지는 미확인이다. **산출물 형태가 아니라
필요성**을 채택했고, 담는 위치는 우리 승인 모델을 따른다.

## Consequences

### Positive

- 모든 surface가 같은 품질 기준을 거친다.
- 기준·점수·판정이 서로 다른 곳에 있어 한 역할이 자기 통과를 결정할 수 없다.
- 점수가 내려가도 최선의 결과를 잃지 않는다.
- granularity가 기준 문장에 포함되어 실제 채점 항목이 된다.

### Cost

- upstream보다 엄격하다. CLI 경로에서도 QA를 거치므로 생성이 느려진다.
- 채점이 LLM 호출이므로 반복마다 비용이 든다. 상한 5회가 그 경계다.
- 수정 적용에 사용자 개입이 필요하므로 완전 자동 경로가 없다. 이는 의도한
  마찰이다.
- 점수의 절대값은 채점자 구현에 의존한다. 정책 버전이 그것을 추적한다.

## Rejected alternatives

- **upstream처럼 skill 계층에만 두기**: surface마다 품질 기준이 달라진다.
  §6.5 위반이며 이미 세 번 확인된 비대칭을 네 번째로 반복한다.
- **채점자가 verdict를 반환**: 통과선을 아는 채점자가 그 선에 맞춰 점수를
  조정할 수 있다.
- **granularity를 단어·정규식으로 판정**: "결과인가 수단인가"는 형제 항목과의
  관계에서 나오므로 문자열로 판정할 수 없다. upstream의 `auto/grading.py`도
  granularity는 검사하지 않는다.
- **마지막 시도를 결과로 사용**: upstream 실사용에서 점수 하락이 실제로
  발생한다.
- **동점을 총점만으로 판정**: 축 점수가 더 나은 시도를 버린다 (§5).
- **상한 도달 시 자동 수락**: 사용자가 기준 미달을 모르고 진행한다.
- **상한 도달 시 자동 거부**: 0.89에서 멈춘 명세를 버리는 것은 사용자 권한을
  대신 행사하는 것이다.
- **QA 결과를 Blueprint 필드로**: 채점 결과를 적는 것만으로 revision이 올라가고
  방향이 바뀌지 않았는데 재승인이 필요해진다 (§8).
- **`accepted_below_threshold`를 점수에서 매번 계산**: 정책 정의가 사라지면
  기록을 해석할 수 없다. 승인 기록은 자기 자신만으로 읽혀야 한다.

## Verification

- 통과·실패 경계값이 정확히 판정된다.
- 최선의 시도가 마지막 시도와 다를 때 최선이 보고된다.
- 총점이 같으면 축별 평균이 높은 시도가 최선이다.
- 축 평균까지 같으면 먼저 나온 시도가 유지된다.
- 상한 도달 시 `EXHAUSTED`이며 최선의 시도를 함께 제공한다.
- 상한의 마지막 채점이 통과면 `DONE`이다.
- `QaAssessment`가 verdict를 담지 않는다.
- 채점 축이 upstream의 다섯 개와 일치한다.
- 품질 기준이 granularity 규칙을 포함한다.
- `Blueprint`는 QA 결과 필드를 거부하고, `BlueprintApproval`이 그것을 담는다.
- 점수가 임계 미만인데 `accepted_below_threshold`가 없는 승인은 거부된다.
