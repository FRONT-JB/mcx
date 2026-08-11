# DOGFOODING 0008 — Codex-only lifecycle (IN PROGRESS)

- 시작: 2026-08-11
- 대상: text lane과 execution lane을 모두 Codex로 고정한 실사용 경로
- Runtime: `default.text="codex"`, `default.execution="codex_cli"`,
  `gpt-5.6-sol` / `xhigh`
- 형태: 기존 Python retry utility와 실패 unittest가 있는 작은 brownfield git 저장소
- 현재 결과: **첫 mission `MISSION COMPLETE` — Recover를 관측할 두 번째 mission
  준비 중**

## 1. 관측 범위

Codex 하나로 Brief → Blueprint → Execute → Verify → Recover가 이어지는지
실제로 확인하는 것이 목표다. 첫 mission은 순차 lifecycle을, 두 번째 mission은
제어된 실행 후 drift로 Verify HOLD→Recover를, 후속 mission은 generation 후속
경로와 병렬 Coordinator를 관찰하도록 나눴다.
임시 workspace·state·routing config는 모두 `/tmp/mcx-codex-only.i5eTeb` 아래에
두었고 사용자 plugin/MCP 설정은 바꾸지 않았다.

첫 fixture의 baseline은 `retry_delay(status_code, retry_after, default)`가 429에서
항상 default를 돌려주는 구현이다. 초기 unittest 4개 중 numeric·ASCII whitespace
2개가 실패하고, invalid/missing fallback과 비-429 2개는 통과했다.

## 2. 현재까지의 실제 흐름

Codex 질문 3회가 ASCII whitespace, 정확한 429 비교, ASCII 숫자 문법을
구체화했다. clarity는 연속 두 번 기준을 넘었고 closure 3-lane은 다음 숨은
경계를 실제로 찾았다.

1. Python 3.11+의 기본 정수 문자열 변환 한도 4,300자
2. 현재 interpreter의 변환 한도가 더 낮을 때 `int()`가 내는 `ValueError`
3. 기존 테스트 4개만으로 새 파싱·길이 계약을 입증할 수 없다는 검증 공백

합성 과제의 결정은 1~4,300자만 형식상 허용하고, 현재 interpreter에서 `int()`가
실패하면 default로 닫으며 전역 한도나 수동 임의정밀도 변환을 건드리지 않는
것이다. 각 경계를 새 unittest로 고정해야 한다는 closure 지적도 채택했다.

다만 답변의 자연어가 required candidate로 자동 파생되지 않았고, 수동으로 넣은
기존 테스트 criterion은 `repo_evidence` authority라 성공 조건을 만들 권한이
없다. 현재 Gate는 closure blocker 2개, user approval 부재, authority 부족,
승격된 성공 조건 부재를 정확히 표시한다. 이를 agent가 `authority=user`로
꾸미지 않고 실제 사용자 확인에서 멈춘 상태다.

## 3. 도그푸딩이 발견한 결함 1 — 긴 Codex JSONL event

첫 closure audit에서 Codex 0.147.0의 단일 JSONL event가 Python asyncio
`StreamReader` 기본 64 KiB를 넘었다. text adapter가
`ValueError: Separator is found, but chunk is longer than limit`로 중단됐고,
같은 `readline()`을 쓰던 execution adapter도 잠재적으로 동일했다.

pinned Ouroboros의 `providers/codex_cli_stream.py`와
`orchestrator/codex_cli_runtime.py`를 재대조해 16 KiB bounded chunk reader와
50 MiB line 상한을 복원했다. 회귀 테스트는 70 KiB event에서 두 adapter가
수정 전 모두 실패하고 수정 후 통과함을 고정한다. newline 없는 출력은 작은
상한을 주입한 단위 테스트에서 fail closed 한다.

## 4. 도그푸딩이 발견한 결함 2 — workspace 없는 text lane의 cwd 누출

