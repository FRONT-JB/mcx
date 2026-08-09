# Dogfooding 0004 — Brief 단계에서 중단. 결함 1건과 구조적 divergence 확인

- 일시: 2026-08-10 (01:13~02:10 KST)
- Evidence level: **Verified by execution** (사용자 승인 하에 실제 AI 실행)
- Mission: `m-40457a` — `extstat`: 디렉터리를 재귀 순회해 확장자별 파일 개수를
  세고 개수 내림차순으로 출력하는 파이썬 CLI (표준 라이브러리만)
- 구성: `uv run mcx` (0003이 설치 표면을 이미 검증했다), 텍스트·판정 claude
  2.1.226, workspace는 새 git 저장소
- 목표: **Phase 9가 만든 층**(worktree 격리·checkpoint·rollback·진행 표시)의
  실물 검증
- 결과: **Brief 단계에서 중단.** 목표 층에 도달하지 못했다.

## 0. 실측 — 추정 대비

| 축 | 추정 | 실측 | 비고 |
|---|---|---|---|
| claude 콜 | 25~42 | **69** | Brief만으로 초과. Blueprint 이후는 미도달 |
| 명령 수 | — | **105** | |
| 명령 누적 시간 | — | **30분** | 사이의 판단 시간 제외 |

원장(ADR-0038 §6.1)에서 집계한 것이며, **원장이 자기 몫을 했다** — 실측을
따로 계측할 필요가 없었다.

| 명령 | 횟수 | 누적 |
|---|---:|---:|
| `brief audit` | 15 | **24분 (80%)** |
| `brief assess` | 17 | 4.4분 |
| `brief ask` | 4 | 0.7분 |
| `blueprint generate` | 4 | 0.7분 (전부 실패) |

`audit`이 시간의 80%, 콜의 65%다.

## 1. 과제 선정 오류 — 먼저 적는다

0003이 *"파서류 과제는 경계 사례 축으로 스펙이 자라며 감사 라운드가 그에
비례한다"* 를 기록했다. **그것을 알고도 인코딩·파일명 축 과제를 골랐다.**
15라운드 비수렴은 도구의 결함이 아니라 그 선택의 결과다.

감사 질문은 전부 실질이었다 — 관측자의 **답변 간 모순**(비UTF-8은 흘린다 vs
`isprintable()`이면 폐기 — surrogate는 printable이 아니다)도 감사가 잡았다.

구조적 관측 하나는 남는다: `answer → revision+1 → 감사 stale → 감사 → 새 질문`
순환이라, 답할수록 새 축이 열리는 과제에서는 수렴 지점이 스스로 오지 않는다.

## 2. 결함 — Brief Gate가 빈 handoff에 `CLEAR`를 준다

`blueprint generate`가 `BlueprintScopeError: no_acceptance_criteria`로 죽었다.
재현 2/2. 파고든 결과 **원인이 Blueprint가 아니었다**:

```
handoff.goals 0 · constraints 0 · non_goals 0 · success_criteria 0
clarity 0.96 · closure ready · 승인 있음  →  CLEAR
```

clarity는 **대화를 채점하지 칸을 보지 않는다.** 그래서 칸이 비어도 0.96이다.

### 2.1 기본 경로의 결과가 빈 handoff였다

```
brief candidate --resolution confirmed  →  authority=none  →  승격 안 됨
후보 기본값 required=False              →  BLOCK이 아니라 조용한 OMIT
```

승격하려면 `brief resolve --authority user`를 따로 쳐야 한다. Gate의 유일한
요구사항 검사(`UNPROMOTABLE_REQUIREMENT`)는 **기본 경로에서 발동할 수 없다** —
막을 것이 `BLOCK`뿐인데 기본값이 `OMIT`을 만든다.

### 2.2 증상이 층을 잘못 가리켰다

