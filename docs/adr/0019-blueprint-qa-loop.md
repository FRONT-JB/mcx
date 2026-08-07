# ADR 0019 — Blueprint QA 루프

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 3 (Evidence over reasoning), Principle 5 (User authority), §6.5 (surface 간 동일 state)
- Upstream evidence: [SEED_UPSTREAM_FINDINGS.md](../research/SEED_UPSTREAM_FINDINGS.md) §8, §9, §10

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

## Decision

### 1. QA 루프를 Core에 둔다

**upstream**: 루프가 skill 계층에 있고 CLI에는 없다.

**Mission Control**: application 계층에 두어 모든 surface가 같은 루프를 거친다.

**근거**: [ADR-0011](./0011-brief-deliberate-divergences.md) Divergence 1과 같다.
Constitution §6.5는 어느 창구로 들어오든 같은 canonical state를 요구한다.
upstream의 비대칭을 따르면 `mcx blueprint`로 만든 명세와 MCP로 만든 명세의 품질
기준이 달라진다. 이 비대칭은 Brief 종료 gate, Seed 진입 gate에 이어 **세 번째로**
확인된 것이므로 개별 예외가 아니라 일관된 대응이 필요하다.

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

반복마다 점수가 오르내린다(upstream 실사용 기록: `0.81 → 0.87 → 0.88 → 0.87`).
따라서 마지막 시도가 최선이 아닐 수 있다.

- `best`는 최고 점수 시도이며 동점이면 **먼저 나온 것**을 유지한다. 같은 점수면
  덜 고친 쪽이 낫다.
- 상한에 도달했을 때 사용자에게 제시하는 것은 마지막이 아니라 `best`다.
- 점수 하락(`regressed`)을 상태로 노출한다. 사용자가 판단할 정보다.

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
- **상한 도달 시 자동 수락**: 사용자가 기준 미달을 모르고 진행한다.
- **상한 도달 시 자동 거부**: 0.89에서 멈춘 명세를 버리는 것은 사용자 권한을
  대신 행사하는 것이다.

## Verification

- 통과·실패 경계값이 정확히 판정된다.
- 최선의 시도가 마지막 시도와 다를 때 최선이 보고된다.
- 동점이면 먼저 나온 시도가 유지된다.
- 상한 도달 시 `EXHAUSTED`이며 최선의 시도를 함께 제공한다.
- 상한의 마지막 채점이 통과면 `DONE`이다.
- `QaAssessment`가 verdict를 담지 않는다.
- 품질 기준이 granularity 규칙을 포함한다.
