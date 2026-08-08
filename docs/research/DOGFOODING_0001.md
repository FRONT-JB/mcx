# Dogfooding 0001 — 실 AI 전체 파이프라인 첫 완주

- 일시: 2026-08-08
- Evidence level: **Verified by execution** (본 문서의 모든 관측은 실제 실행 출력이다)
- 구성: 위임 port 7종 + ExecutionRuntime 전부 실물 codex CLI 0.146.1 (기본 구성 모델),
  mechanical 검증은 `LocalMechanicalRunner`(AI 아님), 저장소는 파일 어댑터
- 미션: `dogfood-0001` — "텍스트 파일에서 가장 자주 나오는 단어 상위 N개를
  보여주는 명령줄 도구" (빈 workspace, Python 3 stdlib 전용)
- 결과: **Brief 질문 생성부터 Verify Gate `CLEAR`(MISSION COMPLETE)까지 전
  구간을 실제 AI로 완주.** 산출물 `wordfreq.py`·`test_wordfreq.py`는 수동
  spot check에서도 계약대로 동작했다.

## 1. 수치 요약

| 항목 | 값 |
|---|---|
| codex 호출 수 | **47** (질문 4, clarity 10, closure 감사 15, 생성 1, QA 5, 실행 6, semantic 6) |
| Brief | 질문 4 라운드 + 차단 질문 답변 7 라운드, revision 35에서 `CLEAR` |
| closure 감사 | 5순환 (HIGH 차단 4회 → 5회차 READY 수렴) |
| Blueprint | revision 3 승인 — QA 5회 소진 후 임계 미달 수락 (최고 0.79) |
| Execute | AC 6개 전부 1회 실행 성공, 침묵 timeout 없음 (44~104s/AC) |
| Verify | mechanical 6/6 통과 (직접 재실행), semantic 6/6 satisfied (score 0.98~1.0, uncertainty ≤0.02) |
| Recover | **미발동** — 실패 경로는 이번 도그푸딩에서 관측하지 못했다 |

사전 추정(15~25회)의 약 2배가 들었다. 초과분의 대부분은 closure 감사
5순환(15회)과 그에 따른 clarity 재평가(8회)이며, 그중 2순환은 아래 §3의
마찰(프로세스 결함)이 만든 낭비다.

## 2. 잘 동작한 것 (계약이 실물에서 검증됨)

- **질문 생성기**: 4개 질문 전부 단일 질문·실제 gap 겨냥·중복 없음. 한국어
  의도에 한국어로 응답했다.
- **clarity 채점자**: 같은 상태에 대한 반복 채점이 ±0.03 이내로 일관, 지적된
  잔여 공백(오류 문구 미정 등)이 전부 실제 공백이었다.
- **closure 감사**: HIGH 차단 4건 전부 material했다 — ① 아포스트로피 규칙의
  내부 모순(`[a-z0-9']+` vs "문장부호는 구분자"), ② 유니코드 소문자 변환 함정
  (`İ→i̇`, `str.lower()`의 실함정), ③ 폐기 규칙과 신규 규칙의 충돌 명시화,
  ④ 파일 크기/스트리밍 미확정. material 공간이 소진되자 5회차에 두 advisory
  lane 모두 MEDIUM으로 내려가 READY로 **수렴했다** — severity 보정이 동작한다.
  ②는 최종 구현의 `ASCII_LOWER_TABLE`로 이어졌다 (Brief 결정 → 코드 추적 실례).
- **Blueprint 생성기**: 제약 11개·Non-goal 2개를 **원문 그대로** 복사(결정적
  범위 검사 통과), AC 6개 전부에 한 줄 `verify_command` + 정확한 artifact
  경로 + literal `output_assertion`을 작성했다. AC의 기대 출력(토큰화·동률
  정렬 12항목)을 수동 검산한 결과 **정확했다**.
- **SUCCESS CONTRACT 프롬프트**: worker가 완료 전에 verify_command를 스스로
  실행하고 결과를 보고했다 (upstream 문구 채택의 의도된 효과).
- **semantic 평가자**: workspace 안에서 증거를 직접 재현·검사하고 6/6
  satisfied, uncertainty ≤0.02의 확신 있는 판정을 반환했다.
- **Gate 규율**: 실행 attempt의 성공 주장은 어느 경로로도 증거가 되지 않았고,
  mechanical 증거 없이 semantic이 기록되지 않았으며, `CLEAR`는 전부 저장된
  상태의 재계산에서 나왔다.

## 3. 마찰 관측 4건 — upstream 대조 전에는 고치지 않는다

