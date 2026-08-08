# Dogfooding 0003 — 설치된 `mcx` CLI 실물로 실 AI 완주

- 일시: 2026-08-09 (00:40~02:03 KST)
- Evidence level: **Verified by execution**
- Mission: `m-b99bbe` (단축형 자동 생성 id) — `mdtoc.py`: 마크다운 파일에서
  GitHub식 앵커 목차를 stdout으로 출력하는 파이썬 CLI (표준 라이브러리만)
- 구성: 0002와 동일한 vendor 분리(텍스트·판정 claude 2.1.226, 실행 codex
  0.147.0) — 단, 이번에는 스크립트 드라이버가 아니라 **`[project.scripts]`로
  설치된 `mcx` 실물** (ADR-0038 표면, 단축형·최근 mission 기본값 포함)
- 결과: **MISSION COMPLETE** — semantic 9/9 충족(0.90~0.95, uncertainty
  ≤0.15, reward_hacking ≤0.06), Verify Gate `CLEAR`가 mission record에 완료
  기록. 전이 그래프 `brief→blueprint→execute→verify→recover→verify` 완주.

## 1. 수치 — 추정 대비 실측

| 축 | 추정 | 실측 | 차이의 원인 |
|---|---|---|---|
| claude 콜 | 25~40 | **50** | closure 감사 7라운드 × 3-lane = 21콜 (추정 3~6콜) — §4 |
| codex 콜 | 5~10 | **10** | Execute 9 AC + Recover 교정 1 |
| 총 콜 | 30~50 | **60** | +20% — 지배항은 감사 |
| wall-clock | — | **~75분** | 구간표는 아래 |

claude 내역: ask 6, assess 5, audit 21(7라운드×3), blueprint 생성 1,
QA 8(성공 5 + `error_max_turns` 실패 2 + 진단 1), semantic 9.

| 구간 | 시간 | 비고 |
|---|---|---|
| Brief 질문·채점 | ~2.5분 | ask 12~17s, assess 10~15s |
| Brief closure 감사 7회 | ~9분 | 라운드당 44→122s — 상태 성장에 비례 |
| Blueprint 생성 | ~2분 | 9-AC + 실행 가능한 verify 명령 |
| QA 5회 + 계약 결함 | ~19분 | 정상 반복 ~9분 + **결함 우회 ~8분** (§3) |
| Execute (codex) | ~17.5분 | AC당 56~224s |
| Recover 교정 | ~1.3분 | previous_failure 실은 재dispatch |
| Verify mechanical | 0.6s ×2 | 결정적 |
| Verify semantic | ~12분 | AC당 ~80s, 순차 |

## 2. 처음 실물로 관측된 계약 경로

1. **QA EXHAUSTED → `approve --accept-below-threshold`** (ADR-0019 §8).
   점수 궤적 0.75→0.85→0.87→0.88→0.89, 5회 소진. CLI가 ADR-0038 §2의 안내
   (exit 2 + 선택지 두 개)를 정확히 출력했고, 운용자 결정으로 0.89 수락 —
   사유 statement에 기록. 판정자가 AC9(테스트 스위트 요구)의 수단성을 5회
   일관 반대한 것이 원인 — **기각 채널 없음은 upstream 파리티임을 소스로
   재확인** (`mcp/tools/qa.py:124-135` — Iteration N: score/verdict만 렌더,
   우리 ADR-0035 §3 정렬과 자간까지 동일). 판정 철학 충돌의 설계된 출구가
   User Adoption Gate라는 것이 이번에 실증됐다.
2. **자연 발생 Recover** (0002는 주입, 0003은 자연). codex가 UTF-8 BOM
   제거를 빠뜨림 → mechanical `bom=` 불일치 → verify gate `HOLD` (exit 2)
   → `recover plan`이 mechanical_failed packet 1건 도출 → `recover
   dispatch` 교정(attempt 10) → 재검증 mechanical 9/9 → semantic → `CLEAR`.
3. **mission record 전체 전이 그래프**: brief→blueprint→execute→verify→
   recover→**verify**(재검증 edge) 전부 실 흐름 그대로 기록, status
   mismatch 0건, MISSION COMPLETE는 verify gate `CLEAR`만이 기록.
4. **exit code 계약 3종 전부 사용**: 오류 1 (QA 결함), 판정 부정 2 (brief
   gate HOLD·QA continue/exhausted·verify gate HOLD), 성공/CLEAR 0.
5. **단축형 표면**: `mcx brief "<intent>"` 시작(id 자동 생성) 후 전 과정
   `--mission` 없이 완주 — 최근 mission 기본값이 실사용에서 유효.

## 3. 도그푸딩이 잡은 우리 결함 2건 (수정 완료)

1. **무도구 봉투 `--max-turns 1` 계약 결함** — 9-AC Blueprint QA 판정이
   `error_max_turns`로 2회 재현 실패 (~8분 낭비). 근거로 인용했던 upstream
   pairing(`verification_artifacts.py:109`)은 **prose 재질의 lane**의
   것이고, 우리 `--json-schema` lane은 구조화 출력이 내부 턴을 소비한다
   (0002에서 이미 num_turns=2 관측). 무도구 상한 1→8 정정 —
   ADR-0036 §4 정정 note가 등록이다.
