# Open Research and Design Questions

이 목록은 모르는 것을 감추지 않고 구현 전에 검증하기 위한 backlog다.

상태 표기:

- `[ ]` 조사 전
- `[-]` 조사 중
- `[x]` 근거와 결정 문서까지 반영

---

## 0. 현재 우선순위 — Phase 1 (Brief vertical slice)

2026-08-07 Phase 0 검토 후 우선순위화했다. Phase 1 착수 전에는 아래 항목만
조사하고, 나머지 섹션은 해당 Phase 직전에 조사한다.

1. §1 Upstream baseline 중 Brief 관련 항목
   - `pyproject.toml`과 package 경계 기록
   - `ooo interview` 종료 Gate end-to-end 추적
   - `ambiguity <= 0.2`와 user-controlled completion의 reconcile
   - completion candidate streak와 user approval 호출 경로
   - answer provenance enum과 requirement authority 규칙
   - LICENSE와 copied code notice 재확인 (구현 직전)
2. §2 Brief decisions 전체

2026-08-07: 1번 항목의 근거 수집이 완료되어
[INTERVIEW_UPSTREAM_FINDINGS.md](./INTERVIEW_UPSTREAM_FINDINGS.md)에
기록했고, §2 결정은 ADR-0009/0010/0011과 `05_BRIEF.md`에 반영되어 닫혔다.
§1의 Brief 관련 항목은 upstream test 조사(Phase 1 test case 설계 직전)와
LICENSE 재확인(코드 복사 직전)만 남아 `[-]`로 유지한다.

**2026-08-09 정정.** 위 문장의 두 잔여는 이렇게 처분됐다 — upstream **test
조사는 수행되지 않았고**(Phase 1 시한 도과), 전 Stage 조사가 소스 읽기로
진행됐다. 이 한계는 §1 머리말에 공통 조건으로 옮겼다. LICENSE는 발동 조건
자체가 성립한 적이 없다(observe-only).

---

## 1. Upstream baseline

**2026-08-09 인덱스 갱신.** 이 목록은 Phase 1~6 동안 갱신되지 않아, 실제로는
Stage별 findings 문서에 조사가 기록된 항목들이 `[ ]`(조사 전)로 남아 있었다 —
다음 세션이 끝난 조사를 다시 하게 만드는 상태였다. 아래는 근거 문서와 대조한
실제 상태다.

**전 항목 공통 한계**: 조사 수단은 **소스 읽기**였고 upstream **테스트 대조는
수행하지 않았다**. 원래 문구의 "tests로 확인"은 이행되지 않았으므로, 아래
`[x]`는 "소스로 확인"을 뜻한다.

- [x] baseline commit의 `pyproject.toml`과 package 경계를 기록한다. →
      [INTERVIEW_UPSTREAM_FINDINGS](./INTERVIEW_UPSTREAM_FINDINGS.md)
- [x] `ooo interview` skill, MCP handler, CLI path의 실제 종료 Gate를
      end-to-end로 추적한다. → 위 findings, ADR-0009
- [x] architecture의 `ambiguity <= 0.2`와 current source의 user-controlled
      completion을 reconciliate한다. → ADR-0009 (네 조건 모두 필요)
- [x] completion candidate streak와 user approval의 실제 호출 경로를
      확인한다. → ADR-0009·ADR-0011
- [x] answer provenance enum과 requirement authority 규칙을 확인한다. →
      ADR-0010
- [x] Seed 생성 → QA → repair → approval path를 실제 handler로 추적한다. →
      [SEED_UPSTREAM_FINDINGS](./SEED_UPSTREAM_FINDINGS.md)
- [-] Seed field와 immutability/revision behavior를 source에서 확인한다. →
      필드·불변성은 확인(ADR-0017·0021). **잔여 3건**은
      [SEED findings §11](./SEED_UPSTREAM_FINDINGS.md): revision lineage와
      `parent_seed`의 의미, `GradeGate`의 등급 소비 규칙,
      `SeedRepairer.converge`의 bounded stop 조건
- [x] Run이 AC를 atomic-first로 시도하고 분해하는 정확한 조건을 확인한다. →
      [RUN_UPSTREAM_FINDINGS §6](./RUN_UPSTREAM_FINDINGS.md) (분해는 예외
      경로, 자식 2~5·깊이 2·repair 1)
- [x] executed-unverified에 대응하는 upstream state/event를 확인한다. →
      **2026-08-09 조사 완료 — 대응물이 실재한다.**
      `mcp/job_manager.py:249-258`의 `_run_only_verification_meta`
      (`verification_status: "executed_unverified"`, `evaluated: False`,
      `next_step: "ooo evaluate <id>"`)와 `auto/pipeline.py:4650-4676`의
      `complete_unverified`/`complete_verified` 분류
      ([RUN findings §11.1](./RUN_UPSTREAM_FINDINGS.md)). 축은 정렬이고,
      차이는 표현 지위(메타데이터 vs 1급 상태)와 미평가 작업 차단 여부
      (upstream 없음 / 우리는 ADR-0026으로 등록된 divergence)다
- [x] Evaluation pipeline의 short-circuit와 consensus trigger를 확인한다. →
      [VERIFY findings §6~§7](./VERIFY_UPSTREAM_FINDINGS.md) (trigger 6조건),
      [EVALUATE findings](./EVALUATE_UPSTREAM_FINDINGS.md) (3단 파이프라인)
- [-] Repair, resilience, evolve, seed repair의 경계를 비교한다. → repair·
      resilience는 [REPAIR findings §4~§5](./REPAIR_UPSTREAM_FINDINGS.md).
      **evolve 경계는 §10(Phase 10)으로 이관**, seed repair는 위 §11 잔여
- [-] Codex/OpenCode Runtime의 cancellation/resume/error normalization을
      비교한다. → Codex는
      [RUNTIME findings §5](./RUNTIME_UPSTREAM_FINDINGS.md) (thread 기반
      resume, 정합 검증). **OpenCode는 adapter 구현과 함께 이연**
- [x] MCP authoring handler와 execution handler의 recursive dispatch guard를
      확인한다. → [RUNTIME findings](./RUNTIME_UPSTREAM_FINDINGS.md):
      `allowed_tools=[]` + `strict_mcp_config=True`로 재귀·도구 차단,
      이중 dispatch 격리(`:497-503`). 우리 ADR-0004와 같은 축
- [x] pinned commit의 LICENSE와 copied code notice 요구를 재확인한다. →
      MIT © Q00 (2025), [research README](./README.md) baseline snapshot에
      기록. **발동 조건은 "코드 복사 또는 상당한 포팅 전"**
      ([UPSTREAM_MAPPING](./UPSTREAM_MAPPING.md) §라이선스)이며, mcx는
      observe-only라 조건이 발동한 적이 없다 — 원래 문구의 "구현 직전"은
      조건을 잘못 좁혀 적은 것이라 실제 조건으로 정정했다

