# Seed Upstream Findings — Blueprint 대응 조사

> Baseline: `Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943` (v0.50.8)<br>
> Checked: 2026-08-07; empty-list encoding 재확인: 2026-08-11
> (local clone, 해당 commit checkout)<br>
> Scope: [Open Questions §3](./OPEN_QUESTIONS.md#3-blueprint-decisions)<br>
> Evidence level: 별도 표기 없으면 **Verified**

Phase 2의 첫 결정(Blueprint schema) 직전에 조사했다. 결정은
[ADR-0017](../adr/0017-blueprint-schema-baseline.md)에 있다.

---

## 1. `Seed`의 선언된 필드

`core/seed.py:648-750`. 모두 `frozen=True`다.

| 필드 | 타입 |
|---|---|
| `goal` | `str`, `min_length=1` |
| `task_type` | `str`, 기본 `"code"` (code/research/analysis/artifact/document/documentation/presentation) |
| `brownfield_context` | `BrownfieldContext`, greenfield면 빈 값 |
| `constraints` | `tuple[str, ...]` |
| `acceptance_criteria` | `tuple[AcceptanceCriterionSpec, ...]` |
| `ontology_schema` | `OntologySchema` |
| `evaluation_principles` | `tuple[EvaluationPrinciple, ...]` |
| `exit_conditions` | `tuple[ExitCondition, ...]` |
| `metadata` | `SeedMetadata` (`ambiguity_score` 등) |

docstring은 "Direction (goal, constraints, acceptance_criteria) is IMMUTABLE"이라고
규정한다 (`:653-656`).

보조 모델은 단순하다.

- `ExitCondition` (`:256`) — `name`, `description`, `evaluation_criteria`(alias `criteria`)
- `EvaluationPrinciple` (`:272`) — `name`, `description`, `weight`(0..1, 기본 1.0)
- `OntologyField` (`:286`) — `name`, `field_type`(alias `type`), `description`, `required`
- `OntologySchema` (`:304`) — `name`, `description`, `fields`

## 2. `non_goals`는 선언되지 않았지만 방향의 일부다

- `bigbang/seed_generator.py` 전체에 `non_goal`이 **한 번도 등장하지 않는다.**
  추출 프롬프트에도 없다.
- 그러나 `Seed.model_config = {"extra": "allow"}` (`:704-706`)이며 주석은
  "Extra fields are reserved for plugin-owned, structured handoff data"라고 한다.
- `evolution/loop_support.py:1028-1031`이 방향 보존 검사에서
  `approved.to_dict().get("non_goals") != successor.to_dict().get("non_goals")`로
  읽는다. 없으면 `None`이므로 방어적으로 동작한다.
- `core/conductor.py:145`의 `preserve_non_goals: bool = True`가 goal,
  acceptance_criteria, constraints와 나란히 놓이고, `is_non_relaxing` (`:210-219`)이
  넷을 모두 요구한다.

즉 non_goals는 **방향으로 취급되면서 스키마에 선언되지 않은** 상태다. Non-goal
자체는 다른 곳에 존재한다 — `RequirementSection.NON_GOAL`(후보의 칸),
`auto/ledger.py:20`의 `LedgerSource.NON_GOAL`, 그리고 `auto/grading.py:404-415`가
auto 생성 Seed에 non-goal이 없으면 `missing_non_goals`("Add MVP non-goals to bound
scope")를 남긴다. **core gate가 아니라 auto driver의 grading에서만 확인한다.**

## 3. Acceptance criterion identity — 위치가 아니라 내용

`AcceptanceCriterionSpec` (`core/seed.py:452-476`):

| 필드 | 의미 |
|---|---|
| `description` | 사람이 읽는 기준 |
| `semantic_ac_key` | `^ac_[a-f0-9]{16}$`, 없으면 파생 |
| `verify_command` | 확인을 위해 실행할 명령 |
| `expected_artifacts` | 실행 후 존재해야 하는 산출물 |
| `output_assertion` | 출력에서 확인할 조건 |
| `investment` | `InvestmentSpec \| None` |

`derive_semantic_ac_key` (`:610-633`)가 identity를 만든다.

```
payload = {description, verify_command, expected_artifacts, output_assertion}
key     = "ac_" + sha256(json(sort_keys, no space, ensure_ascii=False))[:16]
```

docstring이 의도를 명시한다 — "The digest intentionally excludes list position,
runtime/session identity, and volatile Seed metadata. Preserved structured
criteria keep their explicit key across retries and successors; a semantically
replaced criterion gets a new key when materialized from its changed contract."

즉 **AC의 정체성은 성공 계약 그 자체**이며, 계약이 바뀐 AC는 다른 AC다. 문자열만
있는 legacy AC는 `{"description": str(...).strip()}`으로 파생한다 (`:626-627`).

## 3.1 AC의 검증 수단 — 최소 하나를 요구하지 않는다

세 필드(`verify_command`, `expected_artifacts`, `output_assertion`)가 모두
`default=None`/빈 튜플이며, **최소 하나를 요구하는 검증기가 없다**
(`core/seed.py:452-476`). 즉 upstream도 확인 수단이 전혀 없는 AC를 허용한다.

대신 두 가지를 강제한다.

- **`output_assertion`은 `verify_command`를 요구한다.** 스키마 검증기
  `_validate_raw_success_contract` (`:480-497`)가 `ValueError
  ("output_assertion requires verify_command")`를 올리고, 실행 시 verify gate
  (`orchestrator/parallel_executor.py:9651-9657`)가 같은 이유로 실패시킨다.
- **`verify_command`는 한 줄이어야 한다.** `_unsupported_verify_command_reason`
  (`bigbang/seed_generator.py:1477-1481`) — 여러 줄이나 heredoc은 거부하고
  `python -c`나 `pytest`를 쓰라고 안내한다.

한편 "success contract를 가졌는가"의 판정은 `verify_command` 하나만 본다 —
`orchestrator/shadow_replay.py:622`의
`has_success_contract = ac_spec is not None and bool(ac_spec.verify_command)`.
`expected_artifacts`만 있는 AC를 어떻게 취급하는지는 확인하지 못했다
(`Evidence level: Verified`이나 의도는 `Inferred` 이하).

## 3.2 성공 계약 작성 지침 — exit code는 runner가 따로 본다

생성 프롬프트는 `agents/seed-architect.md`다 (`seed_generator.py:2198-2200`이
`load_agent_prompt("seed-architect")`로 불러온다). AC 계약 작성에 대한 지침이
명시적이다 (`:71-78`).

**`output_assertion`(프롬프트에서는 `expect`)**

- 오직 **출력에 그대로 나타나는 문자열**에만 쓴다. 예: `OK`, `5 passed`.
- 조건·상태·종료코드 서술을 **절대 쓰지 않는다** — `exit code 0`, `returns 0`,
  `success`, `no errors`, `passed` 같은 것들을 명시적으로 금지한다.
- 구별되는 출력 문자열이 없으면 `expect: NONE`으로 둔다.
  **"Exit-code 0 is already verified separately by the runner."**

**`expected_artifacts`**

- 정확한 경로를 모르면 `artifacts: NONE`으로 두고 구체적인 `verify` 명령을 대신
  제공한다 (`:71`).
- **"File or directory existence can be a complete contract."** 다만 대기·차단
  상태가 있을 수 있는 산출물이면 의미적 상태를 확인하는 `verify` 명령도 함께
  둔다 (`:72`).

이것이 §3.1에서 미확인으로 남긴 "왜 `has_success_contract`가 `verify_command`만
보는가"의 답이다. **명령이 있으면 종료코드 검사가 자동으로 따라오므로 명령 자체가
완결된 계약**이다. `output_assertion`은 그 위에 얹는 선택적 추가 검사이고, 억지로
채우면 오히려 취약해진다(테스트 하나 추가하면 `3 passed`가 `4 passed`가 된다).

## 3.3 Granularity contract — 결과인가 수단인가

> 이 규칙의 실제 강제 경로는 §10을 함께 볼 것. 프롬프트 지시일 뿐 아니라 QA
> quality bar의 채점 항목이다.

`agents/seed-architect.md:79-85`. 프롬프트가 스스로 "read carefully"라고 표시한
섹션이며, 문구가 아니라 **AC 품질의 판정 규칙**이다.

> An acceptance criterion names a **state of the finished work** that a user can
> see is true. An implementation step names a **means of reaching that state**.
> These are different categories, and only the first belongs here — deciding
> means is the execution engine's work at runtime, and it decides them better
> with the outcome in hand than with your guess at the path.

판정 방법도 제시한다 — 형제 항목들과 나란히 놓고 읽는다. **스스로 사용자가
가치를 느끼는 것으로 성립하면 결과**이고, **형제 항목으로 가는 이동으로만
이해되면 수단**이며 그 형제에 병합되어야 한다.

> Leaving a means in the criteria list is a **defect equal in severity to a
> missing requirement** — it commits the seed to a path before anyone has
> verified the path is the right one.

그리고 개수를 정하지 않는다 — "How many criteria a goal has is a property of
that goal, discovered by making this judgment."

예를 들면 이렇다.

| 문장 | 종류 |
|---|---|
| "댓글 작성 후 목록 맨 위에 나타난다" | 결과 — 사용자가 볼 수 있는 완성 상태 |
| "Comment 모델에 created_at 인덱스를 추가한다" | 수단 — 위 결과로 가는 경로 |

수단을 AC에 남기면 **아무도 그 경로가 옳은지 검증하기 전에 명세가 경로를
확정한다.** Execute가 결과를 손에 쥐고 판단할 여지가 사라진다.

Mission Control은 이 판정을 아직 구현하지 않았다. `check_scope`는 AC의 **존재
여부**만 보고 종류를 보지 않는다. Phase 2의 "AC quality validation" 항목이 이것에
해당하며, upstream의 대응 위치는 QA judge의 quality bar다 (§10).

## 3.4 생성기가 대화 원문을 읽을 때 필요한 규칙

`agents/seed-architect.md:16-37`. upstream의 seed architect는 **대화 원문을**
읽으므로 provenance를 직접 해석해야 한다.

- `[from-user]`(또는 표기 없음)는 결정, `[from-code]`/`[from-repo]`/
  `[from-research]`는 채택된 사실이며 "a fact is not a decision. Only a decision
  can become a requirement."
- 보류된 관찰 자리에 나타나는 note에 대해 — "That is deliberate, not a truncation
  or an error. Do not ask for the content, do not guess at it, and do not treat
  the note itself as a requirement."
- 질문은 전문이 보이며 — "nothing in a question line becomes a requirement on
  its own."

Mission Control은 생성기에 대화를 넘기지 않고 이미 칸이 나뉜 handoff만 넘기므로
([ADR-0018](../adr/0018-blueprint-generation-contract.md) §2) 이 규칙들이 프롬프트
지시가 아니라 **입력 형태로 해소된다.** 다만 upstream이 이 세 문장을 명시적으로
쓴 이유가 실제 결함(#1755 계열)이라는 점은 우리 선택의 근거를 강화한다.

## 3.5 empty collection은 placeholder가 아니라 구조로 전달한다 (2026-08-11)

> Evidence level: **Observed + Verified** — Codex-only Blueprint generation
> 실물 실패와 pinned `agents/seed-architect.md:38-48,93-109` 직접 대조.

pinned Seed architect는 constraints·acceptance criteria 등 collection을
**single-line JSON array**로 주고받으며 empty collection도 `[]`라는 구조로
표현한다. generic prose placeholder를 collection 원소로 쓰지 않는다.

mcx generator prompt는 빈 handoff section을 `(none)`으로 렌더링했다. 실제 Codex가
이를 `non_goals: ["(none)"]`로 복사했고, 결정적 scope 검사는 승인되지 않은
Non-goal 추가로 정확히 거부했다. 처분은 scope 검사를 약화하거나 sentinel을
사후 삭제하는 것이 아니다. generator 입력 collection을 JSON array로 직렬화해
빈 값의 유일한 표현을 `[]`로 만든다. 모델이 그 뒤에도 항목을 발명하면 기존
scope error가 그대로 막는다.

## 4. 조사했으나 v1에서 다루지 않기로 한 것

`core/seed.py`에는 산출물 경로 검증 장치가 상당량 있다 (`:41-253`).

- Windows 예약 이름과 금지 문자 (`_WINDOWS_FORBIDDEN_COMPONENT_CHARS`,
  `_WINDOWS_RESERVED_COMPONENT_STEMS`)
- POSIX/Windows 경로 길이 한계 (`_POSIX_PORTABLE_PATH_MAX_BYTES = 256`,
  `_WINDOWS_CONSERVATIVE_PATH_MAX_UTF16_UNITS = 260`)
- `MAX_AC_SUCCESS_CONTRACT_ARTIFACTS = 253`, `MAX_AC_SUCCESS_CONTRACT_CHARS = 64_000`
- `expected_artifact_workspace_path_error` — workspace 밖 경로 차단

이 장치들이 무엇을 막는지는 명확하다(경로 조작, 플랫폼 간 비호환, 크기 폭주).
Mission Control이 실제로 산출물 경로를 다루는 시점은 Execute(Phase 3)이므로 그때
함께 재구성한다. `Evidence level: Verified`로 기록만 남긴다.

## 6. 생성 흐름 — 결정적 관문 → 모델 1회 → 결정적 검증

`SeedGenerator.generate` (`bigbang/seed_generator.py:1719`)의 순서.

1. ambiguity threshold gate (`:1770-1789`). `force=True`면 우회하되 실제 점수를
   metadata에 남긴다.
2. `initial_context_summary_missing(state)` 확인 (`:1791-1798`).
3. `build_requirement_distillation(state)` (`:1800`) — 결정적 후보 도출 (§3.1).
4. `apply_requirement_distillation({}, distillation)` (`:1801`) — 결정적 승격
   판정. blocker가 있으면 진행하지 않는다.
5. `_extract_requirements(state)` (`:1981-2050`) — **LLM 호출 한 번**,
   `CompletionConfig(role="seed_generation")`. system + user 두 메시지.
   `_parse_extraction_response`가 실패하면 **한 번 재시도**한다
   (`_MAX_EXTRACTION_RETRIES`).
6. 결정적 파싱과 검증.

**파싱 계층이 파일의 대부분이다.** 2,637줄 중 `_PosixCaseTracker`(셸 문법 추적),
`_scan_pipe_led_ac_field_fragment`, `_reject_duplicate_json_keys`,
`_bounded_json_int`, `_JsonNonFiniteToken` 등이 `:69-1350`에 걸쳐 있다. 모델
출력이 필드 경계를 넘나들거나 JSON을 깨뜨리는 실패를 실제로 겪었다는 증거로
읽힌다.

Mission Control은 handoff가 이미 칸별로 나뉘어 있으므로(§2, ADR-0015) 모델에게
남는 일이 upstream보다 작다. 결정은
[ADR-0018](../adr/0018-blueprint-generation-contract.md)에 있다.

## 7. Seed 승인 — Python core에는 없다 (§9에서 정정)

`SeedApproval`, `approve_seed`, `seed_approved` 계열 심볼이 저장소 전체에 **하나도
없다.**

`cli/commands/seed.py`는 99줄이며 흐름은 다음이 전부다 (`:80-96`).

1. interview state 로드
2. `state.status != InterviewStatus.COMPLETED`면 오류 후 종료
3. `_generate_seed_from_interview(...)` 호출
4. 경로 반환

**사용자 확인 절차가 없다.** `ooo seed`는 생성하고 저장한다. Brief에서 확인한
것과 같은 구조다 — 별도 approval 객체 없이 status 전이가 근거다
([ADR-0011](../adr/0011-brief-deliberate-divergences.md) Divergence 2가 이미
Brief에 대해 기록한 차이가 Seed에서도 그대로 성립한다).

## 8. QA 루프 — 일반 경로에서 **필수**이며 skill 계층에 있다

> **2026-08-07 정정.** 최초 조사에서 `bigbang/`·`core/`·`auto/`만 확인하고
> `skills/`를 보지 않아 "QA는 auto 전용"이라고 잘못 기록했다. 사용자가 실제
> 도그푸딩 화면(`QA 반복 3/5 — 0.88 / 0.90 REVISE`)을 제시해 확인했다. Brief
> 조사에서 이미 `skills/interview/SKILL.md`를 인용해 놓고도 Seed에서 같은 계층을
> 확인하지 않은 것이 원인이다.

`skills/seed/SKILL.md:105-113` — **"QA Refinement Loop (Required after
generation)"**.

- 생성 직후 **"do not present it as final yet"**. QA가 PASS하거나 사용자가
  임계값 미달 결과를 명시적으로 수락하기 전에는 최종본으로 제시하지 않는다
  (`:87`, `:103`).
- **`pass_threshold: 0.90`** — 기본 0.80보다 엄격하다. 이유가 명시되어 있다 —
  "seeds are structural specs and must be precise".
- **Max iterations 5.** 반복마다 최고 점수 seed를 "best attempt"로 추적한다.
- 5회 후에도 PASS가 아니면 사용자에게 세 선택지를 준다 — 그대로 수락 /
  최종 수정 하나만 적용하고 임계값 미달 수락 / `ooo interview`·`ooo unstuck`으로
  에스컬레이션. 6회째 반복은 금지된다.

**첫 생성은 정확히 한 번이고, 이후 수정은 재생성이 아니라 직접 편집이다**
(`:109`) — "do not call `ouroboros_generate_seed` again. It does not accept
revision hints, and re-running it would discard the established ontology."

판정 등급은 `skills/qa/SKILL.md:29-35`.

| 점수 | 판정 | 루프 동작 |
|---|---|---|
| ≥ 0.80 | PASS | done |
| 0.40–0.79 | REVISE | continue |
| < 0.40 | FAIL | escalate |

평가 축은 Correctness, Completeness, Quality, Intent Alignment, Domain-Specific
(`skills/qa/SKILL.md:25`).

`auto/grading.py`와 `auto/seed_repairer.py`는 **이것과 별개**로 자율 모드가 쓰는
등급·수리 장치다. 즉 QA는 두 곳에 있고, 사람이 쓰는 경로는 skill 계층이다.

Python core(`ooo seed` CLI)만 QA가 없다. 이는 Brief에서 확인한 CLI/MCP/skill
3층 구조가 Seed에서도 그대로라는 뜻이며
([INTERVIEW_UPSTREAM_FINDINGS](./INTERVIEW_UPSTREAM_FINDINGS.md) §2), 사람이 쓰는
경로에서 가장 강한 관문은 항상 skill 계층에 있다.

## 9. Seed 승인 — skill 계층의 User Adoption Gate

> **2026-08-07 정정.** "Seed 승인이 존재하지 않는다"고 기록했으나 Python 심볼에
> 한정된 이야기였다. skill 계층에는 명시적 사용자 채택 관문이 있다.

`skills/seed/SKILL.md:159` — **"Revisions must NEVER be auto-applied by the main
session alone — *'No candidate is accepted by default.'* (Symposium User
Adoption Gate)"**

- 각 수정 후보를 사용자가 선택한다. 충돌 그룹마다 상호 배타적 해소안을 선택지로
  제시하고 "Leave unchanged"를 포함한다 (`:243`).
- 배치 단위 skip 선택지도 항상 포함한다 (`:246`). 다만 이것을 임계값 미달 수락으로
  취급하지 않는다 — 그것은 별도의 명시적 선택이어야 한다.
- 확장 제안과 수렴 제안의 비율을 사용자에게 정보로 보여 준다 (`:233`,
  `Balance: 4 expand / 2 sharpen / 1 remove`). 경고가 아니라 정보이며 "both
  directions are legitimate; the user decides what mix to accept".

Python core에 approval 객체가 없다는 §7의 관찰은 여전히 사실이다. 승인의 실체가
skill 계층의 절차로만 존재하고 상태로 남지 않는다는 점이, Mission Control이 승인을
1급 상태로 만든 [ADR-0011](../adr/0011-brief-deliberate-divergences.md)
Divergence 2의 근거를 Seed에서도 반복 확인해 준다.

## 10. Granularity는 QA quality bar에 들어 있다

> **2026-08-07 정정.** §3.3에서 "코드에서 검사하지 않고 프롬프트 지시로만
> 존재한다"고 기록했으나, 실제 강제 경로를 놓친 서술이었다.

`skills/seed/SKILL.md:130`의 `quality_bar` 문자열이 §3.3의 granularity contract를
**그대로 포함한다.**

> "acceptance_criteria must also be parsimonious in the ontological sense: a
> criterion names a state of the finished work a user can see is true, while an
> implementation step names a means of reaching it, and only the first belongs in
> the list. Read each criterion beside its siblings — one intelligible only as a
> move toward a sibling is that sibling's means and belongs merged into the
> outcome it serves, and **flagging that is as important as flagging a missing
> piece**, since it commits the seed to an unverified path."

즉 판정 주체는 Python 코드가 아니라 **QA judge**이며, 매 반복마다 이 기준으로
채점된다. 같은 quality bar가 요구하는 다른 항목도 함께 있다 — 내부 일관성,
측정·테스트 가능한 acceptance_criteria, 모호한 표현 없는 구체적 constraints,
goal/criteria가 참조하는 모든 엔티티를 덮는 ontology_schema, 필드 간 모순 없음.

## 11. 아직 조사하지 않은 것

추출 프롬프트(`agents/seed-architect.md`)는 2026-08-07에 전문을 읽었다(§3.2·§3.3·
§3.4). 남은 항목은 다음과 같다.

- ~~Seed revision lineage와 `parent_seed`의 의미~~ **2026-08-09 해소.**
  `parent_seed_id`는 `SeedMetadata`의 선언 필드(`core/seed.py:411`)이고
  소비자는 **진화 루프**다 (`evolution/loop.py:444·469·1036·1072`,
  `evolution/projector.py:97`). 즉 **mission 간** lineage 축이며, 우리
  Blueprint의 revision 정수 + `brief_revision` lineage(ADR-0021 §2)와 축이
  다르다 — mission 간 축은 [Open Questions §10](./OPEN_QUESTIONS.md)
  (Phase 10 Reflect/Evolve) 소관이다.
- ~~`GradeGate`가 등급을 실제로 어떻게 소비하는지~~ **2026-08-09 해소 —
  A만 통과다.** `auto/grading.py:488`: `may_run = grade == SeedGrade.A and
  not blockers`. 등급은 결정적으로 매겨진다 — blocker가 있으면 C(`:470-472`),
  repairable finding이 있으면 B(`:481`), 둘 다 없으면 A. 모듈 docstring도
  *"Deterministic A-grade gate"*, 클래스 docstring도 *"prevents B/C Seeds
  from running"*이다.

  채점은 **LLM이 아니라 계산**이다 (`:127-157`): `GapDetector`가 찾은
  gap을 repairable 여부로 finding/blocker에 나누고,
  `coverage = 1 - (open_gaps / 10)`, `ambiguity = 1 - coverage`,
  `risk = 0.05×가정수 + 0.15×blocker수`, `testability`는
  `acceptance_criteria`가 open gap이면 0.85→0.4로 떨어진다.

  **함의**: upstream의 Seed 품질 방어는 **두 층**이다 — LLM 채점(우리
  ADR-0019 QA의 대응물)과 이 결정적 gate. 우리에겐 구조 검사(`check_scope`)만
  있고 점수화된 결정적 층이 없다. 위치는 `auto/`, 즉 **합성 계층 소유**이며
  (CLI findings §2) 우리 대응 층은 Phase 8이다 — 사용자 결정 2026-08-09로
  Phase 8에 배치했다 ([Open Questions §3](./OPEN_QUESTIONS.md)).
- ~~`SeedRepairer.converge`의 bounded stop 조건~~ **2026-08-09 해소 —
  횟수다.** `auto/seed_repairer.py:229-262`: `len(history) >=
  max_iterations`면 최근 리뷰본을 반환하며, docstring이 이유를 말한다 —
  *"the upper bound the pipeline relies on to prevent unbounded LLM cost
  when the reviewer keeps producing the same finding."* 우리 QA 상한 5회
  (ADR-0019)와 같은 축이다.

  부수 규칙 둘: ① 상한이 **repair 직후**에 걸리면 캐시된 review가 수리 전
  seed를 설명하므로 최종 재검토를 정확히 1회 더 한다(stale review가 고쳐진
  seed를 막지 않도록). 우리는 매 revision을 채점하므로 이 문제가 구조적으로
  없다. ② `cancel_event`로 협조적 취소 — 다음 iteration 경계에서
  `RepairCancelled`. 우리 취소 경로는 Phase 7이다.
- ~~`SeedMetadata`가 보존하는 항목 전체~~ **2026-08-08 해소.** 선언 필드는
  `core/seed.py:367-416`의 11개(seed_id, version, created_at, ambiguity_score,
  interview_id, parent_seed_id, generation_mode, degraded, unresolved_slots,
  recovery_reason, decision_provenance). §12가 관측한 `qa_*` 키는 **선언되지
  않았다** — 세션이 `extra="allow"`로 붙인 것. ADR-0019 §8에 반영
- `InvestmentSpec`의 용도
- ~~`agents/seed-closer.md` — §12가 관측한 Seed 직전 closure 감사~~
  **2026-08-08 해소 → §13.** 여섯 축은 규정이며, 위치는 Seed 생성이 아니라
  interview 종료 gate다
- ~~`skills/seed/SKILL.md`의 best attempt 추적 문구 전문~~ **2026-08-08
  해소.** `:113` "Track the highest-scoring seed across all iterations" —
  동점 규칙 없음 확정. ADR-0019 §5에 반영
- 2,637줄 파싱 계층이 방어하는 실패 목록 (구조화 출력을 쓰는 우리에게 어디까지
  해당하는지)
- `ooo seed` 진입이 interview score를 다시 강제하는지
  ([Brief Guide](../05_BRIEF.md) §3의 미조사 항목)

위 항목은 Blueprint use case와 QA 루프를 설계하기 직전에 조사한다.

## 12. 런타임 관측 — v0.50.8 도그푸딩 세션 1회

> **Evidence level: Observed.** 소스가 아니라 실행 전사에서 읽은 것이다. 같은
> baseline 버전(0.50.8)이지만 **skill이 LLM으로 구동되므로 관측된 동작이 곧
> 규정은 아니다.** 규정 여부를 확인한 항목만 그렇게 표시한다.
>
> 출처: 사용자가 제공한 `ooo interview` → `ooo seed` 전체 세션 전사
> (2026-08-07, 대상 프로젝트 `ratatouille`).

### 12.1 기존 기록을 확인해 준 것

| 관측 | 확인된 기록 |
|---|---|
| `ooo interview` 종료값은 `ambiguity 0.12`, QA 점수 없음. QA는 `generate_seed` **이후**에 시작 | §8 — QA는 Seed에 붙고 Brief에는 붙지 않는다 |
| 생성된 seed YAML에 최상위 `non_goals` 키가 없고 "비목표: …"가 `constraints` 항목으로 들어감 | §2 — 방향으로 취급되나 스키마에 선언되지 않음 |
| QA REVISE 뒤 `generate_seed`를 재호출하지 않고 YAML을 직접 편집 | §8 — "첫 생성은 정확히 한 번" |
| 수정 후보를 사용자가 선택. `Balance: 4 expand / 2 sharpen / 1 remove / 1 correct` 형식으로 제시 | §9 — User Adoption Gate |
| 채점 축 5개, `Domain Specific 0.74 → 0.90` | §8 — 다섯 축 |

### 12.2 새로 확인한 것

**`ouroboros_generate_seed`는 완결된 MCP interview session을 요구한다.** 파일
경로로 부를 수 없다. 폴백 모드로 진행한 인터뷰는 DB에 남지 않아(`events = 0`)
seed를 만들 수 없었고, 인터뷰를 MCP 모드로 다시 돌려야 했다. 즉 Seed 생성의
입력은 **저장된 Brief 상태**이며 자유 입력이 아니다 —
[ADR-0016](../adr/0016-brief-handoff-projection.md)의 handoff 강제와 같은 방향이다.

**QA judge는 이미 core 계층(MCP 도구 `ouroboros_qa`)에 있고, skill이 갖는 것은
루프 제어뿐이다.** §8이 "QA 루프가 skill 계층에 있다"고 한 것은 정확하지만,
채점 자체는 core에 있다. 즉 Mission Control의
`BlueprintQaJudge` port + `QaLoopState` 분리는 upstream의 분해선과 같고,
[ADR-0019](../adr/0019-blueprint-qa-loop.md)의 divergence는 **루프만 옮기는
것**이지 채점자를 옮기는 것이 아니다.

**skill 계층 QA의 결과가 store로 돌아가지 않는다.** 관측된 세션은 QA를 5회 돌려
seed를 v1.0.0 → v1.5.0으로 고쳤는데, MCP store에는 **v1.0.0(생성 직후 초안)이
남았고** 개정본은 파일에만 존재했다. `ooo run`은 store를 읽으므로 실행하려면
`seed_path`로 파일을 따로 지정해야 한다. 이것은 ADR-0019 §1이 QA를 Core에 두기로
한 근거(Constitution §6.5)를 원칙이 아니라 **실측으로** 뒷받침한다 — surface마다
state가 갈라지면 실행 엔진이 승인되지 않은 초안을 읽는다.

**총점 동점은 축 점수로 갈렸다.** 궤적은 `0.81 → 0.87 → 0.88 → 0.87 → 0.88`이고
3회차와 5회차가 동점이었다. 세션은 5회차를 채택하며 근거를 "차원별로는 이전
최고보다 낫다 — Correctness 0.85 → 0.90"이라고 밝혔다.

> ⚠️ `skills/seed/SKILL.md`는 "최고 점수를 best attempt로 추적한다"까지만 말하고
> **동점 규칙을 규정하지 않는다** (§8 조사 범위에서 확인). 따라서 이 관측은
> 규정이 아니라 1회 실행의 판단이다. Mission Control은 이 관측을 채택했다
> ([ADR-0019](../adr/0019-blueprint-qa-loop.md) §5) — 반대 방향의 규칙을 근거
> 없이 유지하는 것보다 관측된 동작을 따르는 편이 divergence를 줄이기 때문이다.

**임계 미달 수락이 산출물에 기록된다.** 관측된 seed metadata:

```yaml
qa_best_score: 0.88
qa_threshold: 0.9
qa_iterations: 5
qa_accepted_below_threshold: true
```

> 2026-08-08 소스 확인: 이 키들은 `SeedMetadata`에 **선언되어 있지 않다**
> (`core/seed.py:367-416`). 세션이 `extra="allow"`(§2)로 임의로 붙인 것이다.
> Mission Control은 **이 산출물 형태가 아니라 필요성**을 채택했다 — 어디에
> 담을지는 [ADR-0019](../adr/0019-blueprint-qa-loop.md) §8이 정한다.

**Seed 생성 직전에 closure 감사가 있다.** 여섯 축(소유권/SSoT, lifecycle·복구,
마이그레이션, cross-client, API 계약, 검증)을 점검하고 1건이 blocking으로 걸려
질문이 한 번 더 나갔다. `agents/seed-closer.md`가 대응 위치로 보이나 소스를
확인하지 않았다. §11에 조사 항목으로 추가한다.

### 12.3 Stage→Runtime 바인딩이 조용히 우회됐다

> 같은 세션의 후속 관측. **이것은 Execute(Phase 3)와 MCP surface(Phase 7)에
> 해당하므로 지금 결정하지 않고 기록만 남긴다.** 결정 항목은
> [Open Questions](./OPEN_QUESTIONS.md) §4·§5·§8에 등록했다.

사용자는 config에 실행 단계 Runtime을 지정해 두었다.

```yaml
orchestrator:
  runtime_profile:
    stages:
      interview: claude
      execute:   codex      # ← 구현은 codex가 한다
      evaluate:  claude
      reflect:   codex
```

`codex-cli 0.146.1`이 설치되어 있고 정상 호출된다. 그런데 실제 구현은 **Claude
세션이 자기 편집 도구로 직접 수행했다.** 서버 파이프라인과 클라이언트 트랙까지
세 단계가 커밋된 뒤에야 사용자가 알아챘다.

원인은 어느 한 계층의 버그가 아니라 **계층 사이의 빈칸**이다.

| 계층 | 아는 것 | 모르는 것 |
|---|---|---|
| config | 어느 Stage를 어느 Runtime이 맡는지 | 그 매핑이 실제로 조회됐는지 |
| orchestrator (`ooo run`) | 매핑을 읽고 CLI를 띄운다 | 자기가 호출되지 않은 경우 |
| skill/session | Seed 이후 무엇을 할지 사용자와 정한다 | config에 그런 매핑이 있다는 사실 |

`stages.execute`는 orchestrator가 호출될 때만 조회된다. 세션이 "직접 구현"
경로를 제안하고 사용자가 그것을 고르면 orchestrator는 아예 실행되지 않으므로,
매핑은 **무시된 것이 아니라 조회되지 않는다.** 경고도, Telemetry도, Gate도
없다. 사용자가 묻지 않았으면 끝까지 몰랐을 상태다.

**이것은 §12.2의 store 미반영과 같은 실패 유형이다.** 그쪽은 skill이 만든
*state*를 core가 모르는 것이고, 이쪽은 skill이 만든 *작업*을 core가 모르는
것이다. 둘 다 "가장 강한 관문이 skill 계층에 있다"(§8)의 대가다 — 관문이 있는
계층은 결과를 소유하지 않고, 결과를 소유한 계층은 관문을 갖지 않는다.

**두 결함이 겹치는 지점도 관측됐다.** 세션은 codex로 넘길 때의 주의사항을 이렇게
말했다 — store의 seed는 v1.0.0이고 QA로 다듬은 v1.5.0은 파일에만 있으므로
`seed_path`를 명시하지 않으면 codex가 열등한 버전을 읽는다. 즉 §12.2의 state
분기는 가설이 아니라 **다음 Stage가 잘못된 산출물을 조용히 소비하는** 결과로
이어진다.

#### Mission Control에 같은 구멍이 있는가

`mcx execute` CLI는 Runtime port를 거치도록 설계되어 있어 자기가 코드를 쓸 수
없다 ([ADR-0003](../adr/0003-runtime-abstraction.md),
[Architecture](../01_ARCHITECTURE.md) §7.1). **그러나 MCP surface(Phase 7)에서는
host가 에이전트다.** 그 세션은 `mcx` 도구와 자기 편집 도구를 동시에 갖는다 —
관측된 상황과 정확히 같은 조건이다.

[ADR-0004](../adr/0004-stage-scoped-minimum-capability.md)는 이것을 덮지 않는다.
그 ADR이 막는 것은 **위임받은 worker가 위로 탈출하는 것**(Mission Control 재귀
호출, 자기 승인)이고, 관측된 것은 반대 방향 — **통제하는 쪽이 worker의 일을
직접 하는 것**이다.

[ADR-0005](../adr/0005-evidence-over-reasoning.md)의 "Telemetry를 참조하는
Gate만 진행을 결정한다"가 재료는 준다. Execute를 거치지 않았으면 Execute
Telemetry가 없다. 하지만 **Execute Telemetry 없이 나타난 작업을 Verify가 어떻게
다루는지는 아직 정하지 않았다.**


## 13. Closure gate — Brief의 출구 감사

> Checked: 2026-08-08 (동일 baseline clone). Evidence level: **Verified.**
> §12가 관측으로 남긴 closure 감사의 소스 확인이다.

### 13.1 타이밍 — Seed 생성 단계가 아니라 interview의 출구다

§12는 이것을 "Seed 생성 직전"으로 기록했는데, 소스 기준의 정확한 위치는
**interview 종료 gate**다. `skills/interview/SKILL.md` step 8 "Seed-ready
Acceptance Guard": MCP가 seed-ready를 신호해도 **완료 선언과 `ooo seed` 제안
전에** 감사를 통과해야 하고, 통과 후에도 restate gate(step 9)를 거쳐야 한다.

강제는 두 겹이다.

- **MCP 계층**: `mcp/tools/subagent.py:1213-1218`이 인터뷰어 프롬프트에
  "Seed-ready Guard"를 삽입한다 — "Do not treat ambiguity <= 0.2 as
  sufficient for closure."
- **skill 계층**: step 8이 3-lane fan-out 감사를 규정한다
  (tri-panel builder는 `subagent.py:2656`, 합성은 `:2732`).

### 13.2 판정 철학과 여섯 축

`agents/seed-closer.md:13` — **"Treat a low ambiguity score as permission to
audit closure, not permission to close."** 점수는 감사의 자격이지 종료의
자격이 아니다.

판정 기준은 하나다: 남은 미해결 사항이 구현을 **실질적으로(materially)**
바꾸는가. 여섯 축(ownership/SSoT, protocol/API contract, lifecycle/recovery,
migration, cross-client impact, verification)은 그 기준의 점검표이며,
**brownfield 또는 system-level 작업에 한해** 적용한다 (`:15`, `:27`).

gate는 양방향이다 — 너무 이른 종료만이 아니라 과잉 인터뷰도 거부한다
(`:31-34` "Reject Over-Interviewing": 새 질문이 문구 다듬기만 낳으면 이미
끝난 것).

### 13.3 3-lane 구조와 결정적 합성

- `closer` — seed-closer 기준 적용. **이 lane의 판정만 gate다.**
- `contrarian` — 숨은 가정, 건너뛴 결정 공격. HIGH 심각도만 차단.
- `gap_hunter` — 빠진 요구, 검증 불가 AC 사냥. HIGH 심각도만 차단.

합성은 결정적이다: closer가 `seed_ready`가 아니면 차단, 다른 lane은 HIGH만
차단, 차단 시 "MCP says seed-ready, but I am not accepting it yet because
\<gap\>"으로 명시적으로 신호를 뒤집고 가장 임팩트 큰 blocking 질문 하나를
던진다. 병렬 primitive가 없으면 closer 단일 실행이 공식 fallback이다.

§12의 관측(6축 표, 검증 축 blocking)은 이 규정의 실행으로 확인됐다.

### 13.4 Mission Control 함의 — 결정의 소속이 바뀐다

이 감사의 대응물은 **Blueprint 단계가 아니라 Brief Gate(CLEAR 판정)의
확장**이다. 우리 Gate는 결정적(정책 점수 + 승인)인데, upstream은 "점수
충족은 필요조건일 뿐"이라는 판단 감사를 그 위에 얹는다. 도입 여부·형태
(별도 assessor port인지, 기존 clarity 평가의 확장인지)는 결정하지 않았다 —
[Open Questions §2](./OPEN_QUESTIONS.md#2-brief-decisions)에 등록한다.
BlueprintService 설계를 막지 않는다.
