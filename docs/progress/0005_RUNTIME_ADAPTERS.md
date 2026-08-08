# Progress 0005 — Phase 5: Concrete Runtime Adapters 종료 검토

- 일시: 2026-08-08
- 범위: ExecutionRuntime(Codex)·완성 엔진 2종(Codex·Claude)·위임 port 7종의
  vendor 중립 어댑터, 비용·속도 동등성 처분, 실 AI 도그푸딩 2회
- Evidence: ADR-0033~0036, commits 33fa5ba·32a3f17·c1f78db·9df7dd6·0262690,
  530 tests (adapter conformance 95),
  [DOGFOODING_0001](../research/DOGFOODING_0001.md)·
  [DOGFOODING_0002](../research/DOGFOODING_0002.md) (Verified by execution),
  [RUNTIME_UPSTREAM_FINDINGS](../research/RUNTIME_UPSTREAM_FINDINGS.md) §1~§10
- 상태: **검토 수행 완료. Phase 완료 선언은 잔여 항목 처분(사용자 결정)
  대기** — 아래 §3.

## 1. 여섯 질문에 대한 답

### 1.1 구조 검사 — 각 방어가 막는 결함

| 방어 | 막는 결함 |
|---|---|
| 명령 구성 순수 함수 + conformance 고정 (양 엔진·실행 adapter) | 플래그 드리프트와 bypass 경로가 테스트 없이 스며드는 것 |
| 침묵 timeout(실행)·총시간 timeout(완성) + process group 정리 | 매달린 worker/완성이 파이프라인을 무기한 정지시키는 것 |
| 실행 adapter의 자체 재시도 금지 | 부작용 시점을 입증 못 하는 재시도가 중복 부작용을 만드는 것 |
| CLI측 스키마 검증(`--output-schema`/`--json-schema`) + 부재 시 예외 | prose·손상 출력이 조용히 성공으로 해석되는 것 |
| transient 패턴만 재시도 (두 엔진 공유) | 결정적 실패의 무의미한 반복 과금 |
| codex read-only sandbox / claude 도구 카탈로그 봉투 | 위임 role의 쓰기·재귀 (ADR-0004의 플래그 강제) |
| `ac_key`·lane의 요청측 바인딩, 축 외 채점 거부 | 판정·관점의 잘못된 귀속, 집계 오염 |
| 원문 보존은 프롬프트 지시 + 결정적 범위 검사의 이중 | 제약 재해석이 프롬프트 위반만으로 통과하는 것 |

프롬프트로만 막는 계약 중 미표시였던 것: 없음 — 단, 실행측
`allowed_tools`의 도구 단위 차단은 여전히 미강제이며 ADR-0033 §6 보류
표에 있다. progress의 Phase 3 라인이 "실제 차단은 Phase 5"라고 낡은
약속을 유지하고 있었다 → **수정** (§2-①).

### 1.2 부품/단계 구분

다섯 Stage 전부가 실제 어댑터로 end-to-end 2회 완주했다 (0001 전부 codex,
0002 claude+codex — Recover 경로 포함). 미조립 부품을 완료로 기록한 곳은
없다 — OpenCode·session/resume/cancel·capability mapping은 체크리스트에
열린 채다. 조립(구성 주입)은 아직 호출자 소유이며 repo 수준 composition
root는 Phase 6(CLI)의 산출물이다 — 이 부재는 결격이 아니라 Phase 경계다.

### 1.3 미등록 이탈

