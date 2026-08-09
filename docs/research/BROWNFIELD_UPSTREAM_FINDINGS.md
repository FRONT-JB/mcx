# Brownfield upstream 조사 — 한 기능이 아니라 세 역할

> Baseline: `Q00/ouroboros` @ `9486c78` (v0.50.8), observe-only.
> Scope: Phase 9 진입 전 조사. 결정은 [ADR-0044](../adr/0044-brownfield-entry-contract.md)가 소유한다.

Evidence level: **Verified (소스)** — 별도 표시가 없으면 pinned baseline 직독이다.

`brownfield`는 upstream에서 단일 기능이 아니다. **서로 독립적인 세 역할**이
같은 이름을 쓴다. 우리 [ADR-0011](../adr/0011-brief-deliberate-divergences.md)
§6은 그중 ①만 기록하고 있었다.

## 1. 모호함 채점의 네 번째 축

`bigbang/ambiguity.py`. greenfield는 3차원, brownfield는 4차원이다.

| 축 | greenfield weight | brownfield weight | floor |
|---|---|---|---|
| goal | 0.40 | 0.35 | 0.75 |
| constraint | 0.30 | 0.25 | 0.65 |
| success_criteria | 0.30 | 0.25 | 0.70 |
| **context** | — | **0.15** | **0.60** |

rubric 원문:

> *"Context Clarity: Is the existing codebase context clear? Are referenced
> codebases, patterns, and conventions well understood?"*

**판정은 자동이다.** `detect_brownfield(cwd)`(`bigbang/explore.py:525`)가
**유효한 git 메타데이터 또는 인식되는 config 파일 하나**라도 있으면 참이다.
참이면 `state.is_brownfield = True`와 함께
`codebase_paths = [{"path": cwd, "role": "primary"}]`가 세팅된다
(`mcp/tools/pm_handler.py:538-542`).

`role`은 두 값이다 — **`primary`(수정 대상)** 와 **`reference`(읽기 전용)**
(`explore.py:120`).

### 1.1 축을 켜면 채울 것도 있어야 한다 — explore 단계

`bigbang/explore.py` 모듈 docstring이 순서를 그대로 말한다:

> 1. config 파일 스캔 (go.mod, package.json, .csproj …)
> 2. tech stack·의존성 식별
> 3. 핵심 타입 정의 발견 (struct, class, interface, enum, const)
> 4. **LLM으로 프로토콜·패턴 요약**
> 5. *"Returns condensed context for injection into interview system prompt"*

즉 4번째 축은 **혼자 켜지지 않는다.** 코드베이스 컨텍스트를 인터뷰 프롬프트에
주입하는 단계가 먼저 있고, `context_clarity`는 그 주입이 충분했는지를 채점한다.

## 2. 저장소 레지스트리

`bigbang/brownfield.py` + `persistence/brownfield.py`. **SQLite DB에 전역
레지스트리**를 둔다.

- 스캔 루트를 **2단계 깊이까지** 훑어 git repo/worktree를 찾는다
- README/CLAUDE.md를 읽어 한 줄 설명을 **Frugal 모델로 생성**한다
  (`generate_desc`)
- 사용자가 그중 **기본 repo**를 고른다 (`ooo brownfield set 6,18,19`)
- `get_default_brownfield_context`가 그 기본값을 인터뷰 컨텍스트로 넘긴다

skill(`skills/brownfield/SKILL.md`)이 스캔 결과를 2열 그리드로 보여 주고 번호로
고르게 한다.

**목적은 "여러 저장소를 오가는 사용자"다.** 홈 디렉토리를 훑어 후보를 모으고
기본값을 기억하는 UX이며, 저장소가 인터뷰마다 달라지는 상황을 전제한다.

## 3. mechanical 명령 자동 검출 — **Verify가 도는 유일한 길**

`evaluation/detector.py`. 모듈 docstring이 계약 전체를 담는다:

> *"one LLM call that proposes lint/build/test/static/coverage commands,
> persisted to `.ouroboros/mechanical.toml` and consumed by
> `build_mechanical_config`."*
>
> *"The contract is deliberately minimal: **every AI proposal is validated
> against an actual entry point on disk** (package.json script, Makefile
> target, binary on PATH) before it is written. **Anything that cannot be
> verified is dropped to `skip`** — Stage 1 must never produce a phantom
> failure."*

