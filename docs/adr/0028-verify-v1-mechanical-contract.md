# ADR 0028 — Verify v1 mechanical 검증 계약

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: Principle 3 (Evidence over reasoning), [ADR-0026](./0026-verify-entry-requires-lineage.md), [ADR-0027](./0027-telemetry-layers-and-v1-schema.md) §1
- Upstream evidence: [VERIFY_UPSTREAM_FINDINGS.md](../research/VERIFY_UPSTREAM_FINDINGS.md)

## Context

Phase 4 첫 slice는 Verify의 mechanical 검증 — 승인된 AC의 성공 계약을 실제로
실행해 증거를 남기는 부분이다. 실행 주체·대상 명령·실행 방식·증거 필드는
도메인 개념의 축이므로 구현 전에 고정한다.

upstream 사실 ([VERIFY_UPSTREAM_FINDINGS](../research/VERIFY_UPSTREAM_FINDINGS.md)):

- AC 성공 계약은 **orchestrator가 직접** 검사한다 — worker의 자기 보고로
  대체될 수 없다 (§1). 검사는 artifacts 존재 → 명령 exit 0 → 출력 assertion
  순서이고, shell로 실행하며, timeout 기본 600초, 실행 전후 workspace digest로
  mutation을 거부한다 (§2).
- repo 수준 명령(mechanical.toml)은 별도 층이며 4겹 안전 모델(allowlist·shell
  연산자 차단·argv 실행·entry-point 검증)을 거친다 (§3~§4).
- 두 층의 안전 기준이 다른 이유는 명령의 출처다 — 승인 경로를 거친 계약 vs
  AI/repo가 작성한 설정 (§5).

## Decision

### 1. 검증 명령의 실행 주체는 Verify use case다

Flight Controller(worker)의 "테스트 통과했습니다" 보고를 증거로 승격하지
않는다. Verify가 명령을 직접 실행하고 그 결과만이 mechanical 증거다 —
upstream의 "not the worker, so a failing check cannot be self-reported away"와
같은 배치다.

upstream은 이 검사를 실행 수용 시점(orchestrator gate)과 평가 시점(Stage 1)
두 번 수행하지만, 우리 v1 Execute는 명령을 실행하지 않으므로(ADR-0024, 동기
fake) 이 검사는 **Verify Stage 한 곳**에 온다. 검증 시점의 통합은
[ADR-0029](./0029-verify-deliberate-divergences.md)에 등록된 divergence다.

### 2. v1이 실행하는 명령은 승인된 Blueprint의 `verify_command`뿐이다

명령의 정당성 경계는 allowlist가 아니라 **승인 경로**다 — verify_command는
Blueprint QA와 사용자 승인을 거친 계약 내용이며, 이는 upstream이
verify_command에 allowlist를 두지 않은 비대칭(§5)과 같은 축이다. repo 수준
명령(mechanical.toml 대응)은 v1에 도입하지 않는다 — 도입할 때 upstream의
4겹 안전 모델(allowlist·shell 연산자 차단·argv 실행·entry-point 검증)과
대조해 별도 ADR로 정한다 (ADR-0029 보류 등록).

승인 경로 밖에서 명령이 들어오는 문을 만들지 않는다 — Verify use case의
입력은 mission id이고, 명령은 항상 저장된 승인 Blueprint에서 읽는다.

### 3. 실행 계약은 upstream AC 수용 gate와 정렬한다

한 AC의 검증 절차 (upstream §2와 같은 순서):

1. `expected_artifacts` 전부가 검증 워크스페이스 아래 존재 — 명령보다 먼저
   검사하고, 누락 전부를 한 번에 보고한다.
2. `verify_command`가 있으면 shell로 실행한다 — 승인된 한 줄 명령이며
   (Blueprint 구조 검증이 전제), `cwd`는 검증 워크스페이스, stderr는 stdout에
   합류한다.
3. timeout은 upstream 기본값 600초를 채택한다. 초과 시 process group을
   종료하고 `timed_out`으로 기록한다.
4. exit code 0이 통과다. `output_assertion`이 있으면 합류 출력에 substring
   으로 존재해야 한다.
5. 성공 계약이 하나도 없는 AC(`verify_command`·`expected_artifacts`·
   `output_assertion` 전부 없음)는 mechanical 층에서 **판정 불가**로
   기록한다 — 통과도 실패도 아니며, 그 사실이 Gate 판정에 드러난다.

