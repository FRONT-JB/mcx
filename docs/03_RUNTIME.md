# Runtime Architecture and Adapter Contract

> **Runtime은 미션을 소유하지 않는다.**<br>
> **Runtime은 Stage를 전이시키지 않는다.**<br>
> **Runtime은 제한된 작업을 수행하고 정규화된 결과와 Telemetry를 반환한다.**

| 항목 | 값 |
|---|---|
| 문서 지위 | Active Draft — Runtime 설계 기준 |
| 상위 기준 | `00_MISSION_CONTROL.md` |
| 인접 문서 | [`01_ARCHITECTURE.md`](./01_ARCHITECTURE.md), [`02_MISSION_LIFECYCLE.md`](./02_MISSION_LIFECYCLE.md), [`04_MCP.md`](./04_MCP.md) |
| 적용 범위 | v1 Runtime-neutral Core, Runtime protocol, Codex/OpenCode adapter 방향 |
| 구현 언어 | Python |
| 정확한 API·schema | **TBD — 구현 전 ADR 또는 계약 테스트로 확정** |

이 문서는 Mission Control Core와 외부 실행 환경 사이의 경계를 정의한다. 목적은
모든 도구를 하나의 추상화에 억지로 끼워 넣는 것이 아니라, Core가 vendor별 CLI,
이벤트, 세션, 모델 이름을 몰라도 동일한 미션 규칙을 적용할 수 있게 하는 것이다.

이 문서의 `MUST`, `MUST NOT`, `SHOULD`, `MAY`는 Constitution의 규범 언어를
따른다. 이 문서가 Constitution과 충돌하면 Constitution이 우선한다.

---

## 1. 결정 요약

v1 Runtime 설계의 기준은 다음과 같다.

1. Mission state, Stage 전이, Gate, Recover 정책은 Core가 소유한다.
2. Runtime Adapter는 공통 요청을 구체 런타임 호출로 변환하고 결과를 정규화한다.
3. 단발성 문장 생성 backend와 도구를 사용하는 execution runtime은 별도 책임과
   호출 의미로 취급한다. 정확한 Python port 수와 이름은 아직 TBD다.
4. Core는 capability를 추측하지 않고 dispatch 전에 조회·검증한다.
5. 런타임이 제공하지 않는 기능은 흉내 내지 않고 `unsupported`로 보고한다.
6. durable Mission ID와 vendor session/thread ID를 동일시하지 않는다.
7. timeout과 cancellation은 공통 신호지만, 실제 종료 보장 수준은 capability로
   표현한다.
8. 모든 invocation은 정규화된 result, error, Telemetry 중 관찰 가능한 정보를
   잃지 않고 반환한다.
9. 초기 adapter 방향은 Codex와 OpenCode다. Gemini는 v1 범위 밖이다.
10. adapter는 공통 conformance suite를 통과해야 Core에 연결할 수 있다.

---

## 2. 목표와 비목표

### 2.1 목표

- Core가 특정 모델, CLI 인자, event stream 형식에 의존하지 않게 한다.
- Brief, Blueprint, Execute, Verify, Recover가 필요한 실행 능력을 명시적으로
  요청하게 한다.
- 실행의 성공, 실패, 취소, timeout, 부분 결과를 일관된 의미로 관찰하게 한다.
- Stage별 최소 권한을 adapter 경계에서도 강제하고 검증할 수 있게 한다.
- 런타임 교체 후에도 Mission과 Blueprint, Gate history가 유지되게 한다.
- 가짜 Runtime으로 Core의 상태 전이와 실패 경로를 결정적으로 테스트하게 한다.
- vendor 고유 정보가 필요할 때도 공통 필드와 분리된 확장 영역에 보존하게 한다.

### 2.2 비목표

- 모든 vendor 기능을 공통 최저 수준으로 평준화하지 않는다.
- 모델 품질, 비용, 속도를 하나의 점수로 자동 라우팅하지 않는다.
- adapter가 Stage 정책이나 Gate를 대신 판단하게 하지 않는다.
- vendor session을 Mission의 영구 저장소로 사용하지 않는다.
- Gemini adapter를 v1에 포함하지 않는다.
- 필요성이 확인되지 않은 병렬 dispatch, 다중 모델 합의, 장기 worker pool을 먼저
  구현하지 않는다.
- upstream 구현을 추측해 호환성을 주장하지 않는다. upstream 대응은 별도
  `research/` 문서에서 버전과 근거를 붙여 다룬다.

---

## 3. 경계와 용어

```text
Mission Control Core
  ├─ Domain: Mission, Stage, Blueprint, Gate, Telemetry references
  ├─ Application: use case orchestration, policy, persistence transaction
  └─ Ports
       ├─ TextGenerationBackend
       └─ ExecutionRuntime
              │
              ▼
        Runtime Adapter
          ├─ Codex adapter
          └─ OpenCode adapter
```

| 용어 | 이 문서에서의 의미 |
|---|---|
| Core | 미션 상태, 정책, 전이, Gate를 소유하는 Runtime-neutral 영역 |
| Runtime Port | Core가 필요로 하는 실행 계약; vendor 기술이 드러나지 않는다. |
| Runtime Adapter | 공통 계약을 구체 런타임 호출과 이벤트로 변환하는 경계 |
| Flight Controller | 제한된 요청을 실제로 수행하고 증거를 반환하는 실행 주체 |
| Invocation | 한 Runtime 요청을 시작해 terminal result에 이르는 식별 가능한 호출 |
| Runtime session | 구체 런타임이 대화·작업 연속성을 위해 제공할 수 있는 임시 식별자 |
| Mission | Runtime session보다 오래 지속되는 canonical 작업 단위 |
| Capability | Runtime이 실제로 강제하거나 수행할 수 있다고 선언한 능력과 제한 |
| Telemetry | invocation의 행동·관찰·결과를 Gate 근거와 연결하는 구조화된 증거 |

### 3.1 의존 방향

