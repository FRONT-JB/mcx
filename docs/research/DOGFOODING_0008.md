# DOGFOODING 0008 — Codex-only lifecycle (IN PROGRESS)

- 시작: 2026-08-11
- 대상: text lane과 execution lane을 모두 Codex로 고정한 실사용 경로
- Runtime: `default.text="codex"`, `default.execution="codex_cli"`,
  `gpt-5.6-sol` / `xhigh`
- 형태: 기존 Python retry utility와 실패 unittest가 있는 작은 brownfield git 저장소
- 현재 결과: **Brief revision 8 `HOLD` — required 후보 확정과 exact user
  approval 대기**

## 1. 관측 범위

Codex 하나로 Brief → Blueprint → Execute → Verify → Recover가 이어지는지
실제로 확인하는 것이 목표다. 첫 mission은 순차 lifecycle과 실패 복구를,
후속 mission은 generation 후속 경로와 병렬 Coordinator를 관찰하도록 나눴다.
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

현재 command journal은 Codex text **30회**, 29 commands, 누적 command wall
time **552.952초**를 기록한다. 이 중 6회는 긴-line 수정 전 실패한 closure audit
두 번이며, 나머지 증가는 closure가 찾은 경계를 세 차례 보정하고 재감사한 비용이다.
코드 변경 후 전체 자동 테스트는 **1065 passed**다.

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
