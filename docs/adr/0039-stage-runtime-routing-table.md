# ADR 0039 — Stage→Runtime 라우팅 테이블과 설정 표면

- Status: Accepted
- Date: 2026-08-09
- Constitutional basis: [ADR-0003](./0003-runtime-abstraction.md) (Runtime 추상화),
  [ADR-0023](./0023-execute-entry-and-provenance.md) 미이행 약속 해소
- Upstream evidence: [RUN_UPSTREAM_FINDINGS §1·§11.2](../research/RUN_UPSTREAM_FINDINGS.md),
  [RUNTIME_UPSTREAM_FINDINGS §12](../research/RUNTIME_UPSTREAM_FINDINGS.md) (§7 보강)

## Context

[ADR-0023](./0023-execute-entry-and-provenance.md)의 Rejected alternatives는
*"Stage→Runtime 바인딩 표현은 Phase 5에서 upstream의 닫힌 enum + 3단 해석
규칙과 대조해 정한다"*고 약속했다. **Phase 5는 그 대조 없이 지나갔다** —
2026-08-09 로드맵 대조에서 발견된 미이행 약속이다.

현재 구현은 `cli/composition.py`의 `default_adapters()` 하드코딩이다: 텍스트
lane은 `ClaudeCompletion`, 실행은 `CodexExecutionRuntime`
([ADR-0036](./0036-claude-text-lane-contract.md) 사용자 확정 구조). 즉
**라우팅은 이미 실재하는데 표현이 코드 상수**다. 이는 되돌리기 비싼 축(계층
구성과 도메인 축)이므로 실수요를 기다리지 않고 지금 확정한다.

upstream 사실 (Verified — RUN findings §1·§11.2):

- Stage는 **닫힌 enum** 4개(interview/execute/evaluate/reflect)이고 멤버 추가는
  명시적 정당화를 요구한다. per-handler 항목이 테이블로 번지는 것을 의도적으로
  막는다 (`core/orchestrator_stage.py:14-18·44-56`).
- 해석은 **3단**: `stages.get(stage)` → `default` → 현재 runtime_backend
  (`:23-31`).
- 검증은 **fail-fast**다. 알 수 없는 stage key는 로드 시 거부되고
  (`config/models.py:525-538`), 설정 파일이 존재하는데 로드에 실패하면 기본값으로
  조용히 넘어가지 않고 예외를 올린다 — *"operator의 라우팅 실수가 조용히
  fallback runtime으로 재라우팅되면 안 된다"* (`auto/runtime_routing.py:55-66`).
  **파일 부재만이 정당한 "프로필 없음"이다.**
- 테이블은 실행뿐 아니라 **LLM 완성도 라우팅**하며, per-stage 라우팅이
  authoritative다 (`config/loader.py:1685-1707`). `--runtime` override는
  *"one explicit runtime drives both authoring and execution"*.

## Decision

### 1. 라우팅 키는 Stage다 — 닫힌 enum

기존 `domain/stage.py`의 Stage enum(BRIEF·BLUEPRINT·EXECUTE·VERIFY·RECOVER)이
그대로 키다. 멤버는 Lifecycle이 소유하며 라우팅 편의로 늘리지 않는다 —
upstream이 per-handler 항목의 테이블 침범을 막는 것과 같은 이유다.

Stage 개수 차이(우리 5, upstream 4)는 [ADR-0006](./0006-dual-terminology.md)의
용어 축에서 이미 확정된 구조이며 본 ADR이 새로 만드는 차이가 아니다.

### 2. 값은 lane별 backend 쌍이다 — 등록된 divergence

upstream은 **stage 하나에 backend 하나**이고 그 backend가 authoring과 execution을
모두 맡는다. Mission Control은 한 Stage 안에서 텍스트 lane과 실행 lane에 다른
vendor를 쓴다 (Claude 텍스트 + Codex 실행 — ADR-0036 사용자 확정 구조).

```text
routing[Stage] = { text: <backend>, execution: <backend> }
```

**이 축 차이를 divergence로 등록한다.** 채택 이유는 품질이다 — 텍스트 lane의
구조화 출력(`--json-schema` 1급 소비)과 실행 lane의 sandbox 권한 모델이 서로
다른 vendor에서 각각 낫다는 것이 도그푸딩 0002·0003의 관측이다. 비용은 upstream의
"stage = 하나의 하네스" 단순성을 잃는 것이고, 대조 기준은 upstream이 lane 분할을
도입한다면 그 표현이다.

Stage가 한쪽 lane만 쓰면 나머지 항목은 비워 둔다 (Execute는 실행만, Brief는
텍스트만). 비어 있는 lane을 조회하는 것은 프로그래밍 오류이며 조용히 기본값을
주지 않는다.

