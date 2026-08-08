# ADR 0035 — 도그푸딩 마찰의 upstream 대조 처분: 비용·속도는 upstream 동등 이상이어야 한다

- Status: Accepted
- Date: 2026-08-08
- 근거 조사: [DOGFOODING_0001](../research/DOGFOODING_0001.md),
  upstream 대조는 본문 표 (pinned baseline `9486c78` v0.50.8)

## Context

사용자 요구사항 (2026-08-08): **파이프라인의 비용(LLM 호출 수)과 속도는
upstream 동등 이상이어야 한다.** 도그푸딩 0001은 사전 추정의 2배(47호출)가
들었고, 그중 2개 감사 순환(~12호출)이 프로세스 마찰에서 나왔다. 마찰 4건
(research §3)을 pinned baseline과 대조한 결과가 아래 표다.

## 대조 결과

| 항목 | upstream 사실 (근거) | 우리 | 판정 |
|---|---|---|---|
| 질문 생성 | 질문당 완성 1회 (`authoring_handlers.py:2618` `ask_next_question`) | 1회 | 파리티 |
| clarity 채점 주기 | round ≥ 3부터 매 답변 후 1회, 전 차원 한 호출, streak 리셋 동일 (`authoring_handlers.py:3256-3297`) | 필요 시점 2회/순환 (총량 동급) | 파리티 |
| closure 감사 반복 | seed-ready 후보마다 재수행, **상한 없음** (skills/interview §7~§8) | 동일 | 파리티 |
| closure 감사 병렬성 | **3-lane을 한 병렬 배치로 spawn** (skills/interview step 8, `subagent.py` K3). closer 단독이 순차 fallback | 순차 3회 — **wall-clock 3배** | **이탈 → 수정** |
| closure 감사 입력 | **main 세션 전체 관점** — 정본은 transcript, 후보는 파생물 (skills/interview step 8, `core/requirement_candidate.py` docstring) | 미확정 후보만 투영 → 확정 결정 재차단 (낭비 2순환) | **이탈 → 수정** |
| 후보 폐기 상태 | 없음 — 동일 4-resolution. 전체 가시성이 재차단을 막는다 | 없음 + 부분 가시성 | 상태 발명 없이 입력 수정으로 해소 |
| QA 판정자 입력 | **pass threshold와 이전 반복 궤적(iteration/score/verdict)을 프롬프트에 렌더** (`mcp/tools/qa.py:103-165`) | 직전 findings만 | **이탈 → 수정** (ADR-0019 §3 개정) |
| QA 기각 사유 채널 | 판정자에게 없음 — applied/rejected는 skill ledger 전용 (skills/seed step 2) | 없음 | 파리티 — 발명하지 않음 |
| QA 반복당 비용 | 판정 1회 + Socrates + lateral 최대 5 persona + user gate (skills/seed REVISE branch) | 판정 1회 + 운용자 수정 | 우리가 더 저렴 |
| QA 수정 채택 | **User Adoption Gate — 자동 적용 금지** ("No candidate is accepted by default") | 동일 (ADR-0019 §1) | 파리티 |
| 제약 수정 경로 | Socrates·lateral 제안이 user gate로 제약 수정 가능 | verbatim 잠금 (ADR-0018) — QA의 제약 지적이 실행 불가 | **보상 조치** (아래 §4) |
| 완성 호출 전송 | codex provider는 `codex exec` 단발 spawn (`providers/codex_cli_adapter.py:3`) | 동일 | 파리티 |
| semantic AC 판정 | per-AC 순차 (evaluation/semantic.py에 gather 없음; 병렬은 consensus 전용) | 순차 | 파리티 |

**결론: 호출 수는 전 구간 upstream 동등 이하다.** 이탈은 wall-clock(감사
순차 실행)과 낭비 순환을 만든 입력 투영·QA 입력 두 곳이며, 전부 upstream
정렬로 수정한다.

## Decision

### 1. 위임 입력 투영은 후보 전체를 resolution과 함께 전달한다

`open_requirements`(미확정만) → `requirement_candidates`(전체 + resolution).
질문 생성·clarity 채점·closure 감사 모두에 적용한다. upstream의 "main 세션
전체 관점"과 정렬하며, 확정 결정의 재차단(도그푸딩 4순환)과 폐기 후보
재론(3순환)을 입력 가시성으로 해소한다. 폐기 상태는 발명하지 않는다 —
upstream에도 없다. 확인 권위(confirmation_authority)는 여전히 전달하지
않는다 (승격 판정의 재료, ADR-0015).

### 2. closure 감사 3-lane을 병렬로 실행한다

`BriefService.audit_closure`가 closer·contrarian·gap_hunter를
`asyncio.gather`로 동시 수행한다. 합성과 저장은 기존 결정적 순서 그대로다.
어느 lane이든 실패하면 전체가 결과 없음이다(기존 계약 유지). wall-clock
기대 효과: 감사 순환당 2~4분 → 최장 lane 1개 시간.

### 3. QA 요청에 pass threshold와 반복 궤적을 싣는다

`QaRequest`에 `pass_threshold`와 `previous_iterations`(iteration/score/
verdict)를 추가하고 어댑터가 upstream과 같은 자리(`## Pass Threshold`,
`## Previous Iterations`)에 렌더한다. **ADR-0019 §3의 "통과 점수 비전달"은
upstream 미확인 상태에서 세운 규칙이었음을 인정하고 개정한다** — upstream은
threshold를 판정자에게 보여 준다 (`qa.py:150-155`). 직전 findings 전달은
유지한다(우리 쪽이 더 상세하며 모순되지 않는다).

### 4. QA 프롬프트에 고정 필드를 명시한다 (보상 조치, upstream 대응물 없음)

우리는 제약·Non-goal이 handoff 원문 잠금(ADR-0018)이라 upstream과 달리 QA
제안으로 수정할 수 없다. 판정자에게 "constraints와 non-goals는 이 단계에서
고정된 입력"임을 프롬프트로 알리고, 그에 대한 지적은 Brief 단계 재개
대상으로 안내한다. upstream에 대응물이 없는 문장이므로 여기 등록한다.

### 5. 바꾸지 않는 것

- 기각 사유의 판정자 채널 — upstream에도 없다. 기각 기록은 승인
  statement(ADR-0019 §8)에 남긴다.
- 감사 반복 상한 — upstream에도 없다. 도그푸딩 0001에서 5순환 수렴을
  관측했다. 비수렴이 재관측되면 별도 ADR.
- ambiguity 점수의 감사 전달 — upstream tripanel은 싣지만
  (`subagent.py:2677-2680`) anchoring 제거 목적의 등록된 divergence를
  유지한다 (ADR-0020 §5, 2026-08-08 재확인).
- semantic per-AC 순차 실행 — upstream 파리티.

## Cost

- threshold 공개는 "그 선에 맞춘 점수 조정" 위험을 되살린다 — ADR-0019 §3의
  원래 우려. upstream 채택을 우선하고, 점수 분포가 threshold 직상에 몰리는
  패턴이 관측되면 재평가한다.
- 후보 전체 전달로 위임 프롬프트가 길어진다. 후보 수가 큰 mission에서의
  한도는 Brief guide의 context size 규칙(§10 Step 1)이 다룬다.

## Verification

- 감사 병렬성: 세 lane이 동시 시작됨을 stub 지연으로 고정하는 테스트.
- 투영: 확정 후보가 세 위임 요청 전부에 resolution과 함께 나타나는 테스트.
- QA 렌더: threshold·궤적 섹션이 upstream 자리 이름으로 렌더되는 테스트.
