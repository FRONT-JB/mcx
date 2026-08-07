# Persistence Upstream Findings — 저장 계층 조사

> Baseline: `Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943` (v0.50.8)<br>
> Checked: 2026-08-07 (local clone, 해당 commit checkout)<br>
> Scope: [Open Questions §9](./OPEN_QUESTIONS.md#9-persistence-and-telemetry-decisions)<br>
> Evidence level: 별도 표기 없으면 **Verified**

Mission Control은 Phase 1에서 파일 기반 상태로 시작하지만
([ADR-0013](../adr/0013-brief-durable-state-baseline.md)), upstream의 저장 계층은
Execute·Verify·Recover와 MCP를 다룰 때 다시 마주치는 주제다. 이 문서는 그때
참조할 관찰을 미리 보존한다.

---

## 1. 저장소가 하나가 아니다

upstream은 세 종류의 저장을 **서로 다른 매체**에 나눠 둔다. “ouroboros DB”는 그중
둘을 담는 SQLite 파일이다.

| 저장 대상 | 매체 | 위치 |
|---|---|---|
| Interview 상태 | JSON 파일 | `~/.ouroboros/data/interview_<id>.json` |
| 실행 이벤트, 세션 guard, 계보 claim | SQLite | `~/.ouroboros/ouroboros.db` (설정으로 변경 가능) |
| Brownfield 저장소 등록부 | SQLite | 같은 DB의 `brownfield_repos` 테이블 |
| Workflow checkpoint | JSON 파일 + file lock | 별도 checkpoint 경로 |

즉 **인터뷰는 DB를 쓰지 않는다.** Mission Control이 Phase 1에서 파일로 시작하는
선택은 upstream의 대응 지점과 일치한다.

## 2. Event store — append-only 이벤트 테이블

`persistence/schema.py`의 `events` 테이블이 중심이다.

| 컬럼 | 용도 |
|---|---|
| `id` | UUID |
| `aggregate_type` / `aggregate_id` | replay 대상 식별 |
| `event_type` | `dot.notation.past_tense` (예: `execution.ac.completed`) |
| `payload` | JSON |
| `timestamp` | UTC |
| `consensus_id` | 다중 모델 합의 이벤트 연결용 (nullable) |

인덱스는 aggregate 조회와 시간순 replay를 위해 6개가 걸려 있다.

`EventStore`(3,102줄)의 API 성격:

- `append`, `append_batch`, `append_with_rowid`
- `replay(aggregate_type, aggregate_id)`, `get_events_after(...)`
- **조건부 append**: `append_session_start_if_absent`,
  `append_session_terminal_if_active`, `append_session_pause_if_active`
- `supports_cross_process_workers` — 여러 프로세스가 같은 DB를 공유하는지 판정
- 전 메서드가 `async`이며 SQLAlchemy async engine + aiosqlite를 사용한다

### 2.1 Guard 테이블 — append-only의 한계를 보완

이벤트 스트림은 append-only이지만, 그것만으로는 “두 writer가 동시에 같은 세션을
종료 처리”하는 상황을 막지 못한다. upstream은 별도 테이블로 compare-and-set
guard를 둔다.

| 테이블 | 보호 대상 |
|---|---|
| `session_terminal_guards` | 세션 종료 전이의 단일 claim |
| `session_start_guards` | 세션 시작의 중복 방지 |
| `ac_acceptance_guards` | AC 수용 결과의 중복 확정 방지 |
| `lineage_advancement_claims` / `_waiters` | 세대 진행 claim과 대기열 |

**설계 관찰**: append-only 이벤트 스트림은 “무엇이 일어났는가”를 기록하지만,
“이 전이를 누가 선점했는가”는 별도의 원자적 상태가 필요하다. Mission Control이
Gate decision을 이벤트로만 표현하려 할 때 같은 문제를 만난다.

## 3. Checkpoint — 이벤트와 다른 목적

`persistence/checkpoint.py`(661줄)는 이벤트 스트림과 별개로 **작업 재개용
스냅샷**을 저장한다.

- JSON 파일 + file lock, 무결성 검증(hash)
- 롤백을 최대 3단계까지 지원
- `PeriodicCheckpointer`가 백그라운드 태스크로 주기적 저장

이벤트가 “사실의 누적”이라면 checkpoint는 “지금 상태의 사본”이다. 둘은 대체
관계가 아니라 보완 관계로 쓰인다.

## 4. Unit of Work — phase 경계에서 원자적 커밋

`persistence/uow.py`는 한 phase 동안 이벤트를 모아 두었다가 경계에서 이벤트와
checkpoint를 **함께** 커밋한다. 이벤트만 저장되고 checkpoint가 누락되는(또는 그
반대) 부분 실패를 막는 장치다.

`heartbeat.is_holder_alive`를 참조하는 것으로 보아 lock holder 생존 확인과
연동된다.

## 5. Brownfield registry — 사용자가 본 “레포 등록”

`ooo setup list`가 보여주는 등록부의 실체는 `brownfield_repos` 테이블이다.

| 컬럼 | 내용 |
|---|---|
| `path` | 절대 경로 (primary key) |
| `name` | 디렉터리명에서 유도한 이름 |
| `desc` | README/CLAUDE.md에서 LLM이 요약한 한 줄 설명 |
| `is_default` | PM interview의 기본 brownfield context 여부 |
| `registered_at` | 등록 시각 |

등록 절차(`bigbang/brownfield.py`의 `scan_and_register`):

1. scan root에서 git repo/worktree를 depth-bounded로 탐색
2. README/CLAUDE.md를 파싱해 저렴한 모델로 한 줄 설명 생성
3. DB에 CRUD

**목적**: 인터뷰가 “이 프로젝트는 무엇인가”를 매번 사용자에게 묻지 않도록 사전
수집한 맥락을 제공하는 것. Mission Control의 Fact Resolver와 목적이 겹치지만
방식이 다르다 — upstream은 **사전 등록·스캔**, Mission Control은 **필요 시
조회**를 계획한다
([ADR-0011](../adr/0011-brief-deliberate-divergences.md) §6).

## 6. Migration — 최소한의 SQL 러너

`persistence/migrations/`는 알파벳 순으로 SQL 스크립트를 적용하고 `_migrations`
테이블에 적용 이력을 기록한다. 스크립트는 `001_initial.sql`,
`002_brownfield.sql` 둘뿐이다. Alembic 같은 도구를 쓰지 않는다.

**관찰**: event sourcing을 채택했음에도 마이그레이션 도구는 의도적으로 가볍다.

## 7. Project Map — 읽기 전용 projection

`project_map.py`는 이벤트를 재생해 프로젝트 단위 뷰를 만든다. 모듈 docstring이
“EventStore remains authoritative”, “no append or execution-control surface”를
명시한다. 파생 뷰가 권위를 갖지 않는다는 원칙이 코드 주석 수준으로 강제되어
있다.

---

## 8. Mission Control에 주는 시사점

> Decision status: 전부 **Proposed**. Phase 3 진입 전에 ADR로 확정한다.

| 관찰 | Mission Control 함의 |
|---|---|
| 인터뷰는 파일, 실행은 DB | Phase 1 파일 baseline이 upstream과 어긋나지 않음 ([ADR-0013](../adr/0013-brief-durable-state-baseline.md)) |
| append-only + guard 테이블 | Gate decision을 이벤트로만 표현하면 동시 전이 선점 문제가 남는다. 단일 프로세스 v1에서는 지연 가능하나 MCP 도입 시 필수 |
| checkpoint ≠ event | 재개 스냅샷과 증거 누적을 같은 것으로 뭉치지 않는다 |
| UoW로 phase 경계 커밋 | Attempt 경계에서 Telemetry와 상태를 함께 커밋해야 부분 실패가 없다 |
| 전 계층 async | Execute/MCP 단계의 비동기 요구 ([ADR-0012](../adr/0012-python-toolchain-and-layout.md) Divergence 3의 재평가 트리거) |
| 가벼운 migration | 저장 schema 변경 대비는 필요하지만 무거운 도구는 불필요 |
| projection은 권위 없음 | Mission Control의 파생 뷰(요약, 리포트)도 canonical state를 대체하지 않는다 |

## 9. 아직 조사하지 않은 것

- 이벤트 타입 전체 목록과 aggregate 경계 설계
- `events/` 패키지의 이벤트 정의와 versioning 전략
- retention/redaction 정책의 구현 위치
- replay 성능과 snapshot 전략
- 다중 프로세스 worker가 DB를 공유할 때의 실제 제약

위 항목은 Phase 3(Execute) 설계 직전에 조사한다.
