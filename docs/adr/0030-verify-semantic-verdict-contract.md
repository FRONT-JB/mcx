# ADR 0030 — Verify semantic verdict 계약

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 3 (Evidence over reasoning), [ADR-0028](./0028-verify-v1-mechanical-contract.md)
- Upstream evidence: [VERIFY_UPSTREAM_FINDINGS.md](../research/VERIFY_UPSTREAM_FINDINGS.md) §6~§7

## Context

mechanical 검증(ADR-0028)은 "명령이 통과했는가"까지만 답한다. "테스트는
통과하지만 AC는 미충족"과 성공 계약이 없는 AC의 판정은 semantic 층의 몫이며,
그 verdict schema와 uncertainty 표현은 [Open Questions
§5](../research/OPEN_QUESTIONS.md)의 미결정 항목이었다. verdict는 `MISSION
COMPLETE`의 근거가 되는 도메인 개념이므로 구현 전에 축을 고정한다.

upstream 사실 ([VERIFY_UPSTREAM_FINDINGS](../research/VERIFY_UPSTREAM_FINDINGS.md) §6~§7):

- 판정 단위는 AC 하나. 입력은 AC 원문 + 선언된 성공 계약 + goal/constraints +
  실제 소스 파일. 출력은 구조화 JSON(compliance bool, score, uncertainty,
  reward_hacking_risk, reasoning, questions_used, evidence).
- 통과는 `ac_compliance AND score >= 0.8`. uncertainty는 통과 조건이 아니라
  escalation trigger 입력(임계 0.3)이다.
- `reward_hacking_risk >= 0.7`은 단일 최종 gate에서 통과를 뒤집는다.
- escalation(Stage 3)은 ADVOCATE/DEVIL/JUDGE 숙의 + 배심 독립성 4-label.

## Decision

> **정렬 note (2026-08-09, 도그푸딩 0003).** AC 판정 실행은 순차가 아니라
> **AC별 병렬**이다 — upstream은 semantic stage(Stage 2+)를 AC별
> `asyncio.gather`로 돌리고, 하나라도 실패하면 반쪽 평가를 집계하지 않고
> 전체를 중단한다 (`mcp/tools/evaluation_handlers.py:877-955`, "#366").
> 0003에서 AC 9개 순차 판정이 ~12분(AC당 ~80s)으로 실측되어 비용·속도
> 요구사항(ADR-0035) 위반이었고, gather 정렬로 수정했다. 실패 시 전체 중단
> 의미론은 gather의 기본 예외 전파와 전량 성공 후 일괄 저장이 그대로
> 구현한다.

### 1. verdict는 AC 단위이고 필드는 upstream 스키마와 정렬한다

```text
CriterionVerdict          # AC 하나에 대한 semantic 판정
  ac_key                  # lineage
  satisfied               # bool — upstream ac_compliance 대응
  score                   # 0..1 — 전체 품질
  uncertainty             # 0..1 — 판정 자신에 대한 불확신
  reward_hacking_risk     # 0..1 — 평가자를 속이는 산출물 의심
  reasoning               # 판정 근거 설명
  evidence                # 구체 증거 참조 목록
  questions_used          # 평가자가 실제로 물은 질문 (show your work)
```

범위(0..1)는 생성 시점에 강제한다. [Verify Guide](../08_VERIFY.md) §5.2
초안의 4-status(`satisfied|not_satisfied|uncertain|not_observed`)는 채택하지
않는다 — upstream은 bool + uncertainty float이며, `uncertain`을 status로
만들면 "충족인데 불확실"과 "미충족인데 불확실"이 구분되지 않는다.
`not_observed`(관찰 자체가 없음)는 observation adapter(Guide §13 Slice 5)의
축이므로 그 도입 시 재평가한다 (ADR-0029 보류 등록).

### 2. 통과 임계는 upstream 값을 채택한다

- semantic 통과: `satisfied AND score >= 0.8`.
- `uncertainty > 0.3`: 통과 실패가 아니라 **escalation 필요**다. upstream은
  consensus(Stage 3)로 올리지만 v1에 consensus가 없으므로 Gate는 escalation
  대기로 `HOLD`한다 — 불확실한 판정을 통과로도 실패로도 세지 않는다.
- `reward_hacking_risk >= 0.7`: 다른 조건이 전부 통과여도 Gate가 거부한다.
  upstream과 같은 단일 최종 gate 배치이며, 임계가 높은 이유(경미한 의심이
  진짜 통과를 막지 않게)도 함께 채택한다.

