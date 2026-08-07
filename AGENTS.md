# AGENTS.md — Mission Control (`mcx`) 에이전트 작업 지침

이 파일은 새 에이전트 세션(Claude, Codex, OpenCode)이 방향을 잃지 않기 위한
**최소 지침**이다. 상세 규범은 `docs/`가 소유하며, 이 파일은 요약과 포인터만
담는다. 이 파일과 `docs/`가 충돌하면
[Constitution](docs/00_MISSION_CONTROL.md)이 이긴다.

## 프로젝트 정체

Mission Control은 upstream `Q00/ouroboros`의 핵심 워크플로(Interview → Seed →
Run → Evaluate → Repair)를 작은 Python 시스템으로 재구성하며 그 설계 의도를
학습하는 프로젝트다. CLI 이름은 `mcx`다.

> Mission Control is not an AI. It does not generate or review code.
> It coordinates missions.

## 세션 시작 절차

1. [Constitution](docs/00_MISSION_CONTROL.md)을 읽는다. 특히 §24 New Session
   Onboarding Protocol을 따른다.
2. [Progress](docs/progress/README.md)에서 **검증된 현재 상태**와 HOLD/CLEAR를
   확인한다. 코드 구현 시작 가능 여부는 이 문서의 Implementation HOLD 섹션이
   결정한다.
3. 작업과 관련된 문서를 읽는다: [Architecture](docs/01_ARCHITECTURE.md),
   [Lifecycle](docs/02_MISSION_LIFECYCLE.md), [Runtime](docs/03_RUNTIME.md),
   [MCP](docs/04_MCP.md), Stage Guide(`docs/05_BRIEF.md`~`09_RECOVER.md`),
   [ADR](docs/adr/README.md).
4. 사용자의 요청을 현재 Stage, Goal, Non-goal, 권한으로 다시 표현한 뒤 시작한다.

## 진실의 원천 우선순위

사용자의 명시적 결정 > Constitution > Accepted ADR > Architecture/Lifecycle >
Stage Guide/승인된 Blueprint > 테스트·인터페이스 계약 > 구현 > 채팅 기록.

하위 항목이 상위와 충돌하면 하위를 고친다. 충돌을 발견하면 숨기지 않고 드러낸다.

## 용어 규칙 (변경 금지)

| 사용자·CLI 용어 | 내부·upstream 용어 |
|---|---|
| Brief | Interview |
| Blueprint | Seed |
| Execute | Run |
| Verify | Evaluate |
| Recover | Repair |

- Gate 결과는 대문자 `CLEAR` / `HOLD`. `NO-GO`는 사용하지 않는다.
- 최종 성공은 `MISSION COMPLETE`이며 Verify Gate만 선언할 수 있다.
- 실행 주체는 Flight Controller, 구조화된 증거는 Telemetry라 부른다.
- 폐기된 명칭(IntentRelay, Ophion, The Coil, `mctl`, `mc`, GO/NO-GO)을 새 문서와
  코드에 쓰지 않는다.

## 어기면 안 되는 원칙

전체 목록은 Constitution §7과 Appendix A. 요약:

- **문서가 코드보다 먼저다.** Stage/Gate/경계/용어 변경은 문서와 ADR이 먼저다.
- **승인된 Blueprint 없이 Execute하지 않는다.** 승인된 Seed revision은 불변이며,
  변경은 새 revision + 재승인이다 (ADR 0002).
- **Evidence over reasoning.** 에이전트의 "완료" 주장은 완료가 아니다. Telemetry
  없는 `CLEAR`는 없다 (ADR 0005).
- **Stage별 최소 capability.** 자기 작업의 자기 승인 금지, delegated worker의
  Mission Control 재귀 호출 금지 (ADR 0004).
- **Scope는 hard boundary.** 범위 밖 개선 아이디어는 구현하지 않고 기록만 남긴다.
- **Reconstruct before improve.** 원본을 이해하기 전에 다르게 만들지 않는다.
  의도적 차이는 ADR과 테스트로 드러낸다.
- **Core는 Runtime-neutral.** vendor 세부사항은 adapter 경계 안에만 둔다. 초기
  Runtime은 Codex/OpenCode이며 Gemini는 v1 제외 (ADR 0003).

## 과추론·오버프로그래밍 금지

기준은 Constitution §17 (Scope와 Reasoning Discipline). 이 프로젝트가 특히
피하려는 실패는 과추론으로 워크플로가 느려지고 원래 의도에서 벗어나는 것이다.

- 기본은 upstream Ouroboros의 재구성이다. upstream에 없는 구조·기능을 발명하는
  것은 범위 밖이다.
- 현재 Stage와 승인 범위가 요구하지 않는 작업을 미리 수행하지 않는다.
- 요청되지 않은 유연성·설정·추상화를 추가하지 않는다. 단일 사용 코드에
  추상화를 만들지 않는다.
- 간단한 작업을 불필요한 다중 에이전트 구조로 확장하지 않는다.
- 추가 추론이 Gate 결과나 구현 선택을 실질적으로 바꾸지 않으면 중단한다.
- 개선 아이디어와 새 요구사항은 구현하지 않고 기록만 남긴다.

## 미확정 결정 다루기

- 미확정 항목(threshold 수치, persistence 기술, schema, Python 스택 등)은
  Constitution §25와 [Open Questions](docs/research/OPEN_QUESTIONS.md)에 있다.
  구현 편의로 임의 확정하지 않는다. 결정이 필요하면 ADR을 작성하거나 사용자에게
  묻는다.
- upstream 사실은 기록된 기준 commit
  (`docs/research/README.md`의 Baseline snapshot) 기준으로 인용하고, evidence
  level과 함께 `docs/research/`에 기록한다. 세션 기억을 upstream 사실로 승격하지
  않는다.

## 작업 종료 절차

1. 관련 테스트를 실행하고 실제 evidence를 확인한다. 실패를 숨기지 않는다.
2. [Progress](docs/progress/README.md)를 **계획이 아니라 검증된 현재 상태**로
   갱신하고, 완료 항목에 test/commit/artifact를 연결한다.
3. 문서와 구현이 달라졌으면 차이를 기록하거나 문서를 갱신한다.
4. 다음 한 개의 검증 가능한 목표를 지정한다.

## Git 규칙

- 커밋 메시지는 `type(scope): 한국어 설명` 형식. 본문도 한국어를 기본으로 한다.
- `Co-Authored-By:` 등 AI attribution 트레일러를 붙이지 않는다.
- 사용자 승인 없이 push, tag, release하지 않는다.
