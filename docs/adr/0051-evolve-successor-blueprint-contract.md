# ADR 0051 — Evolve가 같은 Mission의 후속 Blueprint 세대를 제안한다

- Status: Accepted
- Date: 2026-08-10
- Constitutional basis: Constitution §5 Mission, §6.1 User authority,
  Principle 2 (Workflow before model), Principle 5 (No self-approval),
  Principle 7 (Durable state), [ADR-0002](./0002-approved-seed-is-immutable.md)
- Upstream evidence:
  [EVOLVE_UPSTREAM_FINDINGS](../research/EVOLVE_UPSTREAM_FINDINGS.md), pinned
  Ouroboros `9486c78575a0332e9b84d93ef5832985291d7943`, focused tests 13 passed
- Supersedes in part:
  [ADR-0017](./0017-blueprint-schema-baseline.md) ontology 유예,
  [ADR-0019](./0019-blueprint-qa-loop.md)·
  [ADR-0021](./0021-blueprint-state-and-revisions.md) Mission 전체 QA 예산

## Context

Phase 10 조사로 Gen 2+의 실제 연결은 확정됐다.

```text
Seed_n + Execute_n + Evaluate_n
  -> Wonder
  -> Reflect
  -> Seed_n+1(parent_seed_id=Seed_n)
  -> Execute_n+1
  -> Evaluate_n+1
```

Reflect는 Blueprint(Seed)를 없애지 않는다. Gen 1의 Brief(Interview)가 하던
**다음 Blueprint 입력 생산**을 대신한다. 따라서 현재
`BlueprintService.generate`의 Brief 전용 경로 옆에 두 번째 생산자가 필요하다.

처음에는 후속 Seed를 새 Mission으로 옮기는 안을 검토했다. 그러나 Mission은
"하나의 Goal을 Brief부터 최종 Verify까지" 추적하는 단위이고, Verify `HOLD`인
Mission은 아직 `ACTIVE`다. 실패할 때마다 Mission을 새로 만들면 같은 Goal의
attempt·승인·evidence가 여러 Mission으로 갈라진다. 반대로 Verify `CLEAR` 뒤의
Mission은 `COMPLETE` terminal이라 다시 열 수 없다. 후속 세대가 놓일 자리는
**Verify `HOLD` 뒤 같은 Mission의 새 Blueprint revision** 하나뿐이다.

기존 네 질문(Brief 없는 생성, 자동 생산자, 승인 권위, AC identity)을
구현 가능한 계약으로 좁히자 두 전제가 더 드러났다.

1. Wonder는 ontology를 필수 입력으로 쓴다. ADR-0017에서 소비자가 없어 유예한
   `ontology_schema`는 이제 소비자가 생겼다.
2. 현재 QA 5회 예산은 Mission 전체다. Gen 1에서 5회를 쓴 뒤 Evolve가 revision을
   만들면 Gen 2는 첫 QA조차 할 수 없다. 수동 편집으로 예산을 우회하지 못하게
   하면서도 세대는 열 수 있는 별도 축이 필요하다.

또 pinned source의 `generate_from_reflect` docstring에는 *"Mechanical AC
contracts cross only explicit keeps"*라고 적혀 있으나, 실제 구현
`evolve_acceptance_contracts`와 focused tests는 explicit `revise`도 같은 parent의
`verify_command`·artifact·assertion을 보존하고 semantic key만 새로 만든다. 이
ADR은 주석이 아니라 실행 코드와 테스트를 따른다.

## Decision

### 1. Evolve는 새 Stage도 새 Mission도 아니다

canonical Stage 다섯 개는 바꾸지 않는다. `wondering`·`reflecting`·`seeding`은
Blueprint의 후속 revision을 만드는 내부 checkpoint이며 `current_stage` 값이
아니다.

Evolve 제안의 진입 조건은 다음 전부다.

- Mission은 `ACTIVE`이고 현재 Blueprint revision이 승인되어 있다.
- 그 정확한 revision의 Execute lineage와 Verify evidence·semantic verdict가 있다.
- 같은 입력으로 Verify Gate를 다시 계산한 결과가 `HOLD`다.
- 같은 parent revision에서 이미 후속 generation을 완료하지 않았다.

한 번의 Core 호출은 Wonder와 Reflect를 거쳐 **후속 Blueprint proposal 하나**를
durable하게 만든 뒤 Blueprint에서 멈춘다. 자동으로 QA를 통과시키거나 Execute를
시작하지 않는다.

