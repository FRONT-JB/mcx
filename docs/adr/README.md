# Architecture Decision Records

ADR은 Mission Control의 중요한 결정을 “무엇을 선택했는가”뿐 아니라 “왜 다른
선택을 하지 않았는가”까지 보존한다.

## 규칙

- 한 ADR은 하나의 결정만 다룬다.
- upstream과 의도적으로 다른 동작은 Stage별 divergence ADR 하나에 모은다
  (Brief는 [0011](./0011-brief-deliberate-divergences.md), Blueprint는
  [0022](./0022-blueprint-deliberate-divergences.md), Execute는
  [0025](./0025-execute-deliberate-divergences.md)). 다른 ADR에서
  결정했더라도 그 divergence ADR에서 링크한다. 대조하지 못한 항목은 "차이 없음"이
  아니라 미확인으로 같은 곳에 적는다.
- 상태는 `Proposed`, `Accepted`, `Superseded`, `Rejected` 중 하나다.
- Accepted ADR의 의미를 바꿀 때는 기존 파일을 덮어쓰지 않고 새 ADR로 대체한다.
- 코드와 하위 문서는 Accepted ADR을 따라야 한다.
- Constitution을 바꾸는 결정은 ADR만으로 확정되지 않으며 사용자 승인이 필요하다.
- 구현 세부사항이 아직 없더라도 검증 가능한 consequence를 기록한다.

## Index

