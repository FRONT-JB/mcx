# Research Index

이 디렉터리는 Mission Control이 무엇을 **결정했는지**가 아니라, 원본과 대화에서
무엇을 **관찰했는지**를 보존한다.

## Documents

- [UPSTREAM_MAPPING.md](./UPSTREAM_MAPPING.md) — Mission Control과 Ouroboros 개념·파일 대응
- [SESSION_DECISIONS.md](./SESSION_DECISIONS.md) — 프로젝트를 시작한 대화의 확정·폐기·미확정 결정
- [OPEN_QUESTIONS.md](./OPEN_QUESTIONS.md) — 구현 전에 원본과 우리 설계에서 확인할 질문
- [INTERVIEW_UPSTREAM_FINDINGS.md](./INTERVIEW_UPSTREAM_FINDINGS.md) — Brief 우선 조사 결과 (Open Questions §0, file:line 근거)
- [PERSISTENCE_UPSTREAM_FINDINGS.md](./PERSISTENCE_UPSTREAM_FINDINGS.md) — 저장 계층(event store, checkpoint, brownfield registry) 조사
- [SEED_UPSTREAM_FINDINGS.md](./SEED_UPSTREAM_FINDINGS.md) — Blueprint(Seed) schema와 acceptance criterion identity 조사
- [RUN_UPSTREAM_FINDINGS.md](./RUN_UPSTREAM_FINDINGS.md) — Execute 진입 경로와 Telemetry provenance 조사 (Open Questions §4 굵은 항목 한정)
- [EVALUATE_UPSTREAM_FINDINGS.md](./EVALUATE_UPSTREAM_FINDINGS.md) — Evaluate 파이프라인·Telemetry 실물 조사
- [VERIFY_UPSTREAM_FINDINGS.md](./VERIFY_UPSTREAM_FINDINGS.md) — mechanical 발견·allowlist·semantic verdict 조사
- [REPAIR_UPSTREAM_FINDINGS.md](./REPAIR_UPSTREAM_FINDINGS.md) — failure taxonomy·retry budget·progress signal 조사
- [MCP_UPSTREAM_FINDINGS.md](./MCP_UPSTREAM_FINDINGS.md) — MCP server 구조(SDK는 adapter 뒤), transport 3종, tool은 CLI와 1:1이 아님(CLI가 MCP 핸들러를 부름), 동기·비동기 tool 쌍과 job 상태 7종, 응답 envelope (Phase 7 설계 재료)
- [BROWNFIELD_UPSTREAM_FINDINGS.md](./BROWNFIELD_UPSTREAM_FINDINGS.md) — `brownfield`는 한 기능이 아니라 세 역할(모호함 4번째 축 `context_clarity`, 저장소 레지스트리, mechanical 명령 자동 검출). 검출은 AI 1회 제안 + 디스크 대조 검증 + 실패 시 버림(*"phantom failure"* 금지). ①은 혼자 켜면 미션이 Gate에서 막힌다 (Phase 9 재료)
- [SKILLS_UPSTREAM_FINDINGS.md](./SKILLS_UPSTREAM_FINDINGS.md) — plugin은 3층이고 host가 둘(Claude Code·Codex), skill이 선언하는 capability 계약, QA 루프·User Adoption Gate·감사 기록·Core 판정 재감사가 전부 skill 소유, 취소는 CLI 직접, 동시 쓰기 재확인은 대응물 없음, worker 재귀 차단은 미확인 (Phase 8 경계 ADR 재료)
- [SECURITY_UPSTREAM_FINDINGS.md](./SECURITY_UPSTREAM_FINDINGS.md) — secret redaction의 네 지점(입력 한도·로깅·저장 거부·MCP 출력 마스킹), replay-unsafe 키 목록, 우리 노출 표면 실측 (Phase 7 진입 조건)
- [RUNTIME_UPSTREAM_FINDINGS.md](./RUNTIME_UPSTREAM_FINDINGS.md) — LLMAdapter/AgentRuntime 분리, codex·claude·opencode 실행 계약 조사 (§10 Claude, §11 OpenCode 사용 시점, §12 runtime×backend 두 축과 MCP 구동 worker — §6 정정)
- [CLI_UPSTREAM_FINDINGS.md](./CLI_UPSTREAM_FINDINGS.md) — CLI 표면 두께·품질 루프의 거처·canonical phase 저장 조사 (Open Questions §8 선행 항목)
- [WORKTREE_UPSTREAM_FINDINGS.md](./WORKTREE_UPSTREAM_FINDINGS.md) — 미션 단위 worktree 격리·복원·정리 경계 조사
- [CHECKPOINT_UPSTREAM_FINDINGS.md](./CHECKPOINT_UPSTREAM_FINDINGS.md) — 평가 이후 authoritative checkpoint 정책 조사
- [ROLLBACK_UPSTREAM_FINDINGS.md](./ROLLBACK_UPSTREAM_FINDINGS.md) — 세대 lineage rewind와 작업 트리 rollback의 두 층 조사
- [CHANGED_FILES_UPSTREAM_FINDINGS.md](./CHANGED_FILES_UPSTREAM_FINDINGS.md) — 변경 파일 수집 기준점·시점·파서 조사
- [EVENT_LAYER_UPSTREAM_FINDINGS.md](./EVENT_LAYER_UPSTREAM_FINDINGS.md) — Runtime 정규화와 canonical event store의 소비자·경계 조사
- [REDACTION_FIELD_TRIAL.md](./REDACTION_FIELD_TRIAL.md) — 실제 입력 형태로 secret redaction 누락·과잉을 대조한 실물 기록
- [EVOLVE_UPSTREAM_FINDINGS.md](./EVOLVE_UPSTREAM_FINDINGS.md) — Reflect가 Gen 2+에서 Brief를 대체하는 방식과 다음 Seed 생성 충돌 조사
- [EVOLVE_BACKEND_AB.md](./EVOLVE_BACKEND_AB.md) — 같은 Wonder/Reflect 계약을 Hermes·Claude로 각 1회 실행한 품질·호출 수·token·지연·격리 비교와 Claude 기본값 유지 처분
- [DOGFOODING_0001.md](./DOGFOODING_0001.md) — 실 AI 도그푸딩 1차 (전부 codex) 관측 기록
- [DOGFOODING_0002.md](./DOGFOODING_0002.md) — 실 AI 도그푸딩 2차 (claude+codex, Recover 경로) 관측 기록
- [DOGFOODING_0003.md](./DOGFOODING_0003.md) — 실 AI 도그푸딩 3차 (설치된 mcx CLI 실물, QA EXHAUSTED·자연 Recover 첫 관측) 기록
- [DOGFOODING_0004.md](./DOGFOODING_0004.md) — Phase 9 첫 실물 관측, Brief에서 중단하고 과제 선정 오류·빈 handoff 결함을 처분한 기록
- [DOGFOODING_0005.md](./DOGFOODING_0005.md) — Phase 9 다섯 층과 rollback·checkpoint를 검증하고 `MISSION COMPLETE`까지 완주한 기록

