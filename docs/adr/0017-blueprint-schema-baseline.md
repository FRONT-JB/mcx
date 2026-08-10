# ADR 0017 — Blueprint schema baseline과 acceptance criterion identity

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 1 (Specification before execution), Principle 3 (Evidence over reasoning), §17 (Scope와 Reasoning Discipline)
- Upstream evidence: [SEED_UPSTREAM_FINDINGS.md](../research/SEED_UPSTREAM_FINDINGS.md)

> **Phase 10 partial supersession (2026-08-10).** 이 ADR이 소비자 부재를 이유로
> 유예한 `ontology_schema`는 Wonder/Reflect가 실제 소비자가 되어
> [ADR-0051](./0051-evolve-successor-blueprint-contract.md) §3에서 도입하기로 했다.
> 나머지 방향 필드·`extra="forbid"`·content-key 결정은 유지된다.

## Context

[Brief handoff](./0016-brief-handoff-projection.md)가 Blueprint의 입력으로
고정되었으므로, 그 입력의 무엇이 Blueprint의 어느 필드가 되는지 정해야 한다.

upstream `core/seed.py`의 `Seed`는 goal, task_type, brownfield_context,
constraints, acceptance_criteria, ontology_schema, evaluation_principles,
exit_conditions, metadata를 가진다. 조사에서 두 가지가 드러났다.

1. **`non_goals` 필드가 없다.** `seed_generator.py` 전체에 `non_goal`이 한 번도
   등장하지 않는다. 그러나 `Seed`는 `extra="allow"`이고
   `evolution/loop_support.py:1028`이 `approved.to_dict().get("non_goals")`로
   읽어 방향 보존 검사에 사용한다. 즉 non_goals는 **방향(direction)의 일부로
   취급되면서 스키마에 선언되지 않은** 상태다.
2. **acceptance criterion의 identity가 위치가 아니라 내용이다.**
   `derive_semantic_ac_key` (`core/seed.py:610-633`)가 description,
   verify_command, expected_artifacts, output_assertion을 정렬된 JSON으로 직렬화해
   SHA-256의 앞 16자를 취한다. docstring이 의도를 밝힌다 — "digest intentionally
   excludes list position, runtime/session identity, and volatile Seed metadata".

## Decision

### 1. v1 Blueprint는 방향(direction)만 담는다

| 필드 | 근거 |
|---|---|
| `mission_id`, `revision`, `brief_revision` | 승인 lineage. 어느 Brief revision에서 나왔는지 없으면 재승인 판정이 성립하지 않는다 |
| `goal` | upstream `Seed.goal` |
| `constraints` | upstream `Seed.constraints` |
| `non_goals` | 아래 §3 |
| `acceptance_criteria` | upstream `Seed.acceptance_criteria` |

`ontology_schema`, `evaluation_principles`, `exit_conditions`,
`brownfield_context`, `task_type`, `metadata`는 **유예한다.** 앞의 셋은
Ouroboros의 evaluate/reflect 진화 루프가 쓰는 구조이며, Mission Control에서
대응 필요가 생기는 시점은 Verify(Phase 4)다. 나머지는 아직 대응 개념이 없다.

> **2026-08-08 시한 재평가 (Phase 4 종료 검토)**: Phase 4 Verify는
> `exit_conditions` 없이 완성되었다 — 핵심 조건("필수 AC가 모두 Verify에서
> 만족")은 Gate의 AC 전수 요구가 이미 덮는다. 남는 조건들(project test/build
> 통과, 사용자 acceptance)은 각각 repo 수준 명령 층(ADR-0028 §2 보류)과
> 사용자 surface에 종속되므로, 유예 시한을 그 도입 시점으로
> 옮긴다 ([ADR-0029](./0029-verify-deliberate-divergences.md) 보류 등록).
>
> **2026-08-09 시한 확정**: repo 명령 층은 여전히 로드맵 미배치이고, 사용자
> acceptance는 **Phase 9 실사용 진입**이다. Phase 6 CLI는 비대화형 단발이라
> acceptance 표면을 만들지 않았다 (원래 표기 "Phase 6·7"의 6은 소진됐다).

유예는 축의 변경이 아니라 필드 추가로 해소되므로 되돌리기 비싼 항목이 아니다
(`AGENTS.md` "되돌리기 비싼 결정" 목록 참조).