| ADR | 결정 | 상태 |
|---|---|---|
| [0001](./0001-workflow-before-runtime.md) | Workflow가 Runtime과 모델보다 우선한다. | Accepted |
| [0002](./0002-approved-seed-is-immutable.md) | 승인된 Seed는 실행 중 불변이다. | Accepted |
| [0003](./0003-runtime-abstraction.md) | Core와 구체 Runtime을 adapter로 분리한다. | Accepted |
| [0004](./0004-stage-scoped-minimum-capability.md) | 각 Stage는 최소 capability만 가진다. | Accepted |
| [0005](./0005-evidence-over-reasoning.md) | 진행과 완료는 Telemetry로 판정한다. | Accepted |
| [0006](./0006-dual-terminology.md) | 사용자 용어와 내부 Ouroboros 용어를 분리한다. | Accepted |
| [0007](./0007-mcp-is-control-surface.md) | MCP는 Core가 아니라 control surface다. | Accepted |
| [0008](./0008-bounded-recovery.md) | Recover는 evidence-driven이며 bounded하다. | Accepted |
| [0009](./0009-brief-completion-gate-policy.md) | Brief 종료는 네 조건을 모두 만족해야 하며 그것만으로 `CLEAR`가 되지 않는다. | Accepted |
| [0010](./0010-answer-provenance-and-requirement-authority.md) | 답변 authority를 분리하고 observation의 요구사항 승격을 투영으로 차단한다. | Accepted |
| [0011](./0011-brief-deliberate-divergences.md) | Brief에서 upstream과 다르게 가는 지점을 기록한다. | Accepted |
| [0012](./0012-python-toolchain-and-layout.md) | Python 3.12 + uv + pydantic + pytest를 사용하고, 실행 모델은 upstream처럼 도메인 동기 / use case·port async로 나눈다. | Accepted |
| [0013](./0013-brief-durable-state-baseline.md) | Brief durable state는 revision 이력을 포함한 단일 JSON 문서로 시작한다. | Accepted |
| [0014](./0014-brief-concurrent-write-protection.md) | stale write 거부를 유지하고 내용 버전과 쓰기 순서를 두 축으로 나눈다. | Accepted |
| [0015](./0015-requirement-candidate-model.md) | Non-goal·충돌·가정·미해결을 하나의 요구사항 후보 모델로 다룬다. | Accepted |
| [0016](./0016-brief-handoff-projection.md) | Brief handoff는 저장하지 않고 CLEAR된 상태에서 매번 파생한다. | Accepted |
| [0017](./0017-blueprint-schema-baseline.md) | Blueprint v1은 방향만 담고 AC는 성공 계약의 내용으로 식별한다. | Accepted |
| [0018](./0018-blueprint-generation-contract.md) | 생성기는 성공 조건만 구체화하고 범위 검사는 결정적으로 한다. | Accepted |
| [0019](./0019-blueprint-qa-loop.md) | 생성 직후 QA 루프를 Core에 두고 최선 시도를 추적한다. | Accepted |
| [0020](./0020-brief-closure-audit.md) | 점수 통과 뒤 3-lane closure 감사가 Brief 종료를 gate한다. | Accepted |
| [0021](./0021-blueprint-state-and-revisions.md) | Blueprint 상태는 revision·QA 기록·승인을 한 문서에 담고, 승인은 채점된 현재 revision을 요구한다. | Accepted |
| [0022](./0022-blueprint-deliberate-divergences.md) | Blueprint에서 upstream과 다르게 가는 지점을 기록한다. | Accepted |
| [0023](./0023-execute-entry-and-provenance.md) | Execute 작업 생성은 단일 use case 경로이고, Telemetry는 생성 주체를 선언 필드로 기록한다. | Accepted |
| [0024](./0024-execute-v1-execution-model.md) | Execute v1은 AC가 곧 실행 단위이고, 선언 순서 순차 실행에 attempt 상태 셋으로 시작한다. | Accepted |
| [0025](./0025-execute-deliberate-divergences.md) | Execute에서 upstream과 다르게 가는 지점을 기록한다. | Accepted |
| [0026](./0026-verify-entry-requires-lineage.md) | Verify 진입은 Execute Gate `CLEAR`(실행 lineage)를 요구한다 — upstream은 요구하지 않는다. | Accepted |
| [0027](./0027-telemetry-layers-and-v1-schema.md) | Telemetry 세 층은 소비자가 정의하고 생산자의 Phase에서 확정한다. report 층 v1 스키마 확정. | Accepted |
| [0028](./0028-verify-v1-mechanical-contract.md) | Verify v1 mechanical 검증 — 실행 주체는 Verify, 명령은 승인된 `verify_command`뿐, 실행 계약과 증거 필드 확정. | Accepted |
| [0029](./0029-verify-deliberate-divergences.md) | Verify에서 upstream과 다르게 가는 지점을 기록한다. | Accepted |
| [0030](./0030-verify-semantic-verdict-contract.md) | semantic verdict는 AC 단위 bool+score+uncertainty이고, 임계 셋(0.8/0.3/0.7)은 upstream 채택이다. | Accepted |
| [0031](./0031-recover-v1-failure-and-retry-contract.md) | Recover v1 — 실패 packet, AC당 재시도 2회, 실패 증거 전달, 동일 오류 3회 중단. | Accepted |
| [0032](./0032-recover-deliberate-divergences.md) | Recover에서 upstream과 다르게 가는 지점을 기록한다. | Accepted |
| [0033](./0033-first-runtime-adapter-contract.md) | 첫 adapter는 Codex ExecutionRuntime — `codex exec` 단발, sandbox 권한, 침묵 timeout, 자체 재시도 없음. | Accepted |
| [0034](./0034-codex-text-backend-contract.md) | text backend는 완성 엔진 하나를 공유 — 읽기 전용 sandbox, transient만 재시도, 구조화 출력 실패는 예외. 첫 port는 semantic 평가자. | Accepted |
| [0035](./0035-dogfooding-cost-parity-dispositions.md) | 비용·속도는 upstream 동등 이상 — 감사 lane 병렬화, 위임 입력에 후보 전체 전달, QA에 threshold·궤적 전달(ADR-0019 §3 개정). | Accepted |
| [0036](./0036-claude-text-lane-contract.md) | 텍스트 lane vendor는 Claude(ADR-0003 범위 변경) — `--json-schema`+`structured_output` 소비, 도구 카탈로그 봉투, 총시간 600s, 프롬프트 클래스는 vendor 중립. | Accepted |
| [0037](./0037-mission-record-and-canonical-stage.md) | Mission record(current Stage)는 합성 계층 소유로 Phase 6 도입 — enforcement는 Gate 재계산 유지, 닫힌 enum·합법 전이 그래프·전이 시각 (record 0004 질문 4 처분). | Accepted |
| [0038](./0038-mcx-cli-surface-contract.md) | `mcx` CLI 표면 — 비대화형 단발 명령(service 메서드 1:1), exit code 0/1/2(upstream 정렬), mission record는 CLI만 기록, 기본 조립 Claude 텍스트+Codex 실행. | Accepted |
| [0039](./0039-stage-runtime-routing-table.md) | Stage→Runtime 라우팅 테이블 — 닫힌 Stage enum 키, lane별 backend 쌍(등록된 divergence: upstream은 stage당 backend 하나), 3단 해석, fail-fast 검증, 설정 표면 `config.toml`(ADR-0038 개정). ADR-0023의 미이행 약속 이행. | Accepted |
| [0040](./0040-secret-redaction-boundaries.md) | Secret redaction — 프로필 둘(저장=자격증명만·경로 유지, host=자격증명+경로), lifecycle 기록은 마스킹이 아니라 거부(prompt·stdout·stderr가 자격증명과 같은 등급), 강제는 호출이 아니라 모델·쓰기 경계. Phase 7 진입 조건 해소. | Accepted |
| [0041](./0041-mcp-control-surface-contract.md) | MCP control surface — tool은 CLI 명령과 1:1이며 `build_parser()`에서 파생, 호출은 같은 `dispatch`를 지난다(등록된 divergence: upstream은 반대 방향). exit 2(HOLD)는 `is_error=false`. job은 원장에서 유도하고 별도 저장소를 두지 않는다. 취소는 디스크 마커 + runtime 관측. transport는 stdio, SDK는 optional extra. | Accepted |
| [0042](./0042-skill-and-core-ownership-boundary.md) | skill/Core 소유 경계 — Core는 "한 번의 판정", skill은 "몇 번·어떤 순서로 부르고 무엇을 묻는가". 판별 질문은 "같은 입력에 항상 같은 답인가". 사용자에게 묻는 것은 전부 skill이고 Core는 드러내기만 한다. 승인 actor는 Core에 넣지 않고 skill이 결정 흔적을 남긴다. QA 루프 divergence는 유지하되 대가를 명시. 실행 lane은 `--ignore-user-config`로 사용자 codex 설정을 상속하지 않고(재귀 경계), 모델은 `config.toml`이 제공하되 없으면 현재 설정을 읽어 채택·기록한다. Fact Resolver는 폐기. | Accepted |
| [0043](./0043-deterministic-blueprint-quality-floor.md) | 결정적 Blueprint 품질 하한 — upstream `GradeGate`의 등급·점수 사전은 이식하지 않는다(`CLEAR`/`HOLD` + 이유가 이미 같은 일을 한다). 위치는 Core(층 이동, upstream은 합성 계층). 새로 막는 것은 **확인 수단이 하나도 없는 Blueprint** 하나이며 upstream 대응물 없는 발명이다. 부분 커버리지는 막지 않고 세어서 드러낸다. | Proposed |
| [0044](./0044-brownfield-entry-contract.md) | Brownfield 진입 계약 — upstream `brownfield`는 세 역할(모호함 4번째 축·저장소 레지스트리·mechanical 명령 검출)이며 따로 판단한다. 레지스트리는 **미도입**(우리 CLI는 mission당 workspace 하나), mechanical 검출은 **도입**하되 축을 AC 수준으로 바꾼다(제안은 AI 1회, 검증은 디스크 대조로 결정적), 4번째 축은 **순서 제약** 때문에 검출 뒤 관측 후 결정. | Accepted |

## Template

```markdown
# ADR NNNN — Title

- Status: Proposed
- Date: YYYY-MM-DD

## Context

## Decision

## Consequences

## Rejected alternatives

## Verification
```

