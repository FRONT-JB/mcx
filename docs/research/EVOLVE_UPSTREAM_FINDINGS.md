# upstream 자가개선 조사 — Gen 2+ 전체 연결 경로

- 조사일: 2026-08-10
- Baseline: `~/.claude/plugins/marketplaces/ouroboros` @ `9486c78` (v0.50.8)
- Evidence level: **Verified — pinned source + focused tests**
- 조사 이유: Phase 10의 첫 조사에서 *"ReflectEngine이 Brief/Blueprint 중 무엇을
  대체하는가"* 를 먼저 알아야 한다. 답에 따라 지금 만든 Brief 5단계의 위치가
  바뀌고, 그것은 계층 경계라 나중에 고치면 비싸다.

---

## 1. 답: **Brief를 대체한다** (Blueprint가 아니라)

`evolution/reflect.py` 모듈 docstring:

> *"Replaces the "contextual interview" approach for Gen 2+. **Interview is Gen 1
> only; Reflect handles all subsequent generations autonomously.**"*

`evolution/loop.py`의 클래스 docstring이 두 수명주기를 나란히 적는다:

```
Gen 1 lifecycle (seed provided externally):
1. Execute(Seed₁) → 2. Evaluate → 3. Record

Gen 2+ lifecycle (autonomous):
1. Wonder(Oₙ, Eₙ) → WonderOutput
2. Reflect(Seedₙ, output, Eₙ, wonder) → ReflectOutput
3. SeedGenerator(reflect_output, parent=Seedₙ) → Seed_{n+1}
4. Execute → 5. Evaluate → 6. Record → 7. 수렴 아니면 1로
```

**Gen 1에는 Wonder도 Reflect도 없고, Gen 2+에는 Interview가 없다.**
Seed(=Blueprint)는 양쪽 모두에 있다 — 대체되는 것은 **입력을 만드는 단계**다.

## 2. Gen 2+에서는 **모호함 채점이 돌지 않는다**

`bigbang/seed_generator.py::generate_from_reflect` docstring:

> *"Reflect applies ontology and identity-bearing prose deltas **without Gen-1
> ambiguity gating**."*

그리고 코드가 그것을 확인해 준다:

```python
metadata = SeedMetadata(
    ambiguity_score=parent_seed.metadata.ambiguity_score,   # 다시 채점하지 않는다
    interview_id=parent_seed.metadata.interview_id,          # 새 interview가 없다
    parent_seed_id=parent_seed.metadata.seed_id,             # 계보만 잇는다
)
```

`ambiguity_score`와 `interview_id`가 **부모 것 그대로** 실린다. Gen 2+는
모호함 임계값을 다시 통과하지 않는다.

## 3. 무엇이 바뀌고 무엇이 상속되는가

`generate_from_reflect`가 만드는 후속 Seed:

| 바뀌는 것 (ReflectOutput에서) | 상속되는 것 (parent Seed에서) |
|---|---|
| `goal` ← `refined_goal` | `task_type` |
| `constraints` ← `refined_constraints` | `brownfield_context` |
| `ontology_schema` ← 변형 적용 | `evaluation_principles` |
| `acceptance_criteria` ← 패치 적용 | `exit_conditions` |
| | `metadata.ambiguity_score`, `interview_id` |

즉 **방향(goal·constraints)과 수용 기준만 진화하고, 판정 원칙과 종료 조건은
고정**이다.

## 4. AC는 문장만 바뀌고 **구조적 권위는 자리로 이어진다**

`evolution/acceptance_contracts.py::evolve_acceptance_contracts` docstring:

> *"Apply reflected prose without reducing structured ACs back to strings.
> Reflect intentionally reasons over human-readable descriptions. Existing
> **mechanical verification and investment fields remain authoritative and are
> carried forward by position**. A revised description receives a **fresh
> semantic key**. Ambiguous deletion and reordering are **rejected** before they
> can rebind structured authority to a different criterion."*

정리하면:

- Reflect는 **설명 문장만** 다룬다. 기계적 확인 계약은 손대지 않는다.
- 확인 계약은 **위치(index)로** 이어진다.
- 설명이 바뀌면 semantic key를 **새로 발급**한다 (같은 자리지만 다른 기준).
- **모호한 삭제·재정렬은 거부**한다 — 구조적 권위가 엉뚱한 AC에 붙는 것을 막는다.

`ACPatch`의 연산은 셋이다: `keep` · `revise` · `add`. **`delete`가 없다.**

`generate_from_reflect` docstring이 한계도 적는다:

> *"Mechanical AC contracts cross only explicit keeps; description changes
> require a future replacement-contract patch."*

## 5. Wonder → Reflect 순서와 빈 변형 감시

`loop.py`는 Wonder를 먼저 돌리고 그 출력을 Reflect에 넘긴다. 그리고 이런 검사가
있다 (`loop.py:1630`):

```python
if wonder_output.questions and not reflect_output.ontology_mutations:
    log("evolution.reflect.empty_mutations", ...)
```

**질문이 나왔는데 변형이 하나도 없으면 기록에 남긴다** — 반성이 형식만 돌고
아무것도 바꾸지 않는 상태를 드러낸다.

Reflect 실패는 **2회까지 재시도**한다 (`max_reflect_attempts = 2`).

## 6. 되돌리기와의 관계

`rewind_to(generation)`가 세대를 자르고 `ACTIVE`로 되돌린다 — *"rewind to Oₙ and
branch from there"*. 즉 **되돌리기는 진화 루프의 일부**이며, 잘린 지점에서 다시
갈라진다 ([ROLLBACK findings](./ROLLBACK_UPSTREAM_FINDINGS.md) §1과 같은 사실).

---

## 우리 구조와의 충돌 지점 (조사 시점의 사실 — 결정은 ADR에서)

1. **`BlueprintService.generate`는 승인된 Brief handoff를 요구한다.** Gen 2+에는
   Brief handoff가 없다 → **Blueprint 생성 경로가 하나 더 필요하다.** 이것이
   계층 경계이며 이 조사의 핵심 결론이다.

2. **`blueprint revise`는 사람이 `--draft-file`로 준다.** Reflect는 같은 자리에
   자동 생산자를 하나 더 놓는다.

3. **우리 Blueprint 승인은 사람이 한다** (`approve`, QA 근거 필수 — ADR-0021).
   upstream Gen 2+는 자율이다. 승인을 누가 하는가가 결정 사항이다.

4. **우리 AC는 내용으로 식별된다** (ADR-0017 — 성공 계약의 내용이 곧 key).
   upstream은 **위치로** 구조적 권위를 잇고 설명이 바뀌면 key를 새로 발급한다.
   두 모델이 다르므로 `ac_patches`를 그대로 받을 수 없다.

5. **Brief 5단계는 재분류가 아니라 통째로 Gen 1 전용이다.** upstream도 같으므로
   divergence는 아니다. 다만 *"Brief 없이 Blueprint를 만든다"* 가 가능해야 한다는
   요구가 여기서 나온다.

6. `orchestrator_stage.py`의 아키텍처 설명은 Hermes를 reflect에 배치하지만 실제
   runtime 선택은 3단 fallback이다. 이 source 조사에서는 실물을 확인하지
   않았고, 후속 [backend A/B](./EVOLVE_BACKEND_AB.md)에서 Hermes·Claude를 각각
   Wonder/Reflect 1회씩 실행했다. Hermes 품질은 충분했지만 hard no-tool 격리와
   telemetry 계약이 약해 **mcx 기본값은 Claude 유지, Hermes는 최초 범위 제외**로
   처분했다.

---

## 7. 한 세대의 전체 연결: 이전 Verify가 다음 Blueprint와 실행을 함께 만든다

upstream의 원문 계약은 다음 두 줄이다
(`evolution/loop.py::_run_generation`):

> *"Gen 1: Execute → Evaluate (seed already provided)"*
>
> *"Gen 2+: Wonder → Reflect → Seed → Execute → Evaluate"*