Phase 5가 만든 upstream과의 차이는 전부 등록되어 있다 — prose 재질의
불채택(ADR-0036 §3), 감사 lane 병렬화·투영 확대·QA 궤적(ADR-0035,
upstream 정렬이므로 이탈 아님), 고정 필드 프롬프트(ADR-0035 §4, 대응물
없음 등록), timeout 형태 비대칭(ADR-0036 §3). 검토에서 하나를 보강했다:
무도구 봉투의 `--max-turns 1`은 우리 임의값이 아니라 upstream pairing
(`verification_artifacts.py:109` — "allowed_tools=[] paired with
max_turns=1")인데 ADR-0036 §4가 근거를 인용하지 않았다 → **보강** (§2-②).

### 1.4 표시 없는 보류

등록 확인: OpenCode·capability mapping(체크리스트), session/resume/
cancel·도구 단위 차단(ADR-0033 §6 표), SDK 전송·envelope telemetry 소비
(ADR-0036 §5). 미표시 1건 발견: **mechanical 명령의 workspace 밖 부작용
무차단** — 0002에서 초안 verify 명령이 `/tmp` 고정 경로에 쓰는 것으로
실물 관측되었는데 research에만 있었다 → progress의 Verify 한계에 **등재**
(§2-③).

### 1.5 계약 문장 원문 여부

문장이 곧 계약인 곳은 전부 upstream 영어 원문이다 — SUCCESS CONTRACT,
granularity contract, quality bar, interviewer 역할 경계, closure 기준
3종, semantic의 declared-contract 문장. Phase 5가 새로 쓴 영어 문장(고정
필드 안내, judge 역할문)은 upstream 대응물이 없는 우리 문장이며 그렇게
등록되어 있다 (ADR-0035 §4).

### 1.6 관측 대조

도그푸딩 2회·스모크 5회의 관측과 모순되는 규칙은 발견하지 못했다.
정정이 필요했던 관측(–`-full-auto` 부재, workspace 부재, json_schema 1급
지원)은 각 ADR 정정 note로 이미 반영되어 있다. 남은 관측-규칙 긴장 2건은
기록만 한다: ① claude 무도구 호출이 `--max-turns 1`에서도 `num_turns 2`로
성공한다(구조화 출력의 내부 도구 턴 — findings §10), ② claude semantic
평가자의 uncertainty(0.05~0.15)가 codex(≤0.02)보다 높게 보정된다 — 임계
0.3 아래라 판정 무영향.

## 2. 검토가 잡은 것 (전부 이번에 수정)

1. progress Phase 3 체크리스트의 "실제 차단은 Phase 5" — Phase 5의 실제
   결과(sandbox 수준 강제 + claude 텍스트 lane의 도구 카탈로그 강제, 도구
   단위 allowlist는 ADR-0033 §6 보류)로 갱신.
2. ADR-0036 §4 무도구 `--max-turns 1`에 upstream 근거 인용 추가.
3. mechanical 명령의 workspace 밖 부작용 무차단을 progress Verify 한계에
   등재 (0002 §5 관측의 소급 표시).

## 3. 잔여 항목의 처분 — 사용자 결정 대기

체크리스트에 열린 세 항목은 서로 묶여 있다. ADR-0003이 "초기 Runtime은
Codex/OpenCode"로 잡았으나, 사용자 확정 구조(2026-08-08)는 claude 텍스트
+ codex 실행으로 이미 충족되어 OpenCode의 v1 필요성이 약해졌다.

| 항목 | 붙어 있는 것 |
|---|---|
| OpenCode adapter conformance | ADR-0003 초기 범위; capability mapping의 실물 대상 |
| session/resume/cancel | ADR-0033 §6 보류 — 둘째 실행 adapter 또는 장기 세션 필요 시 |
| local model capability mapping | OpenCode 도입 시 실물이 생김 |

선택지: (a) 셋을 Phase 5에서 분리해 후속 backlog로 이동하고 Phase 5를
완료 선언 (ADR-0003 범위 note 필요), (b) OpenCode adapter까지 Phase 5
안에서 구현 후 완료 선언. 처분은 사용자 결정으로 올린다 — 결정 전까지
Phase 5는 "검토 수행, 선언 대기" 상태다.

## 4. 미관측으로 남은 것 (결격 아님, 다음 실물 기회에)

- Recover의 재시도 예산 소진·`change_approach`·동일 오류 해시 중단·
  BLOCKED/STALL 분류 (0002에서 교정 1회 성공으로 미도달)
- claude `--json-schema`의 스키마 위반 시 CLI 동작 (위반 사례가 발생하지
  않아 미관측 — 위반 시 `structured_output` 부재 예외 경로가 방어)