### 3. 해석은 3단이다 — upstream 정렬

```text
stages[stage][lane] → default[lane] → 조립 기본값(default_adapters)
```

### 4. 검증은 fail-fast다 — 조용한 fallback 금지

- 알 수 없는 Stage key와 알 수 없는 backend 이름은 **로드 시** 거부한다.
- 설정 파일이 **존재하는데** 파싱·검증에 실패하면 예외를 올린다. 기본 조립으로
  넘어가지 않는다.
- 설정 파일 **부재**만이 정당한 "프로필 없음"이며 이때 기본 조립을 쓴다.

이유는 upstream 주석 그대로다: 운용자의 라우팅 실수가 조용히 다른 vendor로
재라우팅되면, 사용자는 자기가 지정하지 않은 AI가 미션을 수행한 것을 모른다.

### 5. 설정 표면은 `<state-dir>/config.toml`이다 — ADR-0038 개정

[ADR-0038](./0038-mcx-cli-surface-contract.md)의 *"vendor 선택 플래그·설정
파일은 도입하지 않는다"*를 **본 ADR이 개정한다** (사용자 결정 2026-08-09 —
upstream 동등). CLI 플래그는 여전히 도입하지 않는다; 라우팅은 설정 파일로만
들어온다.

형식은 TOML이다 — upstream은 YAML(`config.yaml`)이지만 stdlib `tomllib`으로
의존성 없이 읽을 수 있다 ([ADR-0012](./0012-python-toolchain-and-layout.md)
의존성 최소 원칙). **형식 차이를 divergence로 등록한다** — 되돌리기 싼 축이며,
설정 항목의 의미는 upstream과 같다.

> **2026-08-09 개정 3 — `[backends.<name>]` 축과 쓰기**
> ([ADR-0042](./0042-skill-and-core-ownership-boundary.md) §6).
>
> 이 문단의 원문은 *"우리는 쓰기가 필요 없다"* 였다. 더 이상 사실이 아니다.
>
> 라우팅 표가 **어느 backend를 부를지**를 정하는 것과 별개로, **그 backend를
> 어떻게 부를지**(모델·reasoning effort)가 필요해졌다 — 실행 lane이 재귀 경계
> 때문에 사용자 codex 설정을 상속하지 않기 때문이다. 표 하나를 추가한다:
>
> ```toml
> [backends.codex_cli]
> model = "gpt-5.6-sol"
> reasoning_effort = "xhigh"
> ```
>
> 축을 **stage별이 아니라 backend별**로 둔다. upstream은 per-stage model
> selects를 갖지만(`config.yaml`), 우리는 지금 그것을 요구하는 사용 사례가
> 없다 — 필요해지면 stage 표에 얹는다(되돌리기 싼 축).
>
> **쓰기는 한 곳뿐이다**: `[backends.codex_cli]`가 없을 때 사용자 codex 설정에서
> 읽은 값을 **덧붙인다**(재작성이 아니라 append — 사용자가 쓴 주석과 배치를
> 보존한다). 라우팅 항목은 여전히 읽기 전용이며 우리가 쓰지 않는다.
> `tomllib`은 읽기 전용이지만 덧붙이는 것은 텍스트 한 블록이라 쓰기 라이브러리
> 의존이 생기지 않는다.

### 6. 조회 지점은 composition root 하나다

upstream의 조회 지점은 셋(auto 파이프라인·MCP adapter·config loader)이지만,
Mission Control은 CLI/MCP가 같은 application service와 같은 composition을
공유하므로 (ADR-0038 §1) 조회는 조립 시점 한 번이다. Phase 7 MCP가 붙어도
조회 지점은 늘지 않는다 — upstream이 3곳에서 같은 resolver를 부르는 것과 같은
효과를 구조로 얻는다.

### 7. backend 이름은 vendor가 아니라 vendor×전송이다 (2026-08-09 보강)

레지스트리 키를 vendor 이름(`codex`)으로 둘지 전송까지 담은 이름(`codex_cli`)으로
둘지는 되돌리기 비싼 명명 축이다. **upstream이 후자다** — 같은 codex 바이너리를
`codex exec`로 구동하는 것과 `codex mcp-server`로 구동하는 것을 `codex`와
`codex_mcp`라는 **별개 키**로 등록한다. 근거는 upstream 자신의 선언이다:

> "This is a property of the **(runtime × backend) PAIR** … NOT of the backend
> name alone." (`orchestrator/adapter.py:798-806`)

