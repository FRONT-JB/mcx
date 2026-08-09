# Skills 계층 upstream 조사 — 합성 규칙은 어디에 사는가

> Baseline: `Q00/ouroboros` @ `9486c78` (v0.50.8), observe-only.
> Scope: [Open Questions §8](./OPEN_QUESTIONS.md)의 Phase 8 선행 조사 —
> *"무엇이 skill 소유이고 무엇이 Core 소유인가"*.
> 이 문서는 사실만 기록한다. 우리 결정은 경계 ADR이 소유한다.

Evidence level: **Verified (소스)** — 별도 표시가 없으면 pinned baseline의 파일을
직접 읽은 것이다. `미확인`은 대조하지 못했다는 뜻이며 "차이 없음"이 아니다.

## 1. 배포 실물 — plugin은 3층이고 **host가 둘이다**

| host | manifest | MCP 등록 |
|---|---|---|
| Claude Code | `.claude-plugin/plugin.json` | `.mcp.json` → `ouroboros mcp serve` |
| Codex | `.codex-plugin/plugin.json` | `.mcp.codex.json` → `ouroboros mcp serve --runtime codex --llm-backend codex` |

둘 다 `"skills": "./skills/"`를 가리킨다 — **skill 본문은 host별로 갈라지지
않는다.** 갈라지는 것은 MCP 서버를 어떤 runtime/backend로 띄우는가뿐이다.

skill은 22개다: `interview` `seed` `run` `evaluate` `evolve` `auto` `ralph`
`qa` `status` `cancel` `unstuck` `brownfield` `pm` `publish` `setup` `config`
`update` `resume-session` `tutorial` `welcome` `help` `ooo`.

우리 대조: 우리 CLI 24 명령은 이 목록의 `interview`~`status`에 해당하는 층이
아니라 **그 아래**다. skill 하나가 우리 명령 여러 개를 순서대로 부르는 관계다.

## 2. skill은 runtime에게 **capability 계약**을 선언한다

각 SKILL.md 머리에 `## Required Skill Capabilities` 블록이 있다. skill이
동작하려면 host runtime이 무엇을 제공해야 하는가의 목록이다.

`interview`의 10개:

```
ask_user · inspect_code · call_mcp · run_lateral_review · web_research
run_shell · refine_answer · maintain_ledger · run_closure_gate · restate_goal
```

`seed`의 6개: `ask_user` `inspect_code` `call_mcp` `run_shell` `refine_answer`
`maintain_ledger`.

**이것이 upstream이 경계를 표현하는 방식이다.** skill은 "내가 무엇을 요구하는가"를
선언하고, Core(MCP)는 그중 `call_mcp`로 닿는 부분만 제공한다. `ask_user`·
`maintain_ledger`·`refine_answer`는 **Core에 대응물이 없다** — host 능력이다.

## 3. QA 루프는 **skill 소유**이며 Core tool은 한 번만 불린다

`skills/seed/SKILL.md`의 QA Refinement Loop:

- 첫 생성(`ouroboros_generate_seed`)은 **정확히 한 번** 돈다. 모듈 주석 그대로:
  *"From there on, all revisions are direct YAML edits by you (main session) —
  do not call `ouroboros_generate_seed` again. It does not accept revision
  hints, and re-running it would discard the established ontology."*
- `pass_threshold: 0.90`, `Max iterations: 5`, 최고 점수 시도 추적("best
  attempt"), 상한 도달 시 사용자 선택 3지(수락 / 최종 수동 편집 후 임계 미달
  수락 / `ooo interview`·`ooo unstuck` 에스컬레이션) — **전부 skill 텍스트에
  있다.**
- `quality_bar` 문장도 skill이 인자로 실어 보낸다. Core는 그 문장을 받아
  채점만 한다.

**우리와의 대조 (등록된 divergence, [ADR-0019](../adr/0019-blueprint-qa-loop.md)
§1).** 우리는 QA 루프를 Core에 뒀다. 실질 차이는 수치가 아니라 **수정의
경로**다 — upstream의 revision은 main session의 YAML 직접 편집이고, 우리
`blueprint revise`는 Core의 범위 재검사(제약·Non-goal 원문 보존)를 지난다.

