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

---

## 1. Upstream baseline

- [-] baseline commit의 `pyproject.toml`과 package 경계를 기록한다.
- [-] `ooo interview` skill, MCP handler, CLI path의 실제 종료 Gate를 end-to-end로 추적한다.
- [-] architecture의 `ambiguity <= 0.2`와 current source의 user-controlled completion을 reconciliate한다.
- [-] completion candidate streak와 user approval의 실제 호출 경로를 확인한다.
- [-] answer provenance enum과 requirement authority 규칙을 확인한다.
- [ ] Seed 생성 → QA → repair → approval path를 실제 handler/test로 추적한다.
- [ ] Seed field와 immutability/revision behavior를 source/test에서 확인한다.
- [ ] Run이 AC를 atomic-first로 시도하고 분해하는 정확한 조건을 확인한다.
- [ ] executed-unverified에 대응하는 upstream state/event를 확인한다.
- [ ] Evaluation pipeline의 current short-circuit와 consensus trigger를 tests로 확인한다.
- [ ] Repair, resilience, evolve, seed repair의 경계를 비교한다.
- [ ] Codex/OpenCode Runtime의 cancellation/resume/error normalization을 비교한다.
- [ ] MCP authoring handler와 execution handler의 recursive dispatch guard를 확인한다.
- [ ] pinned commit의 LICENSE와 copied code notice 요구를 구현 직전에 재확인한다.

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
      upstream도 CLI에 user identity 없음). MCP(Phase 7)의 host 대리 승인
      경로만 잔여.
- [ ] user-edited YAML을 지원할지 결정한다.
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
- [ ] parallel execution 도입 Gate를 정의한다.
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
- [ ] semantic 판정의 AC 병렬화를 결정한다. — 도그푸딩 0003에서 AC 9개
      순차 판정에 ~12분 (AC당 ~80s, 서로 독립). 감사 3-lane 병렬화
      (ADR-0035 §2)와 같은 축이나 **upstream evaluate의 AC 병렬 여부
      미확인** — 조사 후 처분 ([DOGFOODING_0003 §5](./DOGFOODING_0003.md)).
- [ ] semantic verdict의 일괄 저장을 유지할지 결정한다. — 진행 중 가시성이
      0이라 12분간 진척 확인 불가 (0003 §5). status 박스(§8)와 함께 처분.
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
- [ ] rollback 지원 범위를 결정한다. (Phase 5 workspace 관리와 함께 —
      upstream `core/worktree.py` 조사 포함, ADR-0032 보류)
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
- [ ] native event 보존과 normalized Telemetry 연결 방식을 정의한다.
      (스트리밍·event 층과 함께 — ADR-0027 §3)
- [-] timeout/cancel/resume contract를 정의한다. → timeout은 침묵 900초
      (upstream stall 채택, ADR-0033 §4). cancel은 스트리밍과 함께, resume은
      upstream 정합 검증(바이너리 해시·모델 고정)과 대조해 도입 (§6 보류)
- [ ] OpenCode local/provider/agent mode를 capability로 어떻게 표현할지
      결정한다. (OpenCode adapter 도입 시 —
      [RUNTIME_UPSTREAM_FINDINGS §6](./RUNTIME_UPSTREAM_FINDINGS.md) 미조사)

## 8. MCP and CLI decisions

- [ ] MCP tool 하나가 한 Stage command와 1:1인지 command/query를 분리할지 결정한다.
- [ ] request/response schema와 error envelope를 정의한다.
- [ ] host session, Mission ID, Runtime handle 전달 규칙을 정의한다.
- [ ] async job/polling/notification 방식을 결정한다.
- [ ] disconnect, cancel, timeout의 의미를 분리한다.
- [ ] CLI와 MCP parity test 전략을 정의한다.
- [ ] **status 박스를 도입한다 (사용자 제안 2026-08-09, 도그푸딩 0003).**
      명령 단위 journal(명령·시작 시각·소요·exit code를 mission별 파일에
      append — 시작 시 기록해 "진행 중"도 표현) + `mcx status`의 구간표
      렌더. upstream 대응물: `ooo status auto`의 "한 줄 한 사실" 블록·스냅샷
      고정·CLI/MCP 미러 ([CLI_UPSTREAM_FINDINGS §5](./CLI_UPSTREAM_FINDINGS.md)),
      `AutoPipelineState.phase_started_at`/`last_progress_at`. 쓰기 주체는
      CLI뿐(ADR-0037 경계 유지) — ADR-0038 개정으로 도입.
- [ ] plugin 설치·발견·설정 UX를 결정한다. — upstream의 배포 실물은
      **plugin = skills + MCP server + CLI 3층**이며 skill이 MCP tool을
      orchestrate한다 (`skills/seed/SKILL.md` frontmatter
      `mcp_tool: ouroboros_generate_seed`,
      [CLI_UPSTREAM_FINDINGS §3](./CLI_UPSTREAM_FINDINGS.md)). 우리 대응:
      Phase 7 MCP server가 기반층이고, CLI/MCP가 같은 application service를
      공유하므로 (ADR-0038 §1) skill 래퍼와 manifest만 얹으면 된다 — Claude·
      Codex 양쪽 다 MCP 클라이언트라 같은 server가 붙는다.
- [ ] **MCP host가 자기 편집 도구로 작업하고 Verify만 호출하는 경로를 어떻게
      다룰지 결정한다.** host는 에이전트이며 `mcx` 도구와 자기 도구를 동시에
      갖는다 — upstream에서 실제로 발생한 조건이다
      ([SEED_UPSTREAM_FINDINGS §12.3](./SEED_UPSTREAM_FINDINGS.md)).
      [ADR-0004](../adr/0004-stage-scoped-minimum-capability.md)는 worker가
      위로 탈출하는 것만 막고 이 방향을 덮지 않는다.
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
- [x] Telemetry event/report/bundle schema를 결정한다. → 층별 소유·시점 확정
      ([ADR-0027](../adr/0027-telemetry-layers-and-v1-schema.md), upstream
      실물은 [EVALUATE_UPSTREAM_FINDINGS](./EVALUATE_UPSTREAM_FINDINGS.md)):
      report 층은 v1 스키마까지 확정(Verify가 생산·소비, Phase 4에서 최종
      필드명), attempt 시각은 Phase 4에서 Clock port와 함께, event 층은
      생산자(스트리밍 adapter)와 함께 Phase 5, bundle은 Phase 4 semantic
      설계에서.
- [-] retention, redaction, output-size 정책을 결정한다. → 발췌·출력 한도는
      report 층 구현 시 upstream 상수와 대조(ADR-0027 §5). secret redaction은
      Phase 5(Runtime 문서·Security ADR).
- [ ] Mission replay와 resume의 최소 보장 수준을 결정한다. (Phase 5 —
      resume 계약과 함께, ADR-0025 보류와 같은 시점)

---

## Definition of resolved

질문은 답변 문장 하나가 생겼다고 완료되지 않는다. 다음을 모두 만족해야 한다.

- primary source 또는 재현 가능한 실험 근거가 있다.
- Mission Control에 채택할지 말지 결정했다.
- 중요한 결정이면 ADR이 있다.
- 관련 Architecture/Stage Guide가 갱신되었다.
- 검증할 테스트 또는 acceptance condition이 있다.