세 번째 closure audit는 mission fixture 대신 부모 프로세스의 mcx 저장소를
읽고 `retry_policy.py`가 없다고 차단했다. Brief lane 계약은 저장소 조사 금지인데,
Codex adapter가 workspace 미지정 시 `-C`를 생략해 cwd를 상속한 것이 원인이었다.

workspace 없음의 의미를 “부모 cwd”가 아니라 “작업물 관찰 권한 없음”으로 복구해,
호출마다 빈 임시 cwd를 `-C`로 준다. 명시 workspace가 있는 semantic evaluator는
기존대로 실제 작업물을 읽기 전용으로 본다. 회귀 테스트는 neutral cwd가 비어
있고 호출 후 제거되는 것까지 확인한다. pinned upstream은 미지정 cwd를
`os.getcwd()`로 채택하므로 이 차이는 Brief divergence register에 기록했다.

## 5. 비용과 현재 evidence

사전 정량 호출 추정을 기록하지 않고 실행을 시작했다. 이는 ADR-0035 비용 규칙을
지키지 못한 절차 결함이며 사후 숫자를 “예상”으로 소급하지 않는다.

Brief revision 8 시점 command journal은 Codex text **30회**, 29 commands,
누적 command wall time **552.952초**를 기록했다. 이 중 6회는 긴-line 수정 전
실패한 closure audit 두 번이며, 나머지 증가는 closure가 찾은 경계를 세 차례
보정하고 재감사한 비용이다. 당시 코드 변경 후 전체 자동 테스트는
**1065 passed**였다.

사용자 확인 뒤 첫 mission을 재개하기 전에 남은 호출을 별도로 추정하고, 완료 시
실측과 비교한다. 아직 Blueprint·Execute·Verify·Recover를 지나지 않았으므로
이 기록은 `MISSION COMPLETE`나 Codex-only 전체 lifecycle 성공을 주장하지 않는다.

## 6. 다음 Gate

아래 한 문장을 required acceptance criterion으로 사용자 권위로 확정하고, 그
내용이 반영된 정확한 Brief revision을 사용자가 승인해야 한다. 그 뒤 동일
revision의 clarity·closure를 다시 통과시켜 Blueprint로 간다.

> 429일 때 ASCII whitespace를 제거한 값이 ASCII `[0-9]+`이고 길이 1~4,300자이며
> 현재 interpreter의 `int()` 변환이 성공하면 그 정수를 반환한다. 그 밖에는
> default, 비-429는 None이다. 기존 4개 unittest를 유지하고 ASCII whitespace,
> 비ASCII 숫자 거부, 1/4,300/4,301자, `int()` ValueError, 비-429 경계를 추가
> unittest로 검증하며 전체 discover 명령이 exit 0이어야 한다.

위 항목은 사용자가 확정했고, 기존 공개 타입 `str | None`을 repository evidence
기반 existing constraint로 추가한 revision 11이 closure `ready`를 받았다.
사용자의 “계속진행해”를 exact revision 11 승인 statement로 기록한 뒤 Brief Gate는
`CLEAR`였다.

## 7. Blueprint 진입과 결함 3 — `(none)`이 실제 Non-goal이 됐다

첫 `blueprint generate`는 실패했다. handoff의 Non-goals가 비어 있었고 prompt는
이를 `(none)`으로 표시했는데, 실제 Codex가 `non_goals: ["(none)"]`로 반환했다.
결정적 scope 검사는 `non_goal_not_in_handoff`로 정확히 거부해 revision을 저장하지
않았다.

pinned `agents/seed-architect.md`는 collection을 single-line JSON array로
주고받는다. 생성기 입력의 다섯 목록을 같은 방식으로 바꾸고 empty를 `[]`로
고정했다. `(none)`을 출력에서 사후 삭제하지 않아, 모델이 정말 항목을 발명하면
scope 검사가 계속 막는다. 수정 전 실패와 수정 후 JSON-array 렌더링을 회귀
테스트로 고정했다.