## Evidence levels

| 등급 | 의미 |
|---|---|
| Verified | 기록한 upstream commit의 코드 또는 공식 문서에서 직접 확인 |
| Observed | 실제 CLI·화면·전사·저장 record에서 직접 관측 |
| Session-confirmed | 사용자가 대화에서 명시적으로 확정 |
| Inferred | 여러 근거를 종합한 해석이며 재검증 필요 |
| Proposed | Mission Control을 위한 설계 후보 |
| Superseded | 탐색 중 나왔지만 최종 결정으로 폐기 |

Evidence level은 사실의 **출처와 확실성**만 나타낸다. Mission Control이 그 내용을
채택했는지는 다음 decision status로 별도 기록한다.

## Decision status

| 상태 | 의미 |
|---|---|
| Accepted baseline | Constitution 또는 Accepted ADR에 반영된 현재 규범 |
| Proposed | 검토할 설계 후보이며 아직 규범이 아님 |
| TBD | 근거 수집이나 사용자 결정이 더 필요한 미확정 항목 |
| Excluded from v1 | 현재 v1 범위에서는 의도적으로 제외 |
| Superseded | 다른 결정으로 대체되어 더는 사용하지 않음 |

`Accepted baseline`은 모든 구현 세부가 확정되었다는 뜻이 아니다. 예를 들어
Runtime 분리는 Accepted baseline일 수 있지만 protocol method와 streaming shape는
여전히 TBD일 수 있다.

## Research rules

1. upstream `main`을 영구 사실처럼 인용하지 않고 commit을 기록한다.
2. 공식 저장소 코드와 문서를 우선한다.
3. 문서와 코드가 다르면 둘 다 기록하고 실제 동작 테스트를 계획한다.
4. session에서 나온 기억을 upstream 사실로 승격하지 않는다.
5. 원본 수치를 Mission Control 기본값으로 복사하기 전에 실패 사례와 테스트를 만든다.
6. 원본 코드 복사 또는 상당한 포팅 전에는 LICENSE와 고지 의무를 다시 확인한다.
7. 연구 결과가 설계를 바꾸면 관련 ADR과 Stage Guide를 갱신한다.

## Baseline snapshot

| 항목 | 값 |
|---|---|
| Upstream | `Q00/ouroboros` |
| Branch | `main` |
| Commit | `9486c78575a0332e9b84d93ef5832985291d7943` |
| Checked | 2026-08-07 |
| License observed | MIT, copyright Q00 (2025) |

이 snapshot은 연구 재현을 위한 기준일 뿐 Mission Control이 해당 코드를 vendoring
한다는 뜻이 아니다.