Core가 port를 정의하고 adapter가 그 port에 의존한다.

```text
domain <- application <- runtime ports <- concrete adapters
```

다음 의존 방향은 금지한다.

```text
domain -> Codex CLI
gate policy -> OpenCode event name
mission state -> vendor session storage
```

vendor SDK 타입과 JSON 원문은 adapter 내부 또는 명시적인 vendor extension
영역에만 존재해야 한다.

---

## 4. Text-generation Backend와 Execution Runtime

Constitution은 질문 한 번을 생성하는 backend와 파일·명령을 다루는 실행 환경을
같은 개념으로 보지 않는다. v1은 최소한 책임 수준에서 둘을 분리한다.

### 4.1 TextGenerationBackend

다음과 같은 제한된 생성 작업에 적합하다.

- Brief의 다음 질문 후보 생성
- Brief 답변의 구조화 또는 요약 초안
- Blueprint 초안 생성
- 정규화된 semantic assessment 초안

기본 성질은 다음과 같다.

- 파일 변경이나 shell 실행을 요구하지 않는다.
- 입력과 출력 계약이 비교적 작고 명시적이다.
- 구조화된 출력 파싱 실패를 정상 응답으로 숨기지 않는다.
- 생성 결과가 Gate decision이나 사용자 승인 그 자체가 아니다.

`TextGenerationBackend`는 이 책임을 설명하기 위한 이름이다. Architecture 문서의
provisional `LLMBackend`와 같은 경계를 가리키며, 실제 Python 타입 이름은 TBD다.

### 4.2 ExecutionRuntime

다음과 같은 상태 있는 작업에 적합하다.

- 승인된 범위 안의 파일 읽기·변경
- build, test, lint 같은 명령 실행
- 도구 호출과 이벤트 스트림 수집
- 기존 worker/thread를 이용한 제한된 후속 작업
- cancellation, timeout, working directory, sandbox 적용

ExecutionRuntime의 결과도 미션 완료 선언이 아니다. 실행 결과와 Telemetry를 Core에
반환하고, Core가 별도 Gate 정책을 적용한다.

### 4.3 공통화의 한계

두 계약은 인증, model selection, token usage 같은 하위 구성 일부를 공유할 수
있다. 그러나 하나의 거대한 `run(prompt)` 인터페이스로 합치면 다음 문제가 생긴다.

- Brief에 불필요한 파일·shell 권한이 따라온다.
- text 응답 성공과 실제 실행 성공을 구분하기 어렵다.
- cancellation 및 session 의미가 모호해진다.
- capability 검증이 문자열 prompt에 묻힌다.
- Verify에서 생성자의 자기평가를 독립 증거처럼 오인하기 쉽다.

따라서 구현 편의를 위한 공통 helper는 가능하지만, application 의미의 port는
분리하는 것이 기본값이다. 정확한 Python protocol 수는 ADR에서 확정한다.

---

## 5. Core와 Runtime의 책임

### 5.1 Core가 반드시 소유하는 것

- `mission_id`, current Stage, Blueprint revision
- 현재 attempt와 이전 attempt history
- 요청할 역할, 목표, Constraints, Non-goals
- Acceptance Criterion과 필요한 Telemetry
- 허용 capability envelope
- Stage 전이, `CLEAR`, `HOLD`, `MISSION COMPLETE`
- retry/recover budget과 무진전 판단
- durable persistence와 optimistic concurrency 정책을 repository port로 조정하는 책임
- 사용자 승인이 필요한 경계

### 5.2 Runtime Adapter가 반드시 수행하는 것

- 공통 요청 검증 후 vendor 호출 형식으로 변환
- working directory, 환경, 도구·파일 범위 등 적용 가능한 제약 설정
- provider transport secret을 제거한 vendor event를 canonical Runtime event 또는
  redacted raw artifact로 변환
- stdout/stderr, 변경 정보, 명령 결과, usage 등 관찰 가능한 데이터 수집
- 종료, 오류, timeout, cancellation 상태 정규화
- runtime/session identifiers를 명시적 namespace와 함께 반환
- provider token, authorization header, transport credential의 canonicalization 전
  redaction과 허용되지 않은 output 제한
- capability discovery 결과와 실제 동작의 불일치 보고

### 5.3 Runtime Adapter가 결정해서는 안 되는 것

- 현재 또는 다음 Stage
- Blueprint 승인 또는 revision 변경
- Gate result
- Runtime 오류 후 Recover 여부와 횟수
- Acceptance Criterion의 최종 충족 여부
- 권한 확대나 새로운 외부 행동 승인
- `MISSION COMPLETE`
- canonical Runtime event를 domain evidence로 해석하거나 직접 durable하게 저장하는 일

adapter는 side effect가 발생하기 전에 끝난 transport failure이고 재전송 안전성이
입증된 경우에만 같은 attempt 안에서 제한적으로 retry할 수 있다. side effect가
시작되었거나 발생 여부가 불명확하면 재실행하지 않고 canonical outcome/event를
application에 반환한다. 후속 실행이 필요하면 application이 새 attempt를 만든다.
허용된 transport retry도 횟수와 결과를 canonical Runtime event로 드러내야 한다.

Runtime Adapter는 Mission state, domain evidence 또는 Telemetry artifact를 직접
persist하지 않는다. application이 canonical Runtime event를 domain evidence로
매핑하고 repository가 durable evidence/state를 저장한다.

---

## 6. Capability Discovery와 Negotiation

Capability는 “이 Runtime이면 아마 될 것”이라는 vendor별 추측이 아니다. 특정
adapter instance와 구성에서 현재 제공 가능한 능력의 버전 있는 snapshot이다.

### 6.1 Capability 범주 후보

정확한 enum은 **TBD**지만 최소한 다음 차원을 표현할 수 있어야 한다.

