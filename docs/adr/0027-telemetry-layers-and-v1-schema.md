# ADR 0027 — Telemetry 세 층의 소유·시점과 report 층 v1 스키마

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 3 (Evidence over reasoning), [ADR-0023](./0023-execute-entry-and-provenance.md) §3, [ADR-0024](./0024-execute-v1-execution-model.md)
- Upstream evidence: [EVALUATE_UPSTREAM_FINDINGS.md](../research/EVALUATE_UPSTREAM_FINDINGS.md) §3~§7

## Context

[Open Questions §9](../research/OPEN_QUESTIONS.md)의 telemetry
event/report/bundle 스키마 결정. [progress
0003](../progress/0003_EXECUTE_VERTICAL_SLICE.md) 종료 검토가 시한을 "Phase 4
진입 전"으로 고정했고, 선행 조건이던 upstream 조사(evaluate의 소비 계약)가
완료되었다.

upstream의 세 층 실물([EVALUATE_UPSTREAM_FINDINGS](../research/EVALUATE_UPSTREAM_FINDINGS.md)):

| 층 | upstream 실물 | 생산 시점 |
|---|---|---|
| canonical event | `execution.session.*` 등을 실행 **중** event store에 append. payload에 identity·attempt·handle·tool_catalog. 컬럼: id/type/timestamp/aggregate/data/… | 스트리밍 실행 중 (§3) |
| report (mechanical 증거) | `VerificationRunArtifact`(명령·exit code·stdout/stderr 경로+발췌) + `VerificationArtifacts`(changed_files·manifest·runs) — 파일 트리 + manifest | 실행 직후, `ooo run`이 직접 (§4) |
| bundle (평가 입력) | `ArtifactBundle`(files + text_summary) — workspace 스캔 | 평가 직전 (§5) |

## Decision

각 층을 "소비자가 정의하고, 생산자가 생기는 Phase에서 구현"으로 배치한다.
스키마를 한꺼번에 확정하지 않는 이유는 발생 경로 없는 스키마가 검증 불가능한
장식이기 때문이다 (ADR-0024와 같은 논리). 단, 각 층의 **축과 시점**은 지금
고정하며, 아래 §1의 report 층은 필드까지 확정한다.

### 1. report 층 — Verify가 소비하는 실행 증거. v1 스키마를 지금 확정한다

Phase 4 mechanical verification이 생산·소비한다. upstream
`VerificationRunArtifact`와 정렬한 **명령 실행 기록**:

```text
VerificationRun
  check_kind          # 무엇을 검사했는가 (lint/build/test/verify_command 등)
  command             # 실행한 명령 (원문)
  exit_code
  passed
  timed_out
  stdout_ref, stderr_ref   # 보존된 원문 출력의 위치 (상태 문서 밖)
  stdout_excerpt, stderr_excerpt  # 판정용 발췌
```

그리고 **검증 묶음** — upstream `VerificationArtifacts` 대응:

```text
VerificationEvidence
  mission_id, blueprint_revision, ac_key   # lineage (ADR-0023 §3과 같은 축)
  execution_attempt_number                 # 어느 attempt를 검증했는가
  runs: VerificationRun 목록
  changed_files                            # 변경 artifact 목록
  manifest_ref                             # 보존 트리의 manifest 위치
```

원문 출력은 mission 상태 문서에 넣지 않는다 — 파일 artifact로 보존하고
상태에는 참조만 남긴다 (upstream의 파일 트리 + manifest 배치). 발췌 한도는
구현 시 upstream 상수(head 500 / tail 2,000자)와 대조해 정한다. 정확한 필드
이름과 보존 경로는 Phase 4 계약 고정(08_VERIFY 정비)에서 이 ADR을 인용해
확정한다.

이 스키마가 [Execute Guide](../07_EXECUTE.md) §9의 미답 질문 중 "어떤
파일/artifact", "어떤 명령과 exit code", "stdout/stderr 위치"에 답한다 —
답의 생산자가 Execute의 attempt 기록이 아니라 Verify의 독립 실행이라는 것이
upstream과 우리의 공통 배치다(agent 요약이 아니라 직접 실행한 증거).

### 2. attempt 시각 — Clock port와 함께 Phase 4에서 attempt 기록에 추가한다

§9의 "언제 시작하고 종료했는가"는 upstream에서 이벤트 `timestamp`가 답한다.
우리 v1에는 event 층이 없으므로 attempt 기록에 `dispatched_at`/`resolved_at`을
추가한다. 시각의 첫 소비자가 Verify report이므로 Phase 4에서 Clock port와
함께 도입한다 — Brief부터 미뤄 온 "시각을 다루지 않는다" 한계의 해소
지점이다.

### 3. canonical event 층 — 생산자(스트리밍 adapter)와 함께 Phase 5에서 확정한다

> **2026-08-10 종결 — [ADR-0049](./0049-runtime-progress-observation.md).**
> Phase 9 조사가 이 절의 전제를 갈랐다: 여기서 한 이름으로 부른 것이 upstream
> 에서는 **성격이 다른 두 층**이었고(정규화 vs 저장), *"실행 중 관찰"* 을 실제로
> 제공하는 것은 **정규화 쪽**이다 — upstream의 진행 표시는 event store를 읽지
> 않는다. 정규화 층은 도입했고 **event store는 도입하지 않았다**(소비자 부재,
> 등록된 divergence). 아래 본문의 *"upstream lifecycle payload와 대조해 확정"*
> 은 event store를 전제로 한 지시였으므로 그 범위에서 무효다.

