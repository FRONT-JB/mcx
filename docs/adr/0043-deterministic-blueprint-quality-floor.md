# ADR 0043 — 결정적 Blueprint 품질 하한

- Status: **Accepted** (사용자 승인 2026-08-10 — §4는 (a) 표시만으로 확정)
- Date: 2026-08-09
- Constitutional basis: [ADR-0005](./0005-evidence-over-reasoning.md) (Evidence
  over reasoning), [ADR-0019](./0019-blueprint-qa-loop.md) (LLM 채점 층),
  [ADR-0042](./0042-skill-and-core-ownership-boundary.md) §1 (소유 판별 규칙)
- Upstream evidence: [SEED findings §11](../research/SEED_UPSTREAM_FINDINGS.md)
  (`auto/grading.py`, `auto/gap_detector.py`)
- 해소 대상: [Open Questions §3](../research/OPEN_QUESTIONS.md)의
  *"결정적 품질 gate(upstream `GradeGate`)의 대응물을 도입한다"* (Phase 8 시한)

## Context

upstream의 Seed 품질 방어는 **두 층**이다 — LLM 채점(우리 ADR-0019 QA의
대응물)과 `auto/grading.py`의 **결정적** gate. 후자는 계산만으로 등급을 매기고
`may_run = grade == SeedGrade.A and not blockers`로 실행을 막는다. 우리에겐
구조 검사(`check_scope`)만 있고 점수화된 결정적 층이 없다고 기록해 두었다.

**조사해 보니 그 기술이 과장이었다.** upstream이 결정적으로 보는 것은
`GapDetector`가 판정하는 **섹션 단위 상태**다 — `REQUIRED_SECTIONS` 각각이
`MISSING`/`WEAK`/`CONFLICTING`/`BLOCKED` 중 하나면 gap이고, `BLOCKED`만
repairable이 아니다(`auto/gap_detector.py:56-76`). 점수는 그 gap 수를 나눈
파생값이다(`coverage = 1 - open_gaps/10`).

즉 **upstream의 결정적 층이 실제로 보는 것은 "필수 칸이 채워졌는가"** 이고,
그것은 우리 `check_scope`가 이미 하는 일이다(빈 goal 거부, 제약·Non-goal 원문
보존, AC 부재 거부, AC 중복 거부).

## Decision

### 1. 등급과 점수 사전은 도입하지 않는다

upstream의 `SeedGrade` A/B/C와 `scores` 사전(`coverage`·`ambiguity`·
`testability`·`execution_feasibility`·`risk`)을 옮기지 않는다.

이유는 **이미 같은 일을 하는 어휘가 있기 때문**이다. `may_run` 한 비트가
필요한 upstream과 달리 우리에겐 `CLEAR`/`HOLD` + `blocking_reasons`가 있고,
그것이 Execute 진입을 이미 막는다. 등급을 더하면 *"왜 못 가는가"* 의 답이 두
군데가 되고, 그때 어느 쪽이 진실인지 판정할 근거가 없다 —
[ADR-0037](./0037-mission-record-and-canonical-stage.md)이 "저장된 Stage vs
Gate 재계산"에서 겪은 문제와 같은 형태다.

점수는 그 자체로 결정을 바꾸지 않는다. upstream에서도 결정을 내리는 것은
`grade == A and not blockers`이며, 점수는 표시값이다.

### 2. 위치는 Core다 — upstream과 다른 층

upstream은 이 gate를 `auto/`, 즉 **합성 계층**에 둔다. 우리는 **Core**
(`evaluate_blueprint_gate`)에 둔다.

근거는 [ADR-0042](./0042-skill-and-core-ownership-boundary.md) §1의 판별
질문이다 — *"같은 입력에 항상 같은 답인가?"* 결정적 검사는 정의상 그렇다.
그리고 §1과 같은 이유로, 실행을 막는 자리가 둘이 되면 안 된다.

**층 이동으로 등록한다** — 강화가 아니다(오늘 확립한 기록 규율,
ADR-0042 §8). 대가는 upstream이 합성 계층에서 이 gate를 끄거나 바꿀 수 있는
반면 우리는 Core를 고쳐야 한다는 것이다.

### 3. 새로 막는 것은 하나다 — **확인 수단이 하나도 없는 Blueprint**

`AcceptanceCriterion.is_mechanically_verifiable`은 이미 계산된다
(`verify_command` · `expected_artifacts` · `output_assertion` 중 하나라도
있는가). `Blueprint.unverifiable_criteria`도 이미 있다. **그런데 어떤 Gate도
그것을 소비하지 않는다.**

결과는 우리 코드 주석이 이미 말해 둔 상태다 (`domain/blueprint/spec.py`
`is_mechanically_verifiable` docstring):

> *"거짓이라고 해서 잘못된 AC는 아니지만, **그런 AC만으로 미션이 구성되면
> 완료를 증거로 선언할 수 없다.**"*

