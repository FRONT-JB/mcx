# Wonder/Reflect backend A/B — Hermes와 Claude

- 실행일: 2026-08-10
- upstream baseline: `~/.claude/plugins/marketplaces/ouroboros` @
  `9486c78575a0332e9b84d93ef5832985291d7943` (v0.50.8)
- Evidence level: **Observed — 실제 CLI 4회 + pinned source 대조**
- 실행물: Hermes Agent v0.17.0 / `OpenAI Codex`, `gpt-5.5`; Claude Code
  2.1.226 / 설정 `opus[1m]`, 실제 응답 `claude-opus-5`

## 결론

**Hermes를 mcx의 Reflect 기본 backend로 고정하지 않는다. Phase 10의 최초
Wonder/Reflect 구현은 기존 [ADR-0036](../adr/0036-claude-text-lane-contract.md)의
`ClaudeCompletion`을 재사용한다.**

이 결론은 Hermes 출력 품질이 낮아서가 아니다. 이번 한 fixture에서는 Hermes가
더 짧고 빨랐으며 Wonder/Reflect 계약도 모두 통과했다. 기각 사유는 배포 계약이다.
upstream `HermesCliLLMAdapter`는 `allowed_tools` 봉투를 하나라도 전달하면 실패하고,
봉투를 빼야만 실행된다. 실제 실행에서는 도구를 쓰지 않았지만 사용자 plugin
41개를 로드하고 MCP server 2개에 각각 세 번 연결을 시도했다. Stage별 최소
capability와 delegated worker의 Mission Control 재귀 금지를 **명령 플래그로
강제**하는 현재 Claude lane보다 약하다.

Hermes는 별도 설치 의존이기도 하다. 지금 기본으로 만들면 배포 필수물이
Claude+Codex에서 Claude+Codex+Hermes로 늘어난다. 품질 이점이 격리·관측 비용을
상쇄한다는 근거는 이 한 번의 실행에서 나오지 않았다.

---

## 1. 질문과 비교 설계

질문은 하나였다.

> 같은 Wonder/Reflect 계약을 현재의 실제 기본 모델로 실행했을 때 Hermes를
> Reflect 기본값으로 고정할 근거가 생기는가?

동일 모델 비교가 아니다. 현재 로컬 배포 후보를 그대로 비교했다. Hermes는
`OpenAI Codex / gpt-5.5`, Claude는 `claude-opus-5`였고 두 adapter 모두 engine
설정상 모델은 `default`였다. 따라서 결과는 모델 자체의 일반 우열이 아니라
**현재 backend 묶음(prompt 전송·격리·기본 모델·telemetry)의 운영 비교**다.

fixture는 기존 Python 서비스의 webhook dispatcher다.

- AC 1 PASS: 결정적 idempotency key와 replay 중복 방지
- AC 2 FAIL: 고정 1초 retry가 `Retry-After: 30`을 무시하고 50개 동시 실패가
  1초 창에 retry 150개를 몰아넣음
- AC 3 PASS: 영구 400은 retry하지 않고 evidence와 함께 dead-letter
- 제약: 기존 HTTP client·job queue만 사용, at-least-once 유지, logical
  delivery마다 retry 최대 3회

Wonder에는 같은 Seed·ontology·execution output·EvaluationSummary를 넣었다.
Reflect는 backend별 Wonder 출력을 이어 쓰지 않고 **미리 고정한 같은
WonderOutput**을 넣었다. 그렇지 않으면 Reflect 입력이 달라져 단계별 비교가
아니게 된다. 따라서 이 실험은 Wonder와 Reflect 각각의 A/B이며, 한 backend의
Wonder→Reflect 연속 응집력 평가는 아니다.

engine 경계의 직렬화된 message hash도 같았다.

| 단계 | 양쪽 공통 message SHA-256 | 문자 수 |
|---|---|---:|
| Wonder | `c883e4fb6a5170a854dc64acdabc129a560c329a1185f5daf314a237420e4145` | 5,426 |
| Reflect | `eca00b6dddf010f6e78a7c1e7ed1f3a7de3d0d25ee6049ddf0f092ae22eb07af` | 6,701 |

단, adapter 이후 전송 모양은 의도적으로 다르다. Hermes는 system/user를
`<system>...`과 `User:` 한 prompt로 평탄화한다. Claude는 system prompt를 별도
권위 채널로 보내고 user prompt만 stdin에 쓴다.

## 2. 호출 예산과 실제

사전 추정은 `2 backend × (Wonder 1 + Reflect 1) × 1순환 = 4회`였다.

실제도 **engine 호출 4회, primary inference turn 4회, retry 0회**였다.

