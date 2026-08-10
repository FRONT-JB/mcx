# Progress 0010 — Phase 10: Reflect/Evolve 종료 검토

- 일시: 2026-08-10
- 범위: pinned upstream Gen 2+ 연결 조사, Hermes/Claude backend A/B,
  successor Blueprint domain·source projection·Wonder/Reflect adapter·CLI/MCP,
  대표 brownfield Gen 2 도그푸딩
- Evidence: [ADR-0051](../adr/0051-evolve-successor-blueprint-contract.md),
  [EVOLVE_UPSTREAM_FINDINGS](../research/EVOLVE_UPSTREAM_FINDINGS.md),
  [EVOLVE_BACKEND_AB](../research/EVOLVE_BACKEND_AB.md),
  [DOGFOODING_0006](../research/DOGFOODING_0006.md), **1030 tests passed**
- 결함 수정 commit: `1aa7384`
- 상태: **Phase 10 COMPLETE (2026-08-10).** 다음 검증 가능한 목표는 Phase 11
  병렬 실행 도입 Gate의 upstream 재대조다.

## 1. 결과

Verify `HOLD`인 같은 Mission에서 current approved Blueprint·Execute attempts·
mechanical/semantic evidence를 exact source로 재구성하고, Wonder→Reflect가 후속
generation의 pending Blueprint를 만드는 경로가 완성됐다. 새 Stage·새 Mission은
없고, QA와 exact user approval 없이는 Execute가 열리지 않는다.

대표 실사용에서는 다음을 실제 AI로 완주했다.

```text
Gen 1 Verify HOLD
→ Evolve generation 2 / revision 2
→ QA 0.76
→ user-adopted revision 3 / QA 0.87
→ ontology까지 보완한 revision 4 / QA 1.00
→ exact user approval
→ Codex Execute 3회
→ mechanical 3/3 + semantic 3/3
→ checkpoint 431cdb2
→ MISSION COMPLETE
```

Evolve 사전 call 추정은 정상 2, 최악 6이었고 실제는 Claude 2회·retry 0이었다.
전체 Mission 원장은 Claude 6, Codex text 5, Codex Execute 3 calls를 기록했다.

## 2. 일곱 질문에 대한 답

### 2.1 구조 검사

| 방어 | 막는 구체 실패 | 강제 지점 |
|---|---|---|
| exact source projection | 오래된/일부 Execute·Verify evidence로 다음 명세를 만든다 | `EvolveService`가 current revision, Execute Gate, attempt 순서, AC별 mechanical+semantic, Verify HOLD를 호출 전에 재계산 |
| content-key patch | 위치가 바뀐 AC에 다른 mechanical contract가 붙는다 | adapter가 Wonder/Reflect index를 즉시 parent content key로 변환 |
| protected keep | 통과하고 challenge되지 않은 AC를 모델이 다시 연다 | adapter/application backstop이 exact keep 강제 |
| ordered full patch | delete·reorder·unknown parent가 lineage를 바꾼다 | 모든 parent를 순서대로 1회 keep/revise, add는 tail만 허용 |
| immutable successor | parent approval·evidence가 수정된 명세에 재사용된다 | 새 revision append + stale approval |
| user adoption Gate | Reflect/QA/host가 자기 제안을 승인한다 | QA + exact current revision approval + Blueprint Gate |
| partial checkpoint | crash 뒤 완료한 Wonder를 다시 호출하거나 다른 source로 Reflect한다 | `EvolutionRecord.phase`와 Wonder/Reflect output을 같은 state 문서에 저장 |
| single-flight | 같은 parent에서 successor 두 개가 생긴다 | mission-scoped lock + completed parent 검사 |

모델 prompt만으로 남긴 규칙은 없다. Goal·Constraint proposal의 의미 판정은 모델이
하지만 parent verbatim 비교와 scope finding 처리는 application이 결정적으로
강제한다. Wonder 질문의 품질 자체는 위임 판단이며 QA·사용자 Gate가 그 결과를
승인 전 상태로 둔다.

### 2.2 부품/단계 구분

단위·통합 fake만 돈 상태가 아니다. DOGFOODING_0006이 real Claude/Codex와 실제
git worktree에서 Verify HOLD→Evolve→QA→approval→Execute→Verify→MISSION COMPLETE를
완주했다. CLI/MCP는 같은 parser/dispatch/application 경계를 쓰고 MCP 실호출
통합 테스트도 있다. Phase 10 부품 중 미조립 상태로 완료 표시한 것은 없다.

### 2.3 미등록 이탈

핵심 이탈은 ADR-0051에 등록돼 있다.

- upstream은 Gen 2+ Reflect 뒤 자동 Execute; mcx는 QA+user approval에서 정지
- upstream event lineage 대신 mission별 atomic Blueprint state 문서
- Goal·Constraints 자동 refinement 대신 parent verbatim + Brief 사용자 결정
- positional patch 대신 durable content key
- 임의 generation rewind/tag 미도입