| 범주 | 예시 질문 |
|---|---|
| interaction | text generation만 가능한가, tool-using execution이 가능한가? |
| filesystem | read/write 범위가 실제로 제한 가능한가? |
| process | 명령 실행, working directory, environment 제한이 가능한가? |
| network | 비활성화·allowlist·승인형 접근을 구분할 수 있는가? |
| tools | explicit allowlist/denylist를 적용할 수 있는가? |
| isolation | sandbox 또는 동등한 강제가 가능한가? |
| session | 새 session, resume, fork 중 무엇을 지원하는가? |
| lifecycle | streaming, cancellation, hard timeout을 지원하는가? |
| output | structured result, diff, command result, token/cost usage가 있는가? |
| approval | 사용자 승인 요청을 전달하거나 금지할 수 있는가? |

### 6.2 Discovery 결과

Capability snapshot은 다음 원칙을 지킨다.

- adapter 이름과 adapter contract version을 포함한다.
- 정적 지원 여부와 현재 구성에서 활성화된 여부를 구분한다.
- `supported`, `unsupported`, `unknown`을 구분한다.
- 제한의 강제 수준을 표현한다. prompt 지시와 sandbox 강제는 같지 않다.
- snapshot 생성 시점과 근거가 되는 구성 fingerprint를 남긴다.
- 비밀 설정값 자체는 포함하지 않는다.

### 6.3 요청과 협상

Core의 dispatch는 필요한 capability를 최소한 다음처럼 구분해야 한다.

- **required**: 없으면 dispatch를 시작하지 않고 `HOLD` 또는 policy error로 귀결
- **optional**: 없더라도 명시된 대체 경로로 진행 가능
- **forbidden**: 해당 작업에서 반드시 제거하거나 차단해야 하는 능력

요청한 capability를 만족하지 못하면 adapter는 기능을 prompt로 흉내 내지 않는다.
예를 들어 실제 write scope 제한을 제공하지 못한다면 `write_scope_enforced=true`라고
보고할 수 없다. Core는 더 안전한 Runtime을 선택하거나 사용자의 결정을 요구한다.

### 6.4 TOCTOU와 drift

discovery 이후 실행 전에 구성이나 권한이 바뀔 수 있다. 따라서 invocation result는
실행에 실제 적용한 capability snapshot 또는 그 hash를 다시 참조해야 한다. discovery
결과와 적용 결과가 다르면 별도 Telemetry event와 오류로 드러낸다.

---

## 7. 정규화된 계약

이 절의 필드와 Python 코드는 설계 방향을 확인하기 위한 **잠정 예시**다. 정확한
이름, 타입, required/optional 여부, serialization schema는 구현 전 계약 테스트와
ADR에서 확정한다.

### 7.1 공통 식별자

모든 요청과 결과는 가능한 범위에서 다음 identity chain을 보존한다.

```text
mission_id
  └─ stage
      └─ attempt_id
          └─ operation_id?       # application의 장기 operation
              └─ dispatch_id?    # durable Runtime dispatch record 후보
                  └─ invocation_id
                      ├─ runtime_adapter_id
                      └─ vendor_session_id? / vendor_thread_id?
```

- `mission_id`는 Mission Control이 발급하고 durable하다.
- `attempt_id`는 같은 Stage의 재시도를 구분한다.
- `operation_id`는 MCP/CLI가 조회할 수 있는 application-level 장기 작업 후보다.
- `dispatch_id`는 외부 호출 전 durable하게 예약할 수 있는 dispatch record 후보다.
- `invocation_id`는 한 adapter 호출을 구분하며 idempotency와 추적에 사용한다.
- vendor ID는 optional이며 namespace 없이 단독 저장하지 않는다.
- vendor ID가 없어도 Mission history를 읽을 수 있어야 한다.

`operation_id`, `dispatch_id`, `invocation_id`를 모두 별도 타입으로 둘지는 TBD다.
구현에서 합치더라도 application 작업, durable dispatch, vendor 호출의 의미와 수명을
혼동해서는 안 된다.

### 7.2 RuntimeRequest — 잠정 예시

```python
# PROVISIONAL PSEUDOCODE — exact schema TBD
@dataclass(frozen=True)
class RuntimeRequest:
    mission_id: MissionId
    stage: Stage
    attempt_id: AttemptId
    invocation_id: InvocationId
    role: str
    objective: str
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]
    acceptance_refs: tuple[AcceptanceRef, ...]
    context_refs: tuple[ArtifactRef, ...]
    required_capabilities: CapabilityRequirement
    forbidden_capabilities: CapabilityRequirement
    workspace: WorkspaceBoundary | None
    telemetry_contract: TelemetryRequirement
    deadline: datetime | None
    continuation: RuntimeContinuation | None
    idempotency_key: str  # application-provided/derived; semantics stay in application
```

요청은 prompt 한 문자열보다 풍부해야 한다. adapter가 vendor prompt를 만들 수는 있지만,
권한과 범위, deadline, Telemetry 요구사항을 prompt text에서 재해석하게 해서는 안 된다.
side-effecting application command의 idempotency는 application-command boundary에서
필수다. 이 필드는 adapter/provider에 전달할 수 있는 표현 예시일 뿐이며 exact key
schema와 Runtime 전달 방식은 **TBD**다.

### 7.3 TextGenerationRequest — 잠정 예시

```python
# PROVISIONAL PSEUDOCODE — exact schema TBD
@dataclass(frozen=True)
class TextGenerationRequest:
    operation: str
    input_messages: tuple[Message, ...]
    response_contract: StructuredOutputContract
    model_policy: ModelPolicy
    deadline: datetime | None
    correlation: CorrelationContext
```

`model_policy`는 특정 모델명을 Core domain에 고정하라는 뜻이 아니다. 비용·지연·구조화
출력 같은 요구를 application configuration이 해석할 수 있는 정책 후보를 뜻한다.

### 7.4 RuntimeResult — 잠정 예시