여기서 세대 번호는 **새 Seed가 실행·평가되어 기록되는 단위**다. 따라서 Gen 2의
입력은 완료된 Gen 1이고, Gen 2 호출 안에서 `Seed₂`를 만든 뒤 곧바로
Execute/Evaluate까지 수행한다.

| 순서 | 입력 | 생산물 | 다음 경계 |
|---|---|---|---|
| 1. replay | `lineage_id`의 모든 `lineage.*` event | `OntologyLineage` read model, 다음/재개 generation | 마지막 완료 Seed를 복원 |
| 2. Wonder | 부모 `Seedₙ`, `ontology`, `execution_outputₙ`, `evaluation_summaryₙ`, 전체 lineage | 질문·grounded AC·ontology tension·계속 여부 | Reflect 입력 |
| 3. Reflect | 부모 Seed, 부모 실행·평가, Wonder, regression report, lineage | 개선 goal·constraints·AC patch·ontology mutation | Seed 생성 입력 |
| 4. Seed | 부모 Seed + ReflectOutput | `Seedₙ₊₁` (`parent_seed_id=Seedₙ.seed_id`) | Execute 입력 |
| 5. Execute/Validate/Evaluate | `Seedₙ₊₁` | 실행 산출물·검증 산출물·`EvaluationSummaryₙ₊₁` | 완료 event |
| 6. record | 새 Seed와 위 산출물 | `lineage.generation.completed` | 다음 호출의 replay 입력 |

`loop.py:1485-1498`에서 Wonder에 실제로 전달하는 값은
`current_seed.ontology_schema`, 이전 완료 세대의 `evaluation_summary`와
`execution_output`, `lineage`, `current_seed`다. `loop.py:1582-1598`의 Reflect는
같은 부모 Seed·실행·평가에 WonderOutput과 regression report를 더한다.
`SeedGenerator.generate_from_reflect`가 `parent_seed_id`를 찍고, 새 Seed가
Execute/Evaluate를 지난다.

완료 event에는 최소한 다음 세대 재구성에 필요한 `seed_json`, `seed_id`,
`parent_seed_id`, `ontology_snapshot`, `execution_output`, `evaluation_summary`,
`wonder_questions`, active/frozen AC index가 함께 들어간다
(`loop.py:1030-1081`). **채팅 출력이나 호출자 메모리가 다음 세대의 입력이
아니다.** 다음 `evolve_step`은 이 event를 다시 읽는다.

## 8. lineage는 저장 객체가 아니라 event에서 매번 만드는 read model이다

`core/lineage.py`의 원문:

> *"OntologyLineage is a read model projected from events -- never persisted
> directly, always reconstructed via LineageProjector."*

`evolve_step`은 호출마다 `replay_lineage(lineage_id)`를 먼저 수행한다. event가
없으면 `initial_seed`가 필수인 Gen 1이고, event가 있으면 `LineageProjector`가
완료·실패·중단·되감기와 control directive를 fold한다.

진행 중 중단을 새 세대로 오인하지 않는 규칙도 명시적이다.

- 마지막 phase가 `COMPLETED`면 `generation + 1`을 연다.
- `FAILED`나 `INTERRUPTED`면 **같은 generation 번호**를 다시 쓴다.
- hard crash면 unfinished generation의 durable `seed_json`과 phase checkpoint를
  복원해 같은 번호에서 재개한다.
- `wondering → reflecting → seeding → executing → evaluating`마다 Seed와 부분
  출력을 checkpoint한다. 실행·검증 경계는 완료 marker가 있어야 건너뛴다.
- 실행 중 hard crash는 외부 side effect를 중복 dispatch할 수 있어 자동 재실행을
  거부한다. 완전한 Wonder/Reflect/평가 상태가 없을 때도 fail-closed다.

즉 mcx가 필요한 것은 단순한 `parent_blueprint_revision` 한 필드만이 아니다.
**부모 산출물의 권위, 같은 세대 재개, 이미 일어난 외부 실행을 구분하는 durable
경계**가 함께 있어야 upstream과 같은 연결이 된다. 구체 저장 설계는 Phase 10
ADR의 몫이며 여기서 확정하지 않는다.

## 9. ontology-only 안정은 성공이 아니라 같은 Seed의 Verify handoff다

