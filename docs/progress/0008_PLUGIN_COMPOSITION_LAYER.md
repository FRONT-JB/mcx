# Progress 0008 — Phase 8: plugin 합성 계층 종료 검토

- 일시: 2026-08-09
- 범위: skill/Core 경계 ADR, worker 재귀 차단, skill 6종 + 양쪽 host 매니페스트,
  결정적 Blueprint 품질 하한, 설치·발견·설정 UX
- Evidence: [ADR-0042](../adr/0042-skill-and-core-ownership-boundary.md)(Accepted)·
  [ADR-0043](../adr/0043-deterministic-blueprint-quality-floor.md)(Proposed),
  commits 7b52f5d·d7c3361·b7b839a·df38159·cc5f3f8·f6ffe72·4a694b1, 765 tests,
  [SKILLS findings](../research/SKILLS_UPSTREAM_FINDINGS.md)
- 상태: **Phase 8 COMPLETE (2026-08-09).** 검토가 잡은 5건은 §2에서 처분했다 —
  1건은 코드 수정, 4건은 등록·재지정이다.

## 1. 일곱 질문에 대한 답

### 1.1 구조 검사 — 각 방어가 막는 결함

| 방어 | 막는 결함 |
|---|---|
| skill이 부르는 tool 이름을 검사 | CLI에서 명령을 빼면 tool은 파서 파생이라 따라 사라지지만 **부르는 skill 문장은 남아** host가 런타임에 실패한다 |
| skill이 쓰는 `--flag`를 파서와 대조 | 같은 결함의 인자판. 실제로 3건을 잡았다 (§1.5) |
| `Required Skill Capabilities` 선언 강제 | host가 무엇을 제공해야 하는지 모른 채 skill이 반쯤 돈다 |
| 양쪽 매니페스트가 같은 `./skills/`를 가리킴 | host별로 skill 본문이 갈린다 |
| 자기참조 MCP 등록을 테스트로 고정 | 배포판 이름으로 되돌리면 **배포 전까지 플러그인이 조용히 죽는다** |
| `version` 필드 | `claude plugin validate`가 경고하고 marketplace 항목과 어긋난다 |
| `--ignore-user-config` | worker가 사용자 codex 설정의 MCP를 보고 Mission Control을 되부른다 (ADR-0004 위반) |
| 모델을 명시하고 기록 | worker 모델이 주변 설정에 좌우되는데 그 사실이 어디에도 안 남는다 |
| `NO_VERIFIABLE_CRITERION` | mechanical 층이 돌 것이 없어 공허하게 통과하고 `MISSION COMPLETE`가 semantic 판정 하나에 얹힌다 |
| tool description을 CLI `help=`에서 파생 | host가 29개 중 무엇을 부를지 고를 근거가 없다 (§2.1) |

**산문으로만 막는 계약 1건** — [ADR-0042](../adr/0042-skill-and-core-ownership-boundary.md)
§3의 **질문 형태 규칙**(단일 선택·충돌 먼저·skip 필수·기본 채택 없음)은
검사가 없다. 같은 ADR의 Cost가 이미 그렇게 예고했고, 여기서 확인한다 —
skill 본문이 그 규칙을 담고 있는지는 사람이 읽어야 안다.

### 1.2 부품/단계 구분

플러그인은 **설치까지 실물로 돈다** — marketplace 등록 →
`claude plugin install mcx@mcx` → skill 6종 인식, `plugin:mcx:mcx ✔ Connected`,
always-on ~189 tok. 검증 후 제거했다.

**미조립인 것을 완료로 적지 않는다: skill이 실제로 미션을 운전한 관측이 없다.**
설치와 인식은 확인했지만, host가 skill을 따라 Brief→Blueprint→Execute→Verify를
완주한 적은 없다. Phase 8의 동기가 *"도그푸딩 0003은 순서를 아는 사람이 60콜을
손으로 이어 붙인 실행이었다"* 인데, **그 수가 줄었는지는 아직 모른다.** 첫
관측은 Phase 9다.

### 1.3 미등록 이탈