```python
# PROVISIONAL PSEUDOCODE — exact schema TBD
@dataclass(frozen=True)
class RuntimeResult:
    invocation_id: InvocationId
    terminal_status: Literal["succeeded", "failed", "cancelled", "timed_out", "indeterminate"]
    output_artifacts: tuple[ArtifactRef, ...]
    events: tuple[CanonicalRuntimeEvent, ...]
    runtime_error: RuntimeError | None
    applied_capabilities_ref: CapabilitySnapshotRef
    continuation: RuntimeContinuation | None
    started_at: datetime
    ended_at: datetime
    vendor_extension: Mapping[str, JsonValue] | None
```

`terminal_status="succeeded"`는 호출이 계약에 따라 종료되었다는 뜻일 뿐이다.
Acceptance Criteria 충족이나 `CLEAR`를 의미하지 않는다.

### 7.5 RuntimeError — 잠정 분류

```text
configuration_error      adapter 구성 또는 필수 실행 파일/인증 누락
capability_mismatch      required capability를 만족하지 못함
permission_denied        정책 또는 외부 런타임이 행동을 거부함
validation_error         요청 자체가 계약을 위반함
transport_error          프로세스/IPC/API 연결 실패
protocol_error           event 또는 structured output을 해석할 수 없음
runtime_failure          worker가 시작됐지만 실행 중 실패
timeout                  deadline 초과
cancelled                요청된 취소가 관찰됨
lost_session             continuation 대상 session을 찾거나 재개할 수 없음
indeterminate            실행 여부나 side effect를 안전하게 판단할 수 없음
```

정확한 enum은 **TBD**다. 중요한 것은 오류의 출처, 재시도 안전성, side effect 여부를
보존하는 것이다. 오류에는 다음 정보가 필요하다.

- 안정적인 공통 code와 사람이 읽을 수 있는 message
- 발생 phase: validate, prepare, start, stream, finalize, cancel
- retry 가능 여부에 대한 adapter의 제한된 hint
- side effect가 없다고 보장할 수 있는지 여부
- vendor 원인에 대한 redacted reference
- 관련 raw Telemetry reference

adapter의 retry hint는 Core의 Recover 결정을 대신하지 않는다.

### 7.6 Telemetry envelope — 잠정 예시

```python
# PROVISIONAL PSEUDOCODE — exact schema TBD
@dataclass(frozen=True)
class CanonicalRuntimeEvent:
    event_id: EventId
    mission_id: MissionId
    stage: Stage
    attempt_id: AttemptId
    invocation_id: InvocationId
    sequence: int
    observed_at: datetime
    source: str
    kind: str
    summary: str
    artifact_refs: tuple[ArtifactRef, ...]
    redaction: RedactionMetadata
    vendor_extension: Mapping[str, JsonValue] | None
```

공통 event 후보에는 invocation lifecycle, command start/result, tool call/result, file
change observation, artifact creation, permission decision, warning, usage, heartbeat 등이
있다. 모든 vendor event를 억지로 공통 enum에 매핑하지 않는다. Gate에 필요한 의미는
정규화하고, 나머지는 redacted raw artifact candidate로 application에 반환할 수 있다.
durable artifact 저장과 reference 발급은 application이 repository/artifact port를 통해
수행한다.

### 7.7 Artifact 계약

큰 stdout, diff, 보고서, raw event stream을 result JSON 안에 무제한으로 넣지 않는다.
artifact reference는 최소한 다음을 제공해야 한다.

- content type과 encoding
- immutable identity 또는 digest
- 생성 invocation과 source
- 크기와 truncation 여부
- redaction 여부
- 접근 권한과 보존 정책 reference

위 pseudocode의 `ArtifactRef`는 논리적 결과 형태다. Runtime Adapter가 durable artifact
store를 직접 쓴다는 뜻이 아니며, 실제 계약은 application이 adapter output을 저장한 뒤
발급한 reference와 runtime workspace locator를 구분해야 한다.

Core는 존재하지 않는 artifact reference로 Gate를 `CLEAR`해서는 안 된다.

---

## 8. Invocation Lifecycle

권장 lifecycle은 다음과 같다. 정확한 method 이름은 **TBD**다.

```text
1. Core builds bounded request
2. Adapter validates request
3. Adapter discovers/revalidates capabilities
4. Core/application authorizes dispatch
5. Adapter prepares isolated invocation
6. Adapter starts worker/session
7. Adapter streams canonical Runtime events to the application
8. Adapter receives terminal outcome or cancellation/timeout
9. Adapter finalizes redacted artifacts and normalized result
10. Application maps canonical events to domain evidence
11. Repository persists durable evidence and state
12. Core evaluates durable evidence at the relevant Gate
```

준비 단계에서 실패하면 실행이 시작되지 않았다는 사실을 명확히 해야 한다. 시작 이후
연결이 끊기면 무조건 `failed`로 단정하지 말고 side effect가 불명확한
`indeterminate` 상태를 사용할 수 있어야 한다.

### 8.1 Streaming과 backpressure

Runtime이 streaming을 지원하더라도 Core domain이 vendor token stream에 의존해서는
안 된다. application layer가 canonical Runtime event sink를 제공할 수 있다. 이
sink는 application boundary로 event를 전달하며 adapter에 persistence 책임을 주지
않는다. 다음을
명시적으로 다룬다.

- sequence ordering과 duplicate event
- consumer가 느릴 때의 buffer/backpressure
- 큰 output의 artifact 전환
- stream 단절 후 terminal result 조회 가능 여부
- 마지막으로 durable하게 저장된 sequence

streaming은 UI 편의가 아니라 실행 중 증거 유실을 막는 수단이기도 하다.

---

## 9. Session, Continuation, Thread

### 9.1 세 종류의 수명

```text
Durable Mission
  └─ 여러 Stage와 attempt를 가로질러 지속

Runtime invocation
  └─ 한 bounded dispatch의 수명

Vendor session/thread
  └─ 특정 adapter가 제공할 수 있는 대화·worker 연속성
```

vendor session이 종료되거나 삭제되어도 Mission과 이전 Gate decisions는 남아야 한다.
반대로 host 대화가 계속된다고 같은 Mission이라는 보장도 없다.

