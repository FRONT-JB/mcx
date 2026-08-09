# ADR 0042 — skill 계층과 Core의 소유 경계

- Status: **Proposed** (§6·§7 두 항목은 사용자 결정 대기)
- Date: 2026-08-09
- Constitutional basis: [ADR-0004](./0004-stage-scoped-minimum-capability.md)
  (Stage별 최소 capability), [ADR-0007](./0007-mcp-is-control-surface.md)
  (MCP는 제어 표면), [ADR-0038](./0038-mcx-cli-surface-contract.md) §1
  (CLI/MCP 공유 경계)
- Upstream evidence: [SKILLS_UPSTREAM_FINDINGS](../research/SKILLS_UPSTREAM_FINDINGS.md),
  [CLI_UPSTREAM_FINDINGS](../research/CLI_UPSTREAM_FINDINGS.md)
- 해소 대상: [Open Questions §8](../research/OPEN_QUESTIONS.md)의 Phase 8 선행
  ("무엇이 skill 소유이고 무엇이 Core 소유인가")와 그 아래 등록된 4건

## Context

Phase 8은 manifest 작업이 아니라 **합성 계층 도입**이다. 지금은 사람이 24개
명령의 순서를 알아야 하고, 도그푸딩 0003은 그 순서를 아는 사람이 60콜을 손으로
이어 붙인 실행이었다.

선을 긋기 전에 upstream이 어디에 그었는지를 조사했다
([SKILLS findings](../research/SKILLS_UPSTREAM_FINDINGS.md)). 한 문장으로:

> **Core는 "한 번의 판정"을 주고, skill은 "그 판정을 몇 번, 어떤 순서로 부르고,
> 사용자에게 무엇을 묻는가"를 소유한다.**

같은 조사에서 **우리가 "upstream보다 강하다"고 적어 둔 주장들을 재검토**했다.
결과는 §8에 있다 — 셋은 성립하고, 둘은 정당화가 만료 중이며, 하나는 과장이었다.

## Decision

### 1. 경계 원칙 — "한 번의 판정"과 "몇 번 부를 것인가"

**Core가 소유하는 것**: 입력이 주어졌을 때 **한 번** 계산되는 것.
판정(Gate), 채점, 생성 1회, 지속 상태, revision, 전이 규칙, 증거.

**skill이 소유하는 것**: 그 한 번을 **언제·몇 번·어떤 순서로** 부를지, 그리고
그 결과를 사람에게 **어떻게 물을지**.

경계선의 실제 판별 질문은 하나다 — **"같은 입력에 항상 같은 답인가?"** 그렇다면
Core, 아니라면(사용자·맥락·반복 횟수에 따라 달라진다면) skill이다.

### 2. Core는 반복을 소유하지 않는다 — 단, 지금 있는 루프는 옮기지 않는다

upstream은 QA 반복(threshold 0.90·최대 5회·최선 시도 추적)을 **skill 텍스트**에
둔다. 우리는 Core에 뒀다 ([ADR-0019](./0019-blueprint-qa-loop.md) §1, 등록된
divergence).

**이 divergence를 유지한다. 옮기지 않는다.** 근거는 셋이다.

1. 되돌리기 비싼 축이다 — QA 루프는 `BlueprintState`의 durable 상태
   (`qa_iterations`, best attempt)와 얽혀 있고
   ([ADR-0021](./0021-blueprint-state-and-revisions.md) §4), 옮기면 상태
   모델이 바뀐다.
2. 우리 CLI는 비대화형 단발이다 ([ADR-0038](./0038-mcx-cli-surface-contract.md)
   §2). skill이 없는 경로에서도 QA가 돌아야 하며, upstream의 `ooo seed`가
   QA 없이 도는 것과 달리 우리는 그 공백을 수용하지 않기로 이미 결정했다.
3. 실물 근거가 있다 — 도그푸딩 0002에서 QA가 0.72→0.87→0.90으로 실 AI 첫
   PASS에 도달했다.

