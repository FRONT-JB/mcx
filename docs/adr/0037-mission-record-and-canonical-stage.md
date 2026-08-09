# ADR 0037 — Mission record와 canonical Stage 저장: 합성 계층 소유, enforcement는 Gate 재계산 유지

- Status: Accepted
- Date: 2026-08-08
- 근거 조사: [CLI_UPSTREAM_FINDINGS §4](../research/CLI_UPSTREAM_FINDINGS.md)
- 처분 대상: [progress 0004](../progress/0004_VERIFY_RECOVER_VERTICAL_SLICE.md)
  질문 4 (시한: Phase 6 전)

## Context

[Lifecycle §3.1](../02_MISSION_LIFECYCLE.md)은 Mission이 최소한 identity,
**current Stage**, state version 등을 가진다고 규범으로 요구한다. 그러나
Phase 1이 "Phase 2에서 다룬다"고 미룬 뒤 재론되지 않은 채 Phase 5까지
완성되었고, 그 결과 모든 Entry Contract의 "현재 Stage가 X다" 조건이 전
Stage에서 미강제다. 실질 보증은 각 진입의 Gate 재계산이 대신하고 있다
(record 0004 질문 4 — 알려진 한계로 등록됨).

upstream 대조 (findings §4): "현재 어느 단계인가"의 durable 기록은
**파이프라인 합성을 소유한 층에만** 있다. `ooo auto`의
`AutoPipelineState.phase`(닫힌 enum 12값, 합법 전이 그래프, 전이 시각·사유,
mission급 원자적 JSON 문서)가 그것이고, 목적은 명문화되어 있다 — "resume
and stall handling", "resume later without silently duplicating execution".
개별 CLI 명령은 이 기록을 참조하지 않고 artifact 전제만 검사하며, resume은
저장 phase로 분기하되 **artifact와 교차 검증**한다 — Seed artifact 없는
후반 phase 재진입은 거부되고, interview가 완료돼 있으면 phase를 전진시킨다
(`auto/pipeline.py:756-778,872`). 저장된 phase 단독으로는 어떤 진입도
허가되지 않는다. 대화형 skill 흐름에는 이런 기록 자체가 없다 — 대화가
순서를 소유한다.

## Decision

1. **Mission record(current Stage 포함)는 합성 계층이 소유한다.** 첫
   실물은 Phase 6 CLI의 mission 상태 문서다. Stage service들은 이 기록을
   읽지도 쓰지도 않는다 — 의존 방향은 합성 → Stage service 단방향이다
   (upstream 정렬: `AutoPipelineState`는 `ooo auto` 소유, 개별 명령 비참조).
2. **저장된 Stage에 enforcement 지위를 주지 않는다.** Stage 진입의 실질
   보증은 지금처럼 각 진입의 Gate 재계산이다. 저장된 Stage와 Gate 재계산이
   어긋나면 그것은 진단 신호이며 **Gate가 이긴다** (upstream 정렬: resume의
   artifact 교차 검증·phase 전진/거부).
3. **형태는 지금 확정한다** (상태 저장 방식 — 되돌리기 비싼 축): 닫힌
   Stage enum, 합법 전이 그래프 검증(위반은 예외), 전이 시각과 사유 기록.
   용도는 표시(status)·resume·stall 탐지다.
4. **Lifecycle §3.1은 유지된다** — 충족 시점이 Phase 6일 뿐이다. Phase
   1~5의 부재는 결격이 아니라 합성 계층의 부재였다 (record 0005 §1.2의
   Phase 경계 논리와 동일).
