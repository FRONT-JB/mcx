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

## 5. 아직 조사하지 않은 것

- Seed 생성 프롬프트의 추출 계약과 QA/refinement 루프
- `InvestmentSpec`의 용도
- `SeedMetadata`가 보존하는 항목 전체
- Seed revision lineage와 `parent_seed`의 의미
- `ooo seed` 진입이 interview score를 다시 강제하는지
  ([Brief Guide](../05_BRIEF.md) §3의 미조사 항목)

위 항목은 Blueprint 생성 계약을 설계하기 직전에 조사한다.
