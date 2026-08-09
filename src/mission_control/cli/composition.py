"""mcx의 기본 조립 — 텍스트 lane은 Claude, 실행은 Codex.

도그푸딩 드라이버의 조립을 그대로 승계한다 (ADR-0038 §6, 사용자 확정 구조
2026-08-08 — ADR-0036 §1). CLI 플래그로 vendor를 고르는 표면은 없고, 라우팅은
``<state-dir>/config.toml`` 하나로만 들어온다 (ADR-0039 §5). 조회 지점은 이
모듈 하나다 — Phase 7 MCP가 붙어도 늘지 않는다 (§6).

정책 세트는 각 도메인의 v1 기본값이다. 정책을 표면에서 조정하는 옵션은
요구되기 전까지 만들지 않는다.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import dataclasses
from dataclasses import dataclass, field
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
from mission_control.adapters.text.codex_completion import CodexCompletion
from mission_control.adapters.text.completion_engine import CompletionEngine
from mission_control.adapters.text.mechanical_detector import PromptedMechanicalDetector
from mission_control.adapters.text.semantic_evaluator import PromptedSemanticEvaluator
from mission_control.adapters.verification.local_mechanical_runner import (
    LocalMechanicalRunner,
)
from mission_control.adapters.verification.mechanical_detection import (
    VerifiedMechanicalDetector,
)
from mission_control.adapters.workspace.checkpoint import GitCheckpointRecorder
from mission_control.adapters.workspace.rollback import GitRollback
from mission_control.application.blueprint_service import BlueprintService
from mission_control.application.brief_service import BriefService
from mission_control.application.execute_service import ExecuteService
from mission_control.application.ports import ExecutionRuntime, MechanicalRunner
from mission_control.application.recover_service import RecoverService
from mission_control.application.verify_service import VerifyService
from mission_control.cli.backend_profile import BackendProfile, load_codex_profile
from mission_control.cli.routing import STAGE_LANES, Lane, RoutingConfigError, load_routing
from mission_control.domain.blueprint.qa import QaPolicy
from mission_control.domain.brief.clarity import ClarityPolicy
from mission_control.domain.execute.state import CapabilityEnvelope
from mission_control.domain.recover.packet import RecoverPolicy
from mission_control.domain.stage import Stage
from mission_control.domain.verify.verdict import SemanticPolicy

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()
SEMANTIC_POLICY = SemanticPolicy.verify_v1()
RECOVER_POLICY = RecoverPolicy.recover_v1()

#: Execute worker에게 허용하는 도구. 도그푸딩 0001·0002와 동일하다.
EXECUTE_ALLOWED_TOOLS = ("edit", "shell")


#: 텍스트 lane에 등록된 backend. 이름은 ``CompletionEngine.backend``와 같다.
TEXT_BACKENDS: Mapping[str, Callable[[], CompletionEngine]] = {
    "claude": ClaudeCompletion,
    "codex": CodexCompletion,
}

#: 실행 lane에 등록된 backend. 이름은 ``ExecutionRuntime.backend``와 같고
#: vendor가 아니라 vendor×전송이다 (ADR-0039 §7) — OpenCode adapter가 들어올
#: 자리는 여기 한 줄이며, 그때 기존 코드는 바뀌지 않는다.
EXECUTION_BACKENDS: Mapping[str, Callable[[], ExecutionRuntime]] = {
    "codex_cli": CodexExecutionRuntime,
}

_REGISTERED: Mapping[Lane, frozenset[str]] = {
    Lane.TEXT: frozenset(TEXT_BACKENDS),
    Lane.EXECUTION: frozenset(EXECUTION_BACKENDS),
}


@dataclass(frozen=True)
class Adapters:
    """vendor 실물 묶음 — 테스트와 대체 조립의 단일 주입점.

    ``completion``·``runtime``은 라우팅이 아무 말도 하지 않을 때 쓰는 조립
    기본값이고, ``routed_*``는 Stage별로 다르게 해석된 것만 담는다. 즉 3단
    해석의 마지막 단이 이 두 필드다 (ADR-0039 §3).
    """

    completion: CompletionEngine
    runtime: ExecutionRuntime
    runner: MechanicalRunner
    routed_completion: Mapping[Stage, CompletionEngine] = field(default_factory=dict)
    routed_runtime: Mapping[Stage, ExecutionRuntime] = field(default_factory=dict)

    def completion_for(self, stage: Stage) -> CompletionEngine:
        _require_lane(stage, Lane.TEXT)
        return self.routed_completion.get(stage, self.completion)

    def runtime_for(self, stage: Stage) -> ExecutionRuntime:
        _require_lane(stage, Lane.EXECUTION)
        return self.routed_runtime.get(stage, self.runtime)


def _require_lane(stage: Stage, lane: Lane) -> None:
    """Stage가 쓰지 않는 lane 조회는 조용한 기본값이 아니라 오류다 (§2)."""
    if lane not in STAGE_LANES[stage]:
        raise RoutingConfigError(
            f"{stage.value} Stage는 {lane.value} lane을 쓰지 않는다 — 조회 자체가 오류다"
        )


def default_adapters() -> Adapters:
    return Adapters(
        completion=ClaudeCompletion(),
        runtime=CodexExecutionRuntime(),
        runner=LocalMechanicalRunner(),
    )


def routed_adapters(
    state_dir: Path, base: Adapters | None = None, *, codex_config: Path | None = None
) -> Adapters:
    """``config.toml``을 읽어 Stage별 backend를 확정한다 — 조회 지점 하나 (§6).

    설정이 없으면 ``base``가 그대로 쓰인다. 설정이 있는데 읽히지 않으면
    :class:`RoutingConfigError`가 올라간다 — 조용한 fallback은 없다 (§4).

    ``codex_config``는 모델 seeding 원천이며 기본은 ``None``(seeding 없음)이다.
    실행 진입점만 실물 경로를 넘긴다 — 라이브러리 호출이 사용자 홈을 조용히
    읽지 않게 한다 (ADR-0042 §6).
    """
    adapters = base if base is not None else default_adapters()
    table = load_routing(state_dir, known=_REGISTERED)
    profile = load_codex_profile(state_dir, codex_config=codex_config)

    completion: dict[Stage, CompletionEngine] = {}
    runtime: dict[Stage, ExecutionRuntime] = {}
    for stage, lanes in STAGE_LANES.items():
        if Lane.TEXT in lanes:
            name = table.backend(stage, Lane.TEXT)
            if name is not None:
                completion[stage] = TEXT_BACKENDS[name]()
        if Lane.EXECUTION in lanes:
            name = table.backend(stage, Lane.EXECUTION)
            if name is not None:
                runtime[stage] = _profiled(EXECUTION_BACKENDS[name](), profile)
    return dataclasses.replace(
        adapters,
        runtime=_profiled(adapters.runtime, profile),
        routed_completion=completion,
        routed_runtime=runtime,
    )


def _profiled(runtime: ExecutionRuntime, profile: BackendProfile) -> ExecutionRuntime:
    """설정 파일의 모델을 실행 runtime에 얹는다 (ADR-0042 §6).

    codex가 아닌 runtime(테스트 fake, 이후의 다른 vendor)은 그대로 지난다 —
    모델 축은 vendor마다 이름이 다르므로 공통 port에 올리지 않는다.
    """
    if not profile or not isinstance(runtime, CodexExecutionRuntime):
        return runtime
    return runtime.with_model(profile.model, profile.reasoning_effort)


@dataclass(frozen=True)
class StateLayout:
    """``--state-dir`` 아래의 고정 배치 (ADR-0038 §6).

    ``config.toml``은 ``state/``·``outputs/``와 같은 층에 둔다 (ADR-0039 §5) —
    운용자 입력이지 mission 상태가 아니다.

    ``worktrees/``도 같은 층이다 (ADR-0045 §1). upstream은 ``worktree_root``를
    별도 config 키로 두지만 우리에겐 상태 루트가 이미 하나 있다.
    """

    root: Path
    state: Path
    outputs: Path
    worktrees: Path

    @classmethod
    def under(cls, state_dir: Path) -> StateLayout:
        return cls(
            root=state_dir,
            state=state_dir / "state",
            outputs=state_dir / "outputs",
            worktrees=state_dir / "worktrees",
        )


def mission_repository(layout: StateLayout) -> FileMissionRepository:
    return FileMissionRepository(root=layout.state)


def brief_service(layout: StateLayout, adapters: Adapters) -> BriefService:
    completion = adapters.completion_for(Stage.BRIEF)
    return BriefService(
        repository=FileBriefRepository(root=layout.state),
        question_generator=PromptedQuestionGenerator(completion=completion),
        clarity_assessor=PromptedClarityAssessor(
            completion=completion, policy_version=BRIEF_POLICY.version
        ),
        closure_assessor=PromptedClosureAssessor(completion=completion),
        closure_challenger=PromptedClosureChallenger(completion=completion),
        policy=BRIEF_POLICY,
    )


def blueprint_service(
    layout: StateLayout, adapters: Adapters, *, workspace: str | None = None
) -> BlueprintService:
    completion = adapters.completion_for(Stage.BLUEPRINT)
    return BlueprintService(
        briefs=FileBriefRepository(root=layout.state),
        brief_policy=BRIEF_POLICY,
        repository=FileBlueprintRepository(root=layout.state),
        generator=PromptedBlueprintGenerator(completion=completion),
        qa_judge=PromptedBlueprintQaJudge(completion=completion),
        qa_policy=QA_POLICY,
        # 검증을 건너뛸 수 없게 조립한다 — 제안기를 직접 주지 않고, 디스크
        # 대조를 품은 detector를 준다 (ADR-0044 §3).
        detector=VerifiedMechanicalDetector(
            proposer=PromptedMechanicalDetector(completion=completion)
        ),
        workspace=workspace,
    )


def execute_service(
    layout: StateLayout,
    adapters: Adapters,
    *,
    workspace: str,
    stage: Stage = Stage.EXECUTE,
) -> ExecuteService:
    """``stage``는 실행 lane의 라우팅 키다 — Recover의 재투입은 Recover 행이다."""
    return ExecuteService(
        briefs=FileBriefRepository(root=layout.state),
        blueprints=FileBlueprintRepository(root=layout.state),
        repository=FileExecuteRepository(root=layout.state),
        runtime=adapters.runtime_for(stage),
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
        evaluator=PromptedSemanticEvaluator(completion=adapters.completion_for(Stage.VERIFY)),
        policy=SEMANTIC_POLICY,
        # 입증된 변경을 미션 브랜치에 고정한다 (ADR-0046).
        checkpoints=GitCheckpointRecorder(),
    )


def recover_service(layout: StateLayout, adapters: Adapters, *, workspace: str) -> RecoverService:
    return RecoverService(
        briefs=FileBriefRepository(root=layout.state),
        blueprints=FileBlueprintRepository(root=layout.state),
        executes=FileExecuteRepository(root=layout.state),
        verifies=FileVerifyRepository(root=layout.state),
        execute=execute_service(layout, adapters, workspace=workspace, stage=Stage.RECOVER),
        semantic_policy=SEMANTIC_POLICY,
        policy=RECOVER_POLICY,
        # 재투입 전에 잔해를 지운다 (ADR-0047).
        rollback=GitRollback(),
    )
