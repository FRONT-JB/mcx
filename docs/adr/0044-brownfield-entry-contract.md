# ADR 0044 — Brownfield 진입 계약: 세 역할의 분리 도입

- Status: **Accepted** (사용자 승인 2026-08-09 — ② 미도입 · ③ 도입 · ① 보류)
- Date: 2026-08-09
- Constitutional basis: [ADR-0011](./0011-brief-deliberate-divergences.md) §6
  (brownfield 유예), [ADR-0042](./0042-skill-and-core-ownership-boundary.md) §1
  (소유 판별 규칙), [ADR-0005](./0005-evidence-over-reasoning.md)
- Upstream evidence: [BROWNFIELD_UPSTREAM_FINDINGS](../research/BROWNFIELD_UPSTREAM_FINDINGS.md)
- 해소 대상: Phase 9의 *"brownfield 탐색·기존 제약 등록 (ADR-0011 유예 해제)"*

## Context

조사에서 전제가 갈라졌다 — `brownfield`는 upstream에서 **한 기능이 아니라 세
역할**이고, [ADR-0011](./0011-brief-deliberate-divergences.md) §6은 그중 하나만
기록하고 있었다.

1. 모호함 채점의 **네 번째 축**(`context_clarity`, weight 0.15, floor 0.60)
2. **저장소 레지스트리** (홈 스캔 + 기본 repo 선택, SQLite)
3. **mechanical 명령 자동 검출** (`.ouroboros/mechanical.toml`)

셋을 한 덩어리로 "brownfield 도입"이라 부르면 필요 없는 것까지 들어오고, 필요한
것의 순서를 놓친다. 이 ADR은 셋을 **따로 판단한다.**

## Decision

### 1. 순서 제약을 먼저 고정한다 — ①은 혼자 켜면 미션을 막는다

`context_clarity`에 floor 0.60이 붙는데 코드베이스 컨텍스트를 주입하는 단계가
없으면 그 축은 항상 낮게 나온다. floor 미달은 Brief Gate를 막으므로
**brownfield 미션이 영원히 `CLEAR`에 도달하지 못한다.**

따라서 도입 순서는 다음 하나뿐이다:

```
컨텍스트를 채우는 장치  →  ① 네 번째 축
③ mechanical 검출은 그와 독립 — Verify가 돌기 위한 선행이다
```

이 제약을 결정으로 못박는 이유는, 자리가 이미 예약돼 있어서
(`ClarityDimension`에 `"context"`가 있다) **weight 한 줄만 추가하면 켜지는
것처럼 보이기 때문**이다.

### 2. ② 저장소 레지스트리는 **도입하지 않는다**

upstream의 레지스트리는 *"여러 저장소를 오가는 사용자"* 를 위한 것이다 — 홈
디렉토리를 2단계까지 훑어 후보를 모으고, LLM으로 한 줄 설명을 만들고, 사용자가
기본값을 골라 DB에 기억시킨다.

**우리 CLI는 그 상황이 아니다.** mission마다 `--workspace` 하나를 인자로 받고
그것이 mission record에 실린다 (ADR-0038 §2 — 비대화형 단발). 전역 레지스트리는
새 저장소(SQLite)와 새 대화형 선택 표면을 요구하며, 둘 다 우리가 명시적으로
기각한 축이다 (ADR-0013 파일 문서, ADR-0038 비대화형).

**등록된 divergence**: upstream에 있는 것을 도입하지 않는다. 발동 조건은
"한 미션이 두 개 이상의 저장소를 참조해야 하는 실수요"다.

다만 **`role`(primary/reference)은 따로 본다** — 이것은 레지스트리가 아니라
capability 축이다. *"이건 고칠 것, 저건 읽기만"* 은 `CapabilityEnvelope`가
표현할 수 있어야 할 구분이며, 지금은 workspace 하나뿐이라 표현 수단이 없다.
**미결로 등록한다** (§5).

### 3. ③ mechanical 검출은 **도입한다** — 축을 바꿔서

brownfield에서 Verify가 도는 유일한 길이다. 그리고 오늘 도입한
[ADR-0043](./0043-deterministic-blueprint-quality-floor.md)
`NO_VERIFIABLE_CRITERION`이 **brownfield에서 곧바로 벽이 된다** — 기존 저장소의
확인 수단을 모르면 AC에 확인 수단을 쓸 수 없고, 쓸 수 없으면 Gate가 막는다.

**upstream 계약에서 그대로 받는 것:**

- 제안은 **AI 호출 1회**
- 제안된 모든 명령을 **디스크에 실재하는 진입점과 대조**한다 (package.json
  script, Makefile target, PATH 바이너리)
- 대조에 실패한 항목은 **버린다.** 추측을 남기지 않는다 —
  *"must never produce a phantom failure"*
- manifest가 하나도 없으면 **수행하지 않는다**
- 검출 실패는 **예외가 아니다.** 미션을 죽이지 않는다

**축을 바꾸는 것:**

upstream의 `mechanical.toml`은 **프로젝트 수준**(`test = "pytest"`)이고 우리
`verify_command`는 **AC 수준**(`pytest tests/test_comments.py`)이다. 파일을 그대로
들여오지 않는다.