도그푸딩에서 새 이탈은 발견되지 않았다. Claude 한도 뒤 Codex routing은 이미
ADR-0039의 Stage→backend 설정 경계 안이다. manual complete ontology replacement는
ADR-0051 §6에 보강했으며 upstream interactive Seed Restate와 Gen 2 autonomous
차이를 함께 표시했다.

### 2.4 표시 없는 보류

새로 드러난 보류는 없다. manual ontology 표면 부재와 status lineage 혼합은
보류로 남기지 않고 같은 Phase에서 수정했다. Hermes는 optional 후보로 명시적으로
제외했고 재개 조건 세 가지(no-tool, rules/plugin/MCP 격리, model/usage telemetry)를
EVOLVE_BACKEND_AB §7에 남겼다.

### 2.5 계약 문장 원문 여부

Wonder/Reflect 역할, 한 generation 연결, replay 계약은 pinned source 원문과 함수·
focused tests를 함께 대조했다. 특히 `generate_from_reflect` docstring의
"explicit keep만 mechanical contract 보존"은 실행 코드와 충돌해 그대로 믿지
않았고, focused tests로 `revise`도 보존함을 확인했다. 번역 문장을 새 계약으로
승격하지 않았다.

### 2.6 관측 대조

실사용이 설계를 지지한 것:

- Evolve 1회가 Wonder+Reflect 정확히 2 calls
- protected AC exact keep
- 실패 AC revise + gap add + ontology mutation
- successor에서 approval stale, Blueprint 정지
- current revision만 Execute·Verify lineage로 소비
- Verify만 MISSION COMPLETE 선언

관측과 모순된 구현 두 건은 즉시 정정했다.

1. QA가 ontology를 고치라고 해도 manual revision이 표현하지 못함
   → optional complete ontology replacement 추가.
2. status가 Gen 1·2 attempts를 합쳐 AC 5개/검증 전으로 표시
   → current revision 집계 + current Verify Gate 표시.

### 2.7 시한 도과 점검

Phase 10을 시한으로 쓴 항목을 전수 검색했다.

| 항목 | 처분 |
|---|---|
| upstream Stage/GenerationPhase/AutoPhase 대조 (ADR-0037) | 완료. 서로 다른 축이며 새 Stage 근거가 아님 (EVOLVE findings §11) |
| generation 지점 이름/tag (ADR-0047) | 완료. 임의 generation rewind 미도입, Blueprint generation+revision과 checkpoint commit으로 충분 |
| stall을 normalized activity 기준으로 변경 (ADR-0049) | 완료. item.started만으로 material progress를 대체할 근거가 없어 silence 기준 유지 |
| ontology 유예 (ADR-0017) | 완료. 소비자가 생겨 ADR-0051 최소 schema로 supersede |
| Hermes 기본 고정 여부 (ADR-0036/Open Questions §10) | 완료. A/B 뒤 Claude 유지, Hermes 최초 범위 제외 |
| Gen 2 representative dogfood | 완료. DOGFOODING_0006 MISSION COMPLETE |
| rollback이 지운 것의 표시 (ADR-0047·0048) | 이번 Mission은 Recover가 발동하지 않아 미관측. **Phase 11 종료 전 targeted dirty-rollback fixture**로 재지정; 자연 발동이 없어도 반드시 실행하고 닫는다 |
| requirement 후보 굵기·파생/수동 중복 (ADR-0050) | Phase 10 fixture가 controlled Brief에서 시작해 미관측. **Phase 11 종료 전 실제 Brief candidate trace audit**로 재지정; 자연 관측이 없어도 fixture로 닫는다 |

마지막 세 항목은 무기한 "실사용 시"가 아니라 최종 구현 Phase 11 종료 전 강제
fixture라는 새 시한과 종료 조건을 붙였다. 무처분 통과는 0건이다.

## 3. 종료 검토가 잡은 추가 결함

`mcx status` Execute row가 Mission 전체 attempts를 합산하고 검증 상태를 고정
문구로 표시했다. revision 4 AC 3개가 `AC 5개`, Verify complete가 `검증 전`으로
나왔다. ADR-0038 §6.1을 current lineage 기준으로 보강하고 다음을 테스트했다.

- current revision attempts만 집계
- stale Verify evidence 재사용 금지
- same revision·AC 반복만 Recover correction으로 집계
- 실제 DOGFOODING_0006 state에서 `AC 3개 · 시도 3회 — 검증 완료`

## 4. 다음 Phase 진입 조건

Phase 11 설계 시작을 막는 미완료 구현은 없다. 다음 한 개의 검증 가능한 목표는
**병렬 실행 도입 Gate**다: pinned upstream의 병렬 work dispatch·실패 격리·
checkpoint ordering을 다시 대조해, 병렬화가 현재 AC content-key·worktree·
evidence lineage를 깨지 않는 최소 계약을 결정한다.