### 4. 증거 레코드 — ADR-0027 §1의 최종 필드

[ADR-0027](./0027-telemetry-layers-and-v1-schema.md) §1이 예고한 필드명을
확정한다. AC 검증의 출력은 upstream gate와 같이 합류(combined)이므로
stdout/stderr 분리 참조 대신 합류 출력 하나를 보존한다.

```text
VerificationRun            # AC 하나의 mechanical 검증 한 번
  ac_key                   # 무엇의 계약인가 (lineage)
  command                  # 실행한 명령 원문 (없으면 None — artifacts만 검사)
  exit_code                # timed_out이면 None
  passed
  timed_out
  missing_artifacts        # 누락된 expected_artifacts (전부)
  output_ref               # 보존된 합류 출력의 위치 (상태 문서 밖)
  output_tail              # 판정용 발췌

VerificationEvidence       # mission 하나의 검증 묶음
  mission_id
  blueprint_revision       # 어느 revision의 계약을 검증했는가
  execution_attempt_numbers  # 어느 실행 위에서 검증했는가 (ADR-0026 lineage)
  runs                     # VerificationRun 목록
```

원문 출력은 파일로 보존하고 상태에는 참조만 남긴다 (ADR-0027 §1). 발췌
한도는 구현 시 upstream 상수(tail 보존, head 500/tail 2,000)와 대조해 정한다.
`changed_files`(git 기반)는 실제 파일 변경이 생기는 concrete adapter와 함께
도입한다 (ADR-0029 보류).

### 5. v1에 도입하지 않는 것 (ADR-0029 등록)

- **workspace mutation guard** — 검증 명령이 작업물을 바꾸는 것의 거부.
  upstream 계약은 기록했고(§2), 도입 시 digest 범위를 함께 정한다.
- **repo 수준 명령과 mechanical.toml 대응물** (§2에서 결정).
- **coverage 판정** — coverage_threshold 축 자체를 v1에 두지 않는다.
- **재시도** — 검증 실패는 결과이지 재시도 대상이 아니다. 실패 후 경로는
  Recover Stage의 결정이다.

## Consequences

### Positive

- "에이전트의 완료 주장은 완료가 아니다"가 처음으로 실행 증거를 갖는다 —
  Verify가 직접 돌린 명령의 exit code만이 mechanical 통과다.
- 실행되는 명령의 출처가 승인된 Blueprint 하나로 고정되어, 검증 경로가
  임의 명령 실행 통로가 되지 않는다.
- 증거 레코드가 upstream 실물과 필드 수준에서 대조 가능하다.

### Cost

- 성공 계약 없는 AC는 mechanical 층이 아무것도 말해주지 못한다 — semantic
  층(후속 slice)까지 Gate가 완결되지 않는다.
- mutation guard 보류 동안, 작업물을 바꾸는 verify_command를 탐지하지 못한다.
- shell 실행을 허용하므로 명령의 안전성이 전적으로 승인 품질에 달린다 —
  Blueprint QA가 명령을 심사하는 유일한 지점이라는 사실이 QA 품질 기준의
  무게를 키운다.

## Rejected alternatives

- **worker 보고를 mechanical 증거로 수용**: upstream이 명시적으로 거부한
  배치("self-reported away")이고, ADR-0005의 부정이다.
- **verify_command에 allowlist 적용**: upstream 비대칭과 어긋나고, 승인
  경로가 이미 그 역할이다. allowlist는 승인 없이 들어오는 명령(repo 설정)의
  방어이며 그 층은 v1에 없다.
- **argv 실행 강제 (shell 금지)**: upstream 예시 계약(`... && echo OK`)이
  shell 합성을 포함한다. 한 줄 shell이 계약 형식이므로 실행기가 그것을
  받아야 한다.
- **timeout을 우리가 새로 정함**: 근거 없는 수치 발명이다. upstream 기본값
  채택이 대조 가능성을 유지한다.

## Verification

- Verify가 실행한 명령의 exit code·출력이 레코드로 남고, worker 보고 문자열이
  증거 경로에 등장하지 않는다.
- 승인된 Blueprint 밖의 명령이 실행되는 경로가 없다 (use case 입력에 명령
  없음).
- expected_artifacts 누락이 명령 실행 없이 전부 보고된다.
- timeout 시 timed_out 레코드가 남고 프로세스가 정리된다.
- 성공 계약 없는 AC가 "판정 불가"로 구분되어 통과로 집계되지 않는다.
