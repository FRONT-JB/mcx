# Progress 0006 — Phase 6: `mcx` CLI 종료 검토

- 일시: 2026-08-09
- 범위: 비대화형 단발 CLI 표면 24명령, mission record(canonical Stage),
  실 AI 도그푸딩 1회, 명령 원장 + `status` 사람용 렌더, Stage→Runtime 라우팅
  테이블과 `config.toml`
- Evidence: ADR-0037·0038(개정 2)·0039, commits 18b014f·6135452·b83283d,
  621 tests, [DOGFOODING_0003](../research/DOGFOODING_0003.md)
  (Verified by execution), [CLI_UPSTREAM_FINDINGS](../research/CLI_UPSTREAM_FINDINGS.md)
- 상태: **Phase 6 COMPLETE (2026-08-09).** 검토가 잡은 4건은 §2에서 전부
  처분했다.

> **이 record 자체가 검토의 첫 발견이다.** Phase 6은 종료 검토 시점까지
> progress record가 없었다 — 절차는 *"답을 그 phase의 progress record에
> 남긴다"*고 요구하는데 남길 자리가 없었다. Phase 1~5는 전부 record를
> 가지고 있었으므로 이것은 Phase 6에 국한된 누락이다.

## 1. 일곱 질문에 대한 답

### 1.1 구조 검사 — 각 방어가 막는 결함

| 방어 | 막는 결함 |
|---|---|
| exit code 0/1/2 분리 | 판정 부정(HOLD)을 오류로 읽어 스크립트가 재시도를 건다 |
| mission record의 합법 전이 그래프 | 기록이 실제로 지나오지 않은 Stage를 지나온 것처럼 보고한다 |
| Gate 재계산이 저장 Stage를 이김 | stale 저장이 잘못된 진입을 허가한다 |
| 어긋남의 명시 표시 | 두 진실이 다른데 사용자가 그 사실을 모른다 |
| append-only 원장, 짝 없는 `start` | 프로세스가 죽은 명령이 원장에서 조용히 사라진다 |
| `status`는 원장을 늘리지 않음 | 원장이 관측 행위를 작업으로 보고한다 |
| 실측 호출 계수 (명령 수 근사 금지) | 명령 하나가 호출 N번인 경우 사용량이 실제보다 작게 보인다 |
| 라우팅 fail-fast | 운용자의 오타가 조용한 재라우팅이 되어, 사용자가 지정하지 않은 AI가 미션을 수행한다 |
| Stage가 안 쓰는 lane 조회 = 오류 | 효과 없는 설정 줄을 라우팅했다고 오해한다 |
| 계층 경계 import 검사 | mission record 소유가 합성 계층 밖으로 새어 진실이 둘이 된다 |

**산문으로만 막던 계약 1건을 발견해 승격했다** — ADR-0037 Verification의
*"Stage service가 mission 문서 모듈에 의존하지 않는다 (import 방향 검사)"*는
사실로는 지켜지고 있었으나 검사가 없었다. `tests/unit/test_layer_boundaries.py`
신설(3 tests).

강제되지 않는 것으로 남긴 항목: 토큰·비용 계측(ADR-0038 §7 보류 — port가
usage envelope를 버려 반환형 변경이 선행), 원장 보존·회전 정책(같은 곳,
미조사), adapter 내부 transient 재시도의 계수(§6.1 b 한계 명시).

### 1.2 부품/단계 구분

end-to-end로 돈다. [DOGFOODING_0003](../research/DOGFOODING_0003.md)이 실
AI로 Brief→Blueprint→Execute→Verify→Recover 전 구간과 mission record 전이
그래프를 통과시켰고, 계약 결함 2건(무도구 max-turns, 원인 사슬 삼킴)을 잡아
수정했다. status 박스와 라우팅 테이블은 도그푸딩 이후 산출물이라 실 AI
관측은 없고 **실물 스모크로 확인했다** — status 세 화면 렌더, 라우팅의 알 수
없는 Stage 키·미등록 backend가 exit 1로 거부되고 파일 부재만 기본 조립으로
가는 것.

미조립 부품을 완료로 기록한 것은 없다. 라우팅의 `opencode` backend는 실물
adapter가 이연이라 **레지스트리에 없고, 그래서 설정에 쓰면 거부된다** —
"열려 있다"와 "동작한다"를 구분해 기록했다.

### 1.3 미등록 이탈

ADR-0038과 ADR-0039가 자기 divergence를 인라인으로 등록하고 있다 — CLI는
Stage가 아니므로 Stage별 divergence ADR(0011/0022/0025)의 대상이 아니다.
등록된 것: 대화형 지점 부재(upstream skill 계층은 대화 안에 있어 대조 불가),
ambiguity 미달 강제 생성 미도입, lane별 backend 쌍(upstream은 stage당 하나),
설정 형식 TOML(upstream YAML).

**추가로 발견된 미등록 이탈은 없다.** 다만 §1.7의 시한 도과 1건이 이탈이
아니라 **미이행 약속**으로 잡혔다.

### 1.4 표시 없는 보류

ADR-0038 §7이 보류를 그 자리에 표시하고 있고, 이번 검토에서 두 건의 표기를
갱신했다 — `status` 사람용 렌더는 개정 2로 도입 완료 표시, vendor 선택 표면은
ADR-0039 §5에 의한 **부분 개정**(설정 파일은 도입, CLI 플래그는 여전히 없음)
표시.

