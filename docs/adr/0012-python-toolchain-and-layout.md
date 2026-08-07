# ADR 0012 — Python toolchain and project layout

- Status: Proposed
- Date: 2026-08-07
- Constitutional basis: §17 (Scope와 Reasoning Discipline), §21 (Verification Policy)
- Upstream evidence: baseline `pyproject.toml`, `tests/` 구조

## Context

Phase 1 첫 코드를 작성하려면 Python 버전, packaging, test framework, lint를
정해야 한다. Constitution §25는 이 항목의 결정 위치를 “Architecture / ADR”로
지정했다.

upstream baseline에서 확인한 구성:

- `requires-python >= 3.12`, `src/` layout, hatchling + hatch-vcs
- uv (`[dependency-groups]`, `uv.lock`, extras 충돌 선언)
- 도메인 모델은 pydantic 2.x, CLI는 typer + rich, 로깅은 structlog
- pytest 9.x + pytest-asyncio(`asyncio_mode = "auto"`) + pytest-cov + pytest-xdist
- ruff (line-length 100, target py312), mypy (python_version 3.12)
- 테스트 628개, `tests/unit/<subpackage>` 미러 구조 + integration/e2e/conformance
- 전 계층이 async이며 blocking I/O는 `asyncio.to_thread`로 오프로드

## Decision

기본 구성은 upstream을 따르고, 네 지점에서 다르게 간다.

### 채택

| 항목 | 값 |
|---|---|
| Python | `>= 3.12` |
| Layout | `src/mcx/`, 테스트는 `tests/`가 패키지 구조를 미러링 |
| Build | hatchling + hatch-vcs |
| 의존성 관리 | uv (`[dependency-groups]`, lock file 커밋) |
| 도메인 모델 | pydantic 2.x |
| 테스트 | pytest, pytest-cov |
| Lint/format | ruff, line-length 100, target py312 |
| 타입 검사 | mypy |

### Divergence 1 — mypy를 strict로 시작

upstream은 `disable_error_code`로 14개 오류 범주를 비활성화했다. 이는 규모가
커진 코드베이스에 점진적으로 타입 검사를 도입할 때의 일반적 타협이다. mcx는
빈 저장소에서 시작하므로 그 부채가 없다.

Brief 도메인의 핵심(authority 값, Gate decision, revision identity)은 타입으로
표현할 때 가장 잘 보호되므로 `strict = true`로 시작한다. 완화가 필요하면 그때
근거와 함께 좁은 범위로 푼다.

### Divergence 2 — 의존성은 필요한 시점에 추가

typer, rich, structlog, sqlalchemy는 Phase 1에 넣지 않는다. Phase 1의 범위는
Brief 도메인·정책·상태이며 CLI와 로깅 백엔드는 Phase 6과 이후의 관심사다.
[ADR-0001](./0001-workflow-before-runtime.md)이 요구하는 “Runtime 없이 Core를
테스트한다”를 의존성 목록에서도 지킨다.

초기 런타임 의존성은 pydantic 하나다.

### Divergence 3 — Phase 1 Core는 동기

upstream은 전 계층이 async다. Phase 1의 외부 I/O는 상태 파일 읽기·쓰기
하나뿐이고, 도메인 규칙과 Gate 정책은 순수 함수로 표현된다. 지금 async를
도입하면 모든 test double과 use case가 이유 없이 async가 된다.

대신 I/O 경계를 port로 분리해 두어, Runtime을 도입하는 Phase 3에서 비동기
구현을 추가해도 도메인이 바뀌지 않게 한다. 도메인 계층에는 I/O를 두지 않는다.

### Divergence 4 — pytest-xdist는 도입하지 않는다

테스트 628개를 병렬 실행할 이유는 mcx에 아직 없다. 실행 시간이 실제 문제가
되면 추가한다.

## Consequences

### Positive

- upstream과 같은 언어·빌드·테스트 기반이라 동작을 직접 비교할 수 있다.
- 의존성이 적어 Core 테스트가 빠르고 외부 장애에 영향받지 않는다.
- strict 타입 검사가 도메인 불변 조건을 코드로 강제한다.
- 동기 Core는 test double이 단순하다.

### Cost

- mypy strict는 초기 작성 비용이 있다.
- 동기에서 비동기로 넘어갈 때 port 구현을 추가해야 한다. 도메인은 유지되지만
  application 계층의 시그니처는 바뀔 수 있다.
- upstream 코드를 참고할 때 async/sync 차이를 매번 변환해야 한다.

## Rejected alternatives

- **upstream 설정을 그대로 복사**: mypy 완화 목록은 upstream의 이력에서 나온
  것이지 설계 결정이 아니다. 빈 저장소가 그 부채를 물려받을 이유가 없다.
- **poetry 또는 pip-tools**: upstream이 uv를 사용하고 lock 재현성이 동등하다.
  다른 도구를 쓸 근거가 없다.
- **처음부터 async 전면 도입**: Phase 1에 비동기가 필요한 I/O가 없다. §17이
  금지하는 선제적 복잡도다.
- **CLI 의존성을 미리 설치**: Phase 1 완료 판정에 CLI가 필요 없다.

## Verification

- `uv sync` 후 Core 테스트가 Codex/OpenCode 설치 없이 실행된다.
- `mypy --strict`가 통과한다.
- Phase 1 테스트가 pydantic 외 런타임 의존성 없이 실행된다.
- 도메인 모듈이 파일시스템·네트워크를 직접 호출하지 않는다.
