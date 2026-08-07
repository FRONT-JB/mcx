# Seed Upstream Findings — Blueprint 대응 조사

> Baseline: `Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943` (v0.50.8)<br>
> Checked: 2026-08-07 (local clone, 해당 commit checkout)<br>
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

- Seed revision lineage와 `parent_seed`의 의미
- `GradeGate`가 등급을 실제로 어떻게 소비하는지 (A만 통과인지, B도 조건부인지)
- `SeedRepairer.converge`의 bounded stop 조건 (횟수인지 등급 정체인지)
- `SeedMetadata`가 보존하는 항목 전체
- `InvestmentSpec`의 용도
- 2,637줄 파싱 계층이 방어하는 실패 목록 (구조화 출력을 쓰는 우리에게 어디까지
  해당하는지)
- `ooo seed` 진입이 interview score를 다시 강제하는지
  ([Brief Guide](../05_BRIEF.md) §3의 미조사 항목)

위 항목은 Blueprint use case와 QA 루프를 설계하기 직전에 조사한다.
