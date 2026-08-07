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

Phase 1 (Brief vertical slice) 구현 중이다. 검증된 현재 상태는
[docs/progress/README.md](docs/progress/README.md)에 있다.

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

## Upstream

이 프로젝트는 [`Q00/ouroboros`](https://github.com/Q00/ouroboros)의 핵심
workflow를 재구성하며 그 설계 의도를 학습한다. 대응표와 의도적 차이는
[research/UPSTREAM_MAPPING.md](docs/research/UPSTREAM_MAPPING.md)와
[ADR-0011](docs/adr/0011-brief-deliberate-divergences.md)에 있다.

## 개발

```bash
uv sync
uv run pytest
uv run mypy src tests
uv run ruff check .
```