---

## 2. Brief decisions

2026-08-07에 ADR-0009/0010/0011로 결정했다.

- [x] Greenfield/Brownfield를 v1에서 구분할지 결정한다. → 정책 자리만 예약, 탐색 단계는 유예 (ADR-0011)
- [x] source provenance의 canonical categories를 결정한다. → authority 2값 + source 별도 축 (ADR-0010)
- [x] clarity dimension과 score 방향을 결정한다. → dimension은 clarity(높을수록 명확), canonical metric은 ambiguity (ADR-0009)
- [x] score threshold, minimum rounds, stability streak의 관계를 결정한다. → 네 조건 모두 필요 (ADR-0009)
- [x] user approval을 command/state 중 어디에 기록할지 결정한다. → revision에 묶인 1급 상태 (ADR-0011)
- [x] 질문 생성 실패와 빈 응답 fallback을 정의한다. → 재개 조건을 명시한 HOLD, terminal status는 Lifecycle 소관 (05_BRIEF §15)
- [x] initial context size와 prompt compaction policy를 정의한다. → 한도 초과 시 요약 round, 기본값 3500자 (05_BRIEF §10 Step 1)
- [x] codebase fact를 누가 어떤 read-only capability로 수집할지 결정한다. → 별도 Fact Resolver 역할 유지 (ADR-0011)
- [x] **closure 감사를 Brief Gate에 도입할지, 어떤 형태로 할지 결정한다.**
      → 3-lane 전부 재구성해 Core에 도입 (사용자 결정 2026-08-08,
      [ADR-0020](../adr/0020-brief-closure-audit.md)). closer의 verdict가
      gate, advisory 두 lane은 HIGH만 차단, 합성은 결정적 도메인 코드.
      계약 문장은 upstream 원문, ambiguity 점수 비전달은 등록된 divergence.

2026-08-08 도그푸딩 0001에서 등록, 같은 날 대조·처분
([DOGFOODING_0001](./DOGFOODING_0001.md) §3,
[ADR-0035](../adr/0035-dogfooding-cost-parity-dispositions.md)):

- [x] closure 감사 입력 투영이 확정 후보를 배제해 이미 결정된 사안을
      재차단한다. → upstream 가드는 main 세션 전체 관점에서 수행
      (skills/interview step 8). 투영을 후보 전체 + resolution으로 수정
      (ADR-0035 §1).
- [x] 폐기(superseded)된 후보가 open requirement로 영구 잔존한다. →
      upstream도 폐기 상태 없음 (동일 4-resolution) — 상태를 발명하지 않고
      전체 가시성으로 해소 (ADR-0035 §1).
- [x] closure 감사에 반복 상한이 없다. → upstream도 없음 (후보마다 재수행).
      파리티로 유지, 비수렴 재관측 시 별도 ADR (ADR-0035 §5). lane 실행은
      upstream 병렬 배치와 정렬해 병렬화 (§2).

## 3. Blueprint decisions

- [x] Seed schema의 필수/선택 필드를 결정한다. → 방향 필드(goal, constraints,
      non_goals, acceptance_criteria)와 lineage만, `extra="forbid"`
      ([ADR-0017](../adr/0017-blueprint-schema-baseline.md))
- [x] Non-goal과 Constraint의 validation rule을 정의한다. → 그대로 옮겨야
      하며 추가·누락은 결정적 범위 검사가 거부
      ([ADR-0018](../adr/0018-blueprint-generation-contract.md))
- [x] AC quality rubric과 QA 통과 policy를 결정한다. → quality bar 문장 +
      0.90/0.40/최대 5회 ([ADR-0019](../adr/0019-blueprint-qa-loop.md))
- [x] Seed revision ID와 parent lineage를 결정한다. → 1부터 연속 정수
      revision, `brief_revision`으로 lineage, 전체 revision 보존
      ([ADR-0021](../adr/0021-blueprint-state-and-revisions.md) §2)
- [-] approval actor와 approval evidence를 결정한다. → evidence는
      `BlueprintApproval`(statement + QA 근거,
      [ADR-0019](../adr/0019-blueprint-qa-loop.md) §8)로 확정. CLI 표면은
      결정 — 승인 주체는 명령을 실행한 로컬 사용자이고 actor 식별자는
      미도입 ([ADR-0038](../adr/0038-mcx-cli-surface-contract.md) §7,
      upstream도 CLI에 user identity 없음). **host 대리 승인 경로만 잔여 —
      시한 재지정 (2026-08-09, Phase 7 종료 검토): Phase 8.** MCP가 승인
      tool을 열어 host 에이전트가 `mcx_blueprint_approve`를 부를 수 있게
      됐고, 그 승인은 기록상 사용자 승인과 구분되지 않는다. 결정 대상은
      "Core가 actor를 기록할 것인가, skill이 사용자 확인을 보증할 것인가"다
      ([progress 0007](../progress/0007_MCP_CONTROL_SURFACE.md) §1.7).
- [ ] user-edited YAML을 지원할지 결정한다.
- [-] **결정적 품질 gate(upstream `GradeGate`)의 대응물을 도입한다.** →
      **2026-08-09 조사·구현 ([ADR-0043](../adr/0043-deterministic-blueprint-quality-floor.md),
      Proposed).** 조사가 아래 기술을 좁혔다 — upstream의 결정적 층이 실제로
      보는 것은 섹션 단위 충족 여부이고 그것은 `check_scope`가 이미 한다.
      등급·점수는 이식하지 않았고(판정 어휘가 둘이 된다), 새로 막는 것은
      **확인 수단이 하나도 없는 Blueprint** 하나다 — 이 축은 upstream 대응물
      없는 발명이다. **잔여: 부분 커버리지 처분(§4) — 표시만/경고/임계값 중
      선택, 실사용 관측 전에는 표시만 권고.**
      upstream의 Seed 품질 방어는 두 층이다 — LLM 채점(우리 ADR-0019 QA)과
      `auto/grading.py`의 **결정적** gate(`may_run = grade == A and not
      blockers`, gap 개수·가정 개수로 coverage·risk를 계산). 우리에겐 구조
      검사(`check_scope`)만 있고 점수화된 결정적 층이 없다. upstream 위치가
      합성 계층(`auto/`)이므로 우리 대응 층도 Phase 8이다
      ([SEED findings §11](./SEED_UPSTREAM_FINDINGS.md)).