> **2026-08-09 정정.** 이 문단은 처음에 *"우리 쪽이 강제가 더 세다"* 로 끝났다.
> 과장이다. upstream의 편집이 무검사인 것이 아니라 **검사 지점이 다르다** —
> Restate의 규칙(*"수락한 항목만, 처음부터 다시 쓰지 말 것, 이미 맞던 필드를
> 잃지 말 것"*)은 host에 대한 지시이고, 실제 방어는 **다음 QA 라운드**다. 우리
> 범위 재검사는 다른 종류의 검사이며, 더 세다는 대가로 upstream에 있는 경로
> 하나를 닫았다 — 제약·Non-goal의 verbatim 잠금 때문에 **QA가 제약을 지적해도
> 실행할 수 없다**. 도그푸딩 0001에서 실제로 관측됐고
> ([DOGFOODING_0001 §3.4](./DOGFOODING_0001.md)), upstream은 같은 자리에서
> Socrates·lateral 제안이 user gate를 거쳐 제약을 수정할 수 있다
> ([ADR-0035](../adr/0035-dogfooding-cost-parity-dispositions.md) 대조표 —
> 보상 조치는 §4). **"더 세다"가 아니라 "다른 것을 막고 다른 것을 잃었다"가
> 정확하다.**

## 4. User Adoption Gate — 질문의 **형태까지** skill이 규정한다

REVISE 분기의 4국면: **Wonder(발산) → Reflect(토론) → Refine(사용자 게이트) →
Restate(적용)**. 명문 규칙: *"Revisions must NEVER be auto-applied by the main
session alone — 'No candidate is accepted by default.'"*

- **Wonder**: 독립 원천 3종에서 후보를 모은다 — QA judge(구조), Socrates
  lens(사용자 의도 증거), `ouroboros_lateral_think` 5 persona(hacker·
  researcher·simplifier·architect·contrarian). 원천이 충돌하면 Wonder에서
  조용히 해소하지 않고 divergent signal로 Reflect에 넘긴다.
- **Reflect**: 후보를 **수렴(2개 이상 원천 일치) / 충돌(사용자가 정할 것) /
  단독(약함)** 으로 태깅하고, 확장 대 수렴 비율을 정보로 표시한다.
- **Refine**: `ask_user`로 **단일 선택 질문만**, 순차로. 충돌 그룹을 먼저
  묻고(상호 배타 옵션 + "그대로 두기"), 그다음 수렴 배치, 그다음 단독 배치.
  배치마다 skip 옵션이 필수이며, **skip은 "임계 미달 수락"이 아니다** —
  임계 미달 수락은 루프 경계에서 별도로 명시적으로 골라야 한다.
- **Restate**: 사용자가 수락한 항목만 기존 YAML에 제자리 편집. 처음부터
  다시 쓰지 않는다.

**이것이 "차단 질문을 누가 어떻게 묻는가"의 upstream 답이다** — skill이 묻고,
질문의 개수·순서·선택 형태·기본값 없음까지 skill이 규정한다.

## 5. "누가 무엇을 채택했는가"의 기록은 **skill 소유 파일**이다

각 revision 후 `~/.ouroboros/seed-revisions/<revision_key>.md`에 감사 블록을
덧붙인다 — iteration N, QA 점수, 원천 태그가 붙은 전 후보, 사용자의
accept/reject 결정, 이전 iteration 대비 diff. 파일 쓰기가 불가하면 같은 블록을
응답에 싣는다(조용히 버리지 않는다).

**Core store로 돌아가지 않는다.** 즉 upstream도 승인 actor를 Core에 넣지 않으며,
대신 **결정의 흔적을 skill 계층이 파일로 남긴다.**

## 6. skill은 Core의 판정을 무조건 신뢰하지 않는다

`interview`의 `## Non-Skippable Gates` 6개 중:

> *"Treat MCP `seed-ready` as permission to audit closure, not as completion."*

즉 Core가 "준비됨"이라고 해도 skill이 **로컬로 closure를 다시 감사한다**
(`run_closure_gate` capability). 나머지 다섯은 자유 답변의 재확인, 가시적
ambiguity ledger 유지, Seed Closer 기준 적용, Restate 게이트, 그리고 seed 생성
제안·실행 전 **명시적 사용자 승인**이다.

우리 대조: 우리는 closure 감사를 Core에 넣었다
([ADR-0020](../adr/0020-brief-closure-audit.md)) — 이미 등록된 divergence이며,
이 조사가 그 divergence의 **반대급부**를 보여준다. upstream에서 이 감사는
skill이 다시 하는 이중 방어인데, 우리는 한 층뿐이다.

## 7. 취소는 skill이 **MCP를 우회해 CLI를 직접 부른다**

`skills/cancel/SKILL.md`: *"This skill interacts **directly with the event
store** (not via MCP tool) to emit cancellation events. It uses the CLI command
under the hood."* 세 모드(대화형 목록 선택 / 명시적 id / `--all`).

우리 대조: 우리는 `mcx_cancel_job`이라는 MCP tool로 했다
([ADR-0041](../adr/0041-mcp-control-surface-contract.md) §5). 우리 CLI에는
취소 명령이 아예 없다 — **취소는 MCP에만 있는 동작이다.** upstream은 반대로 CLI에
있고 MCP tool은 별도로 또 있다(`ouroboros_cancel_job`). 등록 필요.

## 8. 동시 writer 충돌의 skill 층 프로토콜은 **없다**

`stale`을 언급하는 자리는 전부 다른 문제다 — interview skill의 것은 사용자가
답을 정정했을 때 MCP가 정정 이전 질문 상태에 남는 경우의 처리이고, evaluate/qa의
것은 실패 분류 이름(`stale_state`)이다.

**두 writer가 같은 상태를 동시에 쓰는 경우의 재확인 절차는 upstream skill 층에
없다.** 우리 [ADR-0014](../adr/0014-brief-concurrent-write-protection.md) §15가
약속한 재확인은 `upstream 대응물 없음`이다.

## 9. 재귀 — **upstream이 막는지 확인하지 못했다**

확인된 사실만:

- Codex도 host다 (§1). 즉 `ouroboros` MCP 서버가 Codex 쪽에도 등록된다.
- 실행 worker도 codex다 (`codex exec`).
- worker 격리 경계로 upstream이 명시하는 것은 **`--profile`** 이다:
  `orchestrator/codex_cli_runtime.py`의 `_build_command` 주석 — *"The backend
  runtime profile is the worker-isolation boundary, so it owns that singular
  flag when configured."* 명령에 MCP 차단 플래그는 없다.
- 텍스트 lane(Claude Code adapter)에는 `allowed_tools=[]` +
  `strict_mcp_config=True`가 있고, 이것이 authoring handler의 재귀 가드다
  ([RUNTIME findings](./RUNTIME_UPSTREAM_FINDINGS.md)).

**미확인 (대조 못 함):** codex plugin의 MCP 등록이 `codex exec` 하위
프로세스까지 상속되는지, 그리고 upstream의 `--profile`이 MCP 서버 목록까지
갈아끼우는 데 실제로 쓰이는지. 이 둘을 모르면 *"upstream은 이 문제를 풀었다"*
고 말할 수 없다. **upstream이 같은 노출을 가질 가능성을 배제하지 못한다.**

## 10. 요약 — upstream이 그은 선

| 항목 | 소유 | 근거 |
|---|---|---|
| 한 번의 판정·생성·채점 (tool 하나 = 결과 하나) | **Core** | MCP tool 목록 |
| 지속 상태와 session id | **Core** | `generate_seed`가 저장된 session 요구 |
| 반복 루프와 종료 조건 (threshold·max·best attempt) | **skill** | §3 |
| 품질 기준 문장 | **skill** (인자로 전달) | §3 |
| 후보 수집·충돌 태깅·사용자 질문의 형태 | **skill** | §4 |
| 사용자 채택 결정의 감사 기록 | **skill** (파일) | §5 |
| Core 판정의 재감사 | **skill** | §6 |
| 취소 | **CLI 직접** (+ MCP tool 별도) | §7 |
| 동시 쓰기 충돌 재확인 | 없음 | §8 |
| worker 재귀 차단 | 미확인 | §9 |

한 문장으로: **Core는 "한 번의 판정"을 주고, skill은 "그 판정을 몇 번 어떤
순서로 부르고 사용자에게 무엇을 묻는가"를 소유한다.**
