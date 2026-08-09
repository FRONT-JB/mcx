# upstream 자가개선 조사 — Reflect가 Brief를 대체한다

- 조사일: 2026-08-10
- Baseline: `~/.claude/plugins/marketplaces/ouroboros` @ `9486c78` (v0.50.8)
- Evidence level: **source-read**
- 조사 이유: Phase 10 진입 전에 *"ReflectEngine이 Brief/Blueprint 중 무엇을
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

6. Hermes는 reflect 단계의 지정 하네스다 — **이 조사에서는 확인하지 않았다.**
   `upstream 미확인`으로 남긴다.