- Hermes session `20260810_120140_79a4bb`, `20260810_120201_2f3bf4`:
  `api_call_count=1`씩
- Claude session `9650d632-e05d-4d2d-b22e-ebd12fbce484`,
  `aaecce05-1805-4f2e-b2be-1b41be97a8f2`: `num_turns=1`씩

Claude session에는 `ai-title` record도 하나씩 생겼다. 이것이 별도 billable
inference인지 같은 응답의 부가 산출물인지는 로컬 record만으로 확정할 수 없어
호출 수에 더하지 않았다.

## 3. 시간과 사용량

| backend | 단계 | adapter wall time | 입력 token | cache read/write | 출력 token | 결과 |
|---|---|---:|---:|---:|---:|---|
| Hermes | Wonder | 21.334s | 19,422 | 0 | 619 | parse 성공 |
| Hermes | Reflect | 28.536s | 8,949 | read 10,752 | 1,172 | parse 성공 |
| Claude | Wonder | 30.834s | 2 | write 5,211 (1h) | 2,070 | parse 성공 |
| Claude | Reflect | 44.045s | 2 | write 5,620 (1h) | 3,068 | parse 성공 |

합계 wall time은 Hermes **49.870s**, Claude **74.879s**였다. cache를 입력으로
포함한 총 token은 Hermes **40,914**(39,123 in + 1,791 out), Claude
**15,973**(10,835 in + 5,138 out)였다.

달러 비용은 두 경로 모두 현재 사용자의 subscription authentication을 쓰므로
증분 청구액과 token 기반 API 가격을 동일한 축으로 비교할 수 없다. Hermes DB는
두 session을 `subscription_included`, `estimated_cost_usd=0.0`으로 기록했다.
Claude envelope는 API 환산 `total_cost_usd`를 내지만 이는 구독 청구액이 아니다.
따라서 이 프로젝트의 기존 비용 기준(ADR-0035)대로 **호출 수가 1차 비용**, token은
운영 부하의 보조 evidence로 쓴다.

눈에 띄는 차이는 반대 방향 두 개다.

- Hermes는 출력이 Claude의 35% 수준이고 wall time도 67% 수준이었다.
- Hermes 입력은 Claude의 3.6배였다. engine prompt가 길어서가 아니라 startup이
  사용자 설정·rules·plugin·MCP를 함께 싣기 때문이다.

Claude Reflect의 보고 출력은 3,068 token으로 engine의 `max_tokens=3000`을
68 token 넘었다. upstream Claude CLI fallback이 `CompletionConfig.max_tokens`를
CLI flag로 전달하지 않는다는 source 사실이 실물에서도 드러났다.

## 4. Wonder 품질

둘 다 다음을 만족했다.

- 유효 JSON을 engine이 파싱했다.
- PASS인 AC 1·3을 다시 열지 않고 질문 전부를 실패한 AC 2에 grounding했다.
- `Retry-After`, retry timing, aggregate destination pressure, retry budget의
  모호함을 찾았다.
- `should_continue=true`와 관련 ontology tension을 냈다.

| | Hermes | Claude |
|---|---|---|
| 질문 / tension | 5 / 3 | 7 / 5 |
| raw JSON 규율 | 순수 JSON | markdown fence 안 JSON — extractor가 복구 |
| 강점 | 필요한 정의를 짧게 분리하고 AC 2에만 한정 | delivery의 terminal state와 attempt sequence의 충돌, shared destination 부재를 깊게 설명 |
| 약점 | retry 횟수 의미처럼 구현 전에 이미 좁힐 수 있었던 질문도 포함 | 중복 질문이 많고, “새 infra 금지이므로 pacing은 delivery 자체의 속성이어야 한다”는 과한 추론 포함 |

처음 fixture rubric은 aggregate budget을 새 AC가 없는 `gap`으로 예상했다. 그러나
양쪽 모두 기존 AC 2의 *"without overwhelming the destination"*가 이미 이 문제를
덮는다고 보고 `challenge`로 분류했다. **양쪽 판단이 더 보수적이고 타당하다.**
새 AC가 필요한지 여부는 Wonder가 아니라 Reflect가 결합된 AC를 쪼갤 필요성으로
판단할 수 있다. 실험 기대값 자체의 과추론을 결과에 맞춰 숨기지 않는다.

이번 한 번에서는 Hermes가 더 간결하게 같은 핵심을 찾았다. Claude는 더 깊지만
질문 수와 tension 수가 늘어난 만큼 결정에 새로 기여하지 않는 반복도 늘었다.

## 5. Reflect 품질

Reflect에는 양쪽 모두 다음의 고정 Wonder 계약을 넣었다.

