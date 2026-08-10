# DOGFOODING 0007 — parallel Execute + Coordinator + independent Verify

- 일시: 2026-08-10
- 대상: Phase 11 `execute stage --max-workers 3`
- 형태: 기존 Python retry utility를 가진 작은 brownfield git 저장소
- Runtime: dependency/semantic text는 Codex, worker·Coordinator는 Codex CLI
- 결과: **MISSION COMPLETE**

## 1. 관측 목표와 과제

관측 대상은 논리적으로 독립인 세 AC를 같은 dependency stage에서 실제 병렬
실행하고, 두 AC가 같은 파일을 고쳤을 때 Coordinator와 settled revalidation이
그 결과를 안전하게 닫는지였다. 인코딩·복잡한 CLI parsing 같은 무관한 경계 축은
제외했다.

초기 저장소에는 다음 실패가 있었다.

1. `is_retryable(429)`가 거짓이다.
2. `is_retryable(503)`가 거짓이다.
3. `format_attempt(2, 3)`이 `attempt 2/3`이 아닌 문자열을 돌려준다.

앞의 두 AC는 논리적 선후 관계가 없지만 둘 다 `retry_policy.py`를 수정하고,
세 번째 AC는 `metrics.py`만 수정한다. 초기 `python3 -m unittest -q`는 정확히
3건 실패했다.

## 2. 비용 예상과 실측

사전 예상은 `dependency 1 + worker 3 + Coordinator 1 + semantic 3 = 8회`였다.
mechanical Verify와 Gate는 AI를 호출하지 않는다.

실측은 성공 호출 8회에 실패 호출 1회가 더해진 **총 9회**였다.

| lane | 호출 | 결과 |
|---|---:|---|
| Claude text | 1 | 주간 한도, exit 1. `HOLD`로 종료 |
| Codex text | 4 | dependency 1 + semantic 3 |
| Codex CLI execution | 4 | worker 3 + Coordinator 1 |

차이 1회의 원인은 기본 Claude 경로의 주간 quota였다. CLI가 표시한 reset은
**2026-08-13 12:00 Asia/Seoul**이다. 임시 state의 지원되는 routing surface에서
Execute·Verify text lane만 Codex로 바꿔 같은 미션을 재개했다. 총 경과는
3분 18초였다.

## 3. 실제 병렬 Execute

dependency plan은 세 AC를 stage 0 하나에 배치했다. 저장된 `StageRun`은 다음을
보였다.

- `requested_workers=3`, `effective_workers=3`
- grouped attempt 3개가 Runtime effect 전에 저장됨
- 세 Codex worker의 command/file-change event가 서로 겹쳐 관측됨
- exact conflict: `retry_policy.py`
- command event 때문에 세 worker 모두 write attribution `INCOMPLETE`
- Coordinator execution id: `coord-stage-dogfood-0007-0001`

두 retry worker가 각자 같은 set literal을 고쳤고 metrics worker는 별도 파일을
고쳤다. Coordinator는 settled workspace에서 세 결과가 이미 공존함을 확인해 추가
변경 없이 성공했다. 이어 Execute-owned settled revalidation 세 명령이 모두 exit
0이었고 stage는 `EXECUTED_UNVERIFIED`, Execute Gate는 `CLEAR`가 됐다.

## 4. 독립 Verify와 checkpoint

`verify mechanical`은 세 AC 모두 통과하고 실제 변경 파일을
`metrics.py`, `retry_policy.py`로 표시했다. Codex text semantic evaluator 세
판정도 모두 `satisfied=true`, score 1.0이었다. Verify Gate는 `CLEAR`, checkpoint는
`6065f76`, 최종 상태는 **MISSION COMPLETE**였다.

Coordinator 뒤 재검증은 Execute 안전 검사일 뿐 Verify evidence로 재사용되지
않았다. mechanical·semantic evidence와 checkpoint가 별도로 생겨 lineage 경계도
유지됐다.

## 5. Phase 11 강제 fixture

### 5.1 dirty rollback 표시

checkpoint가 있는 실제 git fixture에 tracked 수정 `proven.py`, untracked
`failed_attempt.py`, `nested/trace.txt`, ignored `ignored.cache`를 만들었다. 기존
rollback은 앞의 세 경로를 지우고 ignored 파일을 남겼지만 결과에는 commit만 있어
삭제 목록을 표시하지 못했다.

`Rollback.removed_files`와 수집 실패 구분을 추가한 뒤 같은 fixture는 다음을
실제로 출력했다.

```text
rollback: b866732로 되돌림
  제거 3건: proven.py, failed_attempt.py, nested/trace.txt
```

### 5.2 actual Brief candidate trace

실제 `mcx brief start`→`brief answer`→`brief candidate` CLI trace에서 429·503·표시
형식·외부 의존성 금지를 한 답변에 넣었다. 자동 파생 후보는 의도대로 원문 전체를
한 후보로 보존했다. 이 굵기는 pinned upstream과 같고, 쪼개려면 새 LLM 판단이
필요하므로 유지했다.

반면 같은 section·같은 원문을 수동으로 다시 넣자 후보가 2개로 중복됐다. exact
중복 거부를 추가한 뒤 재실행은 exit 1과 기존 candidate number 2를 표시했고,
저장된 candidate 수와 revision은 늘지 않았다.

## 6. 결론

ADR-0053의 plan, grouped durability, bounded real fan-out, write Telemetry,
Coordinator, settled revalidation, independent Verify가 대표 brownfield 경로에서
한 번에 성립했다. Phase 11 introduction Gate의 마지막 실경로 조건은 `CLEAR`다.

이 실측은 기본 Claude quota가 풀렸다는 증거는 아니다. 기본 조립으로 같은 text
lane을 다시 시험할 수 있는 가장 이른 시각은 CLI가 보고한 2026-08-13 12:00
Asia/Seoul이다.
