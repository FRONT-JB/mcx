# Mission Control

> **Mission Control is not an AI.**<br>
> **Mission Control coordinates missions.**

모호한 요청을 곧바로 코딩 모델에 넘기지 않고, 질문으로 명확화하고 승인 가능한
명세로 고정한 뒤, 범위가 제한된 작업으로 실행하고 증거로 검증하는 workflow
control plane이다. CLI 이름은 `mcx`다.

```text
Brief → Blueprint → Execute → Verify
                                 └─ HOLD → Recover
```

## 현재 상태

Phase 0~11 구현을 완료했다. 다섯 Stage 전부가 실제 AI로 구동되며 실 AI
도그푸딩 7회를 수행했다. 최신 도그푸딩 0007은 실제 worker 3개 병렬 실행,
공통 파일 충돌 감지, Coordinator, 독립 Verify를 거쳐 `MISSION COMPLETE`까지
완주했다. 검증된 현재 상태와 알려진 한계는
[docs/progress/README.md](docs/progress/README.md)에 있다 — 이 README가 아니라
그 문서가 상태의 소유자다.

v1 release candidate는 plugin 새 설치, MCP 33종 handshake, Python 배포물 격리
설치와 MIT 라이선스 포함까지 통과해 Release Gate가 CLEAR다. tag·release는 별도
사용자 승인 전까지 만들지 않는다.

## 설치

**PyPI 배포가 필요 없다.** 플러그인이 자기 소스로 자기 MCP 서버를 띄운다.
Claude는 `.mcp.json`의 `${CLAUDE_PLUGIN_ROOT}`를, Codex는
`.mcp.codex.json`의 plugin-root `cwd`를 사용해 같은 `mcx-mcp`를 `uvx`로 직접
빌드한다.

```bash
claude plugin marketplace add https://github.com/FRONT-JB/mcx   # 또는 로컬 경로
claude plugin install mcx@mcx
```

Codex에서도 같은 marketplace를 설치할 수 있다.

```bash
codex plugin marketplace add FRONT-JB/mcx
codex plugin add mcx@mcx
```

**실물 확인 (2026-08-11)**: Claude와 Codex에 각각 로컬 경로로 새로 등록·설치해
skill 6종을 인식했다. Claude는 `plugin:mcx:mcx ... ✔ Connected`, Codex는 MCP
protocol handshake에서 tool 33종과 실제 `mcx_status` routing event를 확인했다.
검증용 plugin·marketplace 등록은 모두 제거했다.

개발 중에는 MCP 서버만 따로 붙일 수도 있다.

```bash
claude mcp add mcx -- uvx --from "$PWD[mcp]" mcx-mcp
```

```bash
uv sync                      # 개발 환경
uv run mcx --help            # CLI
uv run mcx-mcp tools         # MCP tool 목록 (33개)
```

MCP 서버를 host에 직접 등록하려면 로컬 경로를 가리킨다.

```bash
claude mcp add mcx -- uvx --from "$PWD[mcp]" mcx-mcp
```

## 설정

`<state-dir>/config.toml` 하나다 (기본 `~/.mcx/config.toml`). CLI 플래그로는
받지 않는다.

```toml
[stages.execute]
execution = "codex_cli"      # Stage별 backend (없으면 기본 조립)

[backends.codex_cli]
model = "gpt-5.6-sol"        # 없으면 현재 codex 설정을 읽어 채택하고 여기 적는다
reasoning_effort = "xhigh"
```

실행 worker는 사용자 codex 설정을 **상속하지 않는다** — worker가 Mission
Control을 되부르는 경로를 막기 위해서다
([ADR-0042](docs/adr/0042-skill-and-core-ownership-boundary.md) §6).

## 문서

새 세션은 [AGENTS.md](AGENTS.md)를 먼저 읽는다. 프로젝트의 규범은
[docs/00_MISSION_CONTROL.md](docs/00_MISSION_CONTROL.md)가 소유한다.

| 문서 | 내용 |
|---|---|
| [00_MISSION_CONTROL](docs/00_MISSION_CONTROL.md) | Project Constitution |
| [01_ARCHITECTURE](docs/01_ARCHITECTURE.md) | 구성 요소, 경계, 의존 방향 |
| [02_MISSION_LIFECYCLE](docs/02_MISSION_LIFECYCLE.md) | 상태 머신과 Gate |
| [03_RUNTIME](docs/03_RUNTIME.md) · [04_MCP](docs/04_MCP.md) | Runtime protocol, MCP surface |
| [05](docs/05_BRIEF.md)–[09](docs/09_RECOVER.md) | Stage Guides |
| [adr/](docs/adr/README.md) | Architecture Decision Records |
| [research/](docs/research/README.md) | upstream 조사와 대응표 |

## 참고 프로젝트

이 프로젝트는 [`Q00/ouroboros`](https://github.com/Q00/ouroboros)의 workflow
설계를 참고했다. 개념 대응표와 차이 기록은
[research/UPSTREAM_MAPPING.md](docs/research/UPSTREAM_MAPPING.md)와
[ADR-0011](docs/adr/0011-brief-deliberate-divergences.md)에 있다.

## 개발

```bash
uv sync
uv run pytest
uv run mypy src
uv run ruff check .
uv run ruff format --check src tests
```