검출 결과가 우리 쪽에서 쓰이는 자리는 **Blueprint 생성기의 입력**이다. 생성기가
AC마다 확인 명령을 쓰려면 *"이 프로젝트는 pytest를 쓴다"* 는 사실이 필요하고,
그 공백은 이미 알려진 한계로 등록돼 있다 (*"`context`를 채우는 장치가 없다"*,
B-004).

**소유는 Core다.** [ADR-0042](./0042-skill-and-core-ownership-boundary.md) §1의
판별 질문이 갈린다 — 제안은 AI라 매번 다르지만(→skill 축), **검증은 결정적**
이다(→Core). 이미 우리에게 같은 형태가 있다: 위임 port 7종은 vendor에게 묻고
결과를 도메인 타입으로 강제한다 (ADR-0034). 여덟 번째 port를 추가하는 것이지
새 층이 아니다.

```
MechanicalCommandDetector (port)
  ├─ 제안: CompletionEngine 1회 호출 (텍스트 lane)
  └─ 검증: 디스크 대조 — 결정적, Core 소유
```

### 4. ① 네 번째 축은 **③ 뒤에 켠다**

값은 upstream을 그대로 쓴다 (weight 0.35/0.25/0.25/**0.15**, floor **0.60**).
`is_brownfield` 판정도 upstream 규칙을 쓴다 — **유효한 git 메타데이터 또는
인식되는 config 파일 하나 이상**. 결정적이고 값이 싸며, 사용자에게 묻지 않는다.

**그러나 §1의 순서 제약이 걸린다.** ③이 채워 주는 것은 *확인 명령*이고
`context_clarity`가 묻는 것은 *"코드베이스 컨텍스트가 명확한가"* 로 더 넓다.
③만으로 이 축을 충분히 채우는지는 **모른다.**

따라서 이 ADR은 ①을 **켜지 않는다.** ③을 도입하고 실사용에서
`context_clarity`가 어떤 점수를 받는지 관측한 뒤 결정한다. 관측 없이 켜면
brownfield 미션이 Gate에서 멈추고, 그때 floor를 낮추는 것은 근거 없는 수치
조정이 된다.

**Phase 9는 관측 Phase다** ([progress 0008](../progress/0008_PLUGIN_COMPOSITION_LAYER.md) §3) —
이 항목이 그 성격의 전형이다.

## Consequences

### Positive

- 세 역할이 분리돼, 필요 없는 것(레지스트리)이 필요한 것(검출)에 묻어 들어오지
  않는다.
- `NO_VERIFIABLE_CRITERION`이 brownfield에서 벽이 되는 경로가 미리 열린다.
- *"모델에게 묻되 답을 계산으로 검산한다"* 가 두 번째 사례를 얻어 패턴이 된다
  (첫 사례는 위임 port의 구조화 출력 강제).

### Cost

- brownfield 미션의 모호함 채점은 당분간 greenfield 3축 그대로다 — 코드베이스
  컨텍스트의 불명확함이 ambiguity에 반영되지 않는다. **알려진 한계로 남긴다.**
- 저장소를 여러 개 참조하는 미션은 표현할 수 없다 (§2).
- 검출은 AI 호출 1회를 쓴다 — 비용·속도 축에서 upstream 동등이다(upstream도 1회).

## Rejected alternatives

- **셋을 한 번에 도입** — 레지스트리는 우리 CLI 형태에 필요가 없고, ①은 순서
  제약을 어긴다.
- **`mechanical.toml`을 그대로 들여오기** — 프로젝트 수준 축이라 AC 수준
  `verify_command`와 맞지 않는다 (§3).
- **①만 먼저 켜기 (weight 한 줄)** — 자리가 예약돼 있어 값싸 보이지만
  brownfield 미션을 Gate에서 막는다 (§1).
- **검출을 skill에 두기** — 제안은 AI지만 검증이 결정적이고, 그 검증이 이
  기능의 전부다. skill에 두면 *"디스크에 없는 명령을 쓰지 마라"* 가 산문 강제가
  된다.

## Verification

- 검출된 명령 중 디스크에 진입점이 없는 것은 **결과에 남지 않는다**.
- manifest가 없는 workspace에서는 검출을 시도하지 않는다.
- 검출 실패가 Brief·Blueprint 진행을 막지 않는다.
- AI 호출은 workspace당 1회다 (재실행은 명시적 요청일 때만).
- `is_brownfield` 판정이 git 메타데이터·config 파일만으로 결정된다 (사용자에게
  묻지 않는다).

## 미결로 남기는 것

- **`role`(primary/reference)의 표현** — upstream은 코드베이스 경로마다 수정
  대상/읽기 전용을 구분한다. 우리 `CapabilityEnvelope`에는 자리가 없다.
  실행 권한 축이므로 [ADR-0033](./0033-first-runtime-adapter-contract.md)의
  sandbox 경계와 함께 봐야 한다. **시한 Phase 9 종료 검토.**
- **① 네 번째 축의 도입 여부** — ③ 도입 후 실사용 관측에 달렸다 (§4).
- **검출 결과의 보존 위치** — upstream은 `.ouroboros/mechanical.toml`을
  workspace에 쓴다. 우리는 workspace를 오염시키지 않는 편(state-dir)이 맞아
  보이지만, 그러면 사용자가 손으로 고칠 수 없다. **구현 시 결정.**