`execute=false`로 ontology만 진화시켜 안정돼도 upstream은 `CONVERGED`를 선언하지
않는다. 완료 record에 `verification_handoff_pending=true`를 원자적으로 저장하고
`StepAction.ONTOLOGY_STABLE` → `Directive.EVALUATE`를 낸다. 다음 호출이
`execute=true`면 Wonder/Reflect를 다시 돌리지 않고 **그 안정된 Seed 자체**를
Execute→Evaluate한다.

이는 mcx 원칙과 같은 방향이다. **Executed is not verified**이며 최종 성공은
Verify Gate만 선언할 수 있다. 다만 upstream의 `CONVERGED`를 mcx의
`MISSION COMPLETE`로 그대로 번역할 수 있다는 뜻은 아니다. 그 판정 권위는 Phase
10 설계 ADR과 Verify 계약이 결정해야 한다.

## 10. MCP는 한 세대씩 여는 조율 표면이다

`ouroboros_evolve_step`의 공개 계약은 *"Runs exactly ONE generation"* 이다.

- Gen 1: `lineage_id` + YAML `seed_content`
- Gen 2+: `lineage_id`만 전달 — Seed는 event에서 복원
- 선택: `execute`, `parallel`, `project_dir` 등 실행 정책
- 결과: generation, action, phase, similarity, next generation, 실행·평가·Wonder·
  ontology delta, active/frozen AC

handler와 core는 같은 lineage에 대해 durable single-flight를 걸어 동시 호출이
두 세대를 쓰지 못하게 한다. `ouroboros_start_evolve_step`은 동일 handler를
background job으로 감싸 즉시 job id를 돌려줄 뿐, 별도 진화 의미를 만들지 않는다.

따라서 mcx에 필요한 최소 조율 단위도 **"전체 자가개선 무한 루프" 한 명령이
아니라 재구성 가능한 한 세대 advancement**다. 몇 세대를 연속 호출할지, 언제
멈출지는 skill/조율 계층의 책임이고 Core는 한 호출의 상태 전이와 증거를 책임진다.

## 11. `Stage`, `GenerationPhase`, `AutoPhase`는 서로 다른 축이다

기존 Open Questions의 *"upstream Stage enum에 `RALPH_HANDOFF`와
`UNSTUCK_LATERAL`이 포함된다"* 는 기술은 **틀렸다.** 세 이름은 같은 enum이
아니다.

| upstream 어휘 | 목적 | 값 | mcx에서의 해석 |
|---|---|---|---|
| `orchestrator_stage.Stage` | runtime routing | `interview`, `execute`, `evaluate`, `reflect` | Brief·Execute·Verify 및 Gen 2+ spec 생산 runtime 축 |
| `GenerationPhase` | 한 진화 세대의 복구 checkpoint | `wondering`, `reflecting`, `seeding`, `executing`, `evaluating` + terminal | canonical Stage가 아니라 generation 내부 진행 상태 |
| `AutoPhase` | `ooo auto` 전체 pipeline resume/stall | `INTERVIEW`, `SEED_GENERATION`, `REVIEW`, `REPAIR`, `RUN`, `RALPH_HANDOFF`, `EVALUATE`, `UNSTUCK_LATERAL` 등 | 여러 canonical Stage를 잇는 조율·복구 내부 상태 |

`orchestrator_stage.py`는 새 handler 이름(`qa_judge`, `unstuck`)을 Stage로 늘리지
말고 `AgentProcess` 안에 두라고 명시한다. 실제 role table도 `wonder`, `reflect`,
`lateral`, `context_compression`을 모두 `Stage.REFLECT`에 묶는다.

- `RALPH_HANDOFF`는 성공한 RUN 산출물을 반복 실행/grade 루프에 넘긴 뒤
  EVALUATE로 잇는 **Execute→Verify 조율 checkpoint**다. 독립 lifecycle Stage가
  아니다.