5. exact 필드명, enum 멤버(다섯 Stage와 terminal status의 표현), state
   version과의 관계는 Phase 6 구현 설계에서 Lifecycle §3.2~§3.3과 함께
   확정한다. upstream enum이 stage 내부 국면(RALPH_HANDOFF,
   UNSTUCK_LATERAL)까지 포함하는 것과 우리 다섯 Stage 축의 대응은 그때
   대조한다.

   > **2026-08-09 처분 (Phase 6 종료 검토) — 부분 이행.**
   >
   > - 필드명·enum 멤버는 확정됐다: `MissionRecord`의 `mission_id`,
   >   `workspace`, `current_stage`(Stage 5), `status`(`MissionStatus`),
   >   `completed_at`, `sequence`, `transitions`.
   > - **state version은 `sequence`가 그 자리다** — 쓰기 순서이자 덮어쓰기
   >   판정 값이며(ADR-0014와 같은 축), Lifecycle §3.1이 요구하는 "state
   >   version"을 이것이 충족한다고 여기서 확정한다. 구현은 Phase 6에
   >   있었으나 §3.1과의 대응이 문서에 적힌 적이 없어 미이행으로 보였다.
   > - **upstream enum 대응 대조는 수행하지 않았다.** 우리 다섯 Stage에
   >   stage 내부 국면(RALPH_HANDOFF, UNSTUCK_LATERAL)의 대응물이 있는지
   >   확인되지 않았다. 새 시한은 **Phase 10 (Reflect/Evolve)** — 그 국면들이
   >   upstream 진화 루프의 것이므로 Phase 10 조사가 같은 소스를 읽는다.
   >   [Open Questions §10](../research/OPEN_QUESTIONS.md)에 등록한다.

## Consequences

### Positive

- record 0004 질문 4가 닫힌다 — "미강제"가 미표시 결함이 아니라 결정된
  설계(Gate 재계산이 보증, 저장은 표시·resume용)가 된다.
- Phase 6 CLI의 `status`·resume이 발명 없이 upstream 실물 위에 선다.
- Stage service가 mission 문서를 모른 채 유지된다 — Phase 0~5 코드 무변경.

### Cost

- 진실이 두 곳(저장 Stage, Gate 재계산)에 생긴다. 완화: 어긋남은 Gate가
  이기고, 어긋남 자체를 표시한다(§Verification).
- mission 문서 스키마 확정이 Phase 6 설계로 미뤄지므로, 그 전에 이 문서의
  다른 소비자를 만들지 않는다.

## Rejected alternatives

- **저장된 Stage를 진입 enforcement로 승격** — upstream도 하지 않는다.
  stale 저장이 이기는 순간 잘못된 진입을 허가하는 사고 표면이 된다.
- **각 Stage service가 current Stage를 기록** — 소유가 분산된다. upstream은
  artifact 상태만 두고 phase는 합성이 소유한다.
- **도입하지 않고 Lifecycle §3.1을 개정** — upstream 실물이 있고, Phase 6
  CLI의 status·resume·stall 탐지가 실수요다. 규범을 구현 편의로 깎는
  방향이라 기각.

## Verification (Phase 6에서)

> **2026-08-09 이행 확인 (Phase 6 종료 검토).** 세 항목 모두 충족했고, 첫
> 항목의 문장을 구현에 맞게 정정했다 — 원문 *"불법 전이가 예외로 거부된다"*는
> **CLI 명령이 거부된다**로 오독될 수 있었다. 실제 경계는 아래와 같으며 이것이
> §Decision 2("저장은 표시용, enforcement 아님")의 직접 귀결이다.

- mission 상태 문서에 current Stage 필드가 존재하고, 불법 전이는 **도메인에서
  예외로 거부된다** (`MissionRecord.transit` → `InvalidStageTransitionError`).
  **CLI는 그 예외를 잡아 경고만 남기고 명령은 성공시킨다** — 기록이 진입을
  막으면 저장된 Stage가 enforcement로 승격되기 때문이다
  (`cli/main.py:_record_transition`, `test_illegal_transition_warns_but_command_succeeds`).
- 저장된 Stage와 Gate 재계산이 어긋나는 시나리오에서 Gate 결과가 이기고,
  어긋남이 표시된다 (`mcx status`의 경고 줄, `test_status_reports_record_and_mismatch`).
- Stage service 코드가 mission 문서 모듈에 의존하지 않는다 (import 방향
  검사). **2026-08-09까지 이 검사는 산문뿐이었고** 같은 날
  `tests/unit/test_layer_boundaries.py`로 실검사가 됐다.