### 9.2 Continuation 원칙

- continuation은 명시적이어야 하며 기본적으로 새 invocation을 만든다.
- 재개 시 이전 요청의 권한을 자동 상속하지 않고 현재 Stage 정책으로 재검증한다.
- continuation token은 vendor ID와 adapter namespace, configuration fingerprint를
  포함하거나 참조한다.
- Resume가 불가능하면 새 session에서 필요한 durable context만 재구성할 수 있어야
  한다.
- vendor 대화 전체를 canonical Mission state로 간주하지 않는다.
- stale Blueprint revision을 가진 session은 Execute에 재사용하지 않는다.

### 9.3 Session affinity

성능과 문맥 보존을 위해 affinity를 사용할 수 있지만 정확성 요구가 아니다. adapter를
교체하거나 session을 잃어도 artifact와 Mission state로 작업을 이어갈 수 있어야 한다.
session reuse가 hidden state를 만들 위험이 있으면 새 session을 기본값으로 선택한다.

---

## 10. Timeout과 Cancellation

### 10.1 Deadline 모델

요청에는 상대 duration보다 절대 deadline을 전달하는 것이 기본 방향이다. 여러 계층을
거쳐도 남은 시간이 명확하기 때문이다. 적용 가능한 budget 후보는 다음과 같다.

- queue/prepare timeout
- execution deadline
- idle/heartbeat timeout
- graceful cancellation window
- 전체 Mission/Stage budget

정확한 기본값은 **TBD**이며 Constitution에 고정하지 않는다.

### 10.2 Cancellation 의미

cancellation은 “클라이언트가 더 이상 기다리지 않는다”와 “worker가 실제로 종료됐다”를
구분해야 한다.

```text
cancel requested
  → adapter acknowledges
  → runtime termination attempted
  → termination observed | still running | unknown
```

- 취소 요청 시각과 확인 시각을 Telemetry로 남긴다.
- process tree, child tool call, 외부 side effect가 종료되었는지 가능한 범위에서
  확인한다.
- hard cancellation을 지원하지 않으면 capability에 명시한다.
- 취소 후 부분 artifact와 변경을 삭제하거나 성공으로 숨기지 않는다.
- cancellation 때문에 상태가 불명확하면 `indeterminate`로 반환한다.
- cancellation은 자동 rollback을 의미하지 않는다.

### 10.3 Timeout 의미

timeout은 Acceptance Criterion 실패가 아니라 Runtime lifecycle failure다. 다만 timeout
전에 생성된 변경과 Telemetry는 이후 Recover/Verify에서 중요할 수 있으므로 보존한다.
Core가 새 attempt를 시작하기 전에 이전 worker가 실제로 종료되었는지 확인해야 한다.

---

## 11. Error와 Retry Semantics

### 11.1 오류 층

| 층 | 예 | 담당 판단 |
|---|---|---|
| request | 필수 identity나 scope 누락 | application/adapter validation |
| capability | required sandbox를 제공하지 못함 | Core policy, dispatch 전 중단 |
| adapter | executable, auth, config, parsing 문제 | adapter가 정규화 |
| runtime | worker/tool/command 실행 실패 | adapter가 관찰, Core가 후속 판단 |
| verification | AC 또는 Non-goal 위반 | Verify Gate |
| persistence | result/Telemetry 저장 실패 | application transaction; 전이 금지 |

Runtime 성공과 Verify 성공을 섞지 않는다. 예를 들어 test command가 종료 코드 1을
반환했지만 그 실패를 관찰하는 것이 요청 목적이었다면 invocation transport는 성공적으로
끝났을 수 있다. 그 command result는 Telemetry이고 Gate가 의미를 판정한다.

### 11.2 Idempotency

- side effect가 있는 application command는 application-command boundary에서 안정적인
  idempotency key를 반드시 가져야 한다.
- application/Core가 key namespace, payload conflict, 기존 결과 반환과 새 attempt
  생성 의미를 소유한다.
- adapter는 application이 제공하거나 파생한 key/token을 vendor에 전달할 수 있지만
  독자적인 idempotency 의미나 canonical store를 만들지 않는다.
- 모든 Runtime dispatch는 별도의 안정적인 `invocation_id`로 추적한다.
- 네트워크/프로세스 응답 유실만으로 실행을 즉시 중복 시작하지 않는다.
- exact-once 실행을 보장한다고 쉽게 주장하지 않는다.
- 결과를 재조회할 수 있다면 새 실행보다 조회를 우선한다.

정확한 key schema, namespace, 저장소와 보존 기간은 **TBD**다.

### 11.3 Transport retry와 Recover 구분

transport retry는 동일한 의미의 호출 전달을 복구하는 기술적 동작이다. adapter 내부
retry는 side effect가 시작되기 전 실패했고 재전송 안전성을 입증할 수 있을 때만 같은
attempt에서 허용된다. 그 밖의 failure와 side effect가 불명확한 outcome은 retry하지
않고 application으로 반환한다. application은 정책상 후속 실행이 필요하면 새 attempt를
생성한다.

Recover는 실패 evidence를 바탕으로 새 bounded work를 설계하는 Mission Lifecycle
동작이다. transport retry와 Recover는 attempt lineage와 감사 기록에서 구분되어야 한다.

---

## 12. Telemetry Requirements

Raw Runtime observation → canonical Runtime event → domain evidence/evaluation의 세 층은
**Accepted conceptual baseline**이며 exact schema는 **TBD**다. Runtime Adapter는 두 번째
층까지 책임지고, application이 canonical event를 domain evidence로 매핑하며,
repository가 durable evidence/state를 저장한다. adapter는 persistence를 직접 호출하지
않는다.

Runtime Adapter는 최소한 다음 질문에 답할 canonical event와 redacted artifact를
제공해야 한다.

