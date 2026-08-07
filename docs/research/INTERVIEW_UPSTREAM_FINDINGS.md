# Interview Upstream Findings — Brief 우선 조사

> Baseline: `Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943` (v0.50.8, 2026-08-05)<br>
> Checked: 2026-08-07 (local clone, 해당 commit checkout)<br>
> Scope: [Open Questions §0](./OPEN_QUESTIONS.md#0-현재-우선순위--phase-1-brief-vertical-slice)<br>
> Evidence level: 별도 표기 없으면 **Verified** (baseline commit의 소스에서 직접 확인)

이 문서는 관찰을 보존한다. Mission Control이 각 관찰을 채택할지는
[§8 시사점](#8-2-brief-decisions에-대한-시사점)에 Proposed로만 기록하고,
확정은 ADR과 `05_BRIEF.md` 갱신에서 한다.

---

## 1. Package 경계 (`pyproject.toml`)

- 배포명 `ouroboros-ai`, `requires-python >= 3.12`, hatchling + hatch-vcs.
- 핵심 runtime 의존성: `pydantic 2.x`, `typer`, `click`, `rich`,
  `sqlalchemy[asyncio]` + `aiosqlite`, `structlog`, `anyio`, `jsonschema`,
  `prompt-toolkit`, `pyyaml`, `python-dotenv` (모두 상한 있는 범위 pin).
- optional extras는 supply-chain 이유로 **정확 버전 pin**: `claude`
  (claude-agent-sdk, anthropic), `litellm`, `mcp` (`mcp==2.0.0`), `tui`
  (textual). MCP 2.x와 claude-agent-sdk의 `mcp` 의존성이 충돌해 **별도
  프로세스**로 분리 운영한다는 주석이 있다.
- entry points: `ooo`, `ouroboros` → `cli.main:app`, `ozo` → zcode.
- `src/ouroboros/`는 약 40개 subpackage. Brief 관련 핵심은 `bigbang/`
  (interview·ambiguity·seed 생성), `auto/` (자동 인터뷰 driver),
  `mcp/tools/` (authoring handlers), `cli/commands/init.py`, `events/`,
  `skills/interview/` (host 세션용 skill).

## 2. Interview 종료 Gate — end-to-end

세 개의 surface가 서로 다른 강도의 Gate를 가진다.

### 2.1 CLI (`ooo interview` = `ooo init`)

`cli/main.py:100`이 `interview`를 init Typer app의 별칭으로 등록한다.
`cli/commands/init.py:289-373`의 대화 루프:

1. 질문 생성 → 실패 시 사용자에게 Retry 확인, 거부하면 상태를
   `ABORTED`로 저장하고 종료. ABORTED는 터미널이며 재개 불가
   (`init.py:376-385`).
2. 빈 응답은 거부하고 재입력 (`init.py:325-327`).
3. 응답은 telemetry(HITL events)보다 **먼저** 기록·저장한다
   (`init.py:329-343`).
4. round ≥ `MIN_ROUNDS_BEFORE_EARLY_EXIT`(=3)부터 매 round
   "Continue with more questions?" Confirm → 사용자가 거부하면
   `engine.complete_interview()` 호출 (`init.py:361-371`).

**중요 관찰: CLI 루프에는 ambiguity score Gate가 없다.** 완료는 순수하게
사용자 확인이다. score 기반 Gate는 MCP surface에 있다.

### 2.2 MCP (authoring handler)

`mcp/tools/authoring_handlers.py`의 interview tool 흐름:

- 답변 기록 후, 답변된 round가 3 미만이면 scoring을 생략한다
  (조기 종료가 불가능하므로 LLM 호출 낭비 방지, `:3256-3264`).
- round ≥ 3부터 매 답변 후 ambiguity를 재평가하고, **qualify + streak ≥ 2**면
  사용자 신호 없이 auto-complete한다 (`:3282-3297`).
- 사용자가 명시적으로 `done`을 보내면: score가 qualify할 때 streak를 +1
  (반복 `done`도 stability 신호로 인정, upstream #405) → streak가 2에
  도달해야 완료. 미달이면 "stability check n/2" 메시지로 한 번 더 확인을
  요구한다 (`:3022-3113`). score가 qualify하지 못하면 완료를 거부한다
  (`:3114` 이후).
- streak 저장 실패는 hard error로 처리한다 — 저장 없이 성공 메시지를
  반환하면 two-signal 계약이 깨진다는 주석 (`:3050-3071`, `:3118-3126`).
- `seed_ready_override=True`는 `ooo auto` driver의 safe-default synthesis
  전용 우회다: 모든 필수 gap을 감사된 보수적 기본값으로 채운 뒤에는 인간
  `done` threshold를 다시 요구하지 않는다 (`:2985-3005`).

### 2.3 Skill layer (host 세션)

`skills/interview/SKILL.md:637-676` — MCP가 seed-ready를 신호해도 host
세션은 그대로 완료를 중계하지 않는다.

- **Seed-ready Acceptance Guard**: `closer`(판정 gate 권한),
  `contrarian`, `gap_hunter` 3-lane fan-out으로 closure를 압박 테스트.
  closer가 seed_ready가 아니거나 HIGH 심각도 발견이 있으면 MCP 신호를
  명시적으로 override하고 blocking follow-up 질문을 계속한다.
- **Restate gate**: Guard 통과 후 goal을 한 문장으로 재진술하고
  사용자에게 확인을 받은 뒤에야 `ooo seed`로 진행한다.

## 3. Ambiguity 정책 — `0.2` discrepancy의 해소

[UPSTREAM_MAPPING §2](./UPSTREAM_MAPPING.md#2-brief--interview)가 남긴
충돌은 다음처럼 해소된다. **둘 다 사실이며 층이 다르다.**

- `bigbang/ambiguity.py:36-44`:
  `AMBIGUITY_THRESHOLD = 0.2`, `SEED_CLOSER_ACTIVATION_THRESHOLD = 0.25`,
  `AUTO_COMPLETE_STREAK_REQUIRED = 2`, per-dimension floor
  (goal 0.75, constraint 0.65, success criteria 0.70, brownfield context 0.60).
- 점수 방향: 차원별 clarity(0..1, 높을수록 명확)를 가중 평균해
  `ambiguity = 1 − weighted_clarity`, 4자리 반올림 (`:799-812`).
- 가중치: greenfield 3차원 0.40/0.30/0.30, brownfield 4차원
  0.35/0.25/0.25/0.15(context) (`:46-55`).
- 완료 자격 `qualifies_for_seed_completion` = overall ≤ 0.2 **AND** 모든
  floor 충족 (`:323-332`).
- 사용자 통제: round 상한 없음 (`interview.py:176` "user decides when to
  stop"), 완료 후에도 재개 가능(`can_reopen`, `:269-279`), 재개 시
  저장된 score와 streak를 무효화해 two-signal 안정성을 다시 요구
  (`:1066-1090`), round-limit 자동 완료 없음 (`:1101-1102`).

즉 `0.2`는 "질문 종료를 추천/허용하는 machine gate의 입력"이고, interview
완료는 (a) CLI에서 사용자 Confirm, (b) MCP에서 qualify+streak, (c) skill
layer에서 Acceptance Guard + Restate 사용자 확인이 겹겹이 결정한다.

## 4. Completion candidate streak와 user approval 경로

- streak는 `InterviewState.completion_candidate_streak`로 영속화된다
  (`interview.py:240`).
- 갱신 규칙: qualify하는 score마다 +1, qualify하지 못하면 0으로 리셋
  (`authoring_handlers.py:350-374`). scoring 실패 시에도 stale streak를
  리셋한다 (`reset_on_failure`).
- 사용자 승인의 실체는 세 가지로 분산된다:
  1. CLI: round ≥ 3부터의 Confirm 거부 = 완료 결정.
  2. MCP: `done` 입력 (streak 계약 하에서).
  3. Skill: Restate gate에서 1문장 goal에 대한 명시적 확인.
- 승인의 영속 기록: 별도 approval 객체는 없고 `status = COMPLETED` 전이 +
  CLI의 HITL requested/answered 이벤트(event store, best-effort)가 근거다.

## 5. Answer provenance와 requirement authority

`bigbang/answer_provenance.py` (전문 확인):

- enum: `AnswerProvenance = Literal["user", "observation"]` (`:33`).
- `[from-code]`, `[from-repo]`, `[from-research]`, `[from-data]` prefix가
  observation으로 분류된다. 복합 마커(`[from-code][auto-confirmed]` 등)는
  prefix 매칭으로 포괄 (`:43-59`).
- 구분 축은 **결정 vs 채택된 사실**이지 인간 vs 기계가 아니다 —
  `[from-auto]`/`[from-safe-default]`는 기계가 만든 "결정"이라 user로
  분류된다 (`:70-82`).
- requirement authority 규칙: observation은 요구사항 추출 입력에서 원문이
  차단되고 `WITHHELD_ANSWER_NOTE` placeholder로 대체된다. 질문 텍스트에는
  그대로 남는다(다음 질문을 날카롭게 하는 용도) (`:95-123`).
- 분류는 답이 상태에 들어오는 단일 지점(`record_answer`)에서 한 번 결정되고
  이후에는 필드로만 읽는다. surface마다 마커를 재해석하다 생긴 drift가
  이 설계의 동기다 (upstream #1755, `interview.py:441-479`).

## 6. LICENSE

baseline `LICENSE`는 MIT, copyright (c) 2025 Q00. 코드 복사·상당한 포팅
전 재확인 체크리스트는 [UPSTREAM_MAPPING §11](./UPSTREAM_MAPPING.md#11-license-note)을 따른다.

## 7. 부수 관찰 (Brief 설계에 유용)

- 질문 생성은 5개 내부 perspective(researcher, simplifier, architect,
  breadth-keeper, seed-closer)의 후보 패널에서 선택한다
  (`interview.py:106-151`, `:568-`). seed-closer는 score ≤ 0.25에서 활성화.
- `InterviewStatus`: `IN_PROGRESS | COMPLETED | ABORTED` (`:154-159`).
- initial context는 prompt-safe 한도 3,500자(`:56`)를 넘으면 summary
  round를 먼저 요구한다 (`needs_initial_context_summary`, `:258-267`).
- greenfield/brownfield는 v1급 1st-class 구분이다: `is_brownfield` 플래그,
  별도 가중치·floor, `bigbang/explore.py`의 read-only codebase 탐색
  (config 파일 스캔 → tech stack → 타입 정의 → LLM 요약 → interview
  prompt 주입).
- interview 상태는 파일 기반 `interview_*.json` + file locking으로 저장
  (`interview.py:1106-`, `:1662-1691`). HITL 이벤트는 SQLite event store에
  별도(best-effort) 기록.
- 이벤트 어휘: `interview_started / response_recorded / completed / failed /
  question_parent_handoff / response_emitted / lateral_review_recommended`
  (`events/interview.py`).

## 8. §2 Brief decisions에 대한 시사점

> Decision status: 전부 **Proposed**. 확정은 `05_BRIEF.md` 갱신과 ADR에서.

| §2 질문 | upstream 근거 | Mission Control 제안 |
|---|---|---|
| Greenfield/Brownfield 구분 | 1st-class 구분 (가중치·floor·explore) | v1은 greenfield 먼저, 모델에 `is_brownfield` 자리만 예약 |
| provenance categories | `user`/`observation` + `[from-*]` prefix | 이원 분류 + 출처 마커 채택, 마커 문법은 단순화 |
| clarity dimension·방향 | 차원별 clarity ↑ / overall ambiguity ↓ | 동일 방향 채택 (ambiguity = 1 − 가중 clarity) |
| threshold·rounds·streak 관계 | 0.2 + floors + min 3 rounds + streak 2 | 구조(3중 조건)는 채택, 수치는 테스트로 검증 후 고정 |
| approval 기록 위치 | status 전이 + HITL events | Gate decision 기록에 approval evidence를 명시적으로 포함 (upstream보다 강화) |
| 질문 생성 실패·빈 응답 | CLI: 재시도/ABORTED 터미널; 빈 응답 재입력; MCP: 답변 선저장 | 답변 선저장 + 실패 시 attempt 보존 채택 |
| initial context 한도 | 3,500자 + summary round | 한도 상수화 + 초과 시 요약 요구 채택 |
| codebase fact 수집 | 전용 read-only explore 단계 | v1 범위 결정 필요 (brownfield와 함께) |

## 9. 미확인 / 후속 조사

- `ooo seed`(Blueprint 진입)가 interview score를 다시 강제하는지 —
  Phase 2 (Blueprint) 조사에서 확인한다.
- CLI 경로에 score Gate가 없는 것이 의도인지(문서/이슈 근거) — Mission
  Control은 CLI에도 동일 Gate를 두는 쪽이 헌법(#surface 간 동일 의미)에
  부합하므로, 차이를 두려면 ADR이 필요하다.
- `question_classifier.py`(사실/결정 라우팅), `pm_interview.py`,
  `auto/interview_driver.py` 상세는 Brief 구현 중 필요 시 추가 조사.
- upstream 테스트가 보장하는 행동 목록(`tests/`)은 Phase 1 test case 설계
  직전에 추적한다.
