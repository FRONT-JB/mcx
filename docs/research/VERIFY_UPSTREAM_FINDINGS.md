# Verify Upstream Findings — mechanical 검증의 실행 주체와 안전 모델

> Checked: 2026-08-08. Baseline: `Q00/ouroboros@9486c78` (v0.50.8), 로컬 clone
> (`~/.claude/plugins/marketplaces/ouroboros`).<br>
> Scope: [Open Questions §5](./OPEN_QUESTIONS.md)의 mechanical 항목(명령 발견
> 방식, allowlist 정책)과 Phase 4 첫 slice 계약의 재료 —
> [EVALUATE_UPSTREAM_FINDINGS §8](./EVALUATE_UPSTREAM_FINDINGS.md)이 미조사로
> 남긴 부분.<br>
> Evidence level: 별도 표기 없으면 **Verified** (소스 확인).

## 1. 기계 검증은 두 층이다

- **(a) AC 수용 gate** — orchestrator가 **실행 직후** AC의 성공 계약
  (verify_command / expected_artifacts / output_assertion)을 직접 검사한다.
  `run_verify_commands` 기본 True (`orchestrator/parallel_executor.py:2852-2857`).
  "The orchestrator — **not the worker** — checks the contract so a failing
  check cannot be self-reported away" (`:9636-9637`).
- **(b) evaluation Stage 1** — repo 수준 명령(lint/build/test)을
  `.ouroboros/mechanical.toml`에서 읽어 실행한다. "Stage 1 trusts the toml
  and nothing else" (`evaluation/languages.py:1-14`). post-run 증거 묶음은
  [EVALUATE_UPSTREAM_FINDINGS §4](./EVALUATE_UPSTREAM_FINDINGS.md).

## 2. AC 수용 gate의 계약 (`parallel_executor.py:9631-9768`)

검사 순서와 실행 방식:

1. `output_assertion`은 `verify_command` 없이 성립 불가 (구조 검사가 먼저).
2. `expected_artifacts` 전부 존재 — 싸므로 명령보다 먼저, 누락 전부를 한 번에
   보고 (`:9659-9667`).
3. `verify_command` 실행: **`create_subprocess_shell`** (shell 허용 —
   mechanical.toml 층과 다르다), `cwd`=run 워크스페이스, stderr는 stdout에
   합류, `start_new_session` + timeout 시 process group `SIGKILL`
   (`:9698-9729`). timeout 기본 **600초** (`:2815`).
4. exit code 0 요구, `output_assertion`은 합류 출력에 substring으로 존재해야
   함. 출력은 tail만 보존 (`_VERIFY_OUTPUT_TAIL_CHARS`, `:9741-9762`).
5. **workspace mutation guard**: 실행 전후 content digest를 대조해
   `verify_command`가 작업물을 바꿨으면(또는 digest 재검증 불가면) FAIL —
   "verify_command mutated the workspace" (`:9679-9696`). 검증이 작업을
   고치는 것을 막는다.

재시도: `ac_retry_attempts` — 실패한 AC가 FAILED로 확정되기 전까지
재dispatch되는 횟수. 실제 run 경로 기본 **2** (`:2858-2863`) →
[ADR-0025](../adr/0025-execute-deliberate-divergences.md) 미확인 행("재시도
상한") 부분 해소. 실패 증거의 전달 방식(bounce/repair)은 여전히 미조사.

## 3. mechanical.toml — 스키마와 발견 방식

- 키: `lint` / `build` / `test` / `static` / `coverage` (명령 문자열),
  `timeout` (기본 300초), `coverage_threshold` (기본 0.7)
  (`languages.py:245-282`).
- 우선순위: MCP caller override > toml > 전부 `None` → Stage 1은 검사를
  건너뛴다 — "skips gracefully rather than running the wrong tool"
  (`:13-14`). "검사할 명령이 없음"과 "모든 검사 통과"가 구분된다.
- 발견: 파일이 없으면 **AI detector가 repo를 조사해 한 번 작성**한다 —
  silent best-effort, 실패하면 Stage 1이 빈 채로 다음 단계로 넘어간다
  (하드코딩 preset으로 "phantom-fail"하지 않기 위해,
  `evaluation_handlers.py:710-717`). 언어별 하드코딩 preset은 의도적으로
  제거됐다 (`languages.py:3-7`).

## 4. repo 수준 명령의 안전 모델 (`languages.py`, `detector.py:496-531`)

mechanical.toml의 명령은 실행 전에 네 겹을 통과한다.

1. **실행 파일 allowlist** — 큐레이션된 ~90개(빌드 러너·패키지 매니저·린터·
   테스트 러너). `rm`/`curl`/`bash`류 배제 — "could turn a Stage 1 run into
   remote code execution in CI" (`:32-37`).
2. **shell 연산자 차단** — `&& || | ; > < ` $(` 가 문자열에 있으면 거부,
   통과분은 `shlex` → argv 튜플 → **`create_subprocess_exec`** (shell 없음)
   (`:165-196`, `mechanical.py:93-131`).
3. **경로 제한** — 절대경로·`~`·`..` 거부. `./mvnw`류 프로젝트 wrapper는
   basename allowlist로 허용 (`:198-213`).
4. **entry-point 검증** — `npm run X`/`make target`은 프로젝트 manifest에
   선언된 target만, bare tool도 repo가 선언한 것만. host PATH는 의도적으로
   참조하지 않는다 (`detector.py:496-531`).

위반은 예외가 아니라 **경고 로그 + 해당 검사 drop**이다 — repo가 작성한
toml이 Stage 1을 크래시시키지 못한다.

## 5. 두 층의 안전 비대칭

AC `verify_command`에는 allowlist가 없고 shell이 허용된다. repo 수준 명령에는
네 겹의 안전장치가 있다. 관측되는 구분: verify_command는 **승인 경로를 거친
계약 내용**(seed 생성 시 one-line·heredoc 금지 구조 검증 —
`agents/seed-architect.md` §3, `core/seed.py`)이고, mechanical.toml은 AI/repo가
작성하는 **설정 파일**이다. 대신 verify_command에는 실행 시점 방어(mutation
guard, process group kill, timeout)가 있다. 비대칭의 의도 서술은 allowlist
주석(CI RCE 우려)까지가 소스 근거다.

## 6. 조사하지 않은 것

- semantic(Stage 2) 프롬프트 계약과 consensus(Stage 3) reviewer 독립성 규칙 —
  semantic slice 설계 시 조사한다.
- coverage 판정의 상세 (`coverage_threshold` 적용 지점).
- bounce/repair의 실패 증거 전달 방식 (ADR-0025 미확인 유지).

## Mission Control 함의

결정은 [ADR-0028](../adr/0028-verify-v1-mechanical-contract.md)(v1 mechanical
검증 계약)과 [ADR-0029](../adr/0029-verify-deliberate-divergences.md)(Verify
divergence 등록부)에 있다.
