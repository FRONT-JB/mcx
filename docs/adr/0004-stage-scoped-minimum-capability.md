# ADR 0004 — Stage-scoped minimum capability

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Least capability by stage

## Context

프롬프트로 역할을 설명해도 Runtime에 Shell, Git, filesystem, network 권한이 모두
열려 있으면 모델은 현재 Stage 밖의 작업을 수행할 수 있다. 특히 Brief 중 코드
수정, Verify 중 구현 수정, delegated worker의 Mission Control 재호출은 책임
경계를 무너뜨린다.

## Decision

각 dispatch는 현재 Stage와 역할에 필요한 최소 capability만 부여한다.

- Brief 질문 생성: one-turn, no tool, no file write, no Shell/Git/browser.
- Blueprint 생성/QA: 제공된 context와 구조화 출력에 필요한 capability만 허용.
- Execute: 명시된 workspace/file/tool scope만 허용.
- Verify: 관찰과 검증 권한만 허용하며 구현 수정 권한을 분리.
- Recover: 실패와 관련된 최소 수정 범위만 허용.
- delegated worker의 Mission Control/MCP 재귀 호출은 금지.
- 외부 쓰기, commit/push/deploy/message는 별도 승인이 필요.

제약은 가능한 경우 prompt가 아니라 runtime allowlist, sandbox, filesystem scope로
강제한다.

## Consequences

### Positive

- 역할 이탈과 의도 drift의 피해 반경이 줄어든다.
- self-approval과 recursive orchestration을 구조적으로 차단한다.
- 어떤 권한으로 결과가 만들어졌는지 감사할 수 있다.

### Cost

- Runtime별 권한 모델을 공통 capability로 매핑해야 한다.
- 지나치게 좁은 권한은 작업 실패를 만들 수 있다.
- capability 변경에도 새로운 attempt 또는 승인이 필요할 수 있다.

## Rejected alternatives

- 모든 agent에 전체 도구를 주고 prompt로만 제한한다.
- 한 Stage에서 획득한 권한을 다음 Stage로 자동 상속한다.
- worker가 필요하면 다른 Mission Control tool을 자유롭게 호출하게 한다.

## Verification

- Brief role이 file/Shell tool을 호출할 수 없다.
- Verify role이 코드 수정 tool을 사용할 수 없다.
- scope 밖 파일/외부 쓰기 시도가 차단되고 Telemetry에 기록된다.
- recursion guard가 delegated Mission Control 호출을 거절한다.

