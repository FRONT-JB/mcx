# ADR 0054 — `.git` 없는 소스 복사본 빌드는 manifest와 동기화된 fallback 버전으로 산출한다

- Status: Accepted (사용자 결정 2026-08-19 — 이슈 #1 제안 방향 (a) 선택)
- Date: 2026-08-19
- Constitutional basis: §7 Evidence over reasoning, §17 Scope와 Reasoning
  Discipline, [ADR-0012](./0012-python-toolchain-and-layout.md)
- Upstream evidence: pinned baseline `9486c78` `pyproject.toml:54-66`,
  `.mcp.json` (아래 원문 인용)

## Context

플러그인 설치 경로는 자기 소스에서 자기 MCP 서버를 빌드한다 — Claude는
`.mcp.json`의 `${CLAUDE_PLUGIN_ROOT}[mcp]`, Codex는 `.mcp.codex.json`의
plugin-root `cwd`로 같은 `uvx` self-build를 탄다 (Open Questions §8,
[progress 0008](../progress/0008_PLUGIN_COMPOSITION_LAYER.md)의 자기참조 MCP
등록). 그런데 버전 산출은 `hatch-vcs`(`source = "vcs"`)에만 의존하고 fallback이
없어, git 메타데이터가 없는 소스 복사본에서는 빌드 자체가 실패한다.

실측 증거는 [이슈 #1](https://github.com/FRONT-JB/mcx/issues/1)에 있다.

- marketplace 설치 캐시 `~/.claude/plugins/cache/mcx/mcx/0.1.1/`에는 `.git`이
  없고 `src/mission_control/_version.py`도 없다 (`.gitignore` 대상).
- 그 캐시에서 `uvx --from "<캐시>[mcp]" mcx-mcp`는
  `LookupError: Error getting the version from source 'vcs'`로 빌드에 실패하고,
  Claude Code에는 `Failed to reconnect to mcx: CONNECTION_CLOSED`로 나타난다.
- 복사본에 `_version.py`가 존재해도 동일하게 실패한다 — hatch-vcs의
  `version-file`은 빌드 시 **쓰기** 대상이지 읽기 fallback이 아니다.
- 캐시 사본에 `fallback_version` 한 줄을 추가하면 빌드가 성공하고 서버가 정상
  기동한다 (2026-08-19 실측).

### upstream은 이 문제를 겪지 않는다 — 설치 경로가 다르기 때문이다

pinned baseline(`9486c78`, v0.50.8)의 버전 산출 구성은 우리와 같고 fallback이
없다.

```toml
[tool.hatch.version]
source = "vcs"

[tool.hatch.version.raw-options]
version_scheme = "guess-next-dev"
local_scheme = "no-local-version"
```

그러나 upstream의 플러그인 MCP 등록(`.mcp.json`, 같은 commit)은 소스가 아니라
**PyPI 배포물**을 가리킨다.

```json
"args": ["--from", "ouroboros-ai[mcp]", "ouroboros", "mcp", "serve"]
```

즉 upstream의 설치 경로는 `.git` 없는 소스 복사본을 빌드할 일이 없다.
setuptools-scm이 읽는 버전 메타데이터는 git 또는 PyPI sdist의 `PKG-INFO`에서
오는데, upstream은 후자를 쓰고 우리는 전자만 있는 경로에 소스 복사본을 태운다.
따라서 이 결정에는 upstream 대응물이 없다 — 자기참조 MCP 등록이라는 등록된
divergence(progress 0008)의 결과를 수습하는 우리 쪽 규칙이다.

## Decision

### 1. hatchling + hatch-vcs는 유지한다 (ADR-0012 보완, 계약 변경 아님)

git checkout에서의 버전 산출은 지금처럼 vcs 기반(dev 버전, commit 수 기반
distance)이다. ADR-0012 Decision 표의 Build 항목(hatchling + hatch-vcs)은
바뀌지 않는다.

단, 실측으로 확인된 부수 효과가 하나 있다(아래 Consequences): 태그가 없는
저장소에서는 fallback 값이 dev 버전의 **기준점(태그 대용)** 으로도 쓰인다.

### 2. `fallback_version`을 추가한다

`[tool.hatch.version.raw-options]`에 `fallback_version`을 추가한다. 이 옵션은
setuptools-scm 공식 설정으로, 다른 모든 버전 검출이 실패했을 때 사용할 버전
문자열이며 없으면 오류가 난다 (setuptools-scm `docs/config.md`). hatch-vcs의
`raw-options`는 setuptools-scm에 그대로 전달된다.

```toml
[tool.hatch.version.raw-options]
version_scheme = "guess-next-dev"
local_scheme = "no-local-version"
fallback_version = "0.1.2"
```

의미 축은 다음과 같다. `.git` 없는 소스 복사본은 곧 **배포된 플러그인 버전의
설치 산출물**이므로, fallback 값은 임의 상수가 아니라 그 배포물의 버전이다.

### 3. 동기화 규칙 — fallback은 plugin manifest 버전과 항상 같다

버전을 선언하는 자리는 이제 네 곳이다: `.claude-plugin/plugin.json`,
`.codex-plugin/plugin.json`, `.claude-plugin/marketplace.json`, 그리고
`pyproject.toml`의 `fallback_version`. 네 값은 항상 같아야 하며, plugin 버전을
올리는 커밋이 fallback도 같이 올린다.

이 규칙은 사람의 기억이 아니라 기존 manifest 버전 일치 테스트
(`tests/unit/skills/test_skill_artifacts.py`)를 확장해 기계적으로 강제한다 —
테스트가 `pyproject.toml`을 파싱해 fallback을 같은 집합에 넣는다.

### 3.1 checkout package 버전과 plugin release 버전의 분리 — issue #7

2026-08-23 현재 두 버전 축은 **의도적으로 분리**한다.

| 축 | 원천 | 현재 실측 | 계약 |
|---|---|---|---|
| plugin release version | 두 host manifest·marketplace·`fallback_version` | `0.1.2` | 네 값이 항상 같다 |
| checkout package version | `[project].dynamic = ["version"]` + hatch-vcs `source = "vcs"` | `0.1.3.dev179` | git checkout의 commit 거리로 산출되며 release version과 같을 필요가 없다 |

따라서 untagged checkout에서 `importlib.metadata.version("mission-control")`와
plugin manifest를 항상 같게 비교하는 계약 테스트는 추가하지 않는다. 그런
비교는 현재 개발 산출물의 dev distance와 설치 캐시의 fallback 산출물을
혼동하고, plugin 버전을 올리지 않은 채 checkout commit만 늘어날 때 거짓
실패를 만든다. 이 결정은 issue #7의 선택지 (a)이며, manifest 네 값의
동기화 테스트와 `[project]`의 VCS 동적 버전 설정 검사는 유지·강화한다.

향후 사용자가 tag/release를 승인하면 [progress 0012](../progress/0012_V1_RELEASE_READINESS.md)
§1의 release artifact 재감사에서 **그 release 산출물**의 Python package
version과 plugin release version을 함께 확인한다. 이 문서는 tag/release를
생성할 권한을 부여하지 않으며, release 산출물까지 현재 checkout 계약을
바꾸는 결정은 별도 ADR로 한다.

## Consequences

### Positive

- marketplace 설치 캐시(`.git` 부재)에서 빌드와 MCP 서버 기동이 복구된다.
- 개발 경로(git checkout)의 vcs 산출(빌드 성공, commit 수 기반 dev distance)이
  유지된다.
- fallback 값 잊음은 릴리스 시점이 아니라 테스트 시점에 드러난다.

### Observed — dev 버전의 기준점이 fallback으로 바뀐다

태그 없는 저장소의 git checkout 빌드가 `0.1.devN`에서 `0.1.3.devN`으로 바뀐다.
같은 commit(distance 167)에서 fallback 유무만 바꾼 통제 실험의 실측이다
(2026-08-19): fallback 없으면 `0.1.dev167`, `fallback_version = "0.1.2"`면
`0.1.3.dev167`. setuptools-scm 공식 문서는 fallback을 "다른 검출이 모두 실패했을
때"의 값으로만 기술하므로, 태그 없는 저장소에서 기준점으로 쓰이는 이 동작은
문서화되지 않은 실측 사실로 취급한다.

이 변화는 회귀가 아니라 정렬 개선이다. 기존 `0.1.devN`은 배포된 `0.1.1`보다
**과거**로 정렬됐지만(`0.1.devN < 0.1.1`), 새 dev 빌드는 최신 배포판 다음의
pre-release로 정렬된다(`0.1.2 < 0.1.3.devN`). 태그를 쓰는 upstream에서
guess-next-dev가 "최신 태그 다음의 dev"를 산출하는 것과 같은 의미가 된다.

### Cost

- plugin 버전을 올릴 때 갱신할 자리가 세 곳에서 네 곳이 된다 (테스트가 강제).
- git checkout 빌드(`0.1.3.devN`)와 캐시 빌드(`0.1.2`)의 버전 문자열 형태가
  다르다. 전자는 개발 산출물, 후자는 설치 산출물이므로 의도된 차이다.

## Rejected alternatives

- **(b) `_version.py`를 동봉하고 읽기로 전환**: hatch-vcs의 `version-file`은
  쓰기 전용 hook이라(실측) 읽기 소스로 쓰려면 버전 소스 재설계가 필요하다.
  세 방향 중 비용이 가장 크다.
- **(c) 정적 버전 선언으로 전환**: `[project] version` 고정은 hatch-vcs 폐기
  즉 ADR-0012 Build 계약 변경이고, dev 버전 산출과 upstream 대조 가능성을
  잃는다. 동기화 부담은 (a)와 같으므로 얻는 것이 없다.
- **PyPI 배포로 전환 (upstream 정렬)**: 문제의 근본 회피지만 README의 설치
  계약("PyPI 배포가 필요 없다")을 폐기하고
  [progress 0012](../progress/0012_V1_RELEASE_READINESS.md)의 Non-goal(PyPI
  게시)을 뒤집는 별도 결정이다. 배포 파이프라인·계정 관리가 새로 생긴다.
  사용자가 2026-08-19 (a)를 선택하며 기각했다.

## Verification

- `.git` 없는 소스 복사본에서 `uv build`가 성공하고 버전이 fallback 값이다.
- `.git` 없는 소스 복사본에서 `uvx --from '<복사본>[mcp]' mcx-mcp tools`가
  tool 목록을 출력한다.
- 정상 git checkout에서 `uv build`가 vcs 산출(commit 수 기반 dev distance,
  기준점은 fallback — `0.1.3.devN`)로 성공한다.
- manifest 버전 일치 테스트가 `fallback_version`을 포함해 네 값의 동일성을
  검사한다.
- plugin version 테스트 docstring이 checkout package의 VCS dev version과
  release manifest version을 비교하지 않는 이유를 issue #7 및 이 ADR에
  연결한다. `[project].dynamic`/hatch-vcs source 계약도 테스트로 고정한다.