- [x] schema/ontology를 v1에 포함할지 결정한다. → 제외. upstream 필드 5개
      (ontology_schema 등)는 v1 미포함으로 기록
      ([ADR-0017](../adr/0017-blueprint-schema-baseline.md) Cost)

2026-08-08 도그푸딩 0001에서 등록, 같은 날 대조·처분
([DOGFOODING_0001](./DOGFOODING_0001.md) §3,
[ADR-0035](../adr/0035-dogfooding-cost-parity-dispositions.md)):

- [x] QA 루프에 기각 사유 채널이 없어 기각된 지적이 재제기되고 점수가
      역행·정체한다. → upstream 판정자에게도 기각 채널은 없음 (ledger 전용,
      skills/seed step 2). 대신 upstream은 pass threshold와 반복 궤적을
      프롬프트에 렌더 (`mcp/tools/qa.py`) — 정렬 수정, ADR-0019 §3 개정.
      수정 채택의 User Adoption Gate는 upstream과 파리티 확인 (ADR-0035 §3·§5).
- [x] QA 채점자가 verbatim 잠금 필드(제약·Non-goal)의 수정을 제안한다. →
      upstream은 Socrates·user gate로 제약 수정이 실제 가능해 대응물 없음.
      고정 필드 프롬프트 문장으로 보상, ADR-0035 §4에 등록.

## 4. Execute decisions

- [x] work item의 canonical 이름과 schema를 결정한다. → 별도 엔티티 없음.
      AC key가 실행 단위이고 기록은 attempt
      ([ADR-0024](../adr/0024-execute-v1-execution-model.md) §1)
- [-] atomic-first size 판단과 분해 한도를 정의한다. → v1 분해 미도입.
      도입 시 upstream 한도(자식 2~5, 깊이 2, repair 1)와 대조
      ([ADR-0024](../adr/0024-execute-v1-execution-model.md) §2,
      [ADR-0025](../adr/0025-execute-deliberate-divergences.md) 보류)
- [-] dependency graph와 ready calculation을 정의한다. → v1 미도입 — 선언
      순서 순차 + 실패 중단. upstream 모델(선언 ∪ LLM, 토폴로지 level)은
      [RUN_UPSTREAM_FINDINGS §8](./RUN_UPSTREAM_FINDINGS.md)에 기록
      ([ADR-0024](../adr/0024-execute-v1-execution-model.md) §3)
- [ ] 첫 concrete Runtime Adapter 순서를 결정한다.
- [-] workspace/file scope 표현을 결정한다. → v1 envelope는 workspace 경로 +
      도구 목록 ([ADR-0024](../adr/0024-execute-v1-execution-model.md) §6).
      exact 표현과 차단은 Phase 5
- [-] required idempotency의 exact key, scope, retention, duplicate result
      semantics를 정의한다. → 열린 attempt 1개 규칙만 확정
      ([ADR-0024](../adr/0024-execute-v1-execution-model.md) §7). exact key
      schema는 여전히 미정
- [ ] parallel execution 도입 Gate를 정의한다. → **시한 지정 (2026-08-09,
      사용자 결정): Phase 11** — 독립 항목이다. 2026-08-09 조사로 "OpenCode의
      용도는 종반 병렬 부수 작업"이라는 전제가 upstream 사실이 아님이
      드러났고(upstream은 OpenCode를 Execute 하네스로 배치), 병렬은 OpenCode와
      분리됐다.
- [x] **Execute 진입 경로가 하나임을 무엇이 보장하는지, Telemetry가 "무엇이
      이 작업을 만들었는가"를 기록하는지 결정한다.**
      → 작업 생성은 application use case 단일 경로 + Blueprint Gate `CLEAR`
      요구; 경로 밖 작업의 탐지는 약속하지 않고 "기록의 부재가 판정
      가능해야 한다"를 방어선으로; provenance 네 항목(생성 경로, 실행 주체,
      lineage, 시도)을 선언 필드로 강제
      ([ADR-0023](../adr/0023-execute-entry-and-provenance.md), 소스 조사는
      [RUN_UPSTREAM_FINDINGS](./RUN_UPSTREAM_FINDINGS.md)). Telemetry 없는
      작업의 `CLEAR` 여부(§5)와 MCP host 직접 작업(§8)은 남은 결정이다.

## 5. Verify decisions