```text
Verify HOLD (generation g, revision r)
  -> Wonder -> Reflect
  -> Blueprint generation g+1, revision r+1 (pending QA/approval)
  -> Blueprint HOLD
```

Verify `CLEAR`는 곧 `MISSION COMPLETE`이므로 Evolve 입력이 아니다. 완료 Mission을
다시 열지 않는다.

### 2. `revision`과 `generation`은 다른 축이다

- `revision`: Blueprint 내용이 바뀔 때마다 1씩 증가한다.
- `generation`: 승인된 Blueprint가 Execute→Verify를 지난 뒤 Evolve가 후속
  명세를 열 때만 1씩 증가한다.

예를 들어 Gen 1의 QA 보완이 revision 1→2→3을 만들고 revision 3이 실행·검증된
뒤 Evolve가 만든 첫 결과는 **generation 2, revision 4**다. Gen 2의 수동 QA
보완 revision 5도 generation 2다.

각 Blueprint revision은 `generation`을 가진다. Evolve가 연 첫 revision은
`evolved_from_revision`으로 Verify가 본 parent revision을 가리키고, 같은 세대의
수동 보완 revision은 그 값을 이어받는다. 안정적 세대 identity는
`(mission_id, generation)`이다.

### 3. ontology 최소 스키마를 Blueprint에 연다

ADR-0017의 ontology 유예를 이 ADR이 supersede한다. upstream의 최소 구조와 같은
세 필드만 도입한다.

```text
OntologySchema
  name
  description
  fields[]

OntologyField
  name
  field_type
  description
  required
```

Gen 1의 초기 ontology는 LLM이 발명하지 않는다. 승인된 Brief 요구사항의 경계를
뜻하는 고정 name/description과 빈 fields로 결정적으로 만든다. Evolve에서만
`add | modify | remove` mutation을 적용한다. ontology도 승인 대상 Blueprint의
일부이므로 revision과 함께 불변이며 QA·사용자 승인 전에는 실행 기준이 아니다.

### 4. Wonder/Reflect는 제안하고 application이 결정적으로 조립한다

Wonder 입력은 parent Blueprint(ontology 포함), 그 revision의 Execute result,
Verify evidence·semantic verdict를 application이 투영한 vendor-neutral
`EvolveSourceSnapshot`, 이전 Evolve lineage다. Wonder 질문은 자유 문자열로 두지
않고 parent AC에 대한 `challenge` 또는 Goal에 필요한 `gap`으로 grounding한다.

Reflect는 다음 후보만 반환한다.

- refined goal·constraints
- `keep | revise | add` AC patch
- ontology mutation
- reasoning과 settled AC 표시

LLM 응답의 AC index는 adapter 입력의 표시 좌표일 뿐이다. application 경계에서
즉시 parent AC의 content key로 바꾸고, durable patch는 그 key를 저장한다. Core는
목록 위치를 identity로 사용하지 않는다.

조립은 다음을 결정적으로 강제한다.

- parent AC마다 `keep` 또는 `revise`가 정확히 하나 있어야 한다.
- `add`는 끝에만 붙는다. `delete`와 reorder는 없다.
- Verify에서 통과했고 Wonder가 challenge하지 않은 AC는 강제로 `keep`한다.
- `keep`은 parent `AcceptanceCriterion` 전체를 그대로 복사한다.
- `revise`는 설명만 바꾸고, explicit parent key가 가리키는 mechanical contract
  (`verify_command`, `expected_artifacts`, `output_assertion`)를 그대로 이어받는다.
  설명이 내용 identity의 일부이므로 결과 key는 자동으로 새 값이 된다.
- `add`는 설명만 가진 새 AC다. 존재하지 않는 mechanical 계약을 Reflect가
  발명해 붙이지 않는다. QA·사용자 보완 뒤에도 확인 수단이 전혀 없으면 기존
  Blueprint Gate가 `HOLD`한다.

구체 실패 장면: AC 2 설명을 "429면 재시도한다"에서 "Retry-After와 jitter를
지킨다"로 바꾸면서 AC 1의 `pytest tests/idempotency.py`를 위치 2에 잘못 붙이면,
Verify는 다른 계약을 실행하고도 성공으로 읽는다. explicit parent key와
delete/reorder 거부가 이 재바인딩을 막는다.

