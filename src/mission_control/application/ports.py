"""Core가 외부에 요구하는 계약.

application은 구체 adapter가 아니라 이 port에 의존한다. 저장 매체나 Runtime이
바뀌어도 use case가 바뀌지 않아야 하기 때문이다
(``docs/01_ARCHITECTURE.md`` §6.4, §7.1).

port는 ``async``로 정의한다. Phase 1의 파일 구현은 그 안에서 동기 I/O를
호출하지만, Phase 3 이후 구현이 subprocess와 네트워크를 다루게 되어도 시그니처가
바뀌지 않는다 (``docs/adr/0012-python-toolchain-and-layout.md``).
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mission_control.domain.blueprint.assembly import BlueprintDraft
from mission_control.domain.blueprint.qa import QaAssessment, QaFinding
from mission_control.domain.blueprint.spec import AcceptanceCriterion
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.brief.clarity import ClarityAssessment, ClarityDimension
from mission_control.domain.brief.closure import (
    AdvisoryLane,
    AdvisoryReport,
    CloserReport,
)
from mission_control.domain.brief.requirement import (
    CandidateResolution,
    RequirementSection,
)
from mission_control.domain.brief.state import BriefState
from mission_control.domain.execute.state import ExecuteState
from mission_control.domain.mechanical import MechanicalCommands
from mission_control.domain.recover.packet import PreviousFailure
from mission_control.domain.verify.evidence import (
    CommandExecution,
    VerificationRun,
    VerifyState,
)
from mission_control.domain.verify.verdict import CriterionVerdict


class BriefRepository(Protocol):
    """Brief 상태의 durable 저장소.

    구현은 다음을 보장해야 한다.

    - 부분 기록된 상태가 읽히지 않는다.
    - 저장된 것보다 앞서지 않는 쓰기를 거부한다
      (:class:`~mission_control.domain.errors.StaleWriteError`).
    - 저장 실패를 성공으로 가장하지 않는다. 실패는 예외로 드러나며, 호출자는
      이를 전이 실패로 처리한다 (``docs/05_BRIEF.md`` §15).
    """

    async def load(self, mission_id: str) -> BriefState | None:
        """저장된 Brief를 반환한다. 없으면 ``None``."""
        ...

    async def save(self, state: BriefState) -> None:
        """Brief를 durable하게 기록한다.

        저장이 성공적으로 끝나기 전에는 호출자가 전이 완료를 보고해서는 안 된다.
        """
        ...


class BlueprintRepository(Protocol):
    """Blueprint 상태의 durable 저장소.

    :class:`BriefRepository`와 같은 보장을 요구한다 — 부분 기록된 상태가 읽히지
    않고, 저장된 것보다 앞서지 않는 쓰기를 거부하며
    (:class:`~mission_control.domain.errors.StaleWriteError`), 저장 실패를
    성공으로 가장하지 않는다.

    revision·QA 기록·승인이 한 문서에 함께 저장되어야 한다. 나뉘어 있으면
    "Seed는 저장되고 approval만 유실"된 상태가 가능해지고, 그 상태를 ``CLEAR``로
    오인하지 않는다는 보장을 저장 계층이 줄 수 없다
    (``docs/06_BLUEPRINT.md`` §12, ADR-0021 §1).
    """

    async def load(self, mission_id: str) -> BlueprintState | None:
        """저장된 Blueprint 상태를 반환한다. 없으면 ``None``."""
        ...

    async def save(self, state: BlueprintState) -> None:
        """Blueprint 상태를 durable하게 기록한다.

        저장이 성공적으로 끝나기 전에는 호출자가 전이 완료를 보고해서는 안 된다.
        """
        ...


class ExecuteRepository(Protocol):
    """Execute 상태의 durable 저장소. :class:`BriefRepository`와 같은 보장이다.

    attempt는 dispatch **전에** 저장되어야 한다 (ADR-0024 §4). 저장이
    실패하면 dispatch는 일어나지 않은 것이다.
    """

    async def load(self, mission_id: str) -> ExecuteState | None:
        """저장된 Execute 상태를 반환한다. 없으면 ``None``."""
        ...

    async def save(self, state: ExecuteState) -> None:
        """Execute 상태를 durable하게 기록한다."""
        ...


class ExecutionRequest(BaseModel):
    """AC 하나를 실행하기 위한 bounded 입력.

    승인된 Blueprint의 칸들만 담는다 — 대화 원문도 Brief 상태도 넘기지
    않는다. 제약과 Non-goal은 실행의 경계이고, criterion은 무엇을 만들었다고
    인정할 것인가의 계약이다. ``workspace``와 ``allowed_tools``는 capability
    envelope다 (ADR-0024 §6) — v1에서는 전달·기록까지가 강제 범위이고 실제
    차단은 concrete adapter(Phase 5)가 한다.
    """

    model_config = ConfigDict(frozen=True)

    goal: str
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]
    criterion: AcceptanceCriterion
    workspace: str
    allowed_tools: tuple[str, ...]
    #: 교정 재시도가 가지고 가는 이전 실패 (ADR-0031 §5). 첫 실행에는 없고
    #: Recover 경로에서만 채워진다 — "같은 prompt의 반복"을 막는 장치다.
    previous_failure: PreviousFailure | None = None


class ExecutionOutcome(BaseModel):
    """한 번의 실행 결과.

    성공은 "실행이 끝났다"이지 "AC가 충족됐다"가 아니다 — 충족 판정은
    Verify의 것이다. 실패에는 이유가 필수다. 이유 없는 실패는 Verify와
    Recover가 판정할 재료가 없다.
    """

    model_config = ConfigDict(frozen=True)

    succeeded: bool
    native_session_id: str | None = None
    result_summary: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _error_matches_the_outcome(self) -> ExecutionOutcome:
        if self.succeeded and self.error is not None:
            raise ValueError("a successful outcome cannot carry an error")
        if not self.succeeded and not self.error:
            raise ValueError("a failed outcome requires an error")
        return self


class ExecutionRuntime(Protocol):
    """AC 하나를 실행하는 Runtime Adapter의 계약.

    adapter는 use case가 구성한 요청만 실행하며 **스스로 작업을 만들지
    않는다** (ADR-0023 §1). Mission Control 재귀 호출 수단이 없다
    (ADR-0004). 실행 실패는 예외 또는 ``succeeded=False`` outcome으로
    드러나며, 어느 쪽도 결과를 지어내지 않는다.

    ``backend``는 provenance의 실행 주체 항목에 그대로 기록된다.
    """

    @property
    def backend(self) -> str:
        """이 adapter의 runtime backend 이름 (예: ``fake``, ``codex_cli``)."""
        ...

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        """요청된 AC 하나를 실행하고 결과를 반환한다."""
        ...


class VerifyRepository(Protocol):
    """Verify 상태의 durable 저장소. :class:`BriefRepository`와 같은 보장이다."""

    async def load(self, mission_id: str) -> VerifyState | None:
        """저장된 Verify 상태를 반환한다. 없으면 ``None``."""
        ...

    async def save(self, state: VerifyState) -> None:
        """Verify 상태를 durable하게 기록한다."""
        ...


class MechanicalRunner(Protocol):
    """검증 명령을 실제로 실행하는 adapter의 계약 (ADR-0028 §3).

    실행 대상 명령은 항상 use case가 승인된 Blueprint에서 읽어 전달한다 —
    이 port에 명령을 공급하는 다른 경로는 없다 (ADR-0028 §2). artifacts
    검사가 명령 실행보다 먼저인 순서는 use case가 지킨다.
    """

    async def missing_artifacts(
        self, *, workspace: str, artifacts: tuple[str, ...]
    ) -> tuple[str, ...]:
        """workspace 아래 존재하지 않는 artifact 경로 전부를 반환한다."""
        ...

    async def run(self, *, command: str, workspace: str, timeout_seconds: int) -> CommandExecution:
        """명령을 shell로 실행하고 합류(stdout+stderr) 출력을 반환한다.

        timeout 초과 시 프로세스(그룹)를 정리하고 ``timed_out=True``로
        반환한다 — 예외가 아니다. 시작 자체가 불가능한 경우만 예외다.
        """
        ...


class VerificationOutputStore(Protocol):
    """검증 명령의 원문 출력을 상태 문서 밖에 보존한다 (ADR-0028 §4).

    상태에는 여기서 돌려준 참조만 남는다 — 큰 출력이 mission 상태 문서를
    오염시키지 않게 하는 upstream의 파일 트리 배치와 같다.
    """

    async def preserve(self, *, mission_id: str, sequence: int, ac_key: str, content: str) -> str:
        """출력을 보존하고 참조 문자열을 반환한다."""
        ...


class SemanticEvaluationRequest(BaseModel):
    """AC 하나의 semantic 판정을 위한 bounded 입력 (ADR-0030 §3).

    upstream 프롬프트 계약과 같은 축이다 — AC(성공 계약 포함), 방향 필드,
    그리고 **mechanical 증거**. worker의 ``result_summary``는 여기에도 없다
    (ADR-0028 §1과 같은 이유) — 평가자가 근거로 삼을 수 있는 것은 계약과
    직접 실행된 증거뿐이다.
    """

    model_config = ConfigDict(frozen=True)

    goal: str
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]
    criterion: AcceptanceCriterion
    #: 판정 대상 작업물이 있는 곳. 평가자는 이 안에서 읽기 전용으로
    #: 관찰한다 — 실물 스모크에서 이 필드 없이는 평가자가 엉뚱한 디렉토리를
    #: 검사함이 관측되었다 (2026-08-08, ADR-0034 정정).
    workspace: str = Field(min_length=1)
    #: 이 AC의 mechanical 검증 기록. 성공 계약이 없는 AC는 ``None``.
    mechanical_run: VerificationRun | None = None


class SemanticEvaluator(Protocol):
    """AC 충족을 판정하는 평가자의 계약 (ADR-0030 §3).

    반환하는 verdict의 ``ac_key``는 요청된 criterion의 key와 일치해야 한다 —
    use case가 불일치를 거부한다. Phase 5 전까지 구현은 결정적 test double
    이다.
    """

    async def assess(self, request: SemanticEvaluationRequest) -> CriterionVerdict:
        """요청된 AC 하나를 판정한다."""
        ...


class AskedRound(BaseModel):
    """위임 역할에 전달하는 이전 대화 한 턴.

    저장된 ``BriefRound``를 그대로 넘기지 않는다. 위임받은 역할은 답변의
    authority나 revision 이력을 알 필요가 없고, 알면 그것을 근거로 요구사항을
    지어낼 수 있다.
    """

    model_config = ConfigDict(frozen=True)

    question: str
    answer: str | None


class RequirementView(BaseModel):
    """요구사항 후보 하나의 위임용 투영 — 확정 여부와 무관하게 전부 전달된다.

    미확정만 전달하던 초기 투영은 이미 결정된 사안을 위임 역할이 다시
    차단하게 만들었다 (도그푸딩 0001 §3.1·§3.2). upstream 감사는 main 세션의
    전체 관점에서 수행되므로 확정 결정이 보인다 — 같은 가시성을 준다
    (ADR-0035 §1). 무엇이 열려 있고 무엇이 닫혔는지는 ``resolution``이
    구분한다.

    확인 권위는 여전히 전달하지 않는다 — 그것은 승격 판정의 재료이지 질문의
    재료가 아니며, 알려 주면 그것을 근거로 스스로 확정했다고 판단할 여지가
    생긴다 (ADR-0015).
    """

    model_config = ConfigDict(frozen=True)

    section: RequirementSection
    text: str
    resolution: CandidateResolution
    required: bool


class QuestionRequest(BaseModel):
    """질문 하나를 생성하기 위해 필요한 최소 context.

    Mission Control이 선별해서 전달한다. 파일 경로, 도구 목록, 자격 증명 같은
    실행 수단은 담기지 않는다. 질문 생성 역할은 저장소를 조사하지 않으며 필요한
    사실은 별도의 read-only 경로가 제공한다 (``docs/05_BRIEF.md`` §4.3, §4.4).
    """

    model_config = ConfigDict(frozen=True)

    initial_intent: str
    previous_rounds: tuple[AskedRound, ...]
    requirement_candidates: tuple[RequirementView, ...]


class GeneratedQuestion(BaseModel):
    """생성기가 반환하는 질문 하나와 그 질문이 겨냥한 gap.

    구조적으로 하나만 담는다. 여러 질문을 한 번에 던지면 사용자가 일부만 답하고,
    어느 답이 어느 질문의 것인지 알 수 없게 된다.
    """

    model_config = ConfigDict(frozen=True)

    question: str
    targeted_gap: str


class QuestionGenerator(Protocol):
    """한 번의 dispatch에서 질문 하나를 생성하는 제한된 역할.

    이 port에는 파일 쓰기, Shell, Git, 네트워크, Mission Control 재귀 호출 수단이
    없다. 계약을 프롬프트 문구가 아니라 시그니처로 강제하기 위해서다
    (``docs/adr/0004-stage-scoped-minimum-capability.md``).

    Phase 1의 강제 범위는 여기까지다. 실제 runtime에서 도구를 차단하는 것은
    Runtime Adapter를 도입할 때 함께 다룬다.
    """

    async def generate(self, request: QuestionRequest) -> GeneratedQuestion:
        """질문 하나를 반환한다. 호출자는 dispatch당 한 번만 호출한다."""
        ...


class AssessmentRequest(BaseModel):
    """clarity를 평가하기 위해 필요한 최소 context.

    ``dimensions``는 현재 정책이 가중치를 부여한 축이다. 평가자가 임의의 축을
    고르면 집계가 성립하지 않으므로 무엇을 채점해야 하는지 명시한다.

    threshold, floor, weight는 전달하지 않는다. 평가자의 일은 채점이지 판정이
    아니고, 통과 기준을 알려 주면 그 기준에 맞춰 점수를 조정할 여지가 생긴다.
    판정은 :class:`~mission_control.domain.brief.clarity.ClarityPolicy`가 한다.
    """

    model_config = ConfigDict(frozen=True)

    initial_intent: str
    previous_rounds: tuple[AskedRound, ...]
    requirement_candidates: tuple[RequirementView, ...]
    dimensions: tuple[ClarityDimension, ...]


class ClarityAssessor(Protocol):
    """현재 Brief의 축별 clarity를 채점하는 제한된 역할.

    질문 생성과 분리된 port인 이유는 두 역할이 서로를 정당화하지 못하게 하기
    위해서다. 같은 호출이 질문을 만들고 그 결과를 채점하면 "충분히 물었다"는
    판단을 자기 자신이 내린다 (``docs/adr/0004-stage-scoped-minimum-capability.md``).

    평가 실패는 낮은 점수가 아니라 결과 없음이다. 구현은 결과를 추측해 반환하지
    말고 예외를 올린다 (``docs/05_BRIEF.md`` §11.3).
    """

    async def assess(self, request: AssessmentRequest) -> ClarityAssessment:
        """요청된 모든 dimension의 clarity 점수를 반환한다."""
        ...


class CloserAuditRequest(BaseModel):
    """closer lane 하나를 수행하기 위한 최소 context.

    ``gate_summary``는 정책이 정한 upstream 원문 기준이며 수행자가 바꿀 수
    없다. clarity 평가와 마찬가지로 **ambiguity 점수는 전달하지 않는다** —
    upstream은 점수를 주고 "충분조건으로 쓰지 마라"는 경고를 얹지만, 우리는
    anchoring 위험 자체를 제거한다 (ADR-0020 §5, 등록된 divergence).
    """

    model_config = ConfigDict(frozen=True)

    initial_intent: str
    previous_rounds: tuple[AskedRound, ...]
    requirement_candidates: tuple[RequirementView, ...]
    gate_summary: str


class ClosureAssessor(Protocol):
    """closure gate 기준으로 종료 가능 여부를 판정하는 제한된 역할 (closer).

    verdict를 반환하는 것이 다른 평가 port와 다른 이유는 ADR-0020 §8에 있다 —
    이 판단에는 숨길 통과선이 없다. 판정("구현을 실질적으로 바꿀 미해결 결정이
    있는가") 자체가 이 역할의 일이다.

    이 port에는 파일 쓰기, Shell, Git, 네트워크가 없다. 감사 실패는 결과
    없음이다 — 추측한 verdict를 반환하지 말고 예외를 올린다.
    """

    async def audit(self, request: CloserAuditRequest) -> CloserReport:
        """closure 판정과, 차단 시 가장 임팩트 큰 후속 질문을 반환한다."""
        ...


class ClosureChallengeRequest(BaseModel):
    """advisory lane 하나(contrarian 또는 gap_hunter)를 수행하기 위한 입력.

    ``challenge``와 ``severity_rule``은 정책이 정한 upstream 원문이다. 같은
    port가 lane마다 다른 과제로 두 번 불리므로, 어느 관점을 요청받았는지가
    요청에 명시된다.
    """

    model_config = ConfigDict(frozen=True)

    lane: AdvisoryLane
    challenge: str
    severity_rule: str
    initial_intent: str
    previous_rounds: tuple[AskedRound, ...]
    requirement_candidates: tuple[RequirementView, ...]


class ClosureChallenger(Protocol):
    """지정된 관점으로 종료 결론을 공격하는 제한된 역할.

    판정력이 없다 — 반환한 finding은 HIGH 심각도일 때만 차단하며, 그 규칙은
    port가 아니라 결정적 합성이 정한다
    (:attr:`~mission_control.domain.brief.closure.ClosureAudit.decision`).
    closer와 분리된 port인 이유는 관점 공격이 판정을 겸하면 자기 공격의
    성패를 자기가 정하기 때문이다.
    """

    async def challenge(self, request: ClosureChallengeRequest) -> AdvisoryReport:
        """요청된 lane의 finding과 심각도를 반환한다."""
        ...


class BlueprintGenerationRequest(BaseModel):
    """Blueprint 초안 하나를 만들기 위한 입력.

    **승인된 handoff의 칸들만 전달한다.** 대화 원문도, 관찰 사실도, revision
    이력도 넘기지 않는다. 생성기가 대화를 다시 읽을 수 있으면 Brief에서 합의되지
    않은 것을 요구사항으로 되살릴 수 있고, 그것이 handoff를 둔 이유를 없앤다
    (``docs/adr/0016-brief-handoff-projection.md``).

    ``context``는 예외다. 관찰된 현재 상태는 요구사항이 아니라 성공 조건을
    확인 가능하게 만드는 재료다 — 어떤 명령으로 무엇을 확인할지 정하려면 지금
    무엇이 있는지 알아야 한다.
    """

    model_config = ConfigDict(frozen=True)

    goals: tuple[str, ...]
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]
    success_criteria: tuple[str, ...]
    context: tuple[str, ...]


class BlueprintGenerator(Protocol):
    """성공 조건을 확인 가능한 계약으로 구체화하는 제한된 역할.

    생성기의 일은 **구체화**다. 제약과 Non-goal은 사용자가 정한 경계이므로 그대로
    옮기고, 성공 조건 문장에 "무엇을 실행하고 무엇을 확인할 것인가"를 붙인다.

    범위를 벗어난 초안은 조립 단계가 거부한다
    (:func:`~mission_control.domain.blueprint.assembly.check_scope`). 계약을
    프롬프트 문구가 아니라 결정적 검사로 강제하기 위해서다.

    이 port에는 파일 쓰기, Shell, Git, 네트워크가 없다. 확인 명령을 **작성**하는
    것과 **실행**하는 것은 다른 역할이며, 실행은 Verify가 한다.
    """

    async def generate(self, request: BlueprintGenerationRequest) -> BlueprintDraft:
        """초안 하나를 반환한다. lineage와 revision은 담지 않는다."""
        ...


class QaIteration(BaseModel):
    """이전 채점 한 번의 궤적 — upstream QA 프롬프트의 Previous Iterations 행.

    점수와 판정만 담는다. 판정은 정책이 이미 내린 결과의 기록이지 채점자에게
    판정을 위임하는 것이 아니다 (ADR-0019 §3 개정, ADR-0035 §3).
    """

    model_config = ConfigDict(frozen=True)

    iteration: int
    score: float
    verdict: str


class QaRequest(BaseModel):
    """Blueprint 초안 하나를 채점하기 위한 입력.

    ``quality_bar``는 정책이 정한 문장이며 채점자가 바꿀 수 없다. 무엇이 좋은
    명세인지를 채점자가 정하면 기준과 점수가 같은 곳에서 나온다.

    ``pass_threshold``와 ``previous_iterations``는 upstream QA 프롬프트 정렬이다
    (ADR-0035 §3) — 궤적 없는 채점자의 점수 역행·정체가 도그푸딩 0001에서
    관측되었다. 반복 상한은 여전히 전달하지 않는다.

    ``previous_findings``는 직전 채점에서 지적된 항목이다. 같은 지적을 반복하는지,
    고쳐진 것을 다시 지적하는지 채점자가 알 수 있어야 반복이 수렴한다.
    """

    model_config = ConfigDict(frozen=True)

    goal: str
    constraints: tuple[str, ...]
    non_goals: tuple[str, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    quality_bar: str
    pass_threshold: float
    previous_iterations: tuple[QaIteration, ...] = ()
    previous_findings: tuple[QaFinding, ...] = ()


class BlueprintQaJudge(Protocol):
    """주어진 기준으로 Blueprint 초안을 채점하는 제한된 역할.

    생성기와 분리된 port인 이유는 자기 결과를 자기가 채점하지 못하게 하기
    위해서다 (``docs/adr/0004-stage-scoped-minimum-capability.md``).

    채점자는 초안을 고치지 않는다. 지적과 제안만 반환하고, 무엇을 적용할지는
    사용자가 정한다 — 수정이 자동으로 적용되면 사용자가 승인한 적 없는 명세가
    승인 대상이 된다.

    채점 실패는 낮은 점수가 아니다. 결과를 추측해 반환하지 말고 예외를 올린다.
    """

    async def assess(self, request: QaRequest) -> QaAssessment:
        """점수와 지적 사항을 반환한다. 통과 여부는 판정하지 않는다."""
        ...


class MechanicalDetectionRequest(BaseModel):
    """확인 명령을 제안받기 위한 최소 context (ADR-0044 §3).

    manifest 발췌만 준다. workspace 전체를 읽히지 않는 이유는 이 역할이
    "이 프로젝트를 어떻게 확인하는가"만 답하면 되기 때문이며, 넓은 읽기 권한은
    Stage별 최소 capability에 어긋난다
    (``docs/adr/0004-stage-scoped-minimum-capability.md``).
    """

    model_config = ConfigDict(frozen=True)

    workspace: str
    #: (파일 이름, 발췌) 쌍. 비어 있으면 호출 자체를 하지 않는다.
    manifests: tuple[tuple[str, str], ...]


class MechanicalCommandDetector(Protocol):
    """기존 저장소의 확인 명령을 찾아내는 제한된 역할.

    반환 타입이 :class:`MechanicalCommands`인 것이 계약이다 — **디스크 대조를
    통과한 것만** 나온다. 모델의 제안(:class:`ProposedCommands`)은 이 경계
    안쪽에 있고 밖으로 새지 않는다. 제안과 검증을 갈라 두는 이유는 검증을
    건너뛴 명령이 AC에 박히면 Verify가 없는 진입점을 실행하고, 그 실패가 코드의
    문제로 보이기 때문이다 (upstream *"phantom failure"* 금지).

    검출 실패는 예외가 아니라 **빈 결과**다. 확인 명령을 못 찾은 것이 미션을
    죽여서는 안 된다 — upstream도 같다(`ensure_mechanical_toml`은 실패 시
    ``False``를 돌려주고 끝난다).
    """

    async def detect(self, workspace: str) -> MechanicalCommands:
        """확인된 명령만 반환한다. 제안 단계는 이 경계 안쪽에 있다."""
        ...