전 AC가 확인 수단이 없는 Blueprint는 승인·Execute·Verify를 지나갈 수 있고,
mechanical 층은 돌 것이 없어 **공허하게 통과**하며, `MISSION COMPLETE`는
semantic 판정 하나에만 얹힌다. 그것은 [ADR-0005](./0005-evidence-over-reasoning.md)
*"Telemetry 없는 `CLEAR`는 없다"* 가 막으려던 바로 그 상태다.

따라서 Blueprint Gate에 blocker 하나를 더한다:

```
NO_VERIFIABLE_CRITERION — 확인 수단이 있는 수용 기준이 하나도 없다
```

이것은 **upstream 대응물 없음**이다. upstream의 `testability`는 섹션 단위
(`acceptance_criteria`가 open gap인가)이지 기준 단위가 아니다. 우리 AC 모델이
기준마다 확인 수단을 갖는 구조라서 생기는 축이며, 발명임을 여기 명시한다.

### 4. 부분 커버리지는 막지 않는다 — **표시만 한다** (확정)

*"AC 10개 중 3개만 확인 수단이 있다"* 는 상태를 막지 않는다. 임계값
(예: 50%)은 upstream에 근거가 없고, 우리가 지금 그 수치를 정할 근거도 없다 —
[Constitution §25](../00_MISSION_CONTROL.md)의 "구현 편의로 임의 확정하지
않는다"에 해당한다.

**대신 세어서 드러낸다.** Gate 판정이 `verifiable_criteria` /
`total_criteria`를 싣는다 — `mcx blueprint gate`가 그것을 출력하고, MCP는 같은
값을 `structured_content`로 받는다. 막지는 않지만 Gate를 부르면 보인다.

**`mcx status`에는 아직 싣지 않는다.** 상태 박스는 차단 사유를 원문으로
인용하는 화면이고 이 수치는 차단 사유가 아니다 — §4가 결정되면 그 결과에 맞춰
싣는 편이 낫다(경고로 승격되면 차단 사유 옆자리, 그대로면 별도 줄).

> **사용자 결정 2026-08-10: (a) 표시만 한다.** 막지도, 경고로 승격하지도
> 않는다.
>
> 결정 직전 upstream을 다시 대조해 **근거가 추측이 아님을 확인했다**:
> `has_success_contract`(= `verify_command` 또는 `expected_artifacts` 또는
> `output_assertion`)는 **AC마다 선택**이고, 계약이 없는 AC는 평가에서 그냥
> 건너뛴다 (`evaluation_handlers.py:89` — `if not criterion.has_success_contract:
> continue`). **확인 수단 비율에 대한 규칙이 upstream 어디에도 없다.**
>
> upstream이 100%를 요구하는 축은 따로 있으며 그것은 **판정 커버리지**다
> (`evolution/evaluation_coverage.py` — 모든 AC가 정확히 한 번, 기대 index에,
> 기대 내용으로 판정을 받아야 한다). 임계값이 아니라 **완전성**이며, 우리는
> `SEMANTIC_VERDICT_MISSING` blocker로 이미 같은 것을 요구한다.
>
> 따라서 **표시만 하는 지금 상태가 upstream과 동등**하고, 막는 쪽이 새
> divergence다. 근거가 될 수치는 upstream에도 우리에게도 없다.

## Consequences

### Positive

- `MISSION COMPLETE`가 mechanical 증거 없이 선언되는 경로가 닫힌다.
- 이미 계산되던 `unverifiable_criteria`에 소비자가 생긴다 — 계산만 하고 아무도
  안 보는 필드가 하나 줄어든다.
- 판정 어휘가 하나로 유지된다(`CLEAR`/`HOLD` + 이유).

### Cost

- 확인 수단이 전부 없는 Blueprint를 쓰던 경로가 있다면 깨진다. 그런 Blueprint는
  애초에 Verify가 증거로 판정할 수 없으므로 의도된 파괴다.
- upstream이 합성 계층에서 이 층을 조정하는 유연성을 우리는 갖지 않는다 (§2).
- 부분 커버리지는 여전히 막히지 않는다 (§4).

## Rejected alternatives

- **upstream의 A/B/C 등급과 점수 사전 이식** — 판정 어휘가 둘이 된다 (§1).
- **skill 계층에 두기 (upstream 위치 그대로)** — 실행을 막는 자리가 둘이 되고,
  우리 판별 규칙은 결정적 검사를 Core로 보낸다 (§2).
- **부분 커버리지 임계값 도입** — 근거 없는 수치 확정이다 (§4).
- **QA(LLM)에게 검증 가능성을 맡기기** — 이미 quality bar에 들어 있지만 판정이
  확률적이다. 계산으로 답이 나오는 것을 모델에게 묻지 않는다.

## Verification

- 전 AC가 확인 수단이 없는 Blueprint는 `blueprint gate`에서 `HOLD`이며 이유가
  `NO_VERIFIABLE_CRITERION`이다.
- 하나라도 확인 수단이 있으면 통과한다 (부분 커버리지는 막지 않는다 — §4).
- Gate 판정이 `verifiable_criteria`와 `total_criteria`를 싣는다.
- 승인 여부와 무관하게 판정된다 — 승인된 Blueprint라도 이 blocker는 남는다.
