# ADR 0055 — 저장소 검증 게이트 자동화와 coverage 하한

- Status: Accepted
- Date: 2026-08-22
- Constitutional basis: ADR-0005 Evidence over reasoning, §21 Verification Policy
- Related issue: [#2](https://github.com/FRONT-JB/mcx/issues/2)

## Context

mcx는 `Executed is not verified`를 핵심 원칙으로 두지만, 저장소 자체의
pytest·mypy·ruff·format 검사는 개발자가 수동으로 실행해야 했다. 따라서 변경이
push 또는 pull request에 들어갈 때 검증 명령을 실행했다는 독립 증거가 없었다.

2026-08-22 현재 기준으로 `uv run pytest --cov=src -q`는 1068개 테스트와 총
93% coverage를 통과한다. 이 기준을 그대로 하한으로 고정하면 작은 변경이
coverage를 조금만 낮춰도 즉시 불필요하게 막힐 수 있으므로, 현재 측정값 아래의
90%를 초기 하한으로 둔다. 예를 들어 총 coverage가 89.9%가 되면 CI와 로컬
`uv run pytest`가 실패하고, 90% 이상이면 다른 정적 게이트와 함께 계속 평가한다.

현재 persistence adapter는 POSIX 전용 `fcntl`을 사용한다. Windows runner를
선택하면 테스트가 시작되기 전에 import 단계에서 실패하므로, 플랫폼 지원을
확장하는 별도 결정 전까지 CI runner는 Ubuntu로 제한한다.

## Decision

- `.github/workflows/ci.yml`을 추가해 `push`와 `pull_request`에서 실행한다.
- runner는 `ubuntu-latest`만 사용한다. Windows는 `fcntl` 제약을 해결하는
  별도 작업 전까지 제외한다.
- Python은 저장소의 `.python-version`을 `actions/setup-python`의
  `python-version-file`로 읽는다. 현재 값은 3.12다.
- 의존성은 `uv sync --locked`로 lockfile과 일치하게 설치한다.
- workflow는 다음 명령을 실행한다.
  - `uv run pytest`
  - `uv run mypy src`
  - `uv run ruff check .`
  - `uv run ruff format --check src tests`
- pytest 설정에 `pytest-cov`의 `--cov=src`를 넣어 로컬과 CI의 `uv run pytest`가
  같은 coverage 검증을 수행하게 한다.
- `pyproject.toml`의 `[tool.coverage.report] fail_under = 90`을 공통 하한으로
  사용한다. CI 명령에만 별도 하한을 숨기지 않는다.
- GitHub branch protection, release, tag 생성은 이 ADR의 범위가 아니다.

## Consequences

### Positive

- push와 pull request마다 정적 검사와 테스트의 독립 실행 evidence가 남는다.
- 개발자가 README의 `uv run pytest`를 실행할 때도 CI와 같은 coverage 하한을
  확인한다.
- lockfile, Python 버전, runner 플랫폼 제약이 workflow에 드러난다.

### Cost

- 모든 pytest 실행이 coverage 수집을 포함하므로 로컬 실행 시간이 증가한다.
- 현재는 Windows 플랫폼을 검증하지 못한다.
- 90% 하한을 넘기려면 coverage가 낮은 코드에 테스트를 추가해야 한다.

## Rejected alternatives

- **CI에서만 `--cov-fail-under` 적용**: 로컬 `uv run pytest`와 CI가 서로 다른
  검증 명령이 되어 drift를 만든다.
- **coverage를 현재 측정값인 93%로 고정**: 측정 오차와 작은 정상 변경을
  구분하지 못하고 초기 게이트가 과도하게 불안정해진다.
- **Windows runner 추가**: `fcntl` 기반 persistence 계약을 해결하지 않은 채
  runner만 추가하면 import 실패를 검증 실패로 반복할 뿐이다.
- **macOS runner까지 병렬 추가**: 현재 이슈의 최소 검증 범위는 POSIX 중
  Ubuntu 하나로 충족하며, 별도 OS 호환성 검증은 플랫폼 이슈의 범위다.

## Verification

- 로컬 기준: `uv run pytest --cov=src -q` → 1068 passed, TOTAL 93%.
- 로컬 기준: `uv run mypy src` → no issues found in 93 source files.
- 로컬 기준: `uv run ruff check .` → All checks passed.
- 로컬 기준: `uv run ruff format --check src tests` → 173 files already formatted.
- GitHub 기준: [`main` CI run 32567434695](https://github.com/FRONT-JB/mcx/actions/runs/32567434695)
  → 모든 단계 성공(38초).
- 초기 run [`32567404888`](https://github.com/FRONT-JB/mcx/actions/runs/32567404888)은
  `astral-sh/setup-uv@v9` tag를 해석하지 못해 job 초기화에서 실패했다. 공식
  `v9.0.0` commit SHA를 사용하도록 고쳐 후속 run을 통과시켰다.