### 5. 사용자 소유 방향은 Evolve가 자동 변경하지 않는다

upstream Reflect는 goal과 constraints를 refine한다. Mission Control에서 Goal,
Constraints, Non-goals는 사용자 소유의 hard boundary다. 따라서 최초 Evolve
조립은 세 필드를 parent와 **verbatim 동일**하게 요구한다.

- Reflect의 refined goal/constraints가 같으면 후속 revision을 만든다.
- 다르면 출력과 이유를 durable finding으로 남기고 revision을 만들지 않는다.
  Goal·Constraint 변경은 Brief에서 사용자 결정으로 확정한다.
- upstream에 없는 `non_goals`는 application이 parent에서 그대로 상속한다.

이는 등록된 divergence다. 후속 revision에 사용자 승인이 필요하다는 사실만으로
자동 생산자가 scope 변경안을 승인 대상으로 올려도 된다고 보지 않는다. 사용자가
보는 순간까지 untrusted proposal인 값과, 사용자 의도로 이미 고정된 경계를
구분한다.

### 6. Reflect와 QA는 승인할 수 없다

Evolve 결과는 `BlueprintState.revise`와 같은 불변 revision append를 사용하지만
생산자가 다르다. append 순간 이전 승인은 stale이 되고 다음을 모두 거쳐야 한다.

1. 구조 검사와 Evolve 불변식
2. Blueprint QA
3. 정확한 current revision에 대한 명시적 사용자 승인
4. Blueprint Gate `CLEAR`

upstream Gen 2+의 자율 진행과 의도적으로 다르다. Constitution §6.1과 No
self-approval을 유지하는 차이다. Reflect, QA judge, host 에이전트의 자연어
`approved`는 승인 근거가 아니다.

### 7. QA 예산은 세대별이며, 같은 세대의 revision들이 공유한다

ADR-0019·0021의 Mission 전체 5회 예산을 다음처럼 좁힌다.

- 한 generation 안의 최초 proposal과 수동 refinement revision은 QA 5회를 공유한다.
- 수동 `revise`는 generation을 올리지 않으므로 예산 우회가 되지 않는다.
- Verify `HOLD` evidence에서 Evolve가 다음 generation을 열면 그 generation의
  QA 예산은 0회부터 시작한다.
- `EXHAUSTED` 뒤 최종 수동 수정 1회와 미달 수락 규칙도 generation마다 적용한다.
- FAIL은 그 generation의 QA 루프만 닫는다. 후속 generation은 반드시 Verify
  evidence를 parent로 가져야 하므로 QA 실패만으로 새 generation을 열 수 없다.

이 구분이 없으면 Gen 1에서 5회를 쓴 Mission은 Gen 2 proposal을 만들 수는 있어도
평가·승인할 수 없어 영구 잠긴다. 반대로 revision마다 예산을 리셋하면 사용자가
`revise`를 반복해 무한 QA를 만들 수 있다.

### 8. 부분 진행과 lineage는 Blueprint 상태 문서 안에 보존한다

별도 event store를 도입하지 않는다. 현재 저장 구조는 mission당 한 Blueprint
JSON 문서가 revision·QA·승인을 원자적으로 보존한다(ADR-0021). 같은 문서에
`EvolutionRecord`를 추가한다.

타입의 소유자는 새 `domain/evolve` 패키지다. 이 패키지는 canonical Stage가 아니라
중립 proposal·checkpoint 모델이며 `domain.blueprint`·`domain.verify`·
`domain.execute`를 import하지 않는다. application이 세 domain 상태를 primitive와
Evolve-owned value object로 구성한 `EvolveSourceSnapshot`에 투영한다. Blueprint
state는 이 중립 record를 품을 수 있지만 `VerificationEvidence`나 Blueprint 모델을
Evolve 타입에 역참조하면 순환 의존이 생기므로 금지한다.

각 record의 최소 의미는 다음과 같다.

```text
successor_generation
parent_blueprint_revision
source_verify_sequence
source execution attempt numbers
source AC별 mechanical/semantic outcome + evidence refs의 EvolveSourceSnapshot
phase: wondering | reflecting | seeding | completed
WonderOutput?
ReflectOutput?
result_blueprint_revision?
scope_change_findings[]
```