### 2. AC identity는 성공 계약의 내용 digest다

`key = "ac_" + sha256(정렬된 JSON(description, verify_command, expected_artifacts,
output_assertion))[:16]`. upstream과 같은 payload, 같은 알고리즘, 같은 길이다.

**위치로 식별하지 않는 이유**가 이 결정의 전부다. 목록 인덱스로 식별하면 AC를
중간에 하나 끼워 넣는 순간 이후 AC들이 다른 계약의 증거를 물려받는다. Execute의
결과와 Verify의 증거는 "3번 AC"가 아니라 "이 계약"에 붙어야 한다.

따라서 다음이 성립한다.

- 계약이 같으면 revision과 재시도를 건너 같은 key다.
- 계약의 어느 필드든 바뀌면 새 key이며, 이전 AC의 증거를 상속하지 않는다.
- `expected_artifacts`의 순서도 계약의 일부다. 정렬해서 정규화하지 않는다 —
  계약을 시스템이 임의로 해석하지 않기 위해서다.

upstream은 이 값을 필드로 저장하고(`semantic_ac_key`) 없으면 파생한다. Mission
Control은 **저장하지 않고 항상 파생한다.** 저장하면 계약과 key가 어긋날 수 있고,
어긋났을 때 어느 쪽이 진실인지 판정할 근거가 없다.

### 3. Divergence — `non_goals`를 선언한다

**upstream**: `Seed`에 선언되지 않았고 `extra="allow"` 덕에 실릴 수 있다. 방향
보존 검사는 `to_dict().get("non_goals")`로 방어적으로 읽는다.

**Mission Control**: `non_goals`를 1급 필드로 선언한다.

**근거**: [ADR-0016](./0016-brief-handoff-projection.md)의 handoff가 이미
`non_goals`를 칸으로 담고 있고, upstream 자신도 이 값을 방향의 일부로 다룬다
(`preserve_non_goals`, `is_non_relaxing`). 선언되지 않은 채 방향으로 취급되는
상태는 "무엇이 승인 대상인가"를 스키마로 답할 수 없게 만든다.

### 4. Divergence — 선언되지 않은 필드를 금지한다

**upstream**: `Seed.model_config = {"extra": "allow"}` — "Extra fields are
reserved for plugin-owned, structured handoff data".

**Mission Control**: `extra="forbid"`.

**근거**: [ADR-0002](./0002-approved-seed-is-immutable.md)는 승인된 Blueprint를
불변으로 규정한다. 승인의 의미는 "사용자가 이 내용을 보았다"인데, 검토 경로를
거치지 않은 내용이 불변 산출물에 실릴 수 있으면 그 의미가 성립하지 않는다.
plugin 확장이 실제로 필요해지면 그때 명시적 확장 필드를 설계한다.

### 5. 검증 불가능한 AC를 금지하지 않고 드러낸다 — upstream과 같다

`verify_command`, `expected_artifacts`, `output_assertion`은 모두 선택이며 셋 다
없는 AC가 허용된다. **upstream도 같다** — `AcceptanceCriterionSpec`의 세 필드가
모두 `default=None`/빈 튜플이고, 최소 하나를 요구하는 검증기가 없다
(`core/seed.py:452-476`).

Mission Control은 여기에 조회 수단만 더한다. 셋 다 없으면
`is_mechanically_verifiable`이 거짓이고 `Blueprint.unverifiable_criteria`로
조회된다. 금지하지 않는 이유는 기계적으로 확인할 수 없는 수용 기준이 실제로
존재하며, 금지하면 작성자가 형식만 채우는 `verify_command`를 만들어 넣기
때문이다. Gate에서 어떻게 다룰지는 Blueprint의 QA 정책이 정한다.

### 6. `output_assertion`은 `verify_command`를 요구한다

검사할 출력을 만드는 것이 `verify_command`이므로, 명령 없는 `output_assertion`은
무엇과도 대조되지 않는다. **검증 수단이 있는 것처럼 보이면서 아무것도 확인하지
않는 AC**가 되며, 이는 수단이 아예 없는 AC보다 나쁘다 — 없다는 사실이 드러나지
않기 때문이다.