같은 Brief에서 재시도한 generation은 Blueprint revision 1을 정상 생성했다.
Codex QA는 0.62로 `continue`를 반환하며 빈 ontology, 테스트 artifact 누락,
중복 검증 명령, 측정 불가능한 범위 AC를 지적했다. 같은 초안을 재채점하지 않고,
AC를 한 결과 계약으로 합치고 `retry_policy.py`·`test_retry_policy.py`를 artifact로
명시하며 ontology 6 fields를 채운 revision 2 제안을
`/tmp/mcx-codex-only.i5eTeb/a-blueprint-revision-2-proposal.json`에 만들었다.
`blueprint revise`는 사용자 채택을 뜻하므로 아직 호출하지 않았다.

현재 journal은 Codex text **43회**, 44 commands, 누적 command wall time
**811.711초**다. Brief revision 8 뒤 남은 첫 mission을 9~13회로 예상했으나
타입 계약 재감사와 Blueprint placeholder 실패로 이미 상한 13회를 사용했고
Execute 전이다. 완료 시 이 초과를 최종 대조한다.

사용자가 revision 2 수정안을 채택해 `blueprint revise`로 revision 2를 저장했다.
두 번째 QA는 0.79로 올랐지만 아래 네 모순을 남겼다.

1. `retry_after` ontology가 `string`인데 계약은 `str | None`이다.
2. `delay_result`가 `number`인데 비-429 반환은 `None`이다.
3. 공개 함수 `retry_delay`와 정확한 시그니처가 ontology에 없다.
4. “표준 라이브러리만” 제약을 unittest가 검증하지 않는다.

이를 반영한 revision 3 제안은 nullable 타입을 `str | None`·`int | None`로
명시하고, `retry_delay` callable과 `stdlib-only` dependency policy를 ontology에
추가했다. 수용 기준은 `test_retry_policy.py`가 `retry_policy.py`의 import AST를
검사해 모든 import root가 `sys.stdlib_module_names`에 속하는지 검증하도록 한다.
제안 파일은
`/tmp/mcx-codex-only.i5eTeb/a-blueprint-revision-3-proposal.json`이며 schema load를
통과했지만, 사용자 채택 전이라 mission state에는 적용하지 않았다.

현재 journal은 Codex text **44회**, 46 commands, 누적 command wall time
**890.890초**다. revision 3 재QA부터는 기존 9~13회 추정의 초과 구간이다.

사용자의 “진행해줘”를 revision 3 수정안 채택으로 기록해 revision 3을 저장했다.
세 번째 QA는 **0.98**, 전 dimension 0.97 이상, findings 0건, action `done`으로
통과했다. Blueprint Gate를 실제 호출한 결과 유일한 blocker는
`approval_missing`이며, verifiable criterion은 1/1이다. 수정안 채택은 exact
Blueprint 승인이 아니므로 `blueprint approve`는 아직 호출하지 않았다.

현재 journal은 Codex text **45회**, 49 commands, 누적 command wall time
**953.298초**다. 다음 단계는 사용자가 Blueprint revision 3의 정확한 내용을
승인한 뒤 Gate `CLEAR`를 확인하는 것이다. 승인 전에는 Execute하지 않는다.

## 8. 첫 mission 완료와 비용 대조

사용자의 “진행해줘”를 exact Blueprint revision 3 승인 statement로 기록했고
Blueprint Gate는 `CLEAR`였다. 첫 Execute 진입은 fixture가 만든 `__pycache__/`
때문에 workspace cleanliness에서 호출 전 차단됐다. 두 `.pyc`만 확인해 제거한 뒤
같은 명령을 재실행했다. 이는 committed baseline 외 파일을 거부하는 의도된
worktree 방어이며 제품 결함으로 분류하지 않는다.

