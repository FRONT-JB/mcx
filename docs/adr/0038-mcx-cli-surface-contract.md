# ADR 0038 — `mcx` CLI 표면 계약: 비대화형 단발 명령, exit code, mission record 기록

- Status: Accepted
- Date: 2026-08-09
- 근거 조사: [CLI_UPSTREAM_FINDINGS](../research/CLI_UPSTREAM_FINDINGS.md)
  (§2 표면 파리티 원칙, §5 표면 전례), 도그푸딩 드라이버 2회 실증
  ([DOGFOODING_0001](../research/DOGFOODING_0001.md)·
  [DOGFOODING_0002](../research/DOGFOODING_0002.md))
- 함께 구현: [ADR-0037](./0037-mission-record-and-canonical-stage.md)
  (mission record 형태 확정의 구현 절)

## Context

Phase 6은 다섯 Stage를 동일 application boundary로 조작하는 `mcx` CLI다.
CLI의 대화형 지점은 upstream skill 계층이 대화 안에 있어 대조 불가능한 신규
영역으로 등록되어 있었고 (OPEN_QUESTIONS §8), 선행 조사가 부분 전례를
확보했다: upstream CLI는 판정 FAIL을 exit code 2로 오류(1)와 구분하고, 표면
파리티를 테스트가 아니라 **구현 공유**로 얻으며, 출력 계약을 스냅샷
테스트로 고정한다.

사실상의 원형이 이미 있다: 도그푸딩 드라이버(레포 밖, 339줄)가 22개 단발
명령으로 다섯 Stage 전체를 두 번 완주했다 (Recover 경로 포함). 이 표면은
발명이 아니라 실증된 형태다.

## Decision

### 1. 명령 표면 — application service 메서드와 1:1, CLI에 workflow 로직 없음

`mcx <stage> <verb> [프롬프트]` 형태. 각 명령은 application service
메서드 하나를 호출하고 결과를 렌더한다. CLI는 Gate·retry·Recover를
결정하지 않는다 (upstream 정렬: 표면은 공유 핸들러 위임 — findings §2.
Phase 7 MCP도 같은 service를 공유해 표면 파리티를 구현 공유로 얻는다).

> **개정 1 (2026-08-09, 사용자 결정 — `mcx {동작} {옵션?} {프롬프트}`
> 형식).** 프롬프트 인자(intent·answer·statement)는 플래그가 아니라
> **positional**이고, `mcx brief "<intent>"`는 `brief start`의 단축이다
> (upstream 정렬: `ooo init "Build an API"` 단축 — `cli/main.py:7-9`의
> default-subcommand fallback. 프롬프트가 verb와 같은 단어면 verb로
> 해석되는 모호성도 upstream과 동일). `--mission`은 선택이 된다 —
> `brief start`에서 생략하면 id를 자동 생성하고(upstream `auto_<hex>`
> session id 정렬), 그 외 명령에서 생략하면 **마지막으로 시작한 mission**
> (state의 `current_mission` 포인터)을 쓴다. 최근 mission 기본값은
> upstream CLI에 대응물이 없다(스킬 계층의 "recent session" 추론에만
> 대응) — 등록된 divergence이며, 병행 mission에서는 `--mission` 명시가
> 안전 경계다.