**대신 대가를 여기 명시한다.** skill은 반복 정책을 바꿀 수 없다. upstream의
Wonder→Reflect→Refine→Restate처럼 **후보를 여러 원천에서 모아 사용자에게 고르게
하는 국면**을 skill이 넣으려면, Core의 루프 안이 아니라 **`qa`와 `revise` 사이**
에서 해야 한다. Core는 `revise`에 들어온 것을 받을 뿐 그것이 어떻게 만들어졌는지
묻지 않는다 — 그 자리가 skill의 자리다.

### 3. 사용자에게 묻는 것은 전부 skill이다 — Core는 **묻지 않고 드러낸다**

Core는 `HOLD`와 `blocking_reasons`(closure 차단 질문 포함)를 **데이터로**
내놓는다. 사람에게 묻는 행위는 Core에 없다. MCP 서버도 사람에게 직접 묻지
않는다 ([04_MCP](../04_MCP.md) §1-4 — 서버가 물으면 그 답이 어느 mission의
것인지 서버가 기억해야 한다).

**질문의 형태는 skill이 규정한다.** upstream 정렬로 다음을 skill 계약에 넣는다
(SKILLS findings §4):

- 단일 선택 질문만. 상호 배타 항목을 다중 선택으로 묻지 않는다.
- 충돌 그룹을 먼저 묻고, 그 안에 "그대로 두기"를 항상 포함한다.
- 배치 질문마다 skip 옵션이 있고, **skip은 "임계 미달 수락"이 아니다** —
  임계 미달 수락은 루프 경계에서 별도로 명시적으로 고른다.
- **기본 채택이 없다** (upstream *"No candidate is accepted by default"*).

### 4. 승인 actor는 Core에 넣지 않는다 — skill이 **결정 흔적**을 남긴다

upstream도 Core store에 actor를 넣지 않고, skill이
`~/.ouroboros/seed-revisions/<key>.md`에 후보·원천 태그·accept/reject·diff를
남긴다 (SKILLS findings §5). 우리도 같은 축을 쓴다.

Core는 지금대로 `BlueprintApproval`(statement + QA 근거,
[ADR-0019](./0019-blueprint-qa-loop.md) §8)까지만 들고, "누가 눌렀는가"는
기록하지 않는다. **대신 skill이 사용자 확인을 보증하고 그 흔적을 남긴다** —
이것이 [Open Questions §3](../research/OPEN_QUESTIONS.md) approval actor 잔여의
처분이다.

**Core에 actor 필드를 넣지 않는 이유**: 넣어도 `actor="user"`를 host 에이전트가
쓸 수 있어 방어가 되지 않는다. 값을 채우는 주체와 검증하는 주체가 같으면 필드는
장식이다. 방어는 필드가 아니라 **흔적의 감사 가능성**이다.

### 5. skill은 Core의 판정을 재감사할 수 있다 — 그러나 뒤집을 수는 없다

upstream의 명문 규칙: *"Treat MCP `seed-ready` as permission to audit closure,
not as completion."* (SKILLS findings §6)

우리는 closure 감사를 Core에 뒀으므로([ADR-0020](./0020-brief-closure-audit.md))
방어가 upstream보다 한 겹 적다. skill이 추가 감사를 하는 것을 **허용**하되,
`CLEAR`/`HOLD` 판정 자체는 Core만 낸다. skill의 감사는 "더 물어볼 것"을 만들
뿐 Gate를 뒤집지 않는다.

### 6. worker 재귀 차단 — **결정 대기**

로드맵이 Phase 7에 배치한 `recursion/security tests`가 미이행이고, 방어가
lane마다 다르다 ([progress 0007](../progress/0007_MCP_CONTROL_SURFACE.md) §2.2):
텍스트 lane(Claude)은 `--strict-mcp-config --setting-sources ""`로 끊지만
실행 lane(`codex exec`)은 사용자 codex 설정을 그대로 상속한다.

**이 Phase가 `mcx-mcp`를 host 설정에 등록해 경로를 실제로 연다.** upstream도
Codex를 host로 두고 등록한다(`.codex-plugin/plugin.json` + `.mcp.codex.json`).

**upstream이 이 노출을 막는지는 확인하지 못했다** (SKILLS findings §9). 명시된
격리는 `--profile` 하나이며, 그것이 MCP 서버 목록까지 갈아끼우는지는 미확인이다.
따라서 *"upstream을 따라하면 된다"* 는 출구가 없다.

