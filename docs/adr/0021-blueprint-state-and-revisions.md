# ADR 0021 — Blueprint 상태 저장과 revision 정책

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 7 (Durable state over conversation memory), §14 (Mission State와 Artifacts), [ADR-0002](./0002-approved-seed-is-immutable.md), [ADR-0019](./0019-blueprint-qa-loop.md)
- Upstream evidence: [SEED_UPSTREAM_FINDINGS](../research/SEED_UPSTREAM_FINDINGS.md) §7, §8, §11, §12; [PERSISTENCE_UPSTREAM_FINDINGS](../research/PERSISTENCE_UPSTREAM_FINDINGS.md) §9

## Context

Blueprint domain 부품(spec·assembly·QA)은 있으나 이를 묶는 durable 상태가 없다.
`BlueprintService`가 "handoff 조회 → 생성 → 조립 → QA 반복 → 승인 → 저장"을
닫으려면 다음이 먼저 정해져야 한다 — 무엇을 어디에 저장하는가, revision은 어떻게
표현하는가, QA 채점이 어느 revision을 본 것인지 어떻게 남는가, 승인은 무엇에
묶이는가. 넷 모두 [AGENTS.md](../../AGENTS.md)의 되돌리기 비싼 결정 목록(상태
저장 방식과 revision 표현)에 해당하므로 구현 전에 확정한다.

upstream 사실 (기록된 baseline 기준):

- `ooo seed`는 interview 상태를 읽어 seed를 생성·저장하고 경로를 반환한다.
  승인 객체는 저장소 전체에 없다 (§7). `SeedMetadata`의 선언 필드에 `version`,
  `parent_seed_id`가 있어 seed 간 lineage는 개별 산출물 파일 사이의 참조로
  표현된다 (§11, `core/seed.py:367-416`).
- QA 루프는 skill 계층에 있고, "Track the highest-scoring seed across all
  iterations" (`skills/seed/SKILL.md:113`) — 추적 대상이 점수가 아니라 **최고
  점수의 seed 내용**이다. 반복 상한 5회, 6회째 반복 금지 (§8).
- 런타임 관측에서 skill 계층 QA가 고친 개정본이 store로 돌아가지 않았다 (§12).
  이것이 QA 루프를 state를 소유하는 계층에 둔 근거다 (ADR-0019 §1).
- 승인된 Seed와 approval record의 원자적 연결 요구([Blueprint
  Guide](../06_BLUEPRINT.md) §12)는 upstream에 대응물이 없다 — upstream에는
  approval 자체가 없기 때문이다. 우리가 신설한 개념(ADR-0019 §8)이 저장 형태의
  제약 조건이 된다.

## Decision

### 1. 저장은 ADR-0013 baseline을 Blueprint로 확장한다

Mission당 단일 JSON 문서(`blueprint_<mission_id>.json`) 하나에 **모든 Blueprint
revision, QA 채점 기록, 승인**을 담는다. 쓰기 계약은 ADR-0013 §3과
ADR-0014(원자 교체, file lock, `sequence` 기반 stale write 거부)를 그대로
따른다.

한 문서인 이유는 §12의 원자성 요구다. Blueprint와 approval이 다른 파일에 있으면
"Seed는 저장되고 approval만 유실"된 상태가 물리적으로 가능하고, 그 상태를
`CLEAR`로 오인하지 않는다는 보장을 저장 계층이 줄 수 없다. 한 문서의 원자
교체는 그 상태 자체를 만들지 않는다.

**등록된 차이**: upstream은 seed마다 개별 YAML 파일이고 lineage는
`parent_seed_id` 참조다. 우리는 mission당 한 문서에 revision을 나열한다.
upstream 형태를 따르지 않는 근거는 위의 원자성 요구와, Brief(ADR-0013 §2
"이력이 같은 문서 안에 있으면 참조 revision을 단일 읽기로 검증")와 같은 형태
유지다.

### 2. 내용 변경마다 새 revision, 모든 revision 보존

- 첫 생성은 정확히 한 번이다 (upstream §8 — 이후 수정은 재생성이 아니라 편집).
  이미 Blueprint가 있는 Mission의 재생성 요청은 거부한다.