수치 셋(0.8 / 0.3 / 0.7)은 발명이 아니라 upstream 채택이고, 정책 객체의
versioned 필드로 둔다 (Brief clarity·Blueprint QA 정책과 같은 배치).

### 3. 평가자는 port이고 v1 구현은 결정적 fake다

Brief clarity 평가자·Blueprint QA 채점자와 같은 배치다. port의 입력은
upstream 프롬프트 계약과 같은 축 — AC(성공 계약 포함), goal, constraints,
non-goals, 그리고 **mechanical 증거**(VerificationRun — upstream이 선언 계약을
"grades against"하는 것의 우리 대응). 실제 LLM adapter는 Phase 5다.

worker의 `result_summary`는 이 입력에도 없다 (ADR-0028 §1과 같은 이유).

### 4. Verify Gate의 `CLEAR — MISSION COMPLETE` 조건이 완성된다

현재 Blueprint revision의 **모든 AC**에 대해:

1. 기계 검증 가능한 AC는 mechanical run이 통과 (ADR-0028 — semantic이
   mechanical 실패를 뒤집지 못한다).
2. 모든 AC에 verdict가 존재하고 `satisfied AND score >= 0.8`.
3. 모든 verdict의 `uncertainty <= 0.3`.
4. 모든 verdict의 `reward_hacking_risk < 0.7`.

전부 만족하면 `CLEAR — MISSION COMPLETE` — v1 Gate가 처음으로 도달 가능한
CLEAR를 갖는다. verdict는 검증된 evidence(blueprint revision +
VerificationEvidence)에 바인딩되며, revision이 바뀌면 stale이다.

### 5. consensus(Stage 3)는 v1에 도입하지 않는다

trigger 6조건, ADVOCATE/DEVIL/JUDGE 숙의, 배심 독립성 4-label은 기록으로
남기고(ADR-0029 보류), v1의 escalation은 `HOLD`가 전부다. 도입 시점의 대조
기준: uncertainty·drift trigger 임계(0.3), "votes beat purity"(정족수 아래로
독립성을 사지 않는다), 독립성 라벨의 정직성(unknown vendor ≠ 독립 증거).

## Consequences

### Positive

- "테스트는 통과하지만 AC 미충족"이 판정 가능해진다 — mechanical과 semantic이
  서로를 대체하지 못하는 두 층으로 완성된다.
- MISSION COMPLETE가 도달 가능해지되, 그 근거(두 층 + 불확실성 + 게이밍
  의심)가 전부 기록에 남는다.
- 수치와 스키마가 upstream과 필드 수준에서 대조 가능하다.

### Cost

- 결정적 fake 기준에서 semantic 판정의 **품질**은 여전히 검증되지 않는다 —
  검증되는 것은 판정 주변의 규칙이다 (Phase 5에서 실제 평가자).
- consensus 부재로, 불확실한 판정은 해소 경로 없이 HOLD에 머문다 — 사람이
  개입해야 한다.

## Rejected alternatives

- **4-status enum (가이드 §5.2 초안)**: upstream 대응물이 없고, uncertainty를
  status에 접으면 정보가 준다. bool + float가 upstream 사실이다.
- **uncertainty를 통과 조건으로**: upstream에서 uncertainty는 escalation
  신호다. 통과 조건으로 만들면 "확신 있는 오판"과 "불확실한 정판"을 같은
  축에 놓게 된다.
- **reward_hacking veto 생략**: 필드와 gate 규칙은 결정적이고 싸다. 생략하면
  Phase 5에서 실제 평가자가 위험을 보고해도 받을 자리가 없다.
- **consensus를 지금 구현**: 발동 경로(실제 LLM의 uncertainty)가 없는 v1에서
  는 테스트할 수 없는 장식이다.

## Verification

- verdict 없는 AC가 하나라도 있으면 CLEAR되지 않는다.
- mechanical 실패가 semantic satisfied로 뒤집히지 않는다.
- `uncertainty > 0.3`인 verdict가 있으면 escalation 대기로 HOLD한다.
- `reward_hacking_risk >= 0.7`이면 다른 조건이 전부 통과여도 거부된다.
- 이전 revision의 verdict로는 현재 revision이 CLEAR되지 않는다.
- 전 조건 만족 시 `CLEAR — MISSION COMPLETE`가 선언되고 Verify Gate만 이를
  선언한다.