| 항목 | 값 |
|---|---|
| 산출물 | `.ouroboros/mechanical.toml` |
| 명령 종류 | `lint` · `build` · `test` · `static` · `coverage` (`DetectedCommands`) |
| 호출 수 | **1회** (`ensure_mechanical_toml`) |
| 검증 | package.json script / Makefile target / PATH 바이너리 실재 확인 |
| 검증 실패 | 그 항목을 **버린다**(`skip`) — 추측을 남기지 않는다 |
| manifest 없음 | 아예 수행하지 않는다 (`detector.skipped reason=no_manifests`) |
| 실패 | 예외를 올리지 않고 `False` — 검출 실패가 미션을 죽이지 않는다 |
| 재실행 | idempotent, `force=True`로 재검출 |

### 3.1 반복되는 패턴 — AI가 제안하고 계산이 거른다

| | LLM이 하는 일 | 결정적 층이 하는 일 |
|---|---|---|
| `GradeGate` ([SEED findings §11](./SEED_UPSTREAM_FINDINGS.md)) | 품질 채점 | 계산으로 등급을 매겨 실행 차단 |
| mechanical detect | 명령 제안 | **디스크에 실재하는지 대조**, 없으면 버림 |

두 곳 모두 **모델의 출력을 그대로 신뢰하지 않는다.** 우리
[ADR-0043](../adr/0043-deterministic-blueprint-quality-floor.md) Rejected
alternatives의 *"계산으로 답이 나오는 것을 모델에게 묻지 않는다"* 와 같은 축이며,
여기서는 **모델에게 묻되 답을 계산으로 검산한다**는 한 단계 더 나아간 형태다.

## 4. 우리 쪽 대조

| upstream 역할 | Mission Control 현재 |
|---|---|
| ① 4번째 축 | **자리만 예약** — `ClarityDimension`에 `"context"`가 있고 주석이 *"brownfield 전용이며 v1 첫 구현에서는 자리만"* 이라 적혀 있다 (`domain/brief/clarity.py:40-42`). weight·floor는 greenfield 3축뿐 |
| ① explore 단계 | **없다.** 그리고 이 공백은 이미 알려진 한계로 등록돼 있다 — *"`context`를 채우는 장치가 없다… Fact Resolver가 미구현이다 (B-004)"* ([progress](../progress/README.md)). Fact Resolver는 2026-08-09 폐기했고 그 일은 skill의 `inspect_code`로 넘어갔다 |
| ② 레지스트리 | **없다.** mission마다 `--workspace` 하나이고 mission record가 나른다 |
| ② role(primary/reference) | **없다.** `CapabilityEnvelope`가 workspace 하나와 도구 목록만 갖는다 |
| ③ mechanical 검출 | **없다.** `verify_command`는 Blueprint 생성기가 쓰거나 사람이 적는다 |

### 4.1 축이 다르다 — 그대로 옮길 수 없는 것

upstream의 `mechanical.toml`은 **프로젝트 수준**이다 (`test = "pytest"`).
우리 `verify_command`는 **AC 수준**이다 (`"댓글이 목록에 보인다"` →
`pytest tests/test_comments.py`).

따라서 `mechanical.toml`을 그대로 들여올 수 없다. 검출 결과가 우리 쪽에서
쓰이는 자리는 **Blueprint 생성기의 입력**이다 — 생성기가 AC마다 확인 명령을
쓰려면 *"이 프로젝트는 pytest를 쓴다"* 는 사실이 필요하고, 그 공백이 위 표의
`context`를 채우는 장치 부재다.

## 5. 조사가 드러낸 순서 제약

세 역할은 독립적이지만 **①은 혼자 켜면 미션을 막는다.**

`context_clarity`에 weight 0.15와 floor 0.60이 붙는데, 코드베이스 컨텍스트를
주입하는 단계가 없으면 그 축은 항상 낮게 나온다. floor 미달은 Brief Gate를
막으므로 **brownfield 미션이 영원히 CLEAR에 도달하지 못한다.**

즉 도입 순서는 `explore(또는 그 대응물) → ① 4번째 축`이며, ③은 그와 별개로
Verify가 돌기 위한 선행이다.
