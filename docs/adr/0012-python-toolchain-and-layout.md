# ADR 0012 — Python toolchain and layout

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Principle 10 (Reconstruct before improve), §17 (Scope와 Reasoning Discipline), §21 (Verification Policy)
- Upstream evidence: baseline `pyproject.toml`, `tests/` 구조, `bigbang/interview.py`

## Context

Phase 1 첫 코드를 작성하려면 Python 버전, packaging, test framework, lint, 그리고
**실행 모델**을 정해야 한다. Constitution §25는 이 항목의 결정 위치를
“Architecture / ADR”로 지정했다.

upstream baseline에서 확인한 구성:

- `requires-python >= 3.12`, `src/` layout, hatchling + hatch-vcs
- uv (`[dependency-groups]`, `uv.lock`, extras 충돌 선언)
- 도메인 모델은 pydantic 2.x, CLI는 typer + rich, 로깅은 structlog
- pytest 9.x + pytest-asyncio(`asyncio_mode = "auto"`) + pytest-cov + pytest-xdist
- ruff (line-length 100, target py312), mypy (python_version 3.12)
- 테스트 628개, `tests/unit/<subpackage>` 미러 구조 + integration/e2e/conformance
- **계층별 실행 모델 분리**: pydantic 모델과 순수 계산은 동기, engine/store
  메서드는 async, blocking I/O는 `asyncio.to_thread`로 오프로드

## Decision

기본 구성은 upstream을 따르고, 세 지점에서 다르게 간다.

### 채택

| 항목 | 값 |
|---|---|
| Python | `requires-python >= 3.12`, 개발은 `.python-version`으로 3.12 고정 |
| Package | `src/mission_control/` — 프로젝트명 기반. CLI 이름 `mcx`는 entry point이지 패키지명이 아니다 (upstream도 `ouroboros` 패키지에 `ooo` CLI) |
| Layout | 계층 폴더(`domain` / `application` / `adapters`)를 물리적으로 분리하고 테스트가 이를 미러링 |
| Build | hatchling + hatch-vcs |
| 의존성 관리 | uv (`[dependency-groups]`, lock file 커밋) |
| 도메인 모델 | pydantic 2.x |
| 테스트 | pytest, pytest-asyncio(`asyncio_mode = "auto"`), pytest-cov |
| Lint/format | ruff, line-length 100, target py312 |
| 타입 검사 | mypy |

### 실행 모델 — upstream과 동일한 계층별 분리

실행 모델은 나중에 덧붙일 수 있는 기능이 아니라 **계층 시그니처를 결정하는
구조**다. 전환은 use case와 그 모든 호출자·테스트를 동시에 바꾸는 작업이므로
“필요해지면 그때” 미룰 수 있는 항목이 아니다.

| 계층 | 실행 모델 | 근거 |
|---|---|---|
| 도메인 (clarity 판정, authority 분류, revision 규칙) | 동기 순수 함수 | 대기가 없는 계산이다. upstream의 pydantic 모델도 동기다. |
| Application use case (Brief 시작, 질문 생성, 답변 기록, Gate 판정) | `async` | Phase 3 이후 Runtime dispatch가 이 자리에 들어온다. |
| Port (state repository, text-generation backend, execution runtime) | `async` | 구현이 subprocess·네트워크·async 라이브러리를 사용한다. |

Phase 1 구현은 async use case 안에서 동기 파일 I/O를 직접 호출한다. 대상이 작은
로컬 파일이라 blocking이 문제되지 않으며, 필요해지면 upstream처럼
`asyncio.to_thread`로 오프로드한다. **시그니처는 그대로 유지된다.**

Phase 3 이후에 비동기가 실제로 강제되는 조건은 다음과 같으며, 위 구조는 그 조건이
도래해도 계층 경계를 바꾸지 않는다.

- 사용할 라이브러리가 async 인터페이스만 제공한다 (MCP SDK, aiosqlite,
  SQLAlchemy async, 각종 agent SDK).
- 실행 중인 프로세스의 출력을 수신하면서 동시에 취소·timeout을 처리해야 한다.
- 여러 dispatch를 동시에 진행한다. (v1 비범위이나 Phase 5 이후 후보)

