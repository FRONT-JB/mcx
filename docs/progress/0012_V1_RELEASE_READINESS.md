# Progress 0012 — v1 release-readiness audit

- 일시: 2026-08-11
- 범위: `main`의 v1 공개 계약, plugin 설치, Python 산출물, CLI/MCP smoke,
  문서·버전·라이선스 일치
- Non-goal: 새 기능, PyPI 게시, tag, GitHub release 생성
- 현재 Gate: **CLEAR — ready for user-approved release**

## 1. Release Gate

다음 조건을 모두 실제 산출물과 새 설치 환경에서 확인해야 `CLEAR — ready for
user-approved release`다.

1. `main`이 clean이고 전체 test·lint·format·typecheck가 통과한다.
2. sdist와 wheel이 빌드되고 Python 3.12 격리 환경에서 `[mcp]` extra와
   `mcx`·`mcx-mcp` entry point가 실행된다.
3. Claude plugin validate와 release tag dry-run이 통과한다.
4. Claude와 Codex 각각 새 설치·새 session에서 skill 6종과 MCP tool 33종을
   함께 발견한다.
5. plugin/marketplace/Python release version `0.1.0`이 모순되지 않는다.
6. 공개 저장소의 라이선스 선언과 실제 배포 파일이 일치한다.
7. 임시 설치·등록·산출물을 제거하고 제거 여부까지 확인한다.

`CLEAR`는 tag나 release 생성 권한이 아니다. AGENTS.md 규칙에 따라 둘은 별도
사용자 승인이 있어야 한다.

## 2. 초기 관측

| 검사 | 결과 |
|---|---|
| `claude plugin validate .` | PASS |
| `claude plugin tag --dry-run .` | PASS — `mcx--v0.1.0` 예상, 실제 tag는 만들지 않음 |
| sdist/wheel build | PASS — untagged candidate `0.1.dev153` |
| clean Python 3.12 install | PASS — dependency check, `mcx --help`, MCP tool 33종 |
| Codex local marketplace install | PASS — `mcx@mcx` 0.1.0 |
| 새 Codex session | **HOLD — skill 6종 발견, MCP tool `NONE`** |
| 라이선스 파일 | **HOLD — manifest는 MIT이나 저장소에 LICENSE가 없음** |

추가 정적 검사에서 README의 개발 명령 두 개가 현재 상태와 어긋났다.

- `ruff format --check src tests`는 45개 파일을 지적했다. 설정된 formatter로
  기계적으로 정리하고 전체 회귀를 다시 실행한다.
- `mypy src tests`는 flat test module의 중복 이름에서 중단됐다. 테스트를 strict
  mypy 범위에 넣는 옵션을 실험했지만 137개 파일 769건으로 별도 품질 과제다.
  현재 실제 strict 보장 범위인 `mypy src`로 README를 바로잡는다.

Codex MCP 결함은 [ADR-0042](../adr/0042-skill-and-core-ownership-boundary.md)
§1.1의 host별 bootstrap 계약으로 수정·재검증한다. 라이선스는 기술 구현으로
소유자와 저작권 표기를 추측하지 않는다.

## 3. 수정과 최종 검증

Codex 설치본에서 skill 6종은 보이지만 MCP가 등록되지 않은 원인은
`${CLAUDE_PLUGIN_ROOT}`가 Codex에서 치환되지 않은 채 `uvx --from` 인자로 전달된
것이었다. workflow와 서버 구현은 공유하되 host bootstrap만 분리했다.

- Claude: `.mcp.json` + `${CLAUDE_PLUGIN_ROOT}`
- Codex: `.mcp.codex.json` + plugin root `cwd` + 상대 경로 `.[mcp]`

자연어로 "목록을 알려 달라"고 한 Codex 응답은 수정 후에도 MCP를 없다고
요약했지만, 이는 발견 여부의 신뢰할 수 있는 증거가 아니었다. 설치 cache의 실제
명령으로 MCP protocol handshake를 수행해 tool 33종을 받았고, Codex가
`server=mcx`, `tool=mcx_status`인 `mcp_tool_call` event를 만든 것까지 확인했다.
해당 호출은 비대화식 승인 정책(`-a never`) 때문에 실행 직전에 취소됐으며,
host discovery와 routing 검증에는 충분하다.

| 검사 | 최종 결과 |
|---|---|
| 전체 회귀 | PASS — `1058 passed` |
| lint / format | PASS — `ruff check .`, 171 files formatted |
| type / lock | PASS — `mypy src` 92 files, `uv lock --check` |
| release build | PASS — simulated `0.1.0` sdist/wheel, `twine check` |
| 격리 설치 | PASS — Python 3.12, dependency check, `mcx`, `mcx-mcp` 33 tools |
| Claude plugin | PASS — validate/tag dry-run, 새 로컬 설치에서 skill 6종·MCP server 1개·connected |
| Codex plugin | PASS — skill 6종, MCP handshake 33종, 실제 `mcx_status` routing event |
| 임시 환경 정리 | PASS — Claude/Codex plugin·marketplace 등록 제거 확인 |
| 라이선스 일치 | PASS — MIT, `Copyright (c) 2026 FRONT-JB`, package metadata·wheel·sdist 일치 |

기술 release candidate와 공개 라이선스 일치 검증을 모두 통과했다. tag와 release는
별도 승인 전까지 만들지 않는다.

## 4. 비용 예측과 실측

- 최초 예상: 새 Codex session 1회.
- 실제 AI 호출: 3회.
  1. 수정 전 inventory에서 skill 6 / MCP 0을 재현했다.
  2. 수정 후 같은 inventory 질문은 실제 등록과 달리 MCP가 없다고 요약했다.
  3. `mcx_status` 사용을 명시하자 실제 `mcp_tool_call` routing event가 생성됐다.
- 추가 비-AI 검증: 설치 cache 명령으로 MCP protocol handshake 1회.

예상보다 2회 늘어난 이유는 첫 결함을 수정한 뒤에도 자연어 inventory 응답이
host의 실제 tool registry를 정확히 반영하지 않아, tool 호출 event로 다시
검증해야 했기 때문이다. 다음 검증부터는 자연어 inventory를 Gate evidence로
사용하지 않고 protocol handshake와 tool-call event를 바로 확인한다.

## 5. 라이선스 결정과 재검증

**2026-08-11 사용자 결정:** MIT를 유지하고 저작권자 문구를
`Copyright (c) 2026 FRONT-JB`로 확정했다.

결정 반영 후 다음을 재검증했다.

- root `LICENSE`와 `[project] license = "MIT"`, `license-files = ["LICENSE"]`
- simulated `0.1.0` wheel metadata의 `License-Expression: MIT`와
  `License-File: LICENSE`
- wheel의 `.dist-info/licenses/LICENSE`와 sdist root `LICENSE`
- Python 3.12 격리 설치, dependency check, CLI, MCP tool 33종
- 전체 `1058 passed`, lint, format, typecheck, lock check
- 검증용 임시 디렉터리 제거 확인

따라서 Release Gate를 `CLEAR — ready for user-approved release`로 판정한다.

## 6. 다음 한 개의 검증 가능한 목표

사용자가 tag와 release 생성을 명시적으로 승인하면 `mcx--v0.1.0` tag를 생성해
origin 반영을 확인하고 release artifact를 게시한다.
