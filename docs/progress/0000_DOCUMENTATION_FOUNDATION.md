# Progress 0000 — Documentation Foundation

- Status: COMPLETE
- Started: 2026-08-07
- Completed: 2026-08-07
- Scope owner: Mission Control documentation

## Goal

참조 대화 없이도 새 Claude, Codex, OpenCode 세션이 Mission Control의 목적,
용어, 아키텍처, Lifecycle, Runtime/MCP 경계, 각 Stage 구현 순서를 이해할 수 있는
문서 시스템을 만든다.

## Inputs

- referenced conversation `Ouroboros MCP 구현 방법`
- 사용자가 확정한 Mission Control / `mcx` terminology
- `Q00/ouroboros` current upstream research snapshot
- 빈 `mcx` Git repository

## In scope

- Project Constitution
- Architecture and Lifecycle
- Runtime and MCP boundaries
- five Stage Guides
- foundational ADRs
- current status/roadmap
- upstream mapping/session decisions/open questions

## Out of scope

- Python package 생성
- dependency 선택
- CLI 또는 MCP 구현
- Runtime subprocess 실행
- persistence schema 구현
- upstream 코드 복사
- commit/push/release

## Deliverables

- [x] `docs/00_MISSION_CONTROL.md`
- [x] `docs/01_ARCHITECTURE.md`
- [x] `docs/02_MISSION_LIFECYCLE.md`
- [x] `docs/03_RUNTIME.md`
- [x] `docs/04_MCP.md`
- [x] `docs/05_BRIEF.md`
- [x] `docs/06_BLUEPRINT.md`
- [x] `docs/07_EXECUTE.md`
- [x] `docs/08_VERIFY.md`
- [x] `docs/09_RECOVER.md`
- [x] `docs/adr/`
- [x] `docs/progress/`
- [x] `docs/research/`

## Exit criteria

- [x] 모든 Markdown code fence가 닫혀 있다.
- [x] trailing whitespace와 malformed relative link가 없다.
- [x] 현재 파일을 가리키는 relative link가 존재한다.
- [x] public/internal terminology mapping이 전 문서에서 일치한다.
- [x] `CLEAR`, `HOLD`, `MISSION COMPLETE` 의미가 일치한다.
- [x] Recover `CLEAR`가 Verify로 진행한다.
- [x] exact threshold와 기술 선택의 확정/TBD 상태가 일치한다.
- [x] upstream 사실이 baseline/source와 구분되어 있다.
- [x] Git status와 생성 파일 수를 기록한다.
- [x] 사용자가 문서 범위를 확인한다. (2026-08-07 세션 승인)

## Verification evidence

```text
Markdown files: 25
Lines: 10,052
Words (`wc -w`): 51,919
Relative links checked: 84; missing targets: 0
Internal anchors checked: 3
Navigation reachability from 00_MISSION_CONTROL.md: 25/25
Markdown parser errors: 0
Unbalanced code fences: 0
Trailing-whitespace findings: 0
Terminology/lifecycle targeted scan findings after reconciliation: 0
Git status: docs/ is untracked; no commit created
Other untracked entry: .DS_Store (not part of this documentation work; untouched)
```

## Gate

최종 판정:

```text
COMPLETE — Documentation foundation reviewed and accepted.
```

2026-08-07 세션에서 사용자가 방향, canonical terminology, v1 boundary 요약을
검토하고 진행을 승인했다. 검토 중 확인된 사항:

- upstream 충실성은 현행 규범 수준을 유지한다 — 기본은 원본 충실이며, 차이는
  ADR과 테스트로 문서화된 예외만 허용한다.
- 과추론·오버프로그래밍 방지를 상시 노출하기 위해 루트 `AGENTS.md`
  (에이전트 온보딩 지침, `CLAUDE.md` symlink)를 추가했다. Constitution 수정은
  없었다.

코드 구현 Gate는 [Project Progress](./README.md#implementation-hold)에서 별도로
관리한다.