- 어떤 adapter와 구성으로 invocation을 시작했는가?
- 어떤 capability가 요청되었고 실제 적용되었는가?
- 어떤 vendor session/thread가 사용되었는가?
- 시작·종료·취소·timeout은 언제 관찰되었는가?
- 어떤 tool/command가 어떤 결과를 반환했는가?
- 어떤 artifact와 파일 변경이 관찰되었는가?
- output이 잘렸거나 redaction되었는가?
- 오류가 어느 phase에서 발생했으며 side effect는 확정 가능한가?
- 어떤 원문 증거가 normalized summary를 뒷받침하는가?

### 12.1 원문과 정규화

정규화 과정에서 원문의 중요한 의미를 잃지 않는다.

```text
raw runtime event/artifact
  → adapter removes provider transport secrets
  → canonical Runtime event
  → application applies domain-sensitive redaction and maps evidence
  → repository persists Stage evidence reference
  → Gate decision
```

raw output을 항상 영구 보존한다는 뜻은 아니다. 보존 기간과 민감정보 정책은 별도 결정이
필요하다. 다만 summary만 남겨 Gate의 근거를 재구성할 수 없게 해서는 안 된다.

### 12.2 민감정보

- Runtime Adapter는 provider credential, token, cookie, authorization header와 secret
  environment value를 canonicalization 전에 제거한다.
- application/persistence boundary는 command argument, path, mission/user content 등
  domain-sensitive field를 durable storage 전에 redaction한다.
- 모델이 출력한 비밀값도 신뢰하지 않으며 두 경계에서 각자 검사한다.
- vendor raw payload 접근 권한은 최소화한다.
- redaction 때문에 증거가 불충분해지면 `CLEAR`를 만들지 않는다.

각 계층의 exact field policy는 **TBD**다.

---

## 13. 초기 Adapter 방향

이 절은 v1의 **설계 방향**이다. Codex 또는 OpenCode의 현재 CLI/API 기능에 대한
upstream 사실을 주장하지 않는다. 실제 adapter 구현 전에는 현재 버전의 공식 문서,
도움말, 이벤트 출력, 라이선스와 테스트를 `research/`에 근거와 함께 기록해야 한다.

**v1 확정 (2026-08-08)**: 첫 adapter는 **Codex의 ExecutionRuntime**이고,
순서는 Codex 실행 → Codex text backend → OpenCode다. upstream 조사
([RUNTIME_UPSTREAM_FINDINGS](./research/RUNTIME_UPSTREAM_FINDINGS.md))로 아래
목록의 대부분이 확인되었다 — 호출은 `codex exec` 단발(프롬프트 stdin,
`--json`, `-C`), 권한은 공용 sandbox enum → Codex 플래그 파생(v1 기본
`--full-auto`, bypass 경로 없음), session은 JSONL thread id, timeout은 침묵
900초, adapter 자체 재시도 없음. 스트리밍·resume·cancel·도구 단위 차단은
보류 등록. 계약은
[ADR-0033](./adr/0033-first-runtime-adapter-contract.md)이 고정한다.

### 13.1 Codex Adapter 방향

Codex adapter는 다음을 조사하고 계약에 매핑해야 한다.

- 비대화형 bounded invocation 방식
- working directory와 파일 접근 범위의 강제 가능성
- tool/network/approval/sandbox 정책 표현
- event stream 또는 structured result 가용성
- session/thread 생성과 재개 의미
- cancellation과 child process 종료 관찰
- 변경, 명령 결과, usage를 Telemetry로 수집하는 방법
- Mission Control MCP 재귀 발견을 차단하는 구성 방법

조사 결과가 공통 capability를 충족하지 못하면 adapter에서 이를 명시하고 Core 정책이
dispatch 여부를 결정한다. prompt 문구로 강제 기능을 가장하지 않는다.

#### 13.1.1 Phase 11 parallel amendment — VERIFIED

Codex `--json` 실물에서 편집 도구는 paired `item.started`/`item.completed`
`file_change`와 경로를 냈지만, 셸 리다이렉션 write는 `command_execution`만 냈다.
따라서 Runtime 결과는 workspace 상대 `changed_files`와
`write_telemetry=COMPLETE|INCOMPLETE`를 반환한다. terminal 누락, command event,
unpaired file-change, workspace 밖 경로는 전부 `INCOMPLETE`다. application은
동시 worker의 exact overlap 또는 incomplete attribution이 있으면 같은 Codex
adapter를 별도 Coordinator authority로 한 번 호출한다. 취소 시 process group을
종료하며 Coordinator도 worker와 같은 sandbox·재귀 차단을 쓴다.

이 vendor event projection은 adapter 안에만 있고 Core에는 Codex item type이
새지 않는다. exact 계약과 로컬 probe는 [ADR-0053](./adr/0053-parallel-coordinator-execution-contract.md)과
[parallel findings](./research/PARALLEL_EXECUTION_UPSTREAM_FINDINGS.md), 대표 실경로는
[DOGFOODING_0007](./research/DOGFOODING_0007.md)이 소유한다.

### 13.2 OpenCode Adapter 방향

OpenCode adapter도 동일한 공통 계약과 conformance suite를 따라야 한다. 다음 차이를
명시적으로 모델링할 준비가 필요하다.

- OpenCode가 제공하는 agent/worker 실행 경로
- OpenCode를 통해 local model을 사용하는 생성 경로
- tool 사용, session, event, permission 구성의 실제 가용성
- agent 설정과 model/provider 설정의 구분

### 13.3 Local model과 OpenCode agent는 같은 것이 아니다

local model은 일반적으로 text/tool decision을 생성하는 provider 위치에 가깝고,
OpenCode agent는 prompt, tool policy, 작업 상태와 실행 loop를 포함할 수 있는 실행
주체 위치에 가깝다. v1 설계에서는 다음처럼 구분한다.

```text
OpenCodeRuntime
  ├─ execution behavior / agent configuration
  └─ model provider selection
       └─ local model may be selected here
```