각 항목은 [OPEN_QUESTIONS](./OPEN_QUESTIONS.md) §2·§3에 등록했다. 처분
(수정 ADR / divergence 등록 / 기각)은 pinned baseline 대조 후에 정한다.

> **처분 완료 (2026-08-08).** 사용자 요구(비용·속도 upstream 동등 이상)에
> 따라 같은 날 대조를 수행했다 — 대조표와 처분은
> [ADR-0035](../adr/0035-dogfooding-cost-parity-dispositions.md). §3.1·§3.2는
> 투영 수정(후보 전체 전달), §3.3은 QA 입력 정렬(threshold·궤적, ADR-0019 §3
> 개정) + 기각 채널 비발명, §3.4는 고정 필드 프롬프트 보상. 감사 lane은
> 병렬화되었다.

### 3.1 closure 감사 입력 투영이 확정 후보를 배제한다

감사 입력(`open_requirements`)은 **미확정 후보만** 담는다. 라운드 없이
확정된 후보(예: "스트리밍은 non-goal")는 감사자에게 보이지 않아, 이미 결정된
사안을 HIGH로 차단했다 (4순환째 — 낭비 1순환). 대화 라운드로 같은 결정을
다시 진술하자 통과했다. upstream 감사가 requirement 상태 전체를 보는지
대조가 필요하다.

### 3.2 폐기(superseded)된 후보가 open requirement로 영구 잔존한다

후보를 대체할 때 이전 후보를 `unknown`으로 내리면 promotion에서는 빠지지만
감사 입력에는 계속 나타난다. contrarian이 폐기된 `[a-z0-9']+` 규칙과 신규
규칙의 충돌을 HIGH로 차단했다 (3순환째 — 결정 자체는 유익했으나 후보 수명
관리 부재가 원인). 후보에는 폐기 상태가 없다. upstream의 요구사항 폐기
수명을 대조한다.

### 3.3 QA 루프에 기각 사유 채널이 없다

`previous_findings`는 전달되지만 **운용자가 기각한 지적과 그 사유**는 전달할
수 없다. 채점자는 기각된 지적을 "고쳐지지 않음"으로 읽고 재제기했고, 점수는
0.79 → 0.74 → 0.73으로 역행·정체해 통과선(0.90)에 도달할 수 없었다. 결국
상한 소진 + 임계 미달 수락(ADR-0019 §8)으로 출구했다. upstream은 지적이
architect에 자동 반영되는 구조라 "기각" 개념 자체가 없을 수 있다 — 사용자
채택 divergence(ADR-0019 §1)와의 상호작용을 대조한다. 부수 관측: 내용이
가장 좋은 revision 3의 점수가 최저였다 — 최선 시도 추적(ADR-0019 §5)이
내용 개선과 점수를 동일시할 수 없는 실례다.

### 3.4 QA가 verbatim 잠금 필드의 수정을 제안한다

채점자가 제약 중복 정리·이력 문장 제거를 반복 지적했지만, 제약·Non-goal은
handoff 원문 잠금(ADR-0018)이라 Blueprint 단계에서 실행 불가능한 제안이다.
채점 입력에 "이 필드는 고정"을 알리는지, upstream seed QA가 제약 필드를
어떻게 다루는지 대조한다. (중복의 근원은 Brief가 정제 없이 후보를 그대로
승격하는 우리 v1 구조다 — 같은 대조에서 함께 본다.)

## 4. 기타 관측

- **Recover 미발동**: 전 AC가 1회 실행으로 통과해 실패→교정→재검증 경로는
  실물 관측이 없다. 별도 도그푸딩(의도적 실패 미션)이 필요하다.
- **closure 감사에 반복 상한이 없다**: QA 루프(5회)와 달리 감사는 상한 없이
  반복된다. 이번에는 5순환에 수렴했지만, 수렴 보장은 없다 — upstream의
  interview 종료 루프에 상한이 있는지 대조한다.
- **한 AC 실행이 다른 AC의 계약을 미리 충족한다**: AC 단위 순차 실행에서
  1번 AC의 구현이 사실상 전체 도구를 완성했고, 이후 AC들은 재확인에
  가까웠다. 이 미션 크기에서는 자연스럽고, AC 분해 정책(ADR-0024)의
  문제로 보지 않는다.
- **감사 lane 지연이 가장 크다**: closer/contrarian/gap_hunter 각 40~90s,
  순차 실행으로 감사 1순환에 2~4분. 병렬화는 등록만 한다 (성능 최적화는
  현 단계 범위 밖).