호출 전 record를 만들고, Wonder 완료 뒤와 Reflect 완료 뒤에 각각 저장한다.
마지막 저장은 Reflect output, `completed` record, successor Blueprint revision을
한 번의 원자 교체로 함께 기록한다. 다음 호출은 대화 기억이 아니라 이 record를
읽어 완료된 phase 다음부터 재개한다.

LLM 호출 중 hard crash는 같은 phase의 호출을 다시 할 수 있다. 이 두 역할은
도구·파일 부작용이 없는 text lane이므로 비용 중복만 있고 workspace side effect
중복은 없다. 같은 mission의 두 Evolve 호출은 mission-scoped single-flight로
막는다. normal 경로의 호출 예산은 `Wonder 1 + Reflect 1 = 2` primary calls이며,
기존 Claude transient 정책(phase당 최대 3 attempts)을 포함한 최악 상한은 6회다.

이것은 upstream event replay의 **의도**(partial phase 재구성)를 file-state 형태로
이식한 것이다. event store를 읽는 새 소비자가 생겼다는 이유만으로 프로젝트의
저장 축 전체를 바꾸지 않는다.

### 9. 별도 spec-gap classifier와 generation tag를 만들지 않는다

Core는 Verify `HOLD`를 "implementation" 또는 "spec"으로 새로 분류하지 않는다.
upstream에도 그 분류 축은 없다. `evolve`는 어떤 `HOLD`에도 명시적으로 선택할 수
있는 corrective command이고, `recover`는 승인된 Blueprint를 유지하는 bounded
correction이다. 둘 중 언제 무엇을 호출할지는 ADR-0042의 skill/사용자 조율
책임이다. Evolve를 골라도 revision 승인 전 Execute는 열리지 않으므로 AC 약화가
조용히 실행 기준이 되지 않는다.

임의 generation rewind는 이 slice에 넣지 않는다. 기존 rollback은 마지막 입증
checkpoint인 HEAD만 사용한다. 세대 identity는 Blueprint state에 있고 checkpoint는
이미 `Blueprint-Revision`을 기록하므로, generation rewind 선택 표면이 없는 지금
별도 git tag는 같은 사실의 두 번째 이름이다.

### 10. Surface는 `blueprint evolve`이며 새 Stage를 만들지 않는다

CLI의 명시적 선택은 `mcx blueprint evolve`다. 후속 명세의 결과가 Blueprint이고
Constitution의 다섯 canonical command를 유지해야 하므로 최상위 `evolve` 명령이나
여섯 번째 Stage를 만들지 않는다. composition root는 Blueprint text lane의 같은
`CompletionEngine`을 Wonder와 Reflect에 주입한다. 별도 Evolve routing key는 없다.

surface는 LLM 호출 전에 Mission record가 존재하고 `ACTIVE`인지 확인한다. 저장된
`current_stage == VERIFY`는 요구하지 않는다 — ADR-0037에 따라 stored Stage는
표시·resume용이고, 실제 진입 자격은 `EvolveService`가 current Blueprint·Execute·
Verify 상태로 Gate를 재계산해 결정한다.

- successor revision이 생기면 exit 0, 결과 revision·generation·approval 필요를
  출력하고 Mission record를 Blueprint로 전이한다.
- Reflect가 Goal/Constraint 변경을 제안해 scope finding만 저장되면 exit 2
  `HOLD`다. revision과 Stage 전이는 없다.
- entry·adapter·저장 실패는 exit 1이며 완료하지 못한 evolution phase에서 재개한다.
- MCP tool은 CLI parser에서 `mcx_blueprint_evolve`로 파생하고, 정상 2회 완성 호출은
  장기 작업이므로 `mcx_start_blueprint_evolve` 비동기 짝도 둔다.

Blueprint state의 successor append와 Mission record 전이는 서로 다른 파일 저장소다.
새 transaction store를 만들지 않는다. 전자는 application의 원자 저장이 먼저고,
후자는 성공 응답의 surface 기록이다. 둘 사이에서 중단되면 `status`가 mismatch를
드러내고 Gate 재계산이 이긴다 (ADR-0037). 이 복구 규칙을 cross-store atomicity로
과장하지 않는다.

## Consequences

### Positive

- 실패한 Verify evidence가 같은 Goal의 새 승인 가능 명세로 연결되며 Mission
  lineage가 갈라지지 않는다.