> **2026-08-09 — 이 시한은 무처분 도과했다.** Phase 5는 2026-08-08에 종료됐고
> 스트리밍 adapter는 만들어지지 않았다. Codex adapter는 JSONL을 읽지만 **event를
> 생산하지 않는다**(`src/`에 event 타입이 없다). Phase 5 종료 검토는 질문 7을
> 수행하지 않았고, 2026-08-09 소급 처분이 다룬 7건에도 이 항목은 **없었다**.
> Phase 7 종료 검토도 *"시한 미배치"* 라고만 적고 재지정하지 않았다
> ([progress 0007](../progress/0007_MCP_CONTROL_SURFACE.md) §1.7).
>
> 검토 셋을 통과한 도과이며, 발견 경로는 외부 지적의 검증이었다.
>
> **새 시한 Phase 9 (제안).** 근거는 수요가 그때 생긴다는 것이다 — 실사용에서야
> 긴 실행의 진행 표시가 실수요가 되고, 같은 Phase의 `changed_files`
> ([ADR-0029](./0029-verify-deliberate-divergences.md) 보류)가 같은 생산자를
> 요구한다. 아래 Cost의 *"event 층이 Phase 5까지 비므로 실행 중 관찰은
> 불가능"* 은 **부분적으로 해소됐다**: Phase 6의 명령 원장이 "어느 명령이
> 도는가"를 덮는다. 덮지 못한 것은 **한 번의 긴 실행 안에서 무슨 일이
> 일어나는가**이며, 그것이 이 층에 남은 몫이다.

event의 존재 이유는 실행 **중** 관찰(진행 표시, stall 탐지, resume)이고, 그
생산자는 스트리밍 concrete adapter다. 동기 fake에는 발생 경로가 없다. Phase
5에서 upstream lifecycle payload(EVALUATE_UPSTREAM_FINDINGS §3에 기록)와
대조해 확정하되, [ADR-0023](./0023-execute-entry-and-provenance.md) §3의
제약(생성 경로·실행 주체·lineage·시도는 payload 관례가 아니라 선언 필드)을
그대로 받는다.

### 4. bundle 층 — Verify semantic 단계 입력. Phase 4 semantic 설계에서 확정한다

upstream `ArtifactBundle`(agent 요약 대신 실제 파일)과 같은 축. mechanical
(§1)이 먼저이므로 Phase 4 안에서도 semantic 설계 시점에 다룬다.

### 5. retention·redaction — 값이 등장하는 지점에서 결정한다

출력 크기·발췌 한도는 §1 구현 시 upstream 상수와 대조. secret redaction은
provider transport secret이 실제로 등장하는 Phase 5(concrete adapter)에서
Runtime 문서·Security ADR로 정한다 ([Execute Guide](../07_EXECUTE.md) §9의
세 층 redaction 서술이 그 자리다). replay/resume 보장 수준은 resume 계약과
함께 Phase 5다 (ADR-0025 기존 보류와 같은 시점).

## Consequences

### Positive

- §9의 다섯 항목 전부에 소유자와 시점이 생겼다 — "미정"이 아니라 "어느
  Phase의 어느 소비자가 확정하는가"로 바뀌었다.
- report 층이 upstream과 같은 배치(독립 실행 증거, 파일 보존 + 참조)라서
  Phase 4 구현을 upstream `verification_artifacts.py`와 직접 대조할 수 있다.
- Execute Guide §9의 미답 질문들이 각각 답의 생산자를 갖는다.

### Cost

- Phase 4 전까지 attempt 기록에는 여전히 시각이 없다.
- event 층이 Phase 5까지 비므로, 그때까지 실행 중 관찰(진행 표시)은 불가능
  하다 — 동기 실행이라 관찰할 "중"이 없다는 사실과 일치한다.

## Rejected alternatives

- **세 층 전체 스키마를 지금 확정**: event 층은 생산자가 없어 검증 불가능한
  장식이 된다. bundle은 semantic 설계(소비자) 없이 필드를 정할 근거가 없다.
- **attempt 기록에 명령·출력을 직접 축적**: 상태 문서가 출력 크기에 오염되고,
  upstream이 파일 트리 + manifest로 분리한 이유(§4)와 어긋난다.
- **Execute가 report 층을 생산**: v1 Execute는 명령을 실행하지 않는다(동기
  fake). 독립 실행 증거의 생산자는 Verify다 — agent 요약을 증거로 승격하지
  않는다는 upstream 배치와도 일치한다.

## Verification

- Phase 4 계약 고정이 이 ADR을 인용해 §1의 최종 필드 이름을 확정한다.
- mechanical verification 구현이 명령 원문·exit code·출력 보존 위치를 기록에
  남기고, 그것 없이 Verify Gate가 `CLEAR`되지 않는다.
- attempt 기록에 시각이 추가될 때 기존 저장 파일이 깨지지 않는다 (선택
  필드로 도입).
- Phase 5 event 스키마 설계가 EVALUATE_UPSTREAM_FINDINGS §3과 ADR-0023 §3을
  함께 인용한다.