### Divergence 1 — mypy를 strict로 시작

upstream은 `disable_error_code`로 14개 오류 범주를 비활성화했다. 이는 규모가
커진 코드베이스에 점진적으로 타입 검사를 도입할 때의 일반적 타협이며 설계
결정이 아니다. mcx는 빈 저장소에서 시작하므로 그 부채가 없다.

Brief 도메인의 핵심(authority 값, Gate decision, revision identity)은 타입으로
표현할 때 가장 잘 보호되므로 `strict = true`로 시작한다. 완화가 필요하면 그때
근거와 함께 좁은 범위로 푼다.

### Divergence 2 — 의존성은 필요한 시점에 추가

typer, rich, structlog, sqlalchemy는 Phase 1에 넣지 않는다. Phase 1의 범위는
Brief 도메인·정책·상태이며 CLI와 로깅 백엔드는 Phase 6과 이후의 관심사다.
[ADR-0001](./0001-workflow-before-runtime.md)이 요구하는 “Runtime 없이 Core를
테스트한다”를 의존성 목록에서도 지킨다.

초기 런타임 의존성은 pydantic 하나이며, 개발 의존성은 pytest, pytest-asyncio,
pytest-cov, ruff, mypy다.

이 divergence는 실행 모델과 성격이 다르다. 라이브러리 추가는 나중에 해도 기존
코드를 바꾸지 않는다.

### Divergence 3 — pytest-xdist는 도입하지 않는다

테스트 628개를 병렬 실행할 이유는 mcx에 아직 없다. 실행 시간이 실제 문제가
되면 추가한다. 이것도 나중에 추가해도 기존 코드가 바뀌지 않는 항목이다.

## Consequences

### Positive

- upstream과 같은 언어·빌드·테스트·실행 모델이라 동작을 직접 비교할 수 있고,
  이후 대조 작업에 변환 비용이 없다.
- 실행 모델 전환을 위한 전면 수정이 발생하지 않는다.
- 의존성이 적어 Core 테스트가 빠르고 외부 장애에 영향받지 않는다.
- strict 타입 검사가 도메인 불변 조건을 코드로 강제한다.

### Cost

- Phase 1에는 비동기의 이점이 없는데 `async`/`await` 표기 비용을 지불한다.
- 테스트가 `async def`로 작성되어 pytest-asyncio 의존성이 필요하다.
- 도메인과 application의 실행 모델이 다르므로 경계를 명확히 유지해야 한다.

## Rejected alternatives

- **Phase 1 전체를 동기로 작성하고 Phase 3에서 전환**: 이 ADR의 이전 초안이었다.
  전환 비용을 “port로 격리하면 도메인이 바뀌지 않는다”로 방어했으나, 실제로
  바뀌는 것은 use case 계층 전체와 그 호출자·테스트다. Brief 구현의 실질이 거기
  있으므로 격리 주장이 성립하지 않는다. 또한 upstream이 async인 이유를 “선택”으로
  간주한 판단이 Principle 10에 어긋난다.
- **도메인까지 전면 async**: 대기가 없는 계산을 비동기로 만들 이유가 없고,
  upstream도 그렇게 하지 않는다.
- **upstream 설정을 그대로 복사**: mypy 완화 목록은 upstream의 이력에서 나온
  것이지 설계 결정이 아니다.
- **poetry 또는 pip-tools**: upstream이 uv를 사용하고 lock 재현성이 동등하다.
- **CLI 의존성을 미리 설치**: Phase 1 완료 판정에 CLI가 필요 없다.

## Verification

- `uv sync` 후 Core 테스트가 Codex/OpenCode 설치 없이 실행된다.
- `mypy --strict`가 통과한다.
- `domain` 패키지가 `application`·`adapters`를 import하지 않는다
  ([Architecture](../01_ARCHITECTURE.md) §7.1).
- 도메인 모듈에 `async` 함수와 I/O 호출이 없다.
- use case와 port가 `async`로 정의되어 있다.
- Phase 3에서 Runtime adapter를 추가할 때 use case 시그니처가 바뀌지 않는다.