이번 Phase가 만든 이탈은 전부 그 자리에 등록했다:

| 이탈 | 등록 위치 |
|---|---|
| 자기참조 MCP 등록 (upstream은 PyPI, `${CLAUDE_PLUGIN_ROOT}`는 hooks에만) | Open Questions §8, 테스트 |
| ~~매니페스트 둘이 같은 `.mcp.json` (upstream은 둘로 나눔)~~ | **2026-08-11 폐기** — Codex 실측에서 skill만 보이고 MCP가 누락되어 ADR-0042 §1.1의 host별 bootstrap으로 교체 |
| 결정적 품질 gate 위치가 Core (upstream은 `auto/`) | ADR-0043 §2 |
| 등급·점수 사전 미이식 | ADR-0043 §1 |
| `NO_VERIFIABLE_CRITERION` — **upstream 대응물 없는 발명** | ADR-0043 §3 |
| QA 루프가 Core (upstream은 skill) — 유지 결정 | ADR-0042 §2 |

**미확인으로 남긴 것 1건**: upstream `.mcp.json`의 `"env": {"UV_PYTHON": "3.13"}`.
왜 파이썬을 고정했는지 모르므로 따라 하지 않았고, 그 사실을 Open Questions §8에
적었다. 우리 자기참조 경로는 사용자 환경의 파이썬 해석에 맡긴다.

### 1.4 표시 없는 보류

[ADR-0043](../adr/0043-deterministic-blueprint-quality-floor.md)이 Proposed
상태로 §4(부분 커버리지 처분)를 표시하고 있다.

**표시 없던 보류 1건 발견 — skill 6종의 근거.** upstream은 skill이 22개인데
우리는 6개다. 나머지(`setup`·`config`·`status`·`cancel`·`unstuck`·`evolve`·
`auto`·`ralph` 등)를 만들지 않은 것이 **결정인지 누락인지 기록이 없었다.**
§2.4로 등록했다.

### 1.5 계약 문장 원문 여부

**skill 본문은 영어로 썼다.** host LLM이 읽는 계약이고 upstream skill도 영어다.
번역이 계약을 깎는 자리가 아니다.

**이 질문이 이번 Phase의 가장 값싼 방어를 만들었다.** skill이 인용하는 것은
우리 CLI의 실제 어휘인데, 작성 중 세 곳에서 어긋났고 검사가 전부 잡았다:

| 어긋남 | 실물 |
|---|---|
| QA 액션을 `PASS/REVISE/FAIL`로 씀 | `done`/`continue`/`escalate`/`exhausted` |
| `blueprint revise`에 자유 텍스트를 넘긴다고 씀 | `--draft-file` JSON 전체 문서 |
| 임계 미달 승인에 플래그가 없다고 씀 | `--accept-below-threshold` 필요 |

