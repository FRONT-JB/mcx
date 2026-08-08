# Dogfooding 0002 — 혼합 vendor 완주와 Recover 경로 첫 실물 관측

- 일시: 2026-08-08
- Evidence level: **Verified by execution**
- 구성: **사용자 확정 구조** — 텍스트 lane 7종은 Claude(`ClaudeCompletion`,
  ADR-0036), 실행·교정은 Codex(`CodexExecutionRuntime`). mechanical 검증은
  AI 아님.
- 미션: `dogfood-0002` — "중복 줄 제거 CLI(dedupe.py)" (빈 workspace,
  stdlib 전용, subprocess 기반 unittest 스위트 포함)
- 결과: **Brief부터 `CLEAR`(MISSION COMPLETE)까지 완주. Recover
  실패→교정→재검증 경로가 처음으로 실물에서 돌았다.** 산출물은 수동 spot
  check에서 계약대로 동작 (14 tests OK, `--help`가 파일 경로로 처리).

## 1. 수치 요약과 0001 대비

| 항목 | 0002 (claude+codex) | 0001 (전부 codex) |
|---|---|---|
| AI 호출 수 | **48** (claude 40 + codex 8) | 47 |
| closure 감사 | 5순환, **순환당 45~105s** (병렬 lane) | 5순환, 순환당 125~237s (순차) |
| 확정 사안 재차단 | **0건** (후보 전체 투영) | 2순환 낭비 |
| Blueprint QA | **3회에 PASS (0.72→0.87→0.90)** | 5회 소진, 최고 0.79, 임계 미달 수락 |
| Execute | AC 7개 + 교정 1회 (74~173s/AC) | AC 6개 |
| Verify semantic | 7/7 satisfied, score 0.92~0.97, uncertainty 0.05~0.15 | 6/6, uncertainty ≤0.02 |
| Recover | **실물 관측 완료** (아래 §3) | 미발동 |

사전 추정 25~45회 대비 48회 — 소폭 초과. 원인: ① 운용자 실수 1건의 재수행
5회(§4), ② Claude 생성기가 AC를 7개로 잘게 나눠 실행·판정 호출 증가.
감사 wall-clock은 ADR-0035 §2(병렬화)로 약 **1/2~1/3**이 되었다.

## 2. ADR-0035 수정의 효과 실측

- **후보 전체 투영 (§1)**: 확정된 non-goal·계약을 감사가 재차단하는 일이
  사라졌다. closer는 매 순환 확정 후보를 조목조목 인용하며 판정했다.
- **폐기 후보 잔존**: 여전히 목록에 남지만, 이번에는 두 advisory lane이
  **스스로 MEDIUM으로 강등**하며 "전사에 폐기가 명시돼 있어 성실히 읽으면
  해소된다 — 필요한 것은 목록 정리이지 새 질문이 아니다"라고 판정했다.
  upstream의 "정본은 전사" 원칙이 가시성만으로 성립함을 확인.
- **QA 궤적·threshold 전달 (§3)**: 점수가 0.72→0.87→0.90으로 단조 수렴해
  **실 AI QA의 첫 PASS**가 나왔다. 0001의 역행(0.79→0.73)과 대조적 —
  당시 결핍이 입력 문제였다는 처분을 실측으로 뒷받침한다.
- **고정 필드 프롬프트 (§4)**: 채점 지적 17건 중 제약 원문 수정 요구는
  0건이었다 (0001에서는 반복 지적).

## 3. Recover 경로 실물 관측 (결함 주입은 투명하게 수행)

Execute Gate `CLEAR` 후 **운용자가 `test_dedupe.py`를 의도적으로 제거**했다
— worker가 완료를 주장했지만 산출물이 없는 upstream §12.3 시나리오의 재현.

1. `verify-mech`: 6/7 통과, coverage AC만 `missing_artifacts:
   [test_dedupe.py]`로 실패 (명령은 실행되지 않음 — artifacts 우선 순서).
   Gate `HOLD`.
2. `recover-plan`: 저장된 기록에서 packet 파생 — `mechanical_failed` /
   `unclassified` / `error_excerpt: "expected artifacts missing:
   test_dedupe.py"` / retries_used 0.
3. `recover-dispatch`: 교정 attempt #8이 `previous_failure`를 싣고 codex로
   나가 146초 만에 스위트를 재작성했다.
4. 재검증: mechanical 7/7 (기존 verdicts는 새 evidence가 무효화),
   semantic 7/7 → **`CLEAR — MISSION COMPLETE`**.

미관측으로 남은 것: 재시도 예산 소진(2회), `change_approach` 신호, 동일
오류 해시 3회 중단, BLOCKED/STALL 분류 — 교정이 1회에 성공했기 때문.

## 4. Claude 텍스트 lane 품질 관측

- **질문 생성기**: 4문 전부 실질 (동등성 기준, I/O 계약, 오류·인코딩, 줄
  종결자). targeted_gap 서술이 codex보다 구체적.
- **closure 감사**: 구현 수준 함정을 잡았다 — Python universal newlines가
  단독 `\r`을 재작성해 "줄 중간 \r 보존" 계약과 충돌(HIGH, 산출물의 수제
  `split_lf_lines`로 이어짐), 끝 종결자 뒤 빈 조각의 off-by-one과 빈 파일
  규칙 모순(양 lane HIGH), PEP 538 로케일 승격, fd 리다이렉션 순서까지.
  HIGH 4순환 전부 material, 5순환째 READY 수렴 (0001과 같은 패턴).
- **Blueprint 생성기**: AC 7개에 바이트 단위 검증 명령(`cmp`, 로케일 통제,
  AST import 검사)을 작성 — codex보다 잘게, 더 공격적으로. 대신 하류
  실행·판정 호출이 늘어난다 (granularity의 비용 축).
- **QA 채점자**: 지적 17건 전부 실제 결함 — `;`에 삼켜지는 grep 체인,
  PEP 538로 무력화되는 로케일 테스트, `sys.stdlib_module_names`의 3.10+
  의존, /tmp 공유 경로 경합, 수단-AC 판별(granularity contract 적용)까지.
- **semantic 평가자**: uncertainty 0.05~0.15로 codex(≤0.02)보다 높게
  보고 — 더 겸손한 보정. 임계(0.3) 아래라 판정에는 영향 없음.

## 5. 운용 관측 2건

- **운용자 실수를 Gate가 막았다**: required 후보를 unknown으로 내리자
  `REQUIRED_UNKNOWN` 차단 + handoff 진입 거부. 복구(재확정)에 재평가·재감사
  5호출이 들었다 — 필수 후보의 대체는 "새 후보 먼저, 옛 후보 강등은 그 후"
  순서가 안전하다 (운용 절차 교훈).
- **verify 명령의 workspace 밖 부작용**: revision 1 초안이 `/tmp/mcx_*`
  고정 경로에 쓰는 명령을 만들었고, QA가 경합 위험으로 지적해 mktemp로
  고쳐졌다. mechanical runner는 workspace 밖 쓰기를 차단하지 않는다 —
  repo 수준 명령 층(ADR-0028 §2 보류)과 같은 자리에서 다룰 항목으로 기록.
