# ADR 0050 — 요구사항 후보의 출처: upstream 파생을 이식하고, 전사를 끊은 대가를 Gate가 갚는다

- Status: **Accepted** (사용자 결정 2026-08-10 — "upstream과 유사하면서 가장 안전한 방법")
- Date: 2026-08-10
- Constitutional basis: [ADR-0015](./0015-requirement-candidate-model.md)
  (요구사항 후보 모델), [ADR-0016](./0016-handoff-is-derived.md),
  [ADR-0018](./0018-blueprint-scope-boundary.md) (생성기는 대화를 다시 읽지 않는다)
- Upstream evidence: [DOGFOODING_0004](../research/DOGFOODING_0004.md) §2
- 해소 대상: 도그푸딩 0004가 관측한 **빈 handoff에 `CLEAR`** (Brief Gate)

## Context

도그푸딩 0004에서 `blueprint generate`가 `no_acceptance_criteria`로 죽었다.
파고든 결과 원인은 Blueprint가 아니었다 — **handoff의 칸이 전부 비어 있는데
Brief Gate가 `CLEAR`였다.**

```
handoff.goals 0 · constraints 0 · non_goals 0 · success_criteria 0
clarity 0.96 · closure ready · 승인 있음 → CLEAR
```

### upstream에서는 이 상태가 만들어지지 않는다 — 이유는 둘이다

| | 후보를 누가 만드는가 | 전사를 생성기에 넘기는가 |
|---|---|---|
| upstream | **파생** (`build_requirement_distillation`) | **넘긴다** (`_format_interview_transcript`) |
| mcx | **수동** (`mcx brief candidate`) | **끊는다** (ADR-0016·0018) |

각각 단독으로는 무해하다. 칸이 비면 전사가 받쳐주고, 전사를 끊으면 칸이
채워져 있다 — upstream은 둘 중 하나가 언제나 성립한다. **우리는 둘 다 끊었고,
그 교집합에서 생성기가 받은 것은 의도 82자뿐이었다.**

승격 0건을 검사하지 않는 것 **자체는 upstream 파리티다**
(`authoring_handlers.py:1472-1481`은 `promotion.blockers`만 본다). `required:
bool = False` 기본값도, 권한 부족 시 조용한 `OMIT`도 자간까지 같다. upstream은
그 검사가 **필요 없을 뿐**이다.

### 그리고 파생만 이식해서는 우리 문제가 풀리지 않는다 (실측)

upstream 정규식(`_EXPLICIT_REQUIREMENT_RE` — 한국어·일본어 포함)을 도그푸딩의
실제 답변 21건에 그대로 걸었다:

```
매칭 1 / 미매칭 20
```

upstream의 파생은 스스로 *"conservative"* 라고 밝히며, 요구사항임을 **스스로
선언하는** 답변만 줍는다(`must`·`반드시`·`필수`). 나머지는 evidence로만 남고
**전사가 생성기까지 실어 나른다.** 우리 답변은 특정 축에 대한 결정을 서술형으로
쓴 것이라 그 어휘를 거의 쓰지 않는다.

즉 upstream의 보수적 파생은 **전사가 함께 갈 때만 성립하는 설계**다.

## Decision

### 1. upstream 파생을 이식한다 — 빠뜨릴 명령을 없앤다

`initial_intent`와 답변에서 후보를 **자동으로 만든다**. upstream
`build_requirement_distillation`의 두 갈래를 그대로 옮긴다.

- **`initial_intent` → GOAL 후보**, `USER_STATED` / `CONFIRMED` /
  `authority=USER` / `required=True`. upstream `initial-goal`과 같은 값이다.
  **goal이 비는 경로가 사라진다.**
- **답변 → CONSTRAINT 또는 ACCEPTANCE_CRITERION 후보**, 단 upstream 정규식에
  매칭될 때만. 섹션은 `_CONSTRAINT_RE`가 가른다. 값은 위와 같다.
- **`observation` 답변은 건너뛴다.** upstream이 같은 자리에서 같은 이유로
  건너뛴다 — *"An adopted fact, not a decision."* ADR-0010의 축과 같다.

정규식은 **자간 그대로** 옮긴다. 한국어 어휘를 우리가 늘리지 않는다 — 늘리면
upstream과 대조가 끊기고, 무엇이 요구사항인지의 정의를 우리가 발명하게 된다.

값이 `CONFIRMED`/`USER`인 것이 안전한 이유는 **텍스트가 사용자가 친 원문 그대로**
이기 때문이다. 사이에 LLM이 없다. upstream이 같은 근거를 주석에 적어 두었다.

### 2. 수동 `brief candidate`는 **남긴다** — 전사를 끊은 우리에겐 파생만으로 부족하다

upstream에는 수동 입력 경로가 없다(`RequirementCandidate(` 생성이 MCP 도구
어디에도 없다). 그럼에도 남기는 근거는 §Context의 1/21 실측이다.

**등록된 divergence.** upstream에 없는 표면을 유지한다. 근거는 ADR-0016·0018로
전사를 끊었다는 것이며, **그 결정을 되돌리면 이 divergence의 근거도 사라진다.**

### 3. Gate가 승격된 성공 조건을 요구한다 — 계약을 구현이 따라간다

[Brief Guide §13.1](../05_BRIEF.md)은 이미 *"성공 조건이 Blueprint에서 검증
가능한 AC로 정제될 수 있다"* 와 *"적용 가능한 Constraints가 **기록되어 있다**"* 를
요구한다. **구현이 그 검사를 한 번도 하지 않았다.** clarity는 대화를 채점하지
칸을 보지 않는다 — 그래서 칸이 비어도 0.96이 나왔다.