2. **CLI 오류 원인 사슬 삼킴** — `QaAssessmentError`만 보이고 `from error`로
   연결된 실제 원인(`error_max_turns`)이 stderr에 없어 진단에 우회 스크립트가
   필요했다. `amain`이 cause chain을 출력하도록 수정.

## 4. 집중 분석 — closure 감사와 QA (사용자 요청)

### closure 감사 7라운드는 결함인가 — 아니다, 그러나 비용 지배항이다

- **라운드 직렬화는 upstream 설계다.** upstream 합성 규칙은 "ask the
  **single highest-impact** blocking follow-up question"
  (`skills/interview` step 8) — 라운드당 질문 하나. 우리 lane 스키마의
  "strongest finding" 단수도 같은 축이며, 우리는 두 advisory lane의 질문을
  **모두** 받아 답하므로 upstream보다 라운드를 아낀 편이다.
- **지적 품질은 전부 실질**: ① 유니코드 슬러그 붕괴(한글 헤딩 전멸 위험 —
  goal의 "GitHub식"과 직결), ② 헤딩 인식 경계(해시 뒤 공백·4칸 들여쓰기·
  7해시·`## C#`), ③ 펜스 상태 머신(bool 토글이면 문서 반전), ④ 링크 헤딩의
  내부 모순(6라운드 답변 vs 7라운드 근거 — 감사가 라운드 간 모순을 잡음),
  ⑤ 재충돌 규칙(base 카운터 vs 발급 집합 루프). 전부 구현·출력을 바꾸는
  결정이었고 재지적(중복) 0건 — 답변이 `previous_rounds`로 전달되는 채널이
  작동했다.
- **비용 구조**: 라운드당 3콜 × 상태 크기에 비례하는 지연(44→122s — rounds
  6→13, candidates 7→11 재투영). 파서류 과제는 경계 사례 축으로 스펙이
  자라며 감사 라운드가 그에 비례한다. 관측으로 기록 — 상한·배치 보고는
  upstream에 없으므로(후보마다 재수행, 상한 없음 — ADR-0035 §5) 도입하려면
  divergence ADR이 선행한다.

### QA 5회 소진은 결함인가 — 루프는 일했고, 소진의 출구가 설계대로 열렸다

- 점수 단조 상승(0.75→0.89): 반복마다 실질 결함이 닫혔다 — pytest가
  stdlib-only 제약과 모순(→unittest), 수단형 AC, `python`/`python3` 환경
  가정, CRLF·BOM·탭·닫는 펜스 미정 등. **QA 판정자는 Brief 감사가 6라운드
  거치고도 남긴 구멍을 추가로 잡았다** — 두 루프의 역할이 실제로 다르다는
  실증.
- 소진의 지배항은 판정 철학 충돌(AC9) 하나 — §2-1의 파리티 확인대로 기각
  채널이 없어 5회 재제기되었고, 출구는 사용자 수락이었다. **"철학 충돌은
  상한을 소진시킨다"**를 패턴으로 기록한다 — 완화 후보(판정자에게 이전
  findings나 채택/기각을 전달)는 upstream 대응물이 없어 divergence ADR
  없이는 도입하지 않는다.

## 5. 백로그로 등록한 관측 (구현 안 함 — OPEN_QUESTIONS §5·§8)

1. **semantic 판정 병렬화 후보** — AC 9개 판정은 서로 독립인데 순차 12분.
   감사 3-lane 병렬화(ADR-0035 §2)와 같은 축. upstream evaluate의 AC 병렬
   여부 미확인 — 조사 후 처분.
2. **verdict 일괄 저장 → 진행 가시성 0** — semantic 12분 동안 저장 상태로는
   진척을 알 수 없었다.
3. **status 박스 (사용자 제안, 2026-08-09)** — 명령 단위 journal(명령·시작
   시각·소요·exit code append) + `mcx status`의 구간표 렌더. upstream
   대응물 있음: `ooo status auto`의 "한 줄 한 사실" 블록 + 스냅샷 고정 +
   CLI/MCP 미러 (CLI_UPSTREAM_FINDINGS §5), `AutoPipelineState`의
   `phase_started_at`/`last_progress_at`. 쓰기 주체가 CLI뿐이라 ADR-0037
   소유 경계 유지 — ADR-0038 개정으로 도입 가능.

## 6. 운용 관측

- zsh는 변수의 단어 분리를 하지 않아 옵션 묶음 변수(`$C`)가 한 토큰이 됨 —
  `${=C}` 필요. 도구 결함 아님(운용 메모).
- `--workspace`를 절대 경로로 주면 실행·검증이 전부 그 안에서만 일어남 —
  workspace 밖 부작용(0002 관측)은 이번 verify 명령들이 `/tmp` 고정 경로를
  쓰는 형태로 재현됨 (기존 등록 한계 그대로, 신규 아님).
