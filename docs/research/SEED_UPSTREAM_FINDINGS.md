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

## 5. 아직 조사하지 않은 것

- Seed 생성 프롬프트의 추출 계약과 QA/refinement 루프
- `InvestmentSpec`의 용도
- `SeedMetadata`가 보존하는 항목 전체
- Seed revision lineage와 `parent_seed`의 의미
- `ooo seed` 진입이 interview score를 다시 강제하는지
  ([Brief Guide](../05_BRIEF.md) §3의 미조사 항목)

위 항목은 Blueprint 생성 계약을 설계하기 직전에 조사한다.