- AC 2의 `Retry-After`·jitter 결함을 묻는 challenge 1개
- concurrent delivery의 shared rate/concurrency budget을 묻는 gap 1개
- terminal delivery만 모델링하고 timed attempt·shared pressure가 없다는
  ontology tension 1개

둘 다 정확히 다음 patch shape를 냈고 parser의 deterministic backstop도
통과했다.

```text
keep(AC 1) → revise(AC 2) → keep(AC 3) → add(shared pressure AC)
settled = [0, 2]
ontology mutation 있음
```

Hermes는 revised AC에 `Retry-After`, backoff+jitter, 동시 retry의 분산/throttle을
넣고, 별도 AC에 관측 가능한 per-destination retry pressure budget을 넣었다.
ontology에는 `attempt`, `retry_schedule`, `destination_pressure_budget`을 추가하고
`delivery`를 attempt sequence를 가진 개념으로 수정했다.

Claude도 같은 결정을 더 구체적인 timestamp·delay source·window ceiling으로
표현했다. 다만 ontology mutation에서 PASS인 AC 3의 `dead_letter`까지 attempt
history를 보존하도록 수정했다. 유용할 수는 있지만 이번 실패를 고치는 데 필수는
아니며 system prompt의 *"Do NOT change things that are working well"*보다 넓다.

따라서 이번 fixture의 계약 정확성은 둘 다 충분하다. Claude는 증거 가능성을 더
명시적으로 만들었고, Hermes는 같은 결정에 더 적은 출력과 변경으로 도달했다.
**한 번의 결과로 모델 품질 우열을 일반화하지는 않지만, Hermes 품질을 이유로
배제할 근거도 없다.**

## 6. backend 계약 차이와 배포 판단

| 축 | Hermes upstream adapter | Claude upstream adapter / 현재 mcx lane |
|---|---|---|
| 도구 봉투 | `allowed_tools is not None`이면 즉시 실패 | `allowed_tools=[]`를 native `--tools ""`로 강제 |
| MCP·지침 격리 | 없음 | `--strict-mcp-config --setting-sources ""` |
| 실제 관측 | plugin 41개 load, MCP 2개 연결 재시도, tool call 0 | tool catalog 비움, 설정 source 비움, tool call 0 |
| 출력 계약 | quiet text를 사후 JSON 추출 | system prompt 분리 + JSON 추출/재시도 |
| adapter telemetry | model=`default`, usage 전부 0, raw에는 session id 키만 있고 이번 버전에서는 값도 회수 실패 | token·cost·turn·permission denial envelope 보존 |
| 실제 모델 확인 | adapter 밖 Hermes DB/log 필요 | session record에서 `claude-opus-5` 확인 |
| 설치 | 새 필수 CLI 1개 증가 | 이미 ADR-0036의 필수 lane |

Hermes 최신 CLI 자체에는 `--safe-mode`, `--ignore-rules`, `--toolsets`가 있지만
pinned upstream adapter는 이들을 호출하지 않는다. `--toolsets ""`가 Claude의
빈 catalog와 같은 hard guarantee인지도 이번 source/실행으로 확인하지 않았다.
그 가능성을 근거 없이 adapter 구현으로 승격하지 않는다.

## 7. 처분

1. **기본 backend는 Claude 유지.** ADR-0036을 supersede하지 않는다.
2. **Phase 10 최초 구현에 Hermes adapter를 추가하지 않는다.** Wonder/Reflect는
   기존 vendor-neutral `CompletionEngine`과 `ClaudeCompletion`을 쓴다.
3. Hermes는 삭제 대상이 아니라 **optional 후보**다. 다시 열려면 최소한 다음
   세 조건을 같은 실물 작업에서 증명해야 한다.
   - 빈 tool catalog 또는 동등한 hard no-tool 강제
   - user rules/plugin/MCP를 싣지 않는 격리
   - 실제 model·호출 수·usage를 durable telemetry로 회수
4. 이 실험은 full sequential pipeline test가 아니다. 구현 후 대표 실사용
   Wonder→Reflect→후속 Blueprint 전체 경로를 별도로 dogfood해야 Phase 10을
   COMPLETE로 선언할 수 있다.

## 8. Verification

- 실물: backend별 Wonder·Reflect 각 1회, 총 4 engine call / 4 primary turn /
  retry 0
- pinned upstream 집중 테스트:
  `test_claude_code_adapter.py`, `test_hermes_cli_adapter.py`,
  `test_wonder_scope.py`, `test_wonder_grounding.py`, `test_reflect_delta.py` —
  **205 passed, 1 skipped**
- mcx 전체 회귀: **967 passed**
