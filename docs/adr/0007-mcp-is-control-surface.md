# ADR 0007 — MCP is a control surface, not the Core

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: CLI and MCP boundaries

## Context

이 프로젝트는 Claude, Codex, OpenCode 등 여러 host와 연결되는 MCP에 관심이
크다. 그러나 MCP handler 안에 인터뷰, 상태 전이, Runtime dispatch를 직접
구현하면 프로토콜이 Workflow의 본체가 되고 CLI와 동작이 달라진다.

## Decision

MCP는 Mission Control application boundary를 호출하는 adapter/control surface다.

- Mission state와 Gate는 Core가 소유한다.
- MCP tool은 입력을 검증하고 Core command/query로 변환한다.
- Core 결과를 protocol response로 변환하되 의미를 다시 판정하지 않는다.
- CLI와 MCP는 같은 command/query contract를 사용한다.
- host session, Mission session, Runtime worker session을 구분한다.
- MCP client가 끊겨도 durable Mission state는 유지된다.

## Consequences

### Positive

- CLI와 MCP의 동작 의미가 일치한다.
- transport 변경이 Core state machine을 바꾸지 않는다.
- host를 바꿔도 Mission을 재개할 수 있다.
- protocol handler를 얇게 테스트할 수 있다.

### Cost

- MCP 전에 application boundary를 설계해야 한다.
- job/stream/polling과 같은 transport lifecycle을 Core handle에 매핑해야 한다.
- client disconnect와 Mission cancel을 구분해야 한다.

## Rejected alternatives

- MCP tool마다 별도의 workflow를 구현한다.
- Claude/Codex host conversation을 Mission state로 사용한다.
- MCP client disconnect를 실행 취소로 간주한다.

## Verification

- CLI와 MCP의 동일 command가 같은 Core result를 만든다.
- handler unit test는 business policy를 포함하지 않는다.
- host 재접속 후 Mission ID로 상태를 다시 읽을 수 있다.