Codex worker 1회는 승인 AC 범위의 `retry_policy.py`·`test_retry_policy.py`만
바꾸고 자체 unittest 9건을 통과했다. Execute Gate는 `CLEAR`, 독립 mechanical은
1/1(exit 0, missing artifact 0), Codex semantic은 1/1(score 1.0, uncertainty 0.01,
reward-hacking risk 0.01)이었다. Verify Gate가 `CLEAR`를 선언해 첫 mission은
**`MISSION COMPLETE`**다. checkpoint는 `aa9461c`다.

최종 journal은 **57 commands**, command wall time **1,146.136초**, Codex text
**46회** + Codex execution **1회**다. Brief revision 8 뒤 남은 구간은 9~13회로
예상했지만 실제는 text 16회 + worker 1회 = **17회**, 상한보다 4회 많았다. 초과
원인은 closure의 타입 계약 재감사, Blueprint empty placeholder 실패 재생성,
nullable/callable/dependency ontology를 닫기 위한 QA revision 2회다.

이 성공 경로는 Recover를 호출하지 않았다. 따라서 이 시점에도 “Codex-only로 모든
Phase를 검증했다”고 주장하지 않는다.

## 9. 두 번째 mission — 병렬 Coordinator + 제어된 Verify HOLD→Recover 계획

도그푸딩 시작 때 이미 만든 committed `b-workspace` fixture를 그대로 사용한다.
서로 독립인 `metrics.py`와 `retry_policy.py`에 실패 unittest 3건이 있다.

1. `is_retryable`은 429·503만 true여야 한다.
2. `retry_delay`는 429 numeric header를 정수로, invalid는 default로, 그 밖의
   status는 None으로 처리해야 한다.
3. `format_attempt(2, 3)`은 `"attempt 2/3"`이어야 한다.

첫 두 계약은 같은 `retry_policy.py`, 세 번째는 `metrics.py`를 수정한다. 이를 AC
3개와 dependency stage로 고정해 `execute stage --max-workers 3`의 shared-worktree
fan-out과 exact overlap→Coordinator를 관찰한다. unrelated boundary는 단순 정수·
문자열에 한정한다.

settled Execute 뒤 Verify 전에 fixture에 **제어된 외부 drift** 한 줄을 주입해
한 승인 계약을 깨뜨린다. mechanical Verify가 실제 실패를 기록하면 그 evidence로
Recover plan→Codex dispatch→Verify 재실행을 관찰한다. drift는 임시 fixture에만
적용하며 mcx 저장소나 사용자 환경은 바꾸지 않는다.

사전 비용 추정: Brief 질문·closure 10~14 text calls + Blueprint 2~4 + semantic
Verify 2 + Recover text/worker 1~2로 **Codex text 13~20회 × 1회 순환**, 병렬 worker
3회 + Coordinator 1회 + Recover worker 1회로 **Codex execution 4~5회**를 예상한다.
실제 호출 수와 차이는 완료 뒤 대조한다.

기존 fixture의 `__pycache__` 4개를 확인·제거해 committed baseline을 복구한 뒤
mission `dogfood-codex-b`를 시작했다. 첫 Brief 질문은 `retry_after`의 whitespace,
부호, 선행 0, 계약 밖 runtime type 경계를 묻는다. 이 중 공개 타입은 repository
observation으로 답할 수 있지만 문자열 문법은 사용자 결정이다. 사용자는 권장안을
채택해 앞뒤 ASCII whitespace 6종 제거, 나머지 ASCII `[0-9]+`, 선행 0 허용,
`str | None` 밖 runtime type은 범위 밖으로 확정했다. 두 번째 질문은
`format_attempt`가 0·음수·`current > total`을 검증할지 물었고, 사용자는 검증 없이
그대로 포맷하는 권장안을 확정했다. 세 번째 질문은 첫 mission에서 승인한 계약을
재사용해 ASCII 숫자열 1~4,300자와 현재 interpreter `int()` ValueError→default로
기록했다. clarity는 goal 1.00, constraint 0.98, success criteria 0.86이며 stability
1이다. 현재 질문은 `default`의 0·음수 허용 여부이고, 현재 실측은 Codex text
5회다.
