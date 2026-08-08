"""fake 자리에 Codex adapter를 끼워도 Core는 한 줄도 바뀌지 않는다.

ExecuteService는 ScriptedRuntime 대신 CodexExecutionRuntime(stub CLI)을 받아
같은 계약으로 돈다 — runtime-neutral Core의 첫 실증이다 (ADR-0003, ADR-0033).

계약: docs/adr/0033-first-runtime-adapter-contract.md Verification
"""

from pathlib import Path
import stat
import sys
import textwrap

from mission_control.adapters.persistence.file_blueprint_repository import (
    FileBlueprintRepository,
)
from mission_control.adapters.persistence.file_brief_repository import FileBriefRepository
from mission_control.adapters.persistence.file_execute_repository import (
    FileExecuteRepository,
)
from mission_control.adapters.runtime.codex_execution_runtime import CodexExecutionRuntime
from mission_control.application.execute_service import ExecuteService
from mission_control.domain.blueprint.qa import QaAssessment, QaPolicy
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.brief.clarity import (
    ClarityAssessment,
    ClarityPolicy,
    DimensionScore,
)
from mission_control.domain.brief.closure import (
    AdvisoryLane,
    AdvisoryReport,
    CloserReport,
    CloserVerdict,
    ClosureAudit,
    ClosureSeverity,
)
from mission_control.domain.brief.state import BriefState
from mission_control.domain.execute.state import AttemptStatus, CapabilityEnvelope

BRIEF_POLICY = ClarityPolicy.greenfield_v1()
QA_POLICY = QaPolicy.blueprint_v1()

CRITERION = AcceptanceCriterion(description="목록에 댓글이 보인다", verify_command="pytest -k list")

STUB = """
    import sys
    arguments = sys.argv[1:]
    last_message_path = arguments[arguments.index("--output-last-message") + 1]
    sys.stdin.read()
    print('{"type": "thread.started", "thread_id": "th-e2e"}')
    with open(last_message_path, "w") as handle:
        handle.write("구현 완료")
    sys.exit(0)
"""


def _write_stub(directory: Path) -> str:
    script = directory / "codex-stub.py"
    script.write_text(textwrap.dedent(STUB), encoding="utf-8")
    launcher = directory / "codex-stub"
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)
    return str(launcher)


def _cleared_brief() -> BriefState:
    state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    state = state.record_answer(
        question="누가 쓰나요?", answer="로그인 사용자", authority="decision"
    )
    state = state.record_answer(
        question="완료 확인은?", answer="목록에 보이면", authority="decision"
    )
    assessment = ClarityAssessment(
        scores=(
            DimensionScore(dimension="goal", clarity=0.9, justification="t"),
            DimensionScore(dimension="constraint", clarity=0.9, justification="t"),
            DimensionScore(dimension="success_criteria", clarity=0.9, justification="t"),
        ),
        policy_version=BRIEF_POLICY.version,
    )
    for _ in range(BRIEF_POLICY.required_stability):
        state = state.record_assessment(assessment=assessment, policy=BRIEF_POLICY)
    audit = ClosureAudit(
        closer=CloserReport(verdict=CloserVerdict.READY, reason="nothing material remains"),
        contrarian=AdvisoryReport(
            lane=AdvisoryLane.CONTRARIAN, severity=ClosureSeverity.LOW, finding="minor"
        ),
        gap_hunter=AdvisoryReport(
            lane=AdvisoryLane.GAP_HUNTER, severity=ClosureSeverity.LOW, finding="minor"
        ),
    )
    return state.record_closure_audit(audit=audit).approve(statement="이대로 진행")


async def test_the_real_adapter_slots_in_without_touching_the_core(
    tmp_path: Path,
) -> None:
    store, workspace = tmp_path / "store", tmp_path / "workspace"
    workspace.mkdir()
    brief = _cleared_brief()
    await FileBriefRepository(root=store).save(brief)
    blueprint = Blueprint(
        mission_id="m-1",
        revision=1,
        brief_revision=brief.revision,
        goal="댓글 기능",
        acceptance_criteria=(CRITERION,),
    )
    blueprint_state = BlueprintState.start(blueprint=blueprint).record_qa(
        assessment=QaAssessment(score=0.92), policy=QA_POLICY
    )
    await FileBlueprintRepository(root=store).save(
        blueprint_state.approve(statement="이대로 진행", policy=QA_POLICY)
    )

    service = ExecuteService(
        briefs=FileBriefRepository(root=store),
        blueprints=FileBlueprintRepository(root=store),
        repository=FileExecuteRepository(root=store),
        runtime=CodexExecutionRuntime(cli_path=_write_stub(tmp_path)),
        envelope=CapabilityEnvelope(workspace=str(workspace), allowed_tools=("edit",)),
    )

    state = await service.dispatch_next(mission_id="m-1")

    attempt = state.attempts[-1]
    assert attempt.status is AttemptStatus.EXECUTED_UNVERIFIED
    assert attempt.runtime_backend == "codex_cli"
    assert attempt.native_session_id == "th-e2e"
    assert attempt.result_summary == "구현 완료"