- [-] project-specific mechanical command 발견 방식을 결정한다. → v1은 발견
      없음 — 승인된 Blueprint의 `verify_command`만 실행
      ([ADR-0028](../adr/0028-verify-v1-mechanical-contract.md) §2). upstream의
      발견 방식(AI detector가 `.ouroboros/mechanical.toml` 작성, "toml만
      신뢰")은 repo 명령 도입 시의 대조 기준으로 기록
      ([VERIFY_UPSTREAM_FINDINGS §3](./VERIFY_UPSTREAM_FINDINGS.md))
- [x] command allowlist와 custom command 승인 정책을 결정한다. → v1의 명령
      정당성 경계는 **승인 경로**다 — Verify use case에 명령 입력이 없고
      항상 승인된 Blueprint에서 읽는다. allowlist(upstream 4겹 모델)는 승인
      없이 들어오는 repo 명령의 방어이며 그 층의 도입 시 함께 온다
      ([ADR-0028](../adr/0028-verify-v1-mechanical-contract.md) §2,
      [VERIFY_UPSTREAM_FINDINGS §4~§5](./VERIFY_UPSTREAM_FINDINGS.md))
- [x] semantic verdict schema와 uncertainty 표현을 결정한다. → AC 단위
      `satisfied`(bool) + `score` + `uncertainty`(0..1) + `reward_hacking_risk`
      + reasoning/evidence/questions_used. uncertainty는 통과 조건이 아니라
      escalation 신호(임계 0.3, v1은 HOLD). 임계 셋(0.8/0.3/0.7)은 upstream
      채택 ([ADR-0030](../adr/0030-verify-semantic-verdict-contract.md),
      [VERIFY_UPSTREAM_FINDINGS §6](./VERIFY_UPSTREAM_FINDINGS.md))
- [ ] UI/API/CLI observation adapter의 우선순위를 결정한다.
- [x] semantic 판정의 AC 병렬화를 결정한다. → **병렬로 정렬 (2026-08-09).**
      upstream은 semantic stage를 AC별 `asyncio.gather`로 돌리고 하나라도
      실패하면 전체 중단 (`mcp/tools/evaluation_handlers.py:877-955` —
      Verified). 0003 실측(순차 ~12분)이 비용·속도 요구사항 위반이라 gather
      정렬 + Barrier 테스트로 고정 (ADR-0030 정렬 note,
      [DOGFOODING_0003 §5](./DOGFOODING_0003.md)).
- [x] semantic verdict의 일괄 저장을 유지할지 결정한다. → **유지한다**
      (2026-08-09, status 박스와 함께 처분). ① 0003이 제기한 것은 저장
      방식이 아니라 **가시성**이었고, 명령 원장이 그것을 덮는다 — `verify
      semantic`이 시작 시각과 함께 "진행 중"으로 표시된다
      ([ADR-0038](../adr/0038-mcx-cli-surface-contract.md) §6.1). ② AC별
      증분 저장은 부분 `SemanticAssessment`를 만들고, Gate가 미완성 판정
      묶음을 읽을 수 있는 경로가 열린다 (ADR-0030 §3의 revision·policy 묶음
      계약이 깨진다). ③ upstream도 `asyncio.gather` + 실패 시 전체 중단이라
      결과 집합이 원자적으로 나온다 — 일괄 저장이 upstream 정렬이다.
      **남은 것**: 명령 *안*의 진척(3/9)은 스트리밍 이벤트 층이 있어야
      가능하며, 이미 등록된 보류다 (ADR-0027 §3, ADR-0033 §6).
- [x] conditional consensus를 v1에 포함할지 결정한다. → 미포함 — escalation은
      HOLD가 전부. trigger 6조건·숙의 구조·배심 독립성은 도입 시 대조 기준으로
      기록 ([ADR-0030](../adr/0030-verify-semantic-verdict-contract.md) §5,
      [VERIFY_UPSTREAM_FINDINGS §7](./VERIFY_UPSTREAM_FINDINGS.md))
- [ ] workspace snapshot/revision 검증 방식을 결정한다.
- [x] **Execute Telemetry 없이 나타난 작업을 Verify가 CLEAR할 수 있는지
      결정한다.** → **없다 — 진입 자체가 막힌다.** Verify 진입이 Execute Gate
      `CLEAR`를 요구한다. upstream evaluate는 lineage를 요구하지 않음을 소스로
      확인했고(§12.3 사고의 직접 원인 —
      [EVALUATE_UPSTREAM_FINDINGS §2](./EVALUATE_UPSTREAM_FINDINGS.md)), 이
      차이는 의도적 divergence로 등록했다
      ([ADR-0026](../adr/0026-verify-entry-requires-lineage.md)). 기록 밖
      artifact 평가는 v1 범위 밖이며 §8 결정의 제약으로 남는다.

## 6. Recover decisions

- [x] failure taxonomy enum을 결정한다. → 원천 4종(실행 실패/mechanical
      실패/semantic 불충족/escalation 대기) + 결정적 분류 `BLOCKED`·`STALL`·
      미분류. upstream 6종 중 verifier 증거 계약이 필요한 것들은 보류
      ([ADR-0031](../adr/0031-recover-v1-failure-and-retry-contract.md) §2~§3,
      [REPAIR_UPSTREAM_FINDINGS §1~§2](./REPAIR_UPSTREAM_FINDINGS.md))
- [-] Recover Stage activation과 RecoveryDirective의 exact serialization을
      정의한다. → 진입(Execute/Verify Gate `HOLD` 근거)과 packet 축은 확정
      (ADR-0031 §1·§6), exact 필드명은 구현 slice에서 Guide §6 목록과 대조
- [x] retry budget과 progress signal을 결정한다. → AC당 교정 재시도 2회
      (upstream `ac_retry_attempts` 채택), 새 revision이 리셋. progress
      signal은 v1에서 동일 오류 해시 제거가 유일한 결정적 신호
      (ADR-0031 §4, [REPAIR_UPSTREAM_FINDINGS §3](./REPAIR_UPSTREAM_FINDINGS.md))
- [-] identical failure/oscillation 탐지 방식을 결정한다. → 동일 실패는
      오류 해시 3회(upstream SPINNING 채택, ADR-0031 §3). oscillation 등
      나머지 3패턴은 이력 축적 후
      ([ADR-0032](../adr/0032-recover-deliberate-divergences.md) 보류)
- [ ] rollback 지원 범위를 결정한다. → **시한 재지정 (2026-08-09, 사용자
      결정): Phase 9 실사용 진입** — brownfield·worktree 격리·AC별
      checkpoint 커밋(upstream `AutoCommitPolicy`, 미등록이었음)과 한 묶음.
      원래 시한 "Phase 5 workspace 관리와 함께"는 Phase 5가 단발 실행
      계약만 확정하고 지나가 낡았다 (upstream `core/worktree.py` 조사 포함,
      ADR-0032 보류 유지).
- [-] blocked/cancelled/unrecoverable 상태를 결정한다. → `BLOCKED`는 결정적
      인식 + `HOLD`(ADR-0031 §3), unrecoverable은 예산 소진 `HOLD`.
      cancelled는 취소 경로(Phase 5)와 함께

## 7. Runtime decisions

- [-] Runtime protocol method와 streaming shape를 결정한다. → v1은 단발
      (`ExecutionRuntime.execute` 유지 — upstream `execute_task_to_result`
      축). 스트리밍은 event 층과 함께 보류
      ([ADR-0033](../adr/0033-first-runtime-adapter-contract.md) §3)
- [x] text-generation backend port를 execution Runtime과 어떻게 분리할지
      결정한다. → 별개 port 유지 — upstream LLMAdapter/AgentRuntime 분리와
      일치, 같은 backend가 양쪽 adapter를 각각 가짐 (ADR-0033 §1,
      [RUNTIME_UPSTREAM_FINDINGS §1](./RUNTIME_UPSTREAM_FINDINGS.md))
- [-] capability descriptor와 mismatch semantics를 정의한다. → upstream은
      선언적 3플래그(이름 검사보다 플래그 분기). 우리 도입은 둘째 adapter
      에서 차이가 실제로 생길 때 (ADR-0033 §6)
- [x] Stage→Runtime 바인딩 표현을 결정한다. → **라우팅 테이블 도입
      (2026-08-09, 사용자 결정 — [ADR-0039](../adr/0039-stage-runtime-routing-table.md)).**
      키는 닫힌 Stage enum, 값은 lane별 backend 쌍(upstream은 stage당 하나 —
      등록된 divergence), 해석 3단, fail-fast 검증, 설정 표면
      `<state-dir>/config.toml`(ADR-0038 개정). ADR-0023이 Phase 5에 약속하고
      이행하지 않은 대조를 이행했다
      ([RUN findings §1·§11.2](./RUN_UPSTREAM_FINDINGS.md)).
- [ ] native event 보존과 normalized Telemetry 연결 방식을 정의한다.
      (스트리밍·event 층과 함께 — ADR-0027 §3)
- [-] timeout/cancel/resume contract를 정의한다. → timeout은 침묵 900초
      (upstream stall 채택, ADR-0033 §4). cancel은 스트리밍과 함께, resume은
      upstream 정합 검증(바이너리 해시·모델 고정)과 대조해 도입 (§6 보류)
- [ ] OpenCode local/provider/agent mode를 capability로 어떻게 표현할지
      결정한다. → **OpenCode adapter와 함께 이연** (2026-08-09 사용자 판단 —
      로컬 모델 성능이 실 하네스 검증 수준이 아니다). 구조는 Phase 6
      라우팅 테이블이 열어 두고, 실물 대상이 생길 때 결정한다.
      [RUNTIME_UPSTREAM_FINDINGS §6](./RUNTIME_UPSTREAM_FINDINGS.md) 미조사
- [ ] **leader-driven 실행 모델(재개 가능한 worker 세션)을 채택할지 결정한다.**
      (2026-08-09 등록) upstream은 단발 실행(`codex exec`, INTERNAL)과 나란히
      **코어가 leader가 되어 addressable·resumable worker 세션을 직접 구동하는**
      계열을 등록해 두고 있다 — codex는 `codex mcp-server`를 **MCP로** 호출하고
      (`codex_mcp`), claude는 `claude -p --resume`를 쓴다(`claude_mcp`).
      우리 대응물은 **없다**(단발만). 실행 모델과 세션 재개 표현은 되돌리기
      비싼 축이므로 실수요를 기다리지 않고 여기 등록한다. 판단 재료: upstream
      기본값은 여전히 단발 계열이고(`config/loader.py:651-658`),
      `codex mcp-server` 세션은 프로세스 귀속이라 단발 턴만 네이티브 지원이며
      다중 턴 resume은 upstream 자신의 미완 과제다.
      → [RUNTIME_UPSTREAM_FINDINGS §12](./RUNTIME_UPSTREAM_FINDINGS.md)

## 8. MCP and CLI decisions

- [x] MCP tool 하나가 한 Stage command와 1:1인지 command/query를 분리할지 결정한다.
      → **1:1이며 `build_parser()`에서 파생한다** ([ADR-0041](../adr/0041-mcp-control-surface-contract.md) §1).
      손으로 적는 목록이 없어 CLI와 어긋날 자리가 구조적으로 없다. upstream은
      1:1이 아니고 공유 지점도 반대 방향이다 — 등록된 divergence.
- [x] request/response schema와 error envelope를 정의한다. → §2.
      exit 0/1/2가 `(is_error, result_type)` 둘로 나뉘고 **HOLD는 오류가
      아니다**(`is_error=false`). `structured_content`는 CLI `--json`과 같은
      payload, `content`는 사람용 렌더.
- [x] host session, Mission ID, Runtime handle 전달 규칙을 정의한다. → §3.
      `mission`은 모든 tool의 필수 인자이며 서버는 "현재 mission"을 기억하지
      않는다 (04_MCP §1-4).
- [x] async job/polling/notification 방식을 결정한다. → §4·§5.
      장기 명령 둘에만 `mcx_start_*` 짝을 두고, **job은 원장에서 유도한다**
      (새 저장소 없음). 접수증은 `dispatch`의 `on_sequence` 훅으로 실제
      sequence를 받는다. notification은 도입하지 않고 host가 폴링한다.
- [-] disconnect, cancel, timeout의 의미를 분리한다. → cancel은 §5로 닫혔다
      (디스크 마커 + runtime 관측, 실물 종료 테스트). **disconnect와
      `job_wait` 대기 상한은 열려 있다** — upstream도 미조사다
      ([MCP findings §9](./MCP_UPSTREAM_FINDINGS.md)).
- [x] CLI와 MCP parity test 전략을 정의한다. → §8.
      **parity를 테스트로 쫓지 않는다** — 같은 `dispatch`를 지나므로 구조가
      보장한다. 검사는 방향 셋이다: MCP가 application을 직접 부르지 않을 것,
      CLI가 MCP를 import하지 않을 것, tool 목록이 CLI 명령 집합과 같을 것.
- [x] **status 박스를 도입한다 (사용자 제안 2026-08-09, 도그푸딩 0003).**
      → **구현 완료 (2026-08-09)** — [ADR-0038](../adr/0038-mcx-cli-surface-contract.md)
      §6.1 개정 2. append-only JSONL 원장(`start`/`end` 두 줄, 짝 없는
      `start`가 "진행 중") + 세 화면 렌더(진행 중·HOLD·MISSION COMPLETE),
      `--full`/`--json`/`--plain`. 쓰기 주체는 CLI뿐이고 `mcx status`는
      원장을 늘리지 않는다. 상태 어휘 5종은 테스트로 닫혀 있다.
      upstream 대응물: `ooo status auto`의 "한 줄 한 사실" 블록·`Pending
      question:` 원문 인용·스냅샷 고정
      ([CLI_UPSTREAM_FINDINGS §5](./CLI_UPSTREAM_FINDINGS.md)),
      `AutoPipelineState.phase_started_at`/`last_progress_at`.
      **호출 수는 실측이다** — 명령 수 근사가 아니라 port 호출을 센다
      (upstream `tui/events.py:594-599` "never a character proxy"). 토큰·비용
      계측은 port 반환형 변경이 선행이라 ADR-0038 §7 보류로 등록했다.
- [-] plugin 설치·발견·설정 UX를 결정한다. → **2026-08-09 확정, 배포만
      잔여.** 발견은 양쪽 host 매니페스트(`.claude-plugin/`·`.codex-plugin/`)가
      같은 `./skills/`와 같은 `./.mcp.json`을 가리키는 형태로 확정했고, 설정은
      `<state-dir>/config.toml` 하나다(라우팅 + backend 모델, CLI 플래그 없음).
      설치는 **PyPI 배포 없이 닫혔다** — `.mcp.json`이
      `${CLAUDE_PLUGIN_ROOT}`를 가리켜 플러그인이 자기 소스로 자기 MCP 서버를
      띄운다. **실물 확인 (2026-08-09, Verified by execution)**: marketplace
      등록 → `claude plugin install mcx@mcx` → skill 6종 인식, MCP 서버
      `✔ Connected`, always-on ~189 tok. 변수는 실제로 치환된다(인자가
      `uvx --from /Users/.../mcx/[mcp] mcx-mcp`로 확장됐다).

      **upstream과 다른 선택이다 — 등록된 divergence.** upstream은 소스를
      플러그인에 전부 넣고도 MCP 서버는 **PyPI**에서 가져오고
      (`uvx --from ouroboros-ai[mcp]` + `env: {"UV_PYTHON": "3.13"}`),
      `${CLAUDE_PLUGIN_ROOT}`는 **hooks에만** 쓴다. 즉 빌드가 필요 없는 것은
      플러그인 루트, 빌드·의존성 해석이 필요한 것은 PyPI로 갈랐다. 우리가
      자기참조를 고른 이유는 배포 승인 없이 완결되기 때문이며, 대가는 첫 기동에
      wheel 빌드가 필요하고 사용자 환경의 파이썬 해석에 맡긴다는 것이다
      (upstream이 `UV_PYTHON`으로 고정한 축 — **왜 고정했는지는 미확인**이라
      따라 하지 않았다).

      같은 관측에서 부수 사실 하나: 이 기계에서 **upstream 자신의 PyPI 경로가
      연결에 실패하고 있다**(`plugin:ouroboros:ouroboros ... ✘ Failed to
      connect`). 원인은 조사하지 않았으므로 PyPI 경로의 일반적 결함으로
      일반화하지 않는다 — 다만 그 경로에 우리에게 없는 실패 지점이 있다는
      관측이다.

      배포판 이름(`mission-control`)과 git 경로는 여전히 열려 있으나 **이제
      선택 사항**이다.
      원래 시한 지정 (2026-08-09, 사용자 결정): Phase 8 — MCP(Phase 7) 직후,
      실사용 진입(Phase 9) 앞.
      upstream의 배포 실물은 **plugin = skills + MCP server + CLI 3층**이며
      skill이 MCP tool을 orchestrate한다 (`skills/seed/SKILL.md` frontmatter
      `mcp_tool: ouroboros_generate_seed`,
      [CLI_UPSTREAM_FINDINGS §3](./CLI_UPSTREAM_FINDINGS.md)). Phase 7 MCP
      server가 기반층이고 CLI/MCP가 같은 application service를 공유한다
      (ADR-0038 §1). Claude·Codex 양쪽 다 MCP 클라이언트라 같은 server가
      붙는다.

      **2026-08-09 정정.** 이 항목의 원문은 "skill 래퍼와 manifest만 얹으면
      된다"였는데 §2의 조사 결과와 충돌한다 — upstream에서 **품질 루프와 합성
      규칙이 skill 계층 소유**다 (합성 계층 둘: skill, `ooo auto`). 따라서
      Phase 8은 manifest 작업이 아니라 합성 계층 도입이며, "무엇이 skill
      소유이고 무엇이 Core 소유인가"의 경계 ADR이 선행한다.
- [ ] **MCP host가 자기 편집 도구로 작업하고 Verify만 호출하는 경로를 어떻게
      다룰지 결정한다.** host는 에이전트이며 `mcx` 도구와 자기 도구를 동시에
      갖는다 — upstream에서 실제로 발생한 조건이다
      ([SEED_UPSTREAM_FINDINGS §12.3](./SEED_UPSTREAM_FINDINGS.md)).
      [ADR-0004](../adr/0004-stage-scoped-minimum-capability.md)는 worker가
      위로 탈출하는 것만 막고 이 방향을 덮지 않는다.
      → **두 번째 도과 → Phase 9 (2026-08-09, Phase 8 종료 검토).** 원래 시한은
      [ADR-0023](../adr/0023-execute-entry-and-provenance.md) §8과
      [ADR-0026](../adr/0026-verify-entry-requires-lineage.md)이 건 *"Phase 7
      전"* 이었고, Phase 8로 재지정됐으나 또 결정되지 않았다. skill은 **행동
      규칙**을 담았다(execute skill의 *"Do not write the code yourself"*,
      verify skill의 *"An agent's claim of success is not evidence"*) — 그러나
      산문이고, ADR-0026이 요구한 *"기록 요구를 유지한 채"* 라는 제약 아래의
      결정은 여전히 없다. **Phase 9인 이유**: 같은 Phase의 brownfield가 정확히
      같은 형태의 문제(루프 밖 코드를 어떻게 Verify에 넣는가)이고, 둘을 따로
      결정하면 서로 어긋난다.
- [ ] **worker가 Mission Control을 재귀 호출하는 것을 무엇이 막는지 결정한다
      (2026-08-09 등록, Phase 7 종료 검토).** 로드맵이 Phase 7에 배치한
      `recursion/security tests`가 미이행이고, 실측 결과 방어가 lane마다 다르다 —
      텍스트 lane(Claude)은 `--strict-mcp-config --setting-sources ""`로 MCP
      재발견과 설정 상속을 끊지만(ADR-0036), **실행 lane(`codex exec`)에는
      대응물이 없어** `~/.codex/config.toml`을 그대로 상속한다. 거기에
      `mcx-mcp`가 등록되면 worker가 Core를 호출할 수 있고
      [ADR-0004](../adr/0004-stage-scoped-minimum-capability.md)가 깨진다 —
      **그 등록을 하는 것이 정확히 Phase 8**이라 지금 도달 불가인 이유는
      방어가 아니라 우연이다. upstream 대조(baseline `9486c78`): upstream의
      `codex exec` 명령에도 MCP 차단 플래그는 없고, 대신 `--profile`을 *"the
      worker-isolation boundary"* 로 명시해 쓴다
      (`orchestrator/codex_cli_runtime.py`) — 우리에게 없는 축이다. 결정 대상은
      **"profile 축을 들여올 것인가, `codex exec --ignore-user-config`로 끊을
      것인가"** 이며, 후자는 사용자 모델·프로필 설정까지 함께 떨어뜨린다.
      [ADR-0033](../adr/0033-first-runtime-adapter-contract.md) adapter 계약
      변경이자 실행 모델 축이라 구현 편의로 확정하지 않는다. **시한 Phase 8**
      ([progress 0007](../progress/0007_MCP_CONTROL_SURFACE.md) §2.2).
- [ ] **Verify lineage 요구와 brownfield가 양립하는지 결정한다 (2026-08-09
      등록, [ADR-0042](../adr/0042-skill-and-core-ownership-boundary.md) §8).**
      [ADR-0026](../adr/0026-verify-entry-requires-lineage.md)은 Verify 진입에
      Execute Gate `CLEAR`를 요구하고, 위 항목의 결정이 *"기록 요구를 유지한 채"*
      내려져야 한다는 제약까지 걸어 뒀다. 그런데 **Phase 9 brownfield는 본래
      루프 밖 코드를 다루는 일**이다 — 기존 코드베이스의 코드는 우리 Execute가
      만들지 않았다. 두 요구가 그대로면 brownfield에서 Verify를 쓸 수 없다.
      ADR-0026의 근거(upstream 실물 사고 §12.3 — 기록 없는 작업이 평가를
      통과했다)는 여전히 유효하므로 요구를 그냥 푸는 것은 답이 아니다. **시한
      Phase 9 진입 전.**
- [x] **tool description을 무엇으로 채울지 결정한다 (2026-08-09 등록·이행).**
      → CLI 하위 파서의 `help=`에서 **파생한다.** 24개 명령에 문구를 넣고
      description이 그것을 읽는다 — 원천이 하나라 `mcx <stage> --help`와 tool
      목록이 같은 문장을 쓴다. 장기 명령 셋은 `(장기)` 표시를 달아 host가
      `mcx_start_*` 짝을 언제 쓸지 판단하게 했다. 검사 셋으로 고정(이름 반복
      금지·원천 일치·장기 표시). Phase 8 시한 안에 이행했으나 skill을 쓰면서도
      미뤄 두었다가 **종료 검토에서야 고쳤다**
      ([progress 0008](../progress/0008_PLUGIN_COMPOSITION_LAYER.md) §2.1).
- [ ] **skill을 몇 개 둘지 결정한다 (2026-08-09 등록, Phase 8 종료 검토).**
      upstream은 22개, 우리는 6개다. 대응물이 이미 있는 것(`status`·`cancel`)과
      해당 Phase가 아닌 것(`evolve`·`brownfield`·`auto`·`ralph`)은 근거가
      명확하다. **판단이 필요한 것은 `setup`·`config`다** — 우리 설정은
      `config.toml` 하나이고 모델은 자동 seeding되므로 대화형 설정 skill의
      필요가 upstream보다 작지만, **"필요 없다"는 결정을 내린 적이 없다.**
      시한 **Phase 9** — 실사용이 설정 UX의 필요를 드러내는 자리다.
- [ ] **차단 질문을 서버가 사람에게 직접 묻지 않는 결정의 upstream 대응물을
      확인한다 (`upstream 미확인`, 2026-08-09 등록).** 우리는 `HOLD`의
      `blocking_reasons`를 데이터로 돌려주고 host가 사람에게 중계하기를
      기다린다. 근거는 [04_MCP §1-4](../04_MCP.md)(*"host 대화 session은
      durable Mission의 identity나 저장소가 아니다"*)이며 우리 쪽 문서다 —
      서버가 직접 물으면 그 답이 어느 mission의 것인지 서버가 기억해야 한다.
      upstream이 같은 자리를 어떻게 두는지는 대조하지 않았다.
- [x] **upstream이 CLI를 얇게 둔 이유를 조사한다 (Phase 6 시작 전).**
      → 의도다 — 조사가 전제도 정정했다
      ([CLI_UPSTREAM_FINDINGS](./CLI_UPSTREAM_FINDINGS.md)): `ooo seed`는
      QA·승인 없는 저장이 아니라 전 단계 완료 검사 + ambiguity gate(대화형
      계속/강제/취소)를 가진 재개·스크립트용 primitive다. 표면이 얇은 것은
      공유 핸들러 위임으로 CLI/MCP 불일치를 막는 명문 원칙(qa.py·status.py
      주석)이고, Seed QA 루프는 합성 계층 둘(skill, `ooo auto`
      REVIEW↔REPAIR + GradeGate)이 항상 붙인다. `mcx blueprint`의 QA 상시
      포함은 upstream use case를 부수지 않는다.
- [x] **`mcx` CLI의 대화형 지점을 결정한다.** →
      [ADR-0038](../adr/0038-mcx-cli-surface-contract.md): v1은 전부
      **비대화형 단발** — 사용자 결정은 인자와 별도 명령으로만 들어오고
      (도그푸딩 2회 검증 형태, Lifecycle §10.2·§10.4 구조 강제), QA
      EXHAUSTED는 exit 2 + §10.1 형식 안내로 멈춘다. exit code는 upstream
      정렬 0/1/2 (판정 부정 = 2, `qa.py:108-109`). QA 우회 플래그와
      ambiguity 강제 생성 대응물은 도입하지 않음(등록된 divergence).
      upstream의 대화형 프롬프트는 합성 흐름(`ooo init`)의 것이라 합성 흐름
      도입 시 재평가 (ADR-0038 §7).

## 9. Persistence and Telemetry decisions

기초 조사는 [PERSISTENCE_UPSTREAM_FINDINGS.md](./PERSISTENCE_UPSTREAM_FINDINGS.md)에
있다. Brief 범위의 baseline은 ADR-0013에서 결정했고, 실행 **상태**의 저장은
Phase 3에서 확정되었다(mission당 단일 JSON 문서, 지속이 dispatch보다 먼저 —
[ADR-0024](../adr/0024-execute-v1-execution-model.md) §4). 실행
**이벤트**(event/report/bundle) 스키마와 나머지는 **Phase 4 진입 전에
§5(evaluate lineage)와 함께** 확정한다 — 스키마의 소비자는 Verify·Recover이며,
소비자 요구를 모른 채 확정하면 upstream 근거 없는 발명이 된다
([progress 0003](../progress/0003_EXECUTE_VERTICAL_SLICE.md) 종료 검토에서
시점 정정. 원래 문구는 "Phase 3 설계 직전"이었다).

- [-] file store, SQLite, event sourcing 중 v1 baseline을 결정한다. (Brief
      범위는 ADR-0013, 실행 상태는 같은 형태의 파일 문서로 구현 — 실행
      이벤트의 저장은 event schema와 함께)
- [-] atomic state transition과 crash recovery 요구를 정의한다. (Execute
      범위는 ADR-0024 §4로 확정 — 지속이 dispatch보다 먼저, 크래시 후
      `DISPATCHED`로 남음이 곧 "결과 불명". Mission 전체 수준은 미정)
- [-] Telemetry event/report/bundle schema를 결정한다. **(2026-08-09 `[x]`에서
      되돌림 — schema 결정은 닫혔지만 event 층은 시한을 도과했다. 아래 참조.)**
      → 층별 소유·시점 확정
      ([ADR-0027](../adr/0027-telemetry-layers-and-v1-schema.md), upstream
      실물은 [EVALUATE_UPSTREAM_FINDINGS](./EVALUATE_UPSTREAM_FINDINGS.md)):
      report 층은 v1 스키마까지 확정(Verify가 생산·소비, Phase 4에서 최종
      필드명), attempt 시각은 Phase 4에서 Clock port와 함께, event 층은
      생산자(스트리밍 adapter)와 함께 Phase 5, bundle은 Phase 4 semantic
      설계에서.

      **2026-08-09 — event 층은 Phase 5 시한을 무처분 도과했다.** Phase 5는
      2026-08-08 종료됐고 스트리밍 생산자는 없다(`src/`에 event 타입 부재).
      Phase 5 종료 검토는 질문 7을 수행하지 않았고, 소급 처분 7건에도 이
      항목은 없었으며, Phase 7 종료 검토는 "시한 미배치"로만 적고 재지정하지
      않았다 — **검토 셋을 통과한 도과**다. 발견 경로는 외부 지적의 검증이었다.
      **새 시한 Phase 9 (제안)**: 실사용에서야 진행 표시가 실수요가 되고 같은
      Phase의 `changed_files`가 같은 생산자를 요구한다. bundle 층은 여전히
      미도입이며 시한이 없다 — 그 사실을 여기 남긴다.
- [-] retention, redaction, output-size 정책을 결정한다. → 발췌·출력 한도는
      report 층 구현 시 upstream 상수와 대조(ADR-0027 §5). **secret
      redaction은 닫혔다 (2026-08-09 —
      [ADR-0040](../adr/0040-secret-redaction-boundaries.md)):** 프로필 둘
      (저장=자격증명만·경로 유지, host=자격증명+경로), lifecycle 기록은
      마스킹이 아니라 거부, 강제는 모델·쓰기 경계.
      원래 시한(Phase 5)은 무처분 도과했고 Phase 7 진입 조건으로 재지정돼
      해소됐다. 조사에서 `state/current_mission`만 0644였음이 드러나 함께
      고쳤다 — "0600이 유일한 방어"라는 기존 기술은 전부 참이 아니었다.
      **retention(원장 보존·회전)은 열려 있다** (ADR-0038 §7 보류, 미조사).
- [-] Mission replay와 resume의 최소 보장 수준을 결정한다. → **부분 이행
      (2026-08-09, Phase 7).** 장기 명령 **취소**는 닫혔다
      ([ADR-0041](../adr/0041-mcp-control-surface-contract.md) §5 — 디스크
      마커 + runtime 관측, 실물 프로세스 종료 테스트). 명령 단위 재개는 파일
      상태로 이미 보장된다(도그푸딩 3회 실증 — 매 명령이 독립 프로세스).
      **남은 둘은 Phase 9로 재지정** (Phase 7 종료 검토): 명령 도중 중단의
      뒷정리(`DISPATCHED` 잔해)와 runtime resume. 둘 다 "무엇으로 되돌아가는가"를
      요구하므로 worktree·checkpoint·rollback과 같은 자리다
      ([progress 0007](../progress/0007_MCP_CONTROL_SURFACE.md) §1.7).

---

## 10. Reflect/Evolve decisions (Phase 10 — 사용자 결정 2026-08-09)

2026-08-09 대조에서 **미등록 공백**으로 발견됐다: upstream의 stage 축은
4개(interview/execute/evaluate/**reflect** — `orchestrator_stage.py`)이고
`ooo evolve`의 mission 간 진화 루프("평가 결과가 다음 스펙을 개선")가
제품 정체성의 절반인데, mcx에는 대응물도 제외 기록도 없었다. 사용자
결정: 제외가 아니라 **전체 도입 조사 (Phase 10)**.

**2026-08-09 범위 격상 (사용자 지시).** "도입 여부 조사"가 아니라 **확실하게
구성**한다. 예비 조사에서 reflect의 정체가 확인됐기 때문이다 — reflect는
부수 작업 단계가 아니라 **2세대 이후의 Interview 대체품**이다
(`evolution/reflect.py`: *"Interview is Gen 1 only; Reflect handles all
subsequent generations autonomously"*). Wonder는 *"What do we still not
know?"*로 빈틈을 찾고, Reflect가 그 위에서 다음 Seed의 AC와 ontology 변형을
만든다. 아키텍처 설명은 reflect 하네스로 **Hermes**를 배치하지만 실제 선택은
stage 설정→profile default→orchestrator fallback 순서라 자동 고정되지 않는다.
Hermes는 upstream 정식 backend이고 로컬 실물도 있다 (`~/.local/bin/hermes`).

- [ ] **Hermes를 reflect에서 어떻게 쓰는지** 조사한다 — 호출 계약, 프롬프트,
      출력 스키마, 다른 backend와 다르게 다루는 점.
- [x] **자가개선 결과가 다음 작업에 연결되는 경로** 조사 완료 (2026-08-10 —
      [EVOLVE findings](./EVOLVE_UPSTREAM_FINDINGS.md) §7~§10). 완료된 부모
      Evaluate의 Seed·execution output·evaluation summary를 Wonder→Reflect에
      넣고, `parent_seed_id`가 있는 후속 Seed를 같은 generation 호출 안에서
      Execute→Evaluate한 뒤 event로 기록한다. 다음 `evolve_step`은 채팅이 아니라
      그 event를 replay한다. 실패·중단·hard crash는 새 generation이 아니라 같은
      번호의 durable checkpoint에서 재개한다.
- [x] **upstream의 내부 phase 축과 우리 다섯 Stage의 대응을 대조했다.**
      (2026-08-10 — [EVOLVE findings](./EVOLVE_UPSTREAM_FINDINGS.md) §11,
      2026-08-09 Phase 6 종료 검토에서 시한 재지정 —
      [ADR-0037](../adr/0037-mission-record-and-canonical-stage.md) §5는 이
      대조를 Phase 6 시한으로 걸었고 **무처분 도과했다**.) 기존 기술을 정정한다:
      `Stage`는 4개 runtime routing 어휘이고 `RALPH_HANDOFF`·
      `UNSTUCK_LATERAL`은 별도 `AutoPhase`다. 전자는 Execute→Verify handoff,
      후자는 Recover 내부의 bounded lateral recovery라 `current_stage`에 새 값을
      추가하지 않는다. generation의 `wondering`~`evaluating`도 별도
      `GenerationPhase` 복구 checkpoint다.
- [ ] Wonder/Reflect 출력의 mcx 대응물을 결정한다 — 우리 Brief/Blueprint의
      어디로 들어오는가. Gen 2+에서 Brief를 대체하는지, 입력으로 합류하는지가
      핵심 갈림길이다 (도그푸딩 기록이 수동으로 하던 역할의 자동화).
- [ ] 도입 ADR을 작성하고 구현한다. Hermes adapter가 필요한지는 조사 결과에
      달렸다 — 텍스트 lane 축이면 `CompletionEngine` 추가로 끝난다.

---

## Definition of resolved

질문은 답변 문장 하나가 생겼다고 완료되지 않는다. 다음을 모두 만족해야 한다.

- primary source 또는 재현 가능한 실험 근거가 있다.
- Mission Control에 채택할지 말지 결정했다.
- 중요한 결정이면 ADR이 있다.
- 관련 Architecture/Stage Guide가 갱신되었다.
- 검증할 테스트 또는 acceptance condition이 있다.