| 명령 | service 호출 |
|---|---|
| `mcx brief "<intent>"` (= `brief start`, +`--workspace`) | `BriefService.start` + mission record 생성 |
| `mcx brief ask` | `ask_next_question` |
| `mcx brief answer "<답변>"` (+`--authority --question`) | `record_answer` |
| `mcx brief candidate --section --text` (+옵션) | `record_candidate` |
| `mcx brief resolve --number --resolution` (+`--authority`) | `resolve_candidate` |
| `mcx brief assess` | `assess_clarity` |
| `mcx brief audit` | `audit_closure` |
| `mcx brief approve "<statement>"` | `approve` |
| `mcx brief gate` | `decide_gate` |
| `mcx brief handoff` | `build_handoff` (관찰용) |
| `mcx blueprint generate` | `BlueprintService.generate` |
| `mcx blueprint qa` | `assess_qa` |
| `mcx blueprint revise --draft-file` | `revise` |
| `mcx blueprint approve "<statement>"` (+`--accept-below-threshold`) | `approve` |
| `mcx blueprint gate` | `decide_gate` |
| `mcx execute next` | `ExecuteService.dispatch_next` |
| `mcx execute gate` | `decide_gate` |
| `mcx verify mechanical` | `VerifyService.run_mechanical` |
| `mcx verify semantic` | `assess_semantics` |
| `mcx verify gate` | `decide_gate` (CLEAR 시 MISSION COMPLETE 기록 — §5) |
| `mcx recover plan` | `RecoverService.plan` |
| `mcx recover dispatch` | `dispatch_correction` |
| `mcx recover gate` | `decide_gate` |
| `mcx status` | mission record + 각 Stage 저장 상태 요약 (읽기 전용) |

`--mission`은 전역 옵션이다. ~~필수이며 "최근 mission" 추론은 없다~~ —
개정 1로 대체: 생략 시 `brief start`는 자동 생성, 그 외는 마지막 시작
mission. 원문이 근거로 든 upstream `ooo seed`의 명시 요구는 사실이며, 그
차이가 개정 1의 등록된 divergence다.

### 2. 대화형 지점 — v1은 전부 비대화형 단발이다

명령 안에서 프롬프트를 띄우지 않는다. 사용자 결정(답변, 후보 확정, 승인,
수정 채택)은 **인자와 별도 명령**으로만 표현된다.

- 근거: 도그푸딩 2회가 이 형태로 완주했다. Lifecycle §10.2가 요구하는
  "`HOLD`를 기록한 순간과 corrective route를 commit한 순간의 구분"이 명령
  경계와 정확히 일치하고, §10.4(사용자 소유 결정을 자동 route하지 않는다)와
  User Adoption Gate(기본 채택 없음)가 구조적으로 강제된다.
- upstream의 대화형 프롬프트(ambiguity 1/2/3, 단계 전환 Confirm — findings
  §5)는 **합성 흐름**(`ooo init`)의 것이다. 우리 v1 범위는 per-stage
  primitive이므로 대화형 지점 자체가 생기지 않는다. 합성 대화형 흐름은
  보류로 등록한다 (§7).
- **QA EXHAUSTED**: `mcx blueprint qa`가 EXHAUSTED에 도달하면 exit 2와 함께
  Lifecycle §10.1 형식의 설명(무엇이 부족한가, 누가 결정해야 하는가,
  선택지: `blueprint revise` / Brief 재개)을 출력하고 멈춘다. 자동 route는
  없다.
- upstream의 ambiguity 미달 강제 생성("Generate Seed anyway (force)")의
  대응물은 도입하지 않는다 — ADR-0009의 네 조건 계약이 이미 사용자 승인을
  1급 조건으로 갖고 있고, ADR-0019 §1이 표면별 우회 비대칭을 금지한다.
  등록된 divergence (upstream `init.py:572-580`).

### 3. exit code — upstream 정렬

| code | 의미 |
|---|---|
| 0 | 명령 성공. 판정 명령이면 긍정 판정 (`CLEAR`, QA PASS) |
| 1 | 오류 — 예외, 계약 위반, 진입 차단(HandoffNotClearedError 등) 포함 (upstream `seed.py:91` 정렬 — 미완료 interview는 exit 1) |
| 2 | 명령은 정상 수행되었고 **판정이 부정** — gate `HOLD`, `blueprint qa`의 PASS 아닌 action (upstream `qa.py:108-109` 정렬 — FAIL은 exit 2) |

### 4. 출력 계약

- stdout: 구조화 JSON (pydantic `model_dump_json` / dataclass `asdict`) —
  도그푸딩 렌더 형태를 승계한다. 사람용 진행 메모(소요 시간 등)는 stderr.