- 수정(`revise`)은 현재 내용을 바꾸지 않고 revision을 하나 올린 새 Blueprint를
  뒤에 붙인다. 승인 뒤 수정도 같은 경로다 — 기존 승인은 이전 revision에 묶인
  채 stale이 된다 (ADR-0002).
- revision 번호는 1부터 연속 증가하는 정수다. 각 revision은 자신을 만든
  `brief_revision`을 담는다 (ADR-0017의 lineage 필드).

### 3. QA 채점 기록은 채점한 revision을 가리킨다

채점 기록을 `(revision, assessment)` 쌍으로 저장한다. upstream이 추적하는 것은
"highest-scoring **seed**"이므로, 점수만 남기고 내용과의 연결을 잃으면 상한
도달 시 사용자에게 제시할 "최선의 시도"가 재구성되지 않는다.

`QaAttempt`/`QaLoopState`(ADR-0019)는 바꾸지 않는다. 점수 이력에서 판정과
최선을 계산하는 기계는 revision을 알 필요가 없고, 연결은 Blueprint 상태가
소유한다. 최선 시도의 revision은 iteration 순서(기록 순서와 동일)로 역참조한다.

### 4. 채점 허용 규칙은 상태가 구조로 강제한다

| 상황 | 규칙 | 근거 |
|---|---|---|
| 누적 채점 횟수가 상한에 도달 | 채점 거부 | upstream §8 — 6회째 반복 금지 |
| 현재 revision이 이미 통과 점수를 받음 | 재채점 거부 | 통과한 내용의 재채점은 점수 갱신 외 효과가 없고, 판정 기준을 흔든다 |
| 마지막 채점이 FAIL (`fail_threshold` 미만) | 이후 채점 거부 | ADR-0019 §6 `ESCALATE` — 명세 수준 문제는 루프로 해결하지 않는다. FAIL 후 루프 폐쇄가 upstream 성문 규칙인지는 **upstream 미확인**이며, threshold 값 자체는 upstream 것이다 (ADR-0019 §2) |
| 통과 후 revise된 새 revision | 잔여 상한 안에서 채점 허용 | 새 내용은 채점된 적이 없다. 상한은 revision이 아니라 루프 전체에 걸린다 (upstream §8 — 반복 사이의 편집이 곧 refinement) |

### 5. 승인은 현재 revision에 묶이고, 그 revision의 채점을 요구한다

- 승인 대상은 항상 **현재(최신) revision**이다. `BlueprintApproval.revision`이
  그것을 가리키고, 이후 revise가 revision을 올리면 승인은 stale이 된다.
- 승인하려면 현재 revision에 대한 채점 기록이 있어야 한다. 채점된 적 없는
  내용의 승인 기록에는 담을 QA 근거가 없다 (ADR-0019 §8의 필드가 성립하지
  않는다).
- 현재 revision의 verdict가 PASS면 그대로 승인한다. REVISE면 **상한이 소진된
  경우에만** `accepted_below_threshold=True`로 승인할 수 있다 — 미달 수락은
  상한 소진 뒤의 선택지다 (upstream §8: 5회 후 세 선택지). FAIL은 승인할 수
  없다.
- `qa_best_score`는 **승인 대상 revision의 최고 점수**다. 루프 전체의 최고
  점수로 정의하면 승인된 내용과 기록된 점수의 대상이 어긋날 수 있고, 그 순간
  `accepted_below_threshold` validator가 지키는 것("통과하지 못한 명세가 통과한
  것으로 기록되지 않는다", ADR-0019 §8)이 무너진다. 정상 흐름(통과 승인, 최선
  시도 수락)에서는 두 정의가 일치한다.
- **알려진 한계**: 상한 도달 시 최선의 시도가 현재 revision이 아니면 그것을
  채택하는 절차가 아직 없다. 수정 후보 채택 절차(**Phase 8** 합성 계층 —
  2026-08-09 재지정, [ADR-0019](./0019-blueprint-qa-loop.md) §7 주석)와 함께
  다루며, 내용 동일성 판정이 필요해지면 [Blueprint Guide](../06_BLUEPRINT.md)
  §18의 content hash open decision을 그때 확정한다.