Brief가 비었는데 표면은 *"Blueprint 초안이 승인된 범위를 벗어난다"* 였다.
원인 층에서 보고되지 않으면 관측자가 두 층을 헤맨다.

## 3. upstream 대조 — 이 상태는 upstream에서 만들어지지 않는다

| | 후보를 누가 만드는가 | 전사를 생성기에 넘기는가 |
|---|---|---|
| upstream | **파생** `build_requirement_distillation` | **넘긴다** `_format_interview_transcript` |
| mcx | **수동** `mcx brief candidate` | **끊는다** (ADR-0016·0018) |

각각 단독으로는 무해하다. 칸이 비면 전사가 받쳐주고, 전사를 끊으면 칸이
채워져 있다 — upstream은 둘 중 하나가 언제나 성립한다. **우리는 둘 다 끊었고,
그 교집합에서 생성기가 받은 것은 의도 82자뿐이었다.**

### 3.1 승격 0건 미검사 자체는 upstream 파리티다

`authoring_handlers.py:1472-1481`은 `promotion.blockers`만 본다. `required:
bool = False` 기본값(`requirement_candidate.py:125`)도, 권한 부족 시 조용한
`OMIT`도 자간까지 같다. **upstream은 그 검사가 필요 없을 뿐이다.**

### 3.2 파생만 이식해서는 풀리지 않는다 (실측)

upstream `_EXPLICIT_REQUIREMENT_RE`(한국어·일본어 어휘가 원본에 있다)를 이
도그푸딩의 실제 답변 21건에 그대로 걸었다:

```
매칭 1 / 미매칭 20
```

upstream의 파생은 스스로 *"conservative"* 라고 밝히며 요구사항임을 **스스로
선언하는** 답변만 줍는다. 나머지는 evidence로만 남고 전사가 실어 나른다. 즉
**upstream의 보수적 파생은 전사가 함께 갈 때만 성립하는 설계다.**

우리 답변은 특정 축에 대한 결정을 서술형으로 쓴 것이라 그 어휘를 거의 쓰지
않는다.

## 4. 처분 — [ADR-0050](../adr/0050-requirement-candidate-provenance.md)

사용자 지시: *"upstream과 유사하면서 가장 안전한 방법"*.

1. **upstream 파생 이식** — 초기 의도 → GOAL 후보(빠뜨릴 명령이 사라진다),
   답변은 upstream 정규식 매칭 시에만. 정규식은 자간 그대로.
2. **수동 경로 유지** — §3.2의 1/21이 근거. 등록된 divergence.
3. **Gate가 승격된 성공 조건을 요구** — Guide §13.1이 이미 요구하던 것이며
   구현이 계약보다 얇았다. constraints·non_goals까지 막지는 않는다.

952 tests (+16).

## 5. 정정 — 자유 텍스트 `-` 문제는 "조용한 실패"가 아니었다

`mcx brief answer "-h/--help는 …"` 이 argparse에 먹혀 라운드가 유실됐다.
이것을 처음 *"조용히 실패했다"* 로 적었으나 **사실이 아니다** — usage가 stderr에
나오고 exit 2로 끝난다. 관측자가 `tail -3`으로 가린 것이다.

남는 간극은 우회 방법(`--`를 마지막에 둔다)이 help에서 보이지 않는 것뿐이며,
help 문구로 처리했다. 파싱은 고치지 않는다 — 전처리를 넣으면 옵션 목록을 두 벌
들고 있어야 하고, 어긋나는 순간 **지금 없는 조용한 실패**가 생긴다.

## 6. 도달하지 못한 것

Phase 9의 네 층(worktree 격리·checkpoint 커밋·rollback·진행 표시)은 **실물
검증이 여전히 0회다.** Execute에 도달하지 못했다.

다음 도그푸딩은 **경계 사례 축이 얕은 과제**로 잡는다 — 목표가 파이프라인
완주가 아니라 그 네 층이므로, Brief를 빨리 통과하는 것이 설계 조건이다.