- `UNSTUCK_LATERAL`은 평가 실패나 Ralph oscillation 뒤 lateral persona를 호출해
  bounded retry를 `RALPH_HANDOFF`/`EVALUATE`로 돌리거나 `BLOCKED`로 끝내는
  **Recover 내부 국면**이다. 새 `current_stage`가 아니다.
- `SEED_GENERATION`·`REVIEW`·`REPAIR`는 upstream runtime Stage enum에는 없지만
  auto pipeline에서는 별도 phase다. 즉 upstream의 4 runtime Stage와 mcx의 5
  lifecycle Stage 수를 직접 비교하면 축을 섞게 된다.

Reflect runtime은 두 책임을 같은 backend 축에 묶는다: (a) Verify 뒤 다음
Blueprint 입력을 만드는 Wonder/Reflect, (b) 막힌 실행을 다른 관점으로 돌리는
lateral recovery. **이 사실만으로 mcx에 여섯 번째 canonical `Reflect` Stage를
추가할 근거는 없다.** 다음 Blueprint의 생산 경계와 Recover 내부 국면으로 나눌지
Phase 10 ADR에서 결정한다.

## 12. Phase 10 진입 시 재검토하기로 한 두 항목

### 12.1 세대 지점 이름

upstream은 두 상태를 분리한다. Python `evolve_rewind`는 event lineage를 지정
generation까지 자르고, shell loop는 성공한 실행 세대마다
`ooo/{lineage_id}/gen_{N}` git tag를 만든다. standalone rewind의 working-tree
checkout은 **선택 사항**이지만 선택하면 그 tag를 쓴다.

따라서 **임의 generation 선택 + 파일 복원**을 mcx에 함께 도입하면 generation과
checkpoint commit을 잇는 안정적 identity가 필요하다. 다만 그 identity가 반드시
git tag여야 하는 것은 아니다. 기존 checkpoint commit에 generation identity를
싣는 설계도 가능하다. ADR-0047의 태그 미도입 결정은 당장 바꾸지 않고, Phase 10
설계 ADR에서 임의 rewind 범위를 먼저 확정한다.

### 12.2 stall 판정

upstream은 하나의 시계로 보지 않는다.

1. event가 전혀 없는 `idle_timeout`
2. event는 있지만 정해진 material event가 없는 `no_material_progress_timeout`
3. 여러 세대의 ontology·평가 점수·질문이 제자리인 semantic stagnation

이는 `item.started` 같은 정규화 activity 하나로 기존 침묵 판정을 교체할 근거가
아니다. 실제 stall을 놓친 관측도 새로 생기지 않았다. 따라서 ADR-0049의 현재
silence-based 판정을 유지하고, Evolve를 설계할 때 generation 전용 material/
semantic 신호를 별도 계약으로 다룬다.

---

## 검증

Pinned baseline에서 다음 focused test 11개를 실행했다.

```text
uv run pytest -q \
  tests/unit/test_evolve_step.py::TestEvolveStepGen2::test_gen2_reconstructs_from_events \
  tests/unit/test_evolve_step.py::TestEvolveStepGen2::test_ontology_only_generations_keep_reflecting_without_evaluation \
  tests/unit/test_evolve_step.py::TestEvolveStepResume::test_resume_after_failed_generation \
  tests/unit/test_evolve_step.py::TestEvolveStepResume::test_hard_crash_replays_the_unfinished_generation \
  tests/unit/orchestrator/test_stage_resolution.py::TestStageEnum::test_has_four_members \
  tests/unit/orchestrator/test_stage_resolution.py::TestLLMRoleStageRouting::test_stage_for_llm_role_maps_reflect_roles \
  tests/unit/auto/test_pipeline_ralph_handoff.py::test_state_machine_allows_run_to_ralph_handoff \
  tests/unit/auto/test_pipeline_lateral.py::test_unstuck_lateral_phase_in_allowed_transitions
11 passed in 3.53s
```

검증한 계약: event replay로 Gen 2 진행, ontology-only 연속 진화, 실패/hard-crash의
같은 generation 재개, 닫힌 4개 runtime Stage와 reflect role mapping,
`RUN→RALPH_HANDOFF`, `EVALUATE⇄UNSTUCK_LATERAL` 전이.