- terminal `MISSION COMPLETE`를 다시 여는 경로가 없다.
- 수동 refinement와 세대 advancement가 `revision`/`generation` 두 축으로
  분리되어 QA 예산 의미가 유지된다.
- position 기반 upstream patch를 content-key 기반 Core에 안전하게 옮긴다.
- Wonder/Reflect 중단 뒤 대화 기억 없이 재개할 수 있다.
- Verify/Execute 모델을 Blueprint에 역참조하지 않아 기존 의존 방향을 지킨다.

### Cost

- Blueprint schema와 QA 상태 계산이 generation을 알게 된다.
- ontology가 승인·QA·serialization 대상에 추가된다.
- Verify 최신값만 보존하던 상태를 EvolutionRecord가 snapshot으로 중복 저장한다.
- upstream처럼 goal/constraints를 자율 refine하지 못한다. scope 변경 제안은
  Brief 사용자 결정에서 한 번 더 멈춘다.
- 한 upstream `evolve_step`을 mcx에서는 proposal→QA→approval→Execute→Verify의
  여러 단발 command로 나눈다.

## Rejected alternatives

- **세대마다 새 Mission 생성**: Verify `HOLD`의 같은 Goal과 evidence를 Mission
  경계 밖으로 쪼갠다. 완료 Mission만 source로 잡으면 실패에서 배우는 핵심 경로가
  사라진다.
- **완료 Mission을 reopen**: `MISSION COMPLETE` terminal과 Verify-only completion을
  깨뜨린다.
- **여섯 번째 Reflect Stage 추가**: upstream의 runtime routing Stage와 generation
  checkpoint를 canonical lifecycle Stage로 오독한다.
- **기존 `blueprint revise --draft-file`만 사용**: Wonder/Reflect output, source
  Verify snapshot, 부분 phase와 생산자 provenance가 사라진다.
- **Reflect가 full AC contract를 새로 작성**: 설명 수정과 검증 명령 변경을 한
  모델 판단에 묶어, 다른 의미의 AC에 기존 권위가 재바인딩될 수 있다.
- **revision마다 QA 예산 리셋**: 수동 revision 반복으로 5회 상한을 무한 우회한다.
- **Mission 전체 QA 예산 유지**: 첫 세대가 예산을 쓰면 후속 세대를 승인할 수 없다.
- **별도 event store**: 현재 atomic state 문서와 같은 사실의 두 번째 저장 축이
  생긴다. 필요한 replay는 EvolutionRecord checkpoint로 충족된다.
- **automatic spec-gap classifier**: upstream에 없는 분류를 발명하고, 오분류가
  곧 Stage 자동 후퇴 또는 잘못된 코드 교정으로 이어진다.

## Verification

- Verify `HOLD`인 current approved revision에서만 successor generation을 연다.
- Verify `CLEAR`/Mission `COMPLETE`, stale revision, evidence 없는 입력은 LLM 호출
  전에 거부한다.
- 같은 parent revision의 concurrent/duplicate Evolve가 successor 둘을 만들지 않는다.
- crash checkpoint에서 완료한 Wonder 또는 Reflect를 다시 호출하지 않고 이어간다.
- explicit keep/revise/add가 모든 parent key를 정확히 한 번 매핑하며 delete,
  reorder, duplicate, unknown key를 거부한다.
- 통과했고 challenge되지 않은 AC는 exact keep이다.
- revise는 mechanical contract를 보존하고 content key를 새로 만들며, add는
  mechanical contract를 발명하지 않는다.
- goal/constraints/non-goals 변경 proposal은 revision을 만들지 않고 Brief 결정을
  요구한다.
- Evolve 결과는 approval이 stale한 Blueprint `HOLD`이고, QA+exact user approval
  없이는 Execute할 수 없다.
- 같은 generation의 manual revision은 QA 예산을 공유하고, Evolve successor만
  다음 generation 예산을 연다.
- 첫 Blueprint ontology가 결정적으로 만들어지고 mutation 결과가 revision과 함께
  불변 저장된다.
- `domain/evolve`가 `domain.blueprint`·`domain.verify`·`domain.execute`를 import하지
  않고 application만 source state를 `EvolveSourceSnapshot`으로 투영한다.
- 정상 한 번은 Wonder·Reflect 각 1회, 총 2 primary calls다.
- Gen 2 대표 실사용 경로를 dogfood하기 전에는 Phase 10을 `COMPLETE`로 선언하지
  않는다.