첫 번째가 특히 징후적이다 — **upstream 조사 직후라 그쪽 어휘가 우리 것으로
섞여 들어왔다.** 오늘 ADR-0042 §8에서 정한 규율("층 이동을 강함으로 위장하지
않는다")과 같은 축의 실수이며, 여기서는 검사가 막았다.

### 1.6 관측 대조

**이번 Phase에는 실 AI 도그푸딩이 없다.** 확인한 것은 플러그인 설치·연결·인벤토리
(실물)와 `codex mcp list` 기반 재귀 레버 실측, `codex exec` 스모크 1회다.

관측과 모순되는 규칙은 없다. 오히려 관측이 설계를 두 번 바꿨다 —
`-c mcp_servers={}`가 병합이라 효과가 없음을 재고 나서 레버를 바꿨고,
`${CLAUDE_PLUGIN_ROOT}` 치환을 재고 나서 배포 의존을 없앴다. **둘 다 내가
"upstream도 그렇게 한다"고 잘못 말한 것을 실측이 정정한 경우다.**

같은 날 외부 지적 6건을 서브에이전트 두 배치로 대조했다 — 4건 거짓, 2건
부분사실. 그 과정에서 **검토 셋을 통과한 시한 도과 1건**(telemetry event 층)과
**시한이 아예 없던 항목 1건**(spec-gap 분류)이 드러나 Phase 9로 등록했다.
서브에이전트 결론 하나(event 층이 "누락이 아니라 나중 Phase")는 직접 확인해
뒤집었다.

### 1.7 시한 도과 점검

Phase 8을 시한으로 지정한 항목 전수:

| 항목 | 처분 |
|---|---|
| [Open Questions §8](../research/OPEN_QUESTIONS.md) skill/Core 경계 | **이행** (ADR-0042 Accepted) |
| [Open Questions §8](../research/OPEN_QUESTIONS.md) plugin 설치·발견·설정 UX | **이행** — 자기참조로 배포 의존까지 없앴다 |
| [Open Questions §8](../research/OPEN_QUESTIONS.md) worker 재귀 차단 | **이행** — 실측으로 레버를 고르고 실물 스모크로 확인 |
| [Open Questions §3](../research/OPEN_QUESTIONS.md)·[ADR-0038](../adr/0038-mcx-cli-surface-contract.md) §7 approval actor | **이행** (ADR-0042 §4 — Core에 필드를 넣지 않고 skill이 흔적을 남긴다) |
| [Open Questions §3](../research/OPEN_QUESTIONS.md) 결정적 품질 gate | **이행** (ADR-0043, Proposed — §4 잔여) |
| [ADR-0019](../adr/0019-blueprint-qa-loop.md) §7·[ADR-0021](../adr/0021-blueprint-state-and-revisions.md) QA revision 제시 | **이행** — blueprint skill의 채택 사이클 |
| [ADR-0011](../adr/0011-brief-deliberate-divergences.md) §3 Fact Resolver | **이행** (폐기) |
| [Open Questions §8](../research/OPEN_QUESTIONS.md) tool description | **미이행이었다 → 이번 검토에서 이행** (§2.1) |
| [ADR-0014](../adr/0014-brief-concurrent-write-protection.md) §15 stale write 재확인 | **미이행 — 2회 연속 도과** (§2.2) |
| [Open Questions §8](../research/OPEN_QUESTIONS.md) host가 자기 편집 도구로 작업하고 Verify만 호출하는 경로 | **미이행 → Phase 9 재지정** (§2.3) |

## 2. 검토가 잡은 것

### 2.1 tool description이 이름의 반복이었다 — 고침

`f"mcx {stage} {verb}"`가 전부였다. host가 29개 중 무엇을 부를지 고르는 유일한
근거인데 정보가 0이다. Phase 7 종료 검토가 이미 발견해 Phase 8 시한을 걸었으나
**skill을 쓰면서도 고치지 않았다.**

재지정 대신 이행했다 — 원인이 CLI 하위 파서의 `help=` 부재였으므로 24개 명령에
문구를 넣고, tool description이 **그것을 파생**하게 했다. 원천이 하나라
`mcx brief --help`와 tool 목록이 같은 문장을 쓴다. 장기 명령 셋은 문구에
`(장기)`를 달아 host가 `mcx_start_*` 짝을 언제 쓸지 판단할 수 있게 했다.

검사 셋으로 고정했다 — 이름 반복 금지, 원천 일치, 장기 표시.

### 2.2 stale write 재확인이 두 번째로 도과했다

[ADR-0014](../adr/0014-brief-concurrent-write-protection.md) §15의 재확인 경로는
Phase 7 시한을 도과해 Phase 8로 재지정됐고, **Phase 8에서도 이행되지 않았다.**
skill 어디에도 동시 쓰기 충돌 절차가 없다(`stale` 언급 셋은 전부 승인·verdict의
stale이지 쓰기 충돌이 아니다).

**세 번째 재지정을 하기 전에 이유를 적는다.** 두 번 밀린 이유는 시한이 "구현
Phase"에 붙어 있었기 때문이다 — 조건(동시 writer)은 Phase 7이 만들었지만
**실제로 충돌이 관측된 적이 없다.** 관측 없이 재확인 문안을 쓰면 그것은 발명이며
upstream 대응물도 없다(SKILLS findings §8).

따라서 **Phase 9로 재지정하되 발동 조건을 함께 건다**: 실사용에서 `StaleWriteError`가
한 번이라도 관측되면 그때 문안을 쓴다. 관측되지 않으면 Phase 9 종료 검토에서
**"발생하지 않는 문제"로 닫는 것**도 정당한 처분이다 — 지금까지처럼 무한히
미루지 않는다.

### 2.3 host가 자기 도구로 작업하고 Verify만 호출하는 경로 — 미결

원래 시한이 *"Phase 7 전"* 이었고 Phase 7을 지나 Phase 8로 재지정됐는데, 이번에도
**결정 기록이 없다.**

skill은 **행동 규칙**을 담았다 — execute skill의 *"Do not write the code
yourself… Verify refuses work it has no record of"*, verify skill의 *"An
agent's claim of success is not evidence"*. 그러나 산문이며,
[ADR-0026](../adr/0026-verify-entry-requires-lineage.md)이 요구한
*"기록 요구를 유지한 채"* 라는 제약 아래의 **결정**은 여전히 내려지지 않았다.

**Phase 9로 재지정한다** — 같은 Phase의 brownfield가 정확히 같은 형태의 문제
(루프 밖 코드를 어떻게 Verify에 넣는가)이고, 둘을 따로 결정하면 서로 어긋난다.

### 2.4 skill이 6종인 근거가 없었다 — 등록

upstream은 22개, 우리는 6개다. 만들지 않은 것들의 성격이 다르다:

- **대응물이 이미 있다**: `status`(=`mcx status` 명령), `cancel`(=`mcx_cancel_job`)
- **해당 Phase가 아니다**: `evolve`(Phase 10), `brownfield`(Phase 9),
  `auto`·`ralph`(합성 자동화 — 우리 `mcx` 우산 skill이 순서만 담고 자동 진행은
  하지 않는다)
- **판단이 필요하다**: `setup`·`config` — 우리 설정은 `config.toml` 하나이고
  모델은 자동 seeding되므로 대화형 설정 skill의 필요가 upstream보다 작다.
  그러나 **"필요 없다"는 결정을 내린 적이 없다**

셋째 부류를 [Open Questions §8](../research/OPEN_QUESTIONS.md)에 등록했다.
시한은 Phase 9 — 실사용이 설정 UX의 필요를 드러내는 자리다.

### 2.5 ADR-0043이 Proposed로 남는다

§4(부분 커버리지: 표시만/경고/임계값)는 사용자 결정이며, 실사용 관측 전에는
"표시만"을 권고한다. Phase 9 진입 전에 닫지 않아도 되지만 **Phase 9 종료
검토의 질문 7 대상**이다.

## 3. 다음 Phase 진입 조건

Phase 9(실사용 진입: brownfield + 되돌리기)에 **진입 조건은 없다.** 다만 이
Phase가 넘기는 것이 많고 성격이 하나로 모인다 — 전부 **실물 관측이 있어야
결정할 수 있는 것들**이다:

| 항목 | 왜 Phase 9인가 |
|---|---|
| stale write 재확인 (§2.2) | 충돌이 실제로 나야 문안을 쓴다 |
| host 자기 도구 경로 (§2.3) | brownfield가 같은 형태의 문제다 |
| telemetry event 층 | 긴 실행의 진행 표시가 실수요가 된다 |
| spec-gap 분류 | 명세의 문제로 실패하는 사례가 생긴다 |
| `cancelled` attempt 상태 | 되돌리기 층과 같은 자리 |
| runtime resume | 같음 |
| 부분 커버리지 처분 (§2.5) | 수치의 근거가 관측에서 나온다 |
| setup/config skill 필요 여부 (§2.4) | 실사용이 설정 UX의 필요를 드러낸다 |

**Phase 9는 구현 Phase가 아니라 관측 Phase에 가깝다.** 그 점을 로드맵에 반영해
둔다 — 여덟 항목을 "실사용 관측으로 결정"이라는 한 묶음으로 다루지 않으면,
관측 없이 하나씩 발명하게 된다.