선택지 둘 — **사용자 결정이 필요하다**:

| | 방법 | 대가 |
|---|---|---|
| A | `codex exec --ignore-user-config` | worker가 사용자 모델·프로필 설정을 잃는다. 도그푸딩 구성이 바뀐다 |
| B | codex profile 축 도입 (upstream 정렬) | 설정 표면이 하나 늘고, profile이 MCP 목록을 갈아끼우는지 먼저 확인해야 한다 |

어느 쪽이든 [ADR-0033](./0033-first-runtime-adapter-contract.md) adapter 계약
변경이다. 결정 전까지 Phase 8의 **Codex host 등록은 보류**한다 — Claude Code
host 등록만으로 시작하면 노출이 열리지 않는다(우리 텍스트 lane은 이미 격리되어
있고, 실행 lane의 codex는 등록 대상이 아니다).

### 7. Fact Resolver — **정당화가 만료됐다. 폐기를 제안한다**

[ADR-0011](./0011-brief-deliberate-divergences.md) §3은 별도 Read-only Fact
Resolver 역할을 두면서 근거를 이렇게 적었다: *"v1 첫 구현은 CLI를 대상으로
하므로 코드 사실을 가져오는 host 세션이 존재하지 않는다."*

**Phase 8이 그 host를 만든다.** upstream 방식(host가 코드를 읽고 `[from-code]`
표기로 답변 제출)이 그때부터 사용 가능해지고, 별도 역할은 upstream에 없는
구조의 잔존이 된다. 아직 **미구현**이므로(B-004) 매몰 비용이 없다.

**제안: Fact Resolver 역할을 폐기하고 upstream 방식으로 돌린다** — skill이
`inspect_code`로 사실을 조사해 `authority=observation` 답변으로 제출한다.
provenance 의미론([ADR-0010](./0010-answer-provenance-and-requirement-authority.md))은
그대로 유지되므로 충실해야 할 대상은 보존된다. **사용자 결정 대기.**

## 8. "우리가 더 강하다"의 재검토

사용자 지적으로 전수 재대조했다. 강함 주장이 실은 **의도를 벗어난 재구성**일 수
있기 때문이다.

| 주장 | 판정 |
|---|---|
| approval을 1급 상태로 (ADR-0011 §2) | **성립.** upstream도 skill 계층에서 명시적 승인을 Non-Skippable Gate로 강제한다 (SKILLS findings §6) — 발명이 아니라 **층 이동**이다 |
| `executed-unverified` 1급 상태 (ADR-0023) | **성립.** upstream docstring이 같은 의도를 말한다(*"prevents final renderers from implying completion"*) — 우리는 그것을 구조로 만들었을 뿐이다 |
| handoff를 명시적 타입으로 (ADR-0016) | **성립하되 주의.** upstream도 경계에서 derive하며 이름만 안 붙인다 — 동작 발명이 아니라 타입 명명이다. 다만 **투영이 좁으면 다음 Stage를 굶긴다**: 도그푸딩 0001에서 실제로 발생해 ADR-0035 §1로 고쳤다 |
| CLI/MCP 동일 Gate (ADR-0011 §1) | **성립하되 파생.** upstream CLI에 gate가 없는 이유는 **사람이 대화 루프 안에 있어서**다. 우리 CLI가 비대화형이라 그 사람이 없고, 그래서 gate가 필요하다 — 정당화가 우리 divergence(ADR-0038 §2)에 의존하는 사슬이다 |
| Verify 진입이 실행 lineage 요구 (ADR-0026) | **성립하되 대가가 도래 중.** 근거가 upstream 실물 사고(§12.3)라 견고하다. 그러나 **Phase 9 brownfield는 본래 루프 밖 코드**이고, ADR-0026은 §8 결정이 *"기록 요구를 유지한 채"* 내려져야 한다는 제약을 걸어 뒀다. 두 요구가 Phase 8·9에서 충돌한다 — §9에 미결로 등록 |
| QA 루프를 Core에 (ADR-0019) | **성립하되 층이 다르다.** 수치는 upstream 채택이고 루프 위치만 다르다. 대가는 §2에 명시했다 — skill이 반복 정책을 소유하지 못한다 |
| Fact Resolver (ADR-0011 §3) | **정당화 만료** → §7 |
| `revise`가 범위 재검사를 지나 "강제가 더 세다" | **과장이었다. 정정했다** ([SKILLS findings §3](../research/SKILLS_UPSTREAM_FINDINGS.md) 2026-08-09 주석). upstream의 편집이 무검사인 게 아니라 **검사 지점이 다음 QA 라운드**다. 우리 verbatim 잠금은 더 센 대신 **upstream에 있는 경로를 닫았다** — QA가 제약을 지적해도 실행할 수 없다 (도그푸딩 0001 §3.4, ADR-0035 보상 조치) |