**표시가 구현과 어긋난 것 1건 발견.** ADR-0037 Verification의 *"불법 전이가
예외로 거부된다"*는 CLI 명령이 거부된다는 뜻으로 읽히지만, 실제로는 도메인이
예외를 올리고 **CLI는 잡아서 경고만 남기고 명령을 성공시킨다**. 이것이 같은
ADR의 핵심 결정("저장은 표시용, enforcement 아님")의 직접 귀결이므로 구현이
아니라 문장을 정정했다.

### 1.5 계약 문장 원문 여부

Phase 6은 표면 계층이라 vendor에게 보내는 계약 문장을 새로 만들지 않았다 —
프롬프트·SUCCESS CONTRACT 블록은 Phase 5 산출물 그대로다. 새로 생긴 문자열은
운용자용 오류 메시지와 `status` 렌더이며, 이 둘은 계약이 아니라 표시다.
번역·의역으로 계약을 깎은 지점 없음.

`status`의 차단 사유는 **원문 그대로 인용한다** — `GateDecision.blocking_reasons`와
`blocking_questions`를 재작성하지 않는다 (upstream `status.py`의
`Pending question:` 블록과 같은 규율).

### 1.6 관측 대조

도그푸딩 0003의 관측과 모순되는 규칙은 남아 있지 않다. 0003이 제기한
가시성 문제("9-AC semantic 판정이 한 덩어리로 보인다")는 명령 원장이 덮었고,
그 처분으로 OPEN_QUESTIONS §5(verdict 일괄 저장)를 **유지**로 닫았다 —
증분 저장은 부분 `SemanticAssessment`를 만들어 Gate가 미완성 판정 묶음을 읽는
경로를 연다.

콜 실측(60)이 추정(30~50)을 초과한 건은 closure 감사 7라운드×3lane으로
원인이 확인됐고 upstream 파리티 동작이다.

### 1.7 시한 도과 점검

Phase 6을 시한으로 지정한 항목 전수:

| 항목 | 처분 |
|---|---|
| [ADR-0003](../adr/0003-runtime-abstraction.md) — Execute backend 교체 구조 | **이행** (b83283d, ADR-0039) |
| [ADR-0037](../adr/0037-mission-record-and-canonical-stage.md) Verification 3항목 | **이행** — 1항목은 문장 정정, 1항목은 검사 신설 (§1.1·§1.4) |
| [ADR-0037](../adr/0037-mission-record-and-canonical-stage.md) §5 — 필드명·enum·state version | **부분 이행.** 필드명·enum 확정됐고, `sequence`가 Lifecycle §3.1의 "state version" 자리임을 이번에 명문화했다 |
| [ADR-0037](../adr/0037-mission-record-and-canonical-stage.md) §5 — upstream enum 국면 대조 | **무처분 도과 → 재지정.** `RALPH_HANDOFF`·`UNSTUCK_LATERAL` 대응 대조 미수행. 새 시한 **Phase 10** ([Open Questions §10](../research/OPEN_QUESTIONS.md)) — 그 국면이 진화 루프의 것이라 같은 소스를 읽는다 |
| [ADR-0017](../adr/0017-blueprint-schema-baseline.md) `exit_conditions` | **이미 처분됨** (2026-08-09) — 사용자 acceptance는 Phase 9, "Phase 6·7"의 6은 소진 |
| [ADR-0019](../adr/0019-blueprint-qa-loop.md) QA revision 제시 표면 | **이미 처분됨** — Phase 7 MCP (Phase 6은 비대화형이라 제시 표면 없음) |
| [Open Questions §7](../research/OPEN_QUESTIONS.md) OpenCode capability 표현 | **이연 유지** — 구조는 열렸고 실물 adapter가 조건 |
| [CLI findings §8](../research/CLI_UPSTREAM_FINDINGS.md) 대화형 지점 | **처분됨** — ADR-0038 §2가 비대화형 단발로 확정 |

진행 중인 잔여 하나는 시한이 아예 없다: `exit_conditions`의 project 검사
부분이 "repo 명령 층(ADR-0028 §2 보류) — **로드맵 미배치**"다. 시한 없는
항목은 도과를 탐지할 수 없으므로 여기 명시해 둔다.

## 2. 검토가 잡은 것

1. **Phase 6 progress record 부재** → 이 문서 신설.
2. **산문으로만 막던 import 방향 계약** → `tests/unit/test_layer_boundaries.py`
   (3 tests). Stage service→mission record, domain→cli, domain→adapters.
3. **ADR-0037 Verification 문장이 구현과 불일치** → 도메인 예외와 CLI 경고의
   경계를 명시하도록 정정.
4. **ADR-0037 §5의 upstream enum 대조 무처분 도과** → Phase 10으로 재지정하고
   Open Questions §10에 등록.

## 3. 다음 Phase 진입 조건

Phase 7 (MCP control surface)의 진입 조건은 **secret redaction Security ADR**
이다 (Open Questions §9). MCP는 host가 Core를 호출하는 inbound 표면이므로,
Telemetry·원장·`status` 응답이 host 대화로 나가기 전에 무엇을 가리는지가
표면 설계보다 먼저다.