- 출력 형태는 테스트로 고정한다 (upstream 정렬: status 출력은 스냅샷
  테스트로 고정 — findings §5).
- rich·typer는 도입하지 않는다 — argparse + stdlib (ADR-0012 Divergence 2
  연장: 22개 명령 도그푸딩에 argparse로 충분했다. 도입은 실수요 시 재평가).

### 5. mission record — ADR-0037의 구현 형태

- `domain/mission.py`: `MissionRecord` — `mission_id`, `workspace`,
  `current_stage`(기존 `domain/stage.py` Stage enum), `status`
  (`active`/`complete`), `sequence`, `transitions`(source, destination,
  at, reason). frozen pydantic, 기존 상태 모델과 동일 패턴.
- 합법 전이 그래프는 [Lifecycle §9](../02_MISSION_LIFECYCLE.md) 표에서
  도출한다: 전진 BRIEF→BLUEPRINT→EXECUTE→VERIFY, 교정
  EXECUTE↔RECOVER·VERIFY→RECOVER·RECOVER→VERIFY, backward
  {EXECUTE,VERIFY,RECOVER}→{BRIEF,BLUEPRINT}. §9.1 금지 전이는 예외로
  거부된다. `MISSION COMPLETE`는 Stage 전이가 아니라 status 전이이며
  **`mcx verify gate`가 `CLEAR`를 반환할 때만** 기록된다 (Constitution:
  Verify Gate만 선언).
- 시각(`at`)은 호출자(CLI 합성)가 주입한다 — 도메인은 결정적으로 유지된다
  (upstream도 호출부에서 `utc_now_iso()` 스탬프).
- 저장: `adapters/persistence/file_mission_repository.py`,
  `mission_<id>.json` — 기존 파일 저장소와 동일한 원자적 교체·stale 쓰기
  거부·안전 id 검사.
- **쓰는 주체는 CLI 명령 핸들러뿐이다.** Stage 진입 명령(`blueprint
  generate`, `execute next`, `verify mechanical|semantic`, `recover
  dispatch`)이 성공하면 합성이 전이를 기록한다. 같은 Stage 재진입은 전이가
  아니다. 기록된 Stage와 다른 불법 전이가 되는 경우 **명령을 실패시키지
  않고** stderr 경고 + 기록 생략한다 — Gate가 이긴다 (ADR-0037 §2).
  `mcx status`가 어긋남을 표시한다.
- **backward route(spec correction)는 v1에 전이 트리거가 없다** — Brief·
  Blueprint 수정 명령은 mission record 전이를 기록하지 않는다. 그 결과
  Execute 이후의 spec 교정은 record와 실제 작업 위치의 어긋남으로 status에
  나타난다. 명시적 route 명령은 합성 흐름(§7)과 함께 재평가한다.
- Lifecycle §3.1의 나머지 항목(active input revisions, attempt lineage,
  GateDecision·Telemetry reference)은 mission record에 **복제하지 않는다** —
  각 Stage 저장소가 소유하고 `mcx status`가 조합해 표시한다. Mission
  aggregate = mission record + Stage 저장소들이며, record는 그중 합성이
  소유한 조각이다.
- `workspace`는 mission record 필드다 — `mcx brief start --workspace`(기본
  cwd)로 저장하고 Execute envelope·Verify 실행 디렉토리로 소비한다.
  upstream은 이를 Seed가 나른다 (`run.py`의
  `resolve_seed_project_path`) — 우리는 Blueprint 스키마가 방향
  필드만으로 확정되어 있어 (ADR-0017) 배치가 다르다. 등록된 divergence.

### 6. composition root와 상태 루트

- `src/mission_control/cli/` = repo의 첫 composition root. 기본 조립은
  사용자 확정 구조 그대로: 텍스트 lane `ClaudeCompletion`, 실행
  `CodexExecutionRuntime` (ADR-0036). vendor 선택 플래그·설정 파일은
  도입하지 않는다 — 대체 조립(codex 텍스트 등)은 composition 함수 인자
  수준으로만 존재하고, 표면 노출은 실수요 시 재평가 (§7).
