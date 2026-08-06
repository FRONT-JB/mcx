# Progress 0000 — Documentation Foundation

- Status: READY FOR USER REVIEW
- Started: 2026-08-07
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
- [ ] 사용자가 문서 범위를 확인한다.

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

현재 판정:

```text
CLEAR — Documentation foundation ready for user review.
```

사용자 범위 확인과 필요한 수정을 반영하면 이 record를 `COMPLETE`로 닫는다. 이
documentation Gate는 코드 구현 Gate와 별개이며, 구현은
[Project Progress](./README.md#implementation-hold)의 조건이 해소될 때까지 `HOLD`다.