새 차단 조건 `REQUIREMENTS_MISSING`을 둔다. 발동은 **승격된
`acceptance_criterion`이 하나도 없을 때**다.

**왜 AC만인가.** Blueprint는 AC 없이는 검증 불가능한 물건이므로 AC의 부재는
언제나 결함이다. constraints·non_goals는 사소한 미션에서 정당하게 빌 수 있다 —
그 둘까지 막으면 Gate가 계약보다 **두꺼워진다**. 좁힌 것을 여기 명시한다.

**upstream에 없는 검사다.** 근거는 §Context에 있다: upstream은 전사 backstop이
있어 필요가 없고, 우리는 그것을 끊었다. **등록된 divergence이며 §2와 같은
전제 위에 있다.**

### 4. `-`로 시작하는 자유 텍스트는 `--` 뒤에 둔다 — 그 사실을 help가 말한다

도그푸딩에서 `mcx brief answer "-h/--help는 …"` 이 argparse에 옵션으로 먹혀
그 라운드가 유실됐다.

> **정정.** 처음 이 결함을 *"조용히 실패했다"* 로 적었으나 **사실이 아니다.**
> argparse는 usage를 stderr에 내고 exit 2로 끝낸다 — 실패는 시끄러웠고,
> 관측자가 `tail -3`으로 가렸을 뿐이다. 실패 처리를 새로 만들 근거가 없다.

남는 실질 간극은 **우회 방법이 help에서 보이지 않는다**는 것 하나다. POSIX
`--` 구분자가 이미 동작하며(마지막에 두면 된다), 그것을 help가 말하지 않는다.

```sh
mcx brief answer --state-dir <경로> -- "-h로 시작하는 답변"
```

자유 텍스트 위치 인자의 help에 이 한 줄을 넣는다. **파싱을 고치지 않는다** —
argparse의 표준 동작을 우회하는 전처리는 우리가 옵션 목록을 두 벌로 들고 있어야
하고, 그 두 벌이 어긋나는 순간 인자가 조용히 사라진다. 지금 없는 실패 모드를
만드는 것이다.

upstream 대응물 없음 — upstream의 답변 경로는 CLI 위치 인자가 아니라 MCP
도구(JSON)다. 우리 표면(ADR-0038)만의 문제다.

## Consequences

### Positive

- **빠뜨릴 수 있는 명령이 사라진다** — goal은 `brief start`만으로 채워진다.
- Gate가 *"CLEAR인데 만들 수 없다"* 를 만들지 않는다. 증상이 Blueprint 층이
  아니라 원인이 있는 Brief 층에서 보고된다.
- 파생 어휘가 upstream과 같아 이후 대조가 성립한다.

### Cost

- **파생이 답변 하나를 통째로 후보 텍스트로 만든다.** 우리 답변은 길고 여러
  결정을 담으므로 굵은 후보가 된다 — upstream도 같다(전사가 받쳐주므로 문제가
  덜하다). 실사용 관측 항목이다.
- 수동 경로가 남아 **후보의 출처가 둘**이다 (§2). 중복 제거를 하지 않으므로
  같은 내용이 파생·수동 양쪽으로 들어올 수 있다.
- §3의 divergence는 ADR-0016·0018에 얹혀 있다. 전사 차단이 풀리면 근거가
  사라진다.

## Rejected alternatives

- **전사를 생성기에 다시 넘긴다 (완전 upstream)** — ADR-0016·0018이 막은 것
  (*합의되지 않은 것을 생성기가 되살린다*)을 되돌린다. 사용자 지시는 "가장
  안전한 방법"이었고, 보호를 푸는 쪽은 그 반대다.
- **파생만 이식하고 수동 경로 제거 (완전 upstream)** — 1/21 실측이 이것을
  기각한다 (§Context). 빈 handoff가 더 은밀한 형태로 재발한다.
- **Gate 검사만 추가하고 파생은 두지 않는다** — 증상 처방이다. 사용자는
  여전히 명령을 빠뜨릴 수 있고, Gate가 막을 뿐 원인은 남는다.
- **한국어 요구사항 어휘를 우리가 확장** — 무엇이 요구사항인지의 정의를 우리가
  발명하는 것이며 upstream 대조가 끊긴다.
- **constraints·non_goals 부재까지 Gate가 막는다** — 사소한 미션에서 정당하게
  비므로 Gate가 계약보다 두꺼워진다 (§3).

## Verification

- `brief start`만 한 상태에서 승격된 GOAL이 하나 있다.
- `반드시`·`필수`·`must`가 든 결정 답변이 후보가 되고, 그렇지 않은 답변은
  되지 않는다. `observation` 답변은 어휘와 무관하게 후보가 되지 않는다.
- 파생 후보의 텍스트가 사용자 원문과 **같다** (요약·변형이 없다).
- 승격된 acceptance_criterion이 없으면 Gate가 `HOLD`이고 사유가 그것을 말한다.
- 승격된 constraint·non_goal이 없는 것만으로는 막지 않는다.
- `brief answer "-h ..."` 처럼 `-`로 시작하는 본문이 옵션으로 해석되지 않는다.

## 미결로 남기는 것

- **파생 후보의 굵기** (§Cost). 답변 하나가 여러 결정을 담으면 후보 하나가
  그것을 통째로 갖는다. 쪼개는 것은 LLM을 사이에 넣는 일이라 upstream이 피한
  자리다. 실사용 관측이 있어야 판단한다. **시한 Phase 10 종료 검토.**
- **파생·수동 중복** (§Cost). 실제로 겹치는 것이 관측되면 그때 본다.
  **시한 Phase 10 종료 검토.**