- 상태 루트는 `--state-dir`(기본 `~/.mcx`) — upstream `--state-dir` +
  `~/.ouroboros/data` 정렬. 내부 배치는 `<state-dir>/state/*.json`(Stage·
  mission 문서), `<state-dir>/outputs/`(Verify 산출물)이다.
- entry point: `[project.scripts] mcx = "mission_control.cli.main:run"`
  (ADR-0012 Divergence 2가 예약한 자리).

### 7. 보류 (도입 시 upstream 대조 기준과 함께)

- **합성 대화형 흐름** (brief→blueprint→execute를 한 명령으로) — upstream
  대응물 `ooo init`/`ooo auto` (findings §3). 대화형 프롬프트·Confirm
  전환은 그 흐름과 함께 온다.
- **vendor 선택 표면** (플래그/설정 파일) — upstream 대응물
  `--llm-backend`·`runtime_profile.stages` (findings §11).
- **approve actor 식별자** — v1 승인 주체는 명령을 실행한 로컬 사용자이고
  evidence는 `--statement`다 (upstream도 CLI에 user identity 없음). MCP
  (Phase 7)에서 host가 대리 승인하는 경로가 생길 때 재평가
  (OPEN_QUESTIONS §3 잔여).
- **status 스냅샷의 사람용 렌더** — v1은 구조화 JSON. 사람용 포맷은 실수요
  시 upstream `_format_auto_status`(한 줄 한 사실) 대조.
  → **실수요 도래 (2026-08-09, 사용자 제안)**: status 박스가 이 항목이다.
  명령 단위 journal + 구간표 렌더로 개정 예정 (Open Questions §8).

## Cost

- 비대화형 단발은 명령 수가 많다 — 완주에 수십 회 호출 (도그푸딩 0002:
  48콜). 합성 흐름 도입 전까지는 조작 부담이 사용자에게 있다.
- exit code 2의 "판정 부정" 범위가 gate 명령과 qa 명령에 걸친다 — 새 판정
  명령이 생길 때마다 이 분류를 명시해야 한다.
- mission record와 Gate 재계산의 이중 진실은 ADR-0037 Cost에 등록된 그대로
  이며, 어긋남 표시가 완화책이다.

## Rejected alternatives

- **명령 안 대화형 프롬프트** (upstream `init.py` 방식) — 합성 흐름의
  것이다. primitive에 넣으면 스크립트 실행이 멈추고, 사용자 결정이
  provenance 없이 tty 입력으로 들어온다 (ADR-0011 위반).
- **`--force`류 gate 우회 플래그** — ADR-0019 §1이 죽인 표면 간 비대칭의
  재생산. upstream의 force도 플래그가 아니라 대화형 명시 선택이었다.
- **typer/rich 도입** — 22개 명령 도그푸딩에 argparse로 충분했다. 의존성은
  실수요에 (ADR-0012).
- **mission record를 Stage service가 갱신** — ADR-0037 기각 사유와 동일
  (소유 분산, upstream은 합성만 소유).

## Verification

- exit code: gate CLEAR→0, HOLD→2, qa PASS→0/비PASS→2, 진입 차단·예외→1.
- 명령→use case 매핑: 각 명령이 지정된 service 메서드를 호출한다 (fake
  조립으로 고정).
- mission record: `brief start`가 생성, Stage 진입 명령 성공 시 전이 기록,
  불법 전이는 경고+생략이고 명령은 성공, `verify gate` CLEAR만 status를
  complete로 바꾼다.
- import 방향: Stage service·domain(mission 제외)이 `domain/mission.py`와
  CLI 패키지에 의존하지 않는다 (ADR-0037 Verification).
- 조립 기본값: 텍스트 lane Claude + 실행 Codex.