**패턴 하나가 드러난다.** 우리가 "더 강하다"고 적은 것 대부분은 실제로는
**같은 의도를 다른 층에 놓은 것**이다. 문제는 강함 자체가 아니라, 층을 옮긴
사실이 "강화"라는 말에 가려 divergence로 읽히지 않는 것이다. 앞으로 층 이동은
**강함이 아니라 층 이동으로** 기록한다.

## Consequences

### Positive

- skill을 쓰기 전에 "이건 어디 소유인가"의 판별 질문이 하나 생긴다(§1).
- 승인 방어가 필드가 아니라 흔적으로 정의되어, 채우는 주체와 검증 주체가 같아
  지는 함정을 피한다(§4).
- 층 이동을 강화로 위장해 온 기록 관행이 교정된다(§8).

### Cost

- skill이 QA 반복 정책을 바꿀 수 없다(§2). upstream의 다국면 후보 게이트를
  넣으려면 `qa`와 `revise` **사이**에서만 가능하다.
- Codex host 등록이 §6 결정까지 보류된다 — Phase 8 산출물이 Claude Code
  한쪽으로 시작한다.
- skill 계약(질문 형태·capability 목록)이 문서로만 강제된다. 산문 계약이므로
  "강제되지 않는 것" 표에 오른다.

## Rejected alternatives

- **QA 루프를 skill로 옮겨 upstream과 층까지 맞춘다** — durable 상태와 얽혀
  있어 되돌리기 비싼 변경이고, 비대화형 CLI 경로에서 QA가 사라진다.
- **Core에 승인 actor 필드를 추가한다** — 값을 채우는 주체가 host 자신이라
  방어가 되지 않는다(§4).
- **skill이 Gate를 뒤집을 수 있게 한다** — 판정 진실이 둘이 된다. ADR-0037이
  "저장된 Stage vs Gate 재계산"에서 겪은 문제와 같은 형태다.
- **재귀 차단을 Phase 8 구현 중에 정한다** — 실행 모델 축이라 구현 편의로
  확정하지 않는다 (AGENTS.md "되돌리기 비싼 결정").

## Verification

- skill 문서가 요구하는 capability 목록이 실제 host 능력과 대조된다.
- `HOLD` 응답에 차단 질문이 **원문 그대로** 실린다 (재작성 금지).
- Core에 사람에게 묻는 코드 경로가 없다 — MCP 서버가 elicitation을 쓰지 않는다.
- skill 감사 결과가 Gate 판정을 바꾸지 않는다.
- Codex host 등록물이 §6 결정 전까지 산출물에 없다.

## 미결로 남기는 것

- **§6 재귀 차단의 레버 선택** — 사용자 결정.
- **§7 Fact Resolver 폐기** — 사용자 결정.
- **Verify lineage 요구와 brownfield의 충돌** (§8) — ADR-0026이 건
  *"기록 요구를 유지한 채"* 제약과 Phase 9 brownfield가 양립하는지. 시한
  **Phase 9 진입 전**, [Open Questions §8](../research/OPEN_QUESTIONS.md)에 등록.
- **동시 쓰기 충돌 재확인의 형태** — upstream 대응물이 없다(SKILLS findings §8).
  ADR-0014 §15가 Phase 8 시한이므로 skill 질문 형태(§3)를 그대로 쓴다는 것까지가
  현재 계획이며, 실제 문안은 미정.
