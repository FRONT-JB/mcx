# Session Decision Record

이 문서는 프로젝트를 시작한 ChatGPT 대화에서 나온 내용을 **현재 결정**, **폐기된
후보**, **미확정 제안**으로 분리한다. 채팅 전체를 새 세션에 다시 넣지 않고도
결정의 출처와 경계를 이해하기 위한 기록이다.

## Session

- Title: `Ouroboros MCP 구현 방법`
- Conversation ID: `6a748b26-a4b8-83ee-bbe8-9fcf9588a03c`
- Imported into project: 2026-08-07

대화는 설계 배경이지만 최종 규범은
[Project Constitution](../00_MISSION_CONTROL.md)과 Accepted ADR이다.

---

## 1. Session-confirmed decisions

### Identity

- 프로젝트/브랜드: **Mission Control**
- CLI: **`mcx`**
- 구현 언어: Python
- 사용자-facing lifecycle: Brief → Blueprint → Execute → Verify → Recover
- 내부/upstream mapping: Interview → Seed → Run → Evaluate → Repair

### Roles and evidence

- control plane: Mission Control
- worker/executor: Flight Controller
- evidence: Telemetry
- Gate outcomes: `CLEAR`, `HOLD`
- terminal success: `MISSION COMPLETE`

### Philosophy

- Mission Control은 작업의 author/reviewer가 아니라 coordinator다.
- Mission Control이 Mission state와 next step을 소유한다.
- Flight Controller는 bounded work를 실행한다.
- Telemetry가 진행의 근거다.
- Workflow가 LLM보다 우선한다.
- agent의 완료 주장은 완료 증거가 아니다.
- Stage별 최소 도구/권한을 실제 환경으로 강제한다.
- over-reasoning, scope drift, 불필요한 다중 agent와 느린 workflow를 피한다.
- chat보다 durable state와 문서를 프로젝트 기억으로 사용한다.

### Project intent

- 가벼운 “비슷한 도구”보다 Ouroboros의 설계 의도를 깊게 이해하는 재구성이다.
- 원본 behavior를 먼저 이해·구현한 뒤 개선한다.
- 제품 용어는 Mission Control로 바꾸되 내부 개념은 원본과 직접 대응시킨다.
- 문서가 코드보다 먼저다.
- 각 Stage는 원본 조사 → 설명 → 최소 구현 → 테스트 → diff → 학습 기록 순서다.

### Runtime and MCP

- Workflow Core는 Runtime과 분리한다.
- Codex와 OpenCode가 초기 Runtime 방향이다.
- OpenCode는 local model 또는 제공 agent를 사용할 수 있다.
- Gemini는 사용하지 않는다.
- text-generation backend와 execution Runtime을 구분한다.
- MCP는 Core 엔진이 아니라 외부 control surface/adapter다.
- Core/CLI가 먼저이고 MCP는 그 위에 연결한다.
- delegated worker가 Mission Control을 재귀 호출하지 못하게 한다.

### Documentation

- `docs/00_MISSION_CONTROL.md`는 Constitution/North Star다.
- Architecture, Lifecycle, Runtime, MCP, 각 Stage Guide가 필요하다.
- ADR은 “왜 그렇게 결정했는가”를 보존한다.
- progress는 검증된 현재 상태를 기록한다.
- research는 upstream mapping과 diff를 보존한다.

---

## 2. Superseded names and ideas

다음은 탐색 중 제안되었지만 최종 결정이 아니다.

- IntentRelay
- Ophion
- The Coil
- `mctl`
- `mc`
- Clarify / Specify 같은 이전 command 세트
- GO / NO-GO
- NO-GO를 terminal failure처럼 사용하는 Gate

새 문서와 public API에서 현재 명칭처럼 사용하지 않는다.

---

## 3. Proposed but not confirmed in the session

다음은 유용한 제안이었지만 exact design은 확정되지 않았다.

- `Capability Envelope`, `Work Unit` 같은 class/domain 명칭
- Ambiguity threshold의 정확한 값
- Seed QA score와 grade
- retry count와 stagnation threshold
- SQLite/Pydantic/Typer/Rich 같은 기술 스택
- full event sourcing
- 병렬 실행
- 다중 모델 consensus
- reasoning budget 자동화
- Scope Guard의 구체 schema
- 전체 status enum
- RecoveryDirective의 exact schema와 retry budget
- 문서 디렉터리의 장기 최종 형태

이 항목은 Open Questions와 ADR에서 결정한다.

---

## 4. Resolved contradictions

### “Mission Control never asks questions”

초기 표현 중 “Mission Control은 질문하지 않는다”는 문장은 Brief와 충돌한다.
현재 해석은 다음과 같다.

> Mission Control은 Brief Workflow를 조정한다. 질문 생성이 필요하면 tool-less,
> bounded Flight Controller/LLM backend에 위임하고, 상태와 Gate는 Mission
> Control이 소유한다.

### Recover as fifth linear Stage

사용자 command 목록에는 Recover가 포함되지만, 성공 미션이 항상 Verify 뒤에
Recover를 통과하는 것은 아니다. Recover는 HOLD와 failure evidence에서 진입하는
canonical corrective Stage다. Recover `CLEAR`는 항상 Verify로 진행한다. 제품 결정
또는 명세 수정은 Recover work가 아니며 source `HOLD`에서 Brief/Blueprint로 직접
routing한다.

### Runtime selection and interview model

execution Runtime을 Codex로 선택했다고 interview 질문도 반드시 Codex가 만든다고
가정하지 않는다. text-generation backend와 execution Runtime은 분리된 책임이다.

---

## 5. Decision maintenance

새 대화에서 결정이 바뀌면 이 파일만 수정하지 않는다.

1. Constitutional change인지 판단한다.
2. 필요한 ADR을 작성한다.
3. Constitution과 관련 Stage Guide를 갱신한다.
4. 이 문서에는 supersession 관계를 기록한다.