따라서 “local model 지원”을 곧바로 “독립 execution runtime 지원”으로 기록하지
않는다. local model이 structured output이나 tool use 등 required capability를 실제로
충족하는지도 별도로 discovery해야 한다.

### 13.4 Gemini 제외

Gemini는 v1 Runtime adapter 대상이 아니다. 관련 추상화 hook, config placeholder,
미검증 adapter skeleton을 미리 추가하지 않는다. 향후 포함하려면 실제 사용 사례,
capability mapping, 보안 경계, conformance 결과를 제안하고 범위 변경 승인을 받는다.

---

## 14. Security and Trust Boundary

Runtime은 신뢰 가능한 내부 함수가 아니라 side effect를 만들 수 있는 외부 실행
경계다.

### 14.1 요청별 최소 권한

adapter는 가능한 실제 제어 수단으로 다음을 적용한다.

- filesystem read/write scope
- working directory
- tool allowlist/denylist
- network policy
- environment variable allowlist와 secret injection policy
- process execution policy
- 외부 메시지, 배포, commit/push 같은 별도 승인 행동
- 시간·비용·attempt budget

Brief의 text generation 요청이 Execute용 write 권한을 상속해서는 안 된다. Verify도
관찰만 필요하다면 write capability를 받지 않는 것이 기본값이다.

### 14.2 Prompt injection과 untrusted content

저장소 파일, issue, 웹 문서, tool output은 지시가 아니라 데이터일 수 있다. adapter와
Flight Controller 구성은 untrusted content가 capability policy를 변경하지 못하게 해야
한다. policy는 prompt보다 바깥 계층에서 강제한다.

### 14.3 Mission Control 재귀 호출 금지

Flight Controller의 도구 목록에서 Mission Control MCP/CLI orchestration 기능을
제거하거나 차단한다. 단순히 “호출하지 말라”는 prompt만으로 충분하지 않다.
invocation origin과 orchestration depth를 전달해 방어적으로 재귀 요청을 거부하는 것도
필요하지만, 가장 강한 경계는 tool을 제공하지 않는 것이다.

### 14.4 Runtime output은 command가 아니다

Runtime output과 vendor event는 Mission state mutation command로 직접 역직렬화하지
않는다. application layer가 schema, current revision, policy를 검증한 뒤 허용된 상태
변경만 수행한다.

### 14.5 공급망과 실행 파일

adapter가 외부 CLI/SDK에 의존한다면 version pinning, executable path, provenance,
update policy, license를 기록해야 한다. PATH에서 발견한 임의 실행 파일을 신뢰하는
기본값은 피한다. 정확한 배포 방식은 ADR 대상이다.

---

## 15. Adapter Conformance Test Suite

모든 concrete adapter는 동일한 행동 계약을 테스트해야 한다. vendor별 unit test만으로
Core 연결을 허용하지 않는다.

### 15.1 필수 공통 시나리오

1. **Capability truthfulness**
   - 지원/미지원/불명 capability가 정확히 보고된다.
   - forbidden capability가 실제 invocation 구성에서 제거된다.
2. **Identity propagation**
   - mission, stage, attempt, invocation identity가 result와 event에 유지된다.
3. **Success is not CLEAR**
   - successful runtime result가 Gate를 직접 변경하지 않는다.
4. **Structured output failure**
   - 파싱 불가 결과가 빈 성공으로 바뀌지 않는다.
5. **Permission denial**
   - 금지된 write/network/tool 호출이 차단되고 증거가 남는다.
6. **Timeout**
   - deadline 초과가 정규화되고 부분 Telemetry가 보존된다.
7. **Cancellation**
   - requested/acknowledged/terminated 상태를 구분한다.
8. **Session loss**
   - resume 실패가 새 Mission 생성이나 silent restart로 바뀌지 않는다.
9. **Duplicate request**
   - application이 제공한 동일 idempotency key/token이 무분별한 중복 side effect를
     만들지 않으며 adapter가 독자적인 key 의미를 만들지 않는다.
10. **Stream interruption**
    - 마지막 durable sequence와 결과의 불확실성을 보고한다.
11. **Redaction**
    - provider transport secret fixture가 canonical Runtime event와 adapter가 반환한 raw
      artifact에 노출되지 않는다.
12. **Recursion guard**
    - Flight Controller가 Mission Control control surface를 호출할 수 없다.
13. **Vendor extension isolation**
    - vendor payload가 domain type이나 Gate policy에 누출되지 않는다.
14. **Applied capability drift**
    - discovery와 실제 적용 구성이 다르면 오류/Telemetry가 발생한다.

### 15.2 Deterministic Test Double

첫 Runtime 구현은 실제 vendor adapter보다 앞서 deterministic fake 또는 scripted
Runtime을 제공해야 한다. 이 test double은 다음 결과를 재현 가능하게 주입한다.

- 성공, 실패, 취소, timeout, indeterminate
- event 순서, 중복, 누락, 지연
- capability mismatch
- 부분 artifact와 session loss
- permission denial과 protocol parse failure

test double은 vendor 행동을 모사하는 제품 코드가 아니라 Core 계약을 검증하는
도구다. test 전용 shortcut이 production Gate 규칙을 우회해서는 안 된다.

### 15.3 실제 adapter smoke test

실제 CLI/API가 필요한 테스트는 unit/conformance suite와 분리한다. 설치·인증이 없는
환경에서 무조건 실패하지 않게 marker를 사용하되, release 또는 명시된 verification
환경에서는 실행 결과를 보존한다. 어떤 테스트가 실행되지 않았는지 숨기지 않는다.

---

## 16. Staged Implementation Plan

이 순서는 Runtime 범위를 작고 검증 가능하게 유지하기 위한 제안이다. Architecture와
Lifecycle 결정에 따라 조정할 수 있다.

### Phase R0 — Research and contract examples

- Codex/OpenCode의 현재 공식 invocation, permission, event, session 기능 조사
- version과 근거를 `research/`에 기록
- Brief text generation과 Execute invocation의 최소 example 작성
- capability vocabulary 후보와 보안 요구사항 검토

