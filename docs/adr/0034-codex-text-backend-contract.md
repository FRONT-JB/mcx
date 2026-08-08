# ADR 0034 — Codex text backend 계약과 첫 위임 port

- Status: Accepted
- Date: 2026-08-08
- Constitutional basis: [ADR-0004](./0004-stage-scoped-minimum-capability.md) (Stage별 최소 capability), [ADR-0033](./0033-first-runtime-adapter-contract.md)
- Upstream evidence: [RUNTIME_UPSTREAM_FINDINGS.md](../research/RUNTIME_UPSTREAM_FINDINGS.md) §7, [VERIFY_UPSTREAM_FINDINGS.md](../research/VERIFY_UPSTREAM_FINDINGS.md) §6

## Context

위임 port들(질문 생성기, clarity 평가자, QA 채점자, semantic 평가자 등)은
전부 결정적 fake다. ADR-0033 §2가 실행 adapter 다음 순서로 text backend를
지정했다. 공통 완성 방식·재시도·구조화 출력 처리는 모든 port가 공유하는
축이므로 먼저 고정한다.

upstream 사실: 완성도 `codex exec` 단발이고, 구조화 출력은
`--output-schema`(strict shape — 전 필드 required, additionalProperties
false) + `--output-last-message` 파일 읽기다. 재시도는 transient만 최대
3회 지수 backoff이며 timeout은 재시도하지 않는다
([RUNTIME_UPSTREAM_FINDINGS §7](../research/RUNTIME_UPSTREAM_FINDINGS.md)).

## Decision

### 1. 모든 위임 port는 하나의 완성 엔진을 공유한다

`CodexCompletion` — 프롬프트(stdin)와 strict JSON schema를 받아 구조화
JSON을 돌려주는 엔진 하나. 각 port adapter는 프롬프트 렌더링과 출력의
도메인 모델 변환만 소유한다. 실행 기법(subprocess, 침묵 timeout, process
group 정리)은 실행 adapter와 동일하다.

### 2. text 완성은 읽기 전용 sandbox로 돈다

위임 role은 텍스트를 만들 뿐 작업물을 바꾸지 않는다 — 완성 명령은
`--sandbox read-only`로 실행한다 (upstream 권한 매핑의 default 모드 대응,
ADR-0004의 Stage별 최소 capability). 실행 adapter의 `--full-auto`와
비대칭인 것이 옳다.

### 3. 재시도는 완성에만 있다 — upstream 계약 채택

transient 패턴(공용 코어의 부분집합)만, 최대 3회, `2**attempt` backoff,
**timeout 비재시도**. 근거는 ADR-0033 §4가 예고한 비대칭 — 완성은 부작용이
없어 전체 재시도가 안전하고, 실행은 그것을 입증할 수 없다.

### 4. 구조화 출력 실패는 성공으로 해석하지 않는다

`--output-last-message` 파일의 JSON 파싱 실패, schema 위반, 도메인
검증(0..1 범위 등) 실패는 전부 **예외로 드러낸다** — 재시도하지 않는다
(transient가 아니다). Verify Guide §12 "Parser | evaluator 구조화 출력
손상 | 성공으로 해석하지 않음"의 이행이다.

### 5. 첫 port는 SemanticEvaluator다

근거 — upstream 대응물이 가장 완전하다(시스템 프롬프트 원문 + JSON schema +
임계). 계약:

- **프롬프트**: upstream `semantic-evaluator.md`와 정렬한 영어 원문 —
  "You are a rigorous software evaluation assistant" 축, 필드 의미 정의,
  선언 계약 블록("The AC passes ONLY if the artifact demonstrates the
  declared contract was met. Cite the evidence line."). 입력은
  `SemanticEvaluationRequest`의 구조화 필드(방향·AC 계약·mechanical 증거)
  뿐이다 — worker 주장은 입력에 없다 (ADR-0030 §3).

  > **2026-08-08 스모크 정정**: 요청에 **`workspace`가 필수**로 추가되었고
  > 완성 엔진이 `-C`로 전달한다 — 이것 없이 평가자가 엉뚱한 디렉토리를
  > 검사함이 실물에서 관측되었다
  > ([RUNTIME_UPSTREAM_FINDINGS §8](../research/RUNTIME_UPSTREAM_FINDINGS.md)).
  > 읽기 전용 sandbox(§2)는 그대로다 — 평가자는 작업물을 관찰만 한다.
- **출력 schema**: 우리 verdict 필드와 1:1 — `satisfied`(upstream
  `ac_compliance` 대응), `score`, `uncertainty`, `reward_hacking_risk`,
  `reasoning`, `evidence`, `questions_used`. `goal_alignment`·`drift_score`는
  소비자(consensus trigger)가 보류이므로 schema에 두지 않는다 (ADR-0030 §1
  의 같은 논리 — 소비자 없는 필드는 장식).
- **`ac_key`는 adapter가 바인딩한다** — 평가자가 반환하지 않는다. 잘못
  귀속될 자유도 자체를 없앤다 (VerifyService의 귀속 검증은 그대로 유지 —
  다른 evaluator 구현에 대한 방어다).

나머지 port들(질문 생성기, clarity 평가자, Blueprint 생성기·채점자,
closure 3-lane)은 같은 엔진 위에 port별 ADR 없이 구현하되, **프롬프트가 곧
계약인 지점은 각 구현에서 upstream 원문과 대조**한다 (기존 규칙 유지).

## Consequences

### Positive

- semantic 판정의 **품질**이 처음으로 검증 가능한 대상이 된다 — 지금까지는
  판정 주변 규칙만 검증했다.
- 완성 엔진 하나로 나머지 위임 port가 프롬프트+변환만으로 얇게 구현된다.
- 읽기 전용 sandbox로 위임 role의 권한이 실행 role보다 좁다는 원칙이
  실제 플래그가 된다.

### Cost

- Codex CLI의 strict schema 요구 때문에 open-map 스키마를 쓸 수 없다 —
  우리 verdict 필드는 전부 고정이라 현재는 비용이 없다.
- 실물 CLI 스모크 전까지 플래그 호환성은 conformance test의 가정이다
  (실행 adapter와 같은 등록 상태).

## Rejected alternatives

- **port마다 자체 subprocess 로직**: 침묵 timeout·정리·재시도가 N벌 복제된다.
- **schema 없이 자유 텍스트 + 자체 파싱**: upstream이 `--output-schema`로
  푼 문제를 되풀이한다. 파싱 실패의 낙관적 해석 위험도 커진다.
- **파싱 실패 재시도**: 손상 출력은 transient가 아니다 — 같은 프롬프트의
  재시도는 같은 손상을 반복할 가능성이 높고, 그 판단은 호출자(사람)의 것이다.
- **goal_alignment·drift 필드 포함**: 소비자가 없는 필드는 장식이다
  (ADR-0024·0030과 같은 기각 논리).

## Verification

- 완성 명령이 `--sandbox read-only`를 포함하고 쓰기 권한 플래그가 없다.
- transient 실패가 최대 3회 재시도되고, timeout·파싱 실패는 재시도되지
  않는다.
- schema 파일이 strict(전 필드 required, additionalProperties false)로
  전달된다.
- verdict의 `ac_key`가 항상 요청된 criterion에서 온다.
- 손상된 JSON 출력이 satisfied verdict로 변환되는 경로가 없다.