따라서 우리 `codex_cli`(`ExecutionRuntime.backend`, [ADR-0033](./0033-first-runtime-adapter-contract.md) §1)는
장식이 아니라 축을 담은 이름이며 그대로 유지한다 — 훗날 MCP 구동 변종이 들어와도
키가 충돌하지 않는다.

부수적으로, **한 backend가 lane 하나만 서비스할 수 있다**는 것도 upstream에서
확인된다: `codex_mcp`/`claude_mcp` 항목에는 `runtime_backend`만 있고
`llm_backend`가 없다(`backends/factory_registry.py`). 이는 §2가 등록한
divergence(stage당 lane별 라우팅)를 해소하지는 않는다 — upstream의 것은 *backend가
어떤 lane을 서비스하는가*이고 우리 것은 *stage를 lane별로 어디에 보내는가*다.
축이 다르다는 사실을 여기 명시해 다음 대조가 둘을 혼동하지 않게 한다.

근거: [RUNTIME_UPSTREAM_FINDINGS §12](../research/RUNTIME_UPSTREAM_FINDINGS.md).

## Consequences

### Positive

- 이미 실재하던 라우팅이 명시적 표현을 갖는다 — "왜 이 Stage가 Claude인가"가
  코드 상수가 아니라 데이터로 답해진다.
- 운용자의 설정 실수가 조용한 재라우팅이 아니라 로드 실패로 드러난다.
- Execute의 하네스 교체(codex ↔ opencode — upstream 아키텍처 방향)가 설정
  한 줄이 된다. backend 레지스트리는 등록된 adapter에 대해 열려 있으므로,
  실물 adapter를 나중에 추가해도 기존 코드는 바뀌지 않는다.

### Cost

- 설정 스키마·검증·테스트가 Phase 6 범위에 추가된다.
- lane 축이 upstream과 달라 이후 upstream 라우팅 변경을 그대로 따라갈 수 없다 —
  대조 시 §2의 divergence를 먼저 읽어야 한다.

## Rejected alternatives

- **하드코딩 유지 + divergence 등록만**: 되돌리기 비싼 축을 "실수요 시"로
  미루는 것이고, 그 조건부 시한이 기약 없이 밀린다는 것이 이번 대조의 교훈이다.
- **lane 축을 버리고 upstream처럼 stage당 backend 하나**: 사용자가 확정한
  구조(ADR-0036)를 되돌리는 것이며, 도그푸딩 2회가 그 구조의 근거다.
- **CLI 플래그로 vendor 선택**: ADR-0038의 비대화형 단발 표면과 맞지 않고,
  upstream도 라우팅을 config에 둔다(`--runtime`은 전역 override 하나뿐).
- **YAML 채택**: 의존성이 늘고, 우리는 설정을 읽기만 한다.

## Verification

- 알 수 없는 Stage key를 담은 설정은 로드에서 거부된다.
- 알 수 없는 backend 이름은 로드에서 거부된다.
- 설정 파일이 존재하는데 malformed면 기본 조립으로 넘어가지 않고 예외가 오른다.
- 설정 파일이 없으면 기본 조립(Claude 텍스트 + Codex 실행)이 쓰인다.
- `stages[stage][lane]` → `default[lane]` → 기본 조립 순서가 지켜진다.
- Stage가 쓰지 않는 lane을 조회하면 조용한 기본값이 아니라 오류다.
- 레지스트리 키는 전송을 담은 이름이다 — 실행 lane의 등록 이름이 `codex`가 아니라
  `codex_cli`이고, 이 이름이 provenance(`ExecuteState.runtime_backend`)와 원장
  호출 계수 키에서 동일하다 (§7).

## Amendment — Execute dependency analysis text lane (2026-08-10)

[ADR-0053](./0053-parallel-coordinator-execution-contract.md)이 parallel stage plan을
도입하면서 Execute도 text lane을 사용한다. 실행 worker·Coordinator는 계속
ExecutionRuntime lane이고, dependency analyzer만 tool-less `CompletionEngine`이다.

upstream은 active execution adapter의 `llm_backend`를 읽어 dependency analyzer용
LLM adapter를 새로 만든다(`runner.py:6995-7063`). mcx는 ADR-0034·0036이 이미
text generation과 workspace-write execution을 별도 port와 routing lane으로
분리했으므로, 그 경계를 되합치지 않고 **Execute의 text lane**을 조회한다.

따라서 Stage별 lane 집합은 다음처럼 바뀐다.

```text
Execute = text + execution
```

설정 우선순위·backend registry·fail-fast 규칙은 바뀌지 않는다. 설정이 없으면
기존 기본 조립(Claude text + Codex execution)을 그대로 쓴다. dependency plan의
analyzer backend는 durable plan에 기록되어 execution backend와 달라도 조용히
숨지 않는다.
