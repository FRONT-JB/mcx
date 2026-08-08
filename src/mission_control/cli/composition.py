"""mcx의 기본 조립 — 텍스트 lane은 Claude, 실행은 Codex.

도그푸딩 드라이버의 조립을 그대로 승계한다 (ADR-0038 §6, 사용자 확정 구조
2026-08-08 — ADR-0036 §1). vendor 선택 표면(플래그·설정 파일)은 없다 — 대체
조립은 이 모듈의 ``Adapters`` 주입으로만 표현된다.

정책 세트는 각 도메인의 v1 기본값이다. 정책을 표면에서 조정하는 옵션은
요구되기 전까지 만들지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mission_control.adapters.persistence.file_blueprint_repository import (
    FileBlueprintRepository,
)
from mission_control.adapters.persistence.file_brief_repository import FileBriefRepository
from mission_control.adapters.persistence.file_execute_repository import (
    FileExecuteRepository,
)
from mission_control.adapters.persistence.file_mission_repository import (
    FileMissionRepository,
)
from mission_control.adapters.persistence.file_verify_repository import (
    FileVerificationOutputStore,
    FileVerifyRepository,
)
from mission_control.adapters.runtime.codex_execution_runtime import CodexExecutionRuntime
from mission_control.adapters.text.blueprint_backends import (
    PromptedBlueprintGenerator,
    PromptedBlueprintQaJudge,
)
from mission_control.adapters.text.brief_backends import (
    PromptedClarityAssessor,
    PromptedClosureAssessor,
    PromptedClosureChallenger,
    PromptedQuestionGenerator,
)
from mission_control.adapters.text.claude_completion import ClaudeCompletion
from mission_control.adapters.text.completion_engine import CompletionEngine
from mission_control.adapters.text.semantic_evaluator import PromptedSemanticEvaluator
from mission_control.adapters.verification.local_mechanical_runner import (
    LocalMechanicalRunner,
)
from mission_control.application.blueprint_service import BlueprintService
from mission_control.application.brief_service import BriefService
from mission_control.application.execute_service import ExecuteService
from mission_control.application.ports import ExecutionRuntime, MechanicalRunner
from mission_control.application.recover_service import RecoverService
from mission_control.application.verify_service import VerifyService
from mission_control.domain.blueprint.qa import QaPolicy
from mission_control.domain.brief.clarity import ClarityPolicy
from mission_control.domain.execute.state import CapabilityEnvelope
from mission_control.domain.recover.packet import RecoverPolicy
from mission_control.domain.verify.verdict import SemanticPolicy

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()
SEMANTIC_POLICY = SemanticPolicy.verify_v1()
RECOVER_POLICY = RecoverPolicy.recover_v1()

#: Execute worker에게 허용하는 도구. 도그푸딩 0001·0002와 동일하다.
EXECUTE_ALLOWED_TOOLS = ("edit", "shell")


@dataclass(frozen=True)
class Adapters:
    """vendor 실물 묶음 — 테스트와 대체 조립의 단일 주입점."""

    completion: CompletionEngine
    runtime: ExecutionRuntime
    runner: MechanicalRunner


def default_adapters() -> Adapters:
    return Adapters(
        completion=ClaudeCompletion(),
        runtime=CodexExecutionRuntime(),
        runner=LocalMechanicalRunner(),
    )


@dataclass(frozen=True)
class StateLayout:
    """``--state-dir`` 아래의 고정 배치 (ADR-0038 §6)."""

    state: Path
    outputs: Path

    @classmethod
    def under(cls, state_dir: Path) -> StateLayout:
        return cls(state=state_dir / "state", outputs=state_dir / "outputs")


def mission_repository(layout: StateLayout) -> FileMissionRepository:
    return FileMissionRepository(root=layout.state)


def brief_service(layout: StateLayout, adapters: Adapters) -> BriefService:
    return BriefService(
        repository=FileBriefRepository(root=layout.state),
        question_generator=PromptedQuestionGenerator(completion=adapters.completion),
        clarity_assessor=PromptedClarityAssessor(
            completion=adapters.completion, policy_version=BRIEF_POLICY.version
        ),
        closure_assessor=PromptedClosureAssessor(completion=adapters.completion),
        closure_challenger=PromptedClosureChallenger(completion=adapters.completion),
        policy=BRIEF_POLICY,
    )


def blueprint_service(layout: StateLayout, adapters: Adapters) -> BlueprintService:
    return BlueprintService(
        briefs=FileBriefRepository(root=layout.state),
        brief_policy=BRIEF_POLICY,
        repository=FileBlueprintRepository(root=layout.state),
        generator=PromptedBlueprintGenerator(completion=adapters.completion),
        qa_judge=PromptedBlueprintQaJudge(completion=adapters.completion),
        qa_policy=QA_POLICY,
    )


def execute_service(layout: StateLayout, adapters: Adapters, *, workspace: str) -> ExecuteService:
    return ExecuteService(
        briefs=FileBriefRepository(root=layout.state),
        blueprints=FileBlueprintRepository(root=layout.state),
        repository=FileExecuteRepository(root=layout.state),
        runtime=adapters.runtime,
        envelope=CapabilityEnvelope(workspace=workspace, allowed_tools=EXECUTE_ALLOWED_TOOLS),
    )


def verify_service(layout: StateLayout, adapters: Adapters) -> VerifyService:
    return VerifyService(
        briefs=FileBriefRepository(root=layout.state),
        blueprints=FileBlueprintRepository(root=layout.state),
        executes=FileExecuteRepository(root=layout.state),
        repository=FileVerifyRepository(root=layout.state),
        runner=adapters.runner,
        outputs=FileVerificationOutputStore(root=layout.outputs),
        evaluator=PromptedSemanticEvaluator(completion=adapters.completion),
        policy=SEMANTIC_POLICY,
    )


def recover_service(layout: StateLayout, adapters: Adapters, *, workspace: str) -> RecoverService:
    return RecoverService(
        briefs=FileBriefRepository(root=layout.state),
        blueprints=FileBlueprintRepository(root=layout.state),
        executes=FileExecuteRepository(root=layout.state),
        verifies=FileVerifyRepository(root=layout.state),
        execute=execute_service(layout, adapters, workspace=workspace),
        semantic_policy=SEMANTIC_POLICY,
        policy=RECOVER_POLICY,
    )