**Exit:** 미확인 vendor 가정 없이 두 개의 대표 요청/결과 fixture를 설명할 수 있다.

### Phase R1 — Domain-neutral value objects

- identity, capability requirement/snapshot, artifact reference, normalized error 설계
- serialization round-trip과 validation test
- vendor 타입이 domain/application으로 새지 않는 dependency test

**Exit:** 실제 Runtime 없이 계약 객체를 검증할 수 있다.

### Phase R2 — Deterministic Runtime

- scripted text backend와 execution runtime test double
- success/failure/cancel/timeout/indeterminate event scenarios
- Core가 Runtime success를 Gate success로 오인하지 않는 테스트

**Exit:** Mission Lifecycle 테스트가 vendor 설치 없이 실행된다.

### Phase R3 — Minimal Codex adapter

- 한 개의 bounded Execute 또는 조사 작업 vertical slice
- 실제 capability discovery와 적용 snapshot
- output/error/Telemetry 정규화
- conformance suite와 smoke verification

**Exit:** 명시된 제한 안에서 한 invocation을 실행하고 Gate와 분리된 증거를 남긴다.

### Phase R4 — Minimal OpenCode adapter

- R3와 동일한 공통 계약 적용
- agent path와 local model/provider path를 구분해 검증
- Codex 전용 가정이 Core에 없는지 교차 테스트

**Exit:** 같은 scripted application scenario가 adapter 선택과 무관하게 같은 Core
불변 규칙을 지킨다.

### Phase R5 — Sessions and robust cancellation

- 필요성이 확인된 continuation/resume
- process/session loss와 cancellation race 처리
- stale Blueprint revision과 permission 재검증

**Exit:** 재개와 중단이 durable Mission state를 훼손하지 않는다.

각 Phase에서 현재 필요 없는 범용 plugin system이나 provider matrix를 추가하지 않는다.

---

## 17. Verification Checklist

Runtime 관련 변경은 최소한 다음을 확인한다.

- [ ] Core domain이 vendor SDK/CLI 타입을 import하지 않는다.
- [ ] Runtime result가 Stage 또는 Gate를 직접 변경하지 않는다.
- [ ] required/forbidden capability가 dispatch 전에 검증된다.
- [ ] 실제 적용 capability가 Telemetry에서 추적된다.
- [ ] Mission ID와 vendor session ID가 분리되어 있다.
- [ ] timeout/cancel/indeterminate가 별도 상태로 관찰된다.
- [ ] 부분 결과와 실패 Telemetry가 보존된다.
- [ ] pre-side-effect safe transport retry와 새 attempt가 필요한 outcome을 구분한다.
- [ ] retry가 중복 side effect를 만들 위험을 테스트한다.
- [ ] adapter transport-secret redaction과 application durable redaction을 각각 테스트한다.
- [ ] Mission Control 재귀 호출이 runtime configuration에서 차단된다.
- [ ] adapter conformance suite가 통과한다.
- [ ] 실제로 실행하지 않은 smoke test를 통과한 것처럼 보고하지 않는다.
- [ ] 문서의 provisional schema와 실제 계약 차이를 갱신한다.

---

## 18. Open Decisions

다음은 아직 확정하지 않는다.

| 결정 | 필요한 근거 | 권장 기록 위치 |
|---|---|---|
| Python `Protocol`, ABC, 함수 port 중 선택 | 테스트성, typing, DI 방식 | ADR |
| text backend와 execution runtime의 패키지 분리 수준 | 첫 vertical slice 경험 | Architecture/ADR |
| capability enum과 versioning | Codex/OpenCode 실제 조사 | Runtime ADR |
| event streaming API와 sink 방식 | persistence/backpressure 실험 | ADR |
| artifact 저장 기술과 보존 기간 | 크기, 보안, 재현성 | Architecture/ADR |
| session resume 기본값 | hidden state 위험과 비용 | Runtime ADR |
| application idempotency key schema, namespace, 저장소와 TTL | 중복 command/invocation 시나리오 | Architecture/Persistence ADR |
| hard timeout/process tree 종료 구현 | OS·runtime 지원 조사 | Runtime ADR |
| vendor raw event 보존 범위 | 감사 가능성 대 민감정보 | Security/Telemetry ADR |
| model selection policy 위치 | text backend 실제 요구 | Architecture/ADR |
| Codex/OpenCode 호출 방식과 최소 버전 | 현재 upstream 조사 | `research/` + ADR |
| local model 지원 기준 | structured output/tool capability 검증 | Runtime ADR |
| 비용/token usage의 공통 필드 | vendor 측정 가능성 | Telemetry ADR |

결정 전 임시 구현이 필요하면 명시적으로 experimental/provisional로 표시하고 public
contract로 간주하지 않는다.

---

## 19. 유지보수 규칙

- adapter를 추가할 때 Core의 `if runtime == ...` 분기를 늘리지 않는다.
- 공통 계약에 vendor 전용 필드를 추가하기 전에 실제로 둘 이상의 소비자가 필요한지
  확인한다.
- capability를 새로 선언하면 enforcement와 conformance test를 함께 추가한다.
- runtime upgrade 후 discovery와 normalized fixture를 다시 검증한다.
- vendor 동작 차이는 `research/`의 버전 있는 근거와 adapter test로 남긴다.
- Runtime failure와 Verify failure를 progress 문서에서 구분한다.
- 이 문서의 TBD를 코드가 사실상 결정했다면 문서·ADR을 같은 변경에서 갱신한다.

---

## 20. Closing Contract

Runtime abstraction의 성공은 여러 provider를 같은 함수로 호출하는 데 있지 않다.
런타임이 바뀌어도 다음 불변 조건이 유지되는 데 있다.

```text
Mission state remains durable.
Capabilities remain explicit.
Execution remains bounded.
Evidence remains attributable.
Gate authority remains in Mission Control.
```

> **Runtime executes. Adapter translates. Application evidences. Repository persists. Core decides.**