### 6. Execute 진입 Gate

`evaluate_blueprint_gate`는 순수 함수이며 다음을 모두 요구한다.

- 현재 revision에 대한 승인이 있다 (없으면 `approval_missing`, 이전 revision
  대상이면 `approval_stale`).
- 승인된 revision의 `brief_revision`이 현재 Brief revision과 같다 (다르면
  `brief_revision_stale` — Brief가 그 사이 바뀌었으므로 재평가가 필요하다).

`CLEAR`의 목적지는 Execute 하나다 ([Lifecycle](../02_MISSION_LIFECYCLE.md) §14:
Blueprint `CLEAR` → Clear for Execute). QA 미달·미채점은 별도 blocker로 보지
않는다 — §5가 그런 승인의 생성 자체를 막으므로, Gate에 도달하는 승인은 이미
QA 근거를 담고 있다.

## Consequences

### Positive

- 승인·QA 기록·revision이 한 번의 원자 쓰기로 함께 남아 §12의 원자성 요구가
  저장 형태 자체로 충족된다.
- "이 명세가 기준을 통과했는가, 사용자가 미달을 수락했는가"가 승인된 내용
  기준으로 정확히 남는다.
- 채점 예산 우회(재시작으로 횟수 초기화)가 불가능하다 — 채점 기록이 durable
  상태에 있다.

### Cost

- 문서 하나가 모든 revision을 담으므로 revision이 많아지면 커진다. ADR-0013
  §2와 같은 입장이다 — 실제로 문제가 되면 그때 분리한다.
- 상한 도달 후 최선 시도(현재 revision이 아닌)를 채택하는 경로가 Phase 2에는
  없다. §5의 알려진 한계.
- FAIL 후에는 revise해도 채점·승인 경로가 없다. 에스컬레이션(Brief 복귀)이
  유일한 출구이며, 그 복귀 절차 자체는 Recover/surface 범위다.

## Rejected alternatives

- **seed마다 개별 파일 (upstream 형태)**: approval과 분리 저장되어 §12가
  금지하는 상태(한쪽만 유실)가 물리적으로 가능해진다. upstream에는 approval이
  없어 이 문제가 없었다 — 형태만 복사하면 우리 신설 개념의 보장이 깨진다.
- **`QaAttempt`에 revision 필드 추가**: 검증된 점수-판정 기계에 stage 조립
  관심사가 들어간다. 연결의 소유자는 Blueprint 상태다.
- **`qa_best_score`를 루프 전체 최고 점수로 기록**: 승인된 내용과 점수의
  대상이 어긋나 validator가 무력화된다 (§5).
- **revise를 in-place 수정으로**: 승인 stale 판정의 기준(revision 증가)이
  사라진다 (ADR-0002).
- **미채점 revision의 승인 허용**: QA를 거치지 않은 내용이 "QA 근거를 담은
  승인"으로 기록된다. ADR-0019가 죽인 우회로의 재생산이다.
- **상한 소진 전 미달 수락 허용**: upstream은 미달 수락을 상한 소진 뒤의
  선택지로만 제시한다 (§8). 이르게 허용하면 반복 예산이 장식이 된다.

## Verification

- 첫 생성 후 재생성 요청이 거부된다.
- revise가 revision을 올리고 이전 revision을 바꾸지 않는다.
- 승인 뒤 revise하면 Gate가 `approval_stale`로 `HOLD`한다.
- 채점 없는 revision의 승인이 거부된다.
- 상한 도달 후 채점 요청이 거부된다.
- 이미 통과한 revision의 재채점이 거부된다.
- FAIL 뒤 채점 요청이 거부된다.
- 통과 후 revise된 revision은 잔여 상한 안에서 채점된다.
- REVISE 점수 승인은 상한 소진 + 명시적 미달 수락일 때만 성립한다.
- Brief revision이 바뀌면 Gate가 `brief_revision_stale`로 `HOLD`한다.
- 부분 기록·stale write가 저장 계층에서 거부된다 (ADR-0013·0014와 동일 계약).