upstream은 이를 스키마 검증기(`core/seed.py:480-497`,
`"output_assertion requires verify_command"`)와 실행 시 verify gate
(`orchestrator/parallel_executor.py:9651-9657`) 두 곳에서 강제한다. Mission
Control은 스키마 단계에서 강제한다.

### 7. "success contract 보유"의 판정 기준 — 셋 중 하나

upstream `orchestrator/shadow_replay.py:622`는
`has_success_contract = bool(ac_spec.verify_command)`로 **`verify_command`만**
본다. Mission Control의 `is_mechanically_verifiable`은 셋 중 하나라도 있으면
참이다.

**2026-08-07 해소.** 생성 프롬프트 `agents/seed-architect.md:77`이 이유를
밝힌다 — "Exit-code 0 is already verified separately by the runner." 명령이
있으면 종료코드 검사가 자동으로 따라오므로 **명령 자체가 완결된 계약**이다.
같은 프롬프트가 "File or directory existence can be a complete contract"(`:72`)
라고도 하므로 `expected_artifacts`만 있는 경우도 완결된 계약이다.

따라서 셋 중 하나 기준은 유지한다. 다만 Mission Control에는 아직 **"명령의
종료코드를 검사한다"는 개념 자체가 없다.** Verify(Phase 4)가 verify_command를
실제로 실행할 때 종료코드 검사를 기본 동작으로 넣어야 하며, 그 전까지
`is_mechanically_verifiable`은 "확인 수단이 적혀 있다"까지만 뜻한다.

## Consequences

### Positive

- 증거가 AC 계약에 묶이므로 목록 편집이 증거 귀속을 흔들지 않는다.
- 승인 대상이 스키마로 답해진다. 승인 화면에 없던 내용이 실릴 수 없다.
- Blueprint revision과 Brief revision이 분리되어 lineage를 추적할 수 있다.
- v1 스키마가 작아 Blueprint 생성 계약을 먼저 검증할 수 있다.

### Cost

- upstream Seed의 필드 다섯 개가 없어 이 지점의 1:1 대조가 성립하지 않는다.
- `key`를 저장하지 않으므로 조회할 때마다 digest를 계산한다.
- `extra="forbid"`는 upstream 확장을 그대로 실을 수 없게 한다.
- `expected_artifacts` 순서가 계약이므로 같은 산출물 집합을 다르게 적은 AC가
  다른 identity를 갖는다.
- **upstream의 `verify_command` 한 줄 검사가 없다**
  ([SEED_UPSTREAM_FINDINGS](../research/SEED_UPSTREAM_FINDINGS.md) §3.1 —
  여러 줄·heredoc 거부, `python -c`/`pytest` 안내). 여러 줄 명령은 runner의
  종료코드 판정을 흐리므로 upstream은 생성 시점에 거부한다. 명령이 실제로
  실행되는 것은 Verify(Phase 3~4)이므로 그 설계와 함께 도입한다 — 이 검사가
  schema 검증인지 QA issue인지도 그때 정한다. (2026-08-08까지 보류가 기록되지
  않은 상태였다.)

## Rejected alternatives

- **AC를 목록 인덱스로 식별**: 중간 삽입이 증거 귀속을 조용히 옮긴다.
- **AC identity를 저장**: 계약과 key가 어긋날 수 있고 어느 쪽이 진실인지 판정할
  근거가 없다.
- **`expected_artifacts`를 정렬해 정규화**: 같은 집합을 같은 계약으로 보는 것이
  편하지만, 계약을 시스템이 해석하는 것이며 근거가 없다. 필요해지면 명시적
  결정으로 도입한다.
- **`extra="allow"`로 upstream을 그대로 따름**: ADR-0002의 승인 의미와 충돌한다.
- **`ontology_schema` 등을 지금 포함**: Verify가 요구하기 전에는 채울 근거가
  없고, 빈 구조를 승인 대상에 넣으면 승인의 의미가 흐려진다.

## Verification

- 같은 계약은 위치와 무관하게 같은 key를 갖고, 계약이 바뀌면 새 key를 받는다.
- 선언되지 않은 필드를 담은 Blueprint 생성이 거부된다.
- 검증 수단이 없는 AC가 `unverifiable_criteria`로 드러난다.
- 명령 없는 `output_assertion`이 거부된다.
- Blueprint가 어느 Brief revision에서 나왔는지 보존한다.
