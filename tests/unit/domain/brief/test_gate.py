"""Brief Gate — 상태·정책·승인을 함께 평가한 CLEAR/HOLD 판정.

계약: docs/05_BRIEF.md §11.5, §13 / docs/adr/0009-brief-completion-gate-policy.md
Test Matrix: B-012, B-013, B-025, B-030
"""

from mission_control.domain.brief.clarity import (
    ClarityAssessment,
    ClarityPolicy,
    DimensionScore,
)
from mission_control.domain.brief.gate import GateBlockingCondition, evaluate_brief_gate
from mission_control.domain.brief.state import BriefState
from mission_control.domain.stage import Stage

POLICY = ClarityPolicy.greenfield_v1()


def _assessment(
    goal: float = 0.9, constraint: float = 0.9, success: float = 0.9
) -> ClarityAssessment:
    return ClarityAssessment(
        scores=(
            DimensionScore(dimension="goal", clarity=goal, justification="t"),
            DimensionScore(dimension="constraint", clarity=constraint, justification="t"),
            DimensionScore(dimension="success_criteria", clarity=success, justification="t"),
        ),
        policy_version=POLICY.version,
    )


def _answered_brief(rounds: int = 3) -> BriefState:
    state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    for index in range(rounds):
        state = state.record_answer(question=f"q{index}", answer=f"a{index}", authority="decision")
    return state


def _assessed(
    state: BriefState, assessment: ClarityAssessment | None, *, times: int = 1
) -> BriefState:
    """평가를 실제 횟수만큼 반복해 stability signal을 자연스럽게 쌓는다.

    signal을 직접 주입하지 않는 이유는 도달 불가능한 조합(예: 실패한 평가와
    signal 2)을 테스트가 표현하지 못하게 하기 위해서다.
    """
    for _ in range(times):
        state = state.record_assessment(assessment=assessment, policy=POLICY)
    return state


def _ready_brief() -> BriefState:
    """네 조건과 승인을 모두 갖춘 상태."""
    state = _assessed(_answered_brief(), _assessment(), times=POLICY.required_stability)
    return state.approve(statement="이대로 진행해 주세요")


def _conditions(decision: object) -> list[GateBlockingCondition]:
    return [blocker.condition for blocker in decision.gate_blockers]  # type: ignore[attr-defined]


class TestClearRequiresEverything:
    """§13.1 — 모든 조건이 충족되어야 CLEAR다."""

    def test_all_conditions_met_clears_for_blueprint(self) -> None:
        decision = evaluate_brief_gate(state=_ready_brief(), policy=POLICY)

        assert decision.outcome == "CLEAR"
        assert decision.next_destination is Stage.BLUEPRINT
        assert decision.gate_blockers == ()
        assert decision.clarity_blockers == ()

    def test_decision_references_the_evaluated_revision(self) -> None:
        state = _ready_brief()

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.revision == state.revision

    def test_decision_records_policy_version(self) -> None:
        """정책이 바뀌면 과거 판정의 기준을 추적할 수 있어야 한다."""
        decision = evaluate_brief_gate(state=_ready_brief(), policy=POLICY)

        assert decision.policy_version == POLICY.version

    def test_hold_has_no_next_destination(self) -> None:
        state = _assessed(_answered_brief(), _assessment(), times=POLICY.required_stability)

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"
        assert decision.next_destination is None


class TestApprovalIsNecessary:
    """B-013 — 정보가 충분해도 승인이 없으면 진행하지 않는다."""

    def test_missing_approval_holds(self) -> None:
        state = _assessed(_answered_brief(), _assessment(), times=POLICY.required_stability)

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"
        assert GateBlockingCondition.APPROVAL_MISSING in _conditions(decision)

    def test_stale_approval_holds(self) -> None:
        """승인 후 내용이 바뀌면 그 승인으로 진행할 수 없다."""
        state = _ready_brief().record_answer(
            question="추가 질문", answer="추가 답변", authority="decision"
        )

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"
        assert GateBlockingCondition.APPROVAL_STALE in _conditions(decision)

    def test_stale_approval_is_distinguished_from_missing(self) -> None:
        """두 상황의 다음 행동이 다르므로 이유도 달라야 한다."""
        state = _ready_brief().record_answer(question="q", answer="a", authority="decision")

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert GateBlockingCondition.APPROVAL_MISSING not in _conditions(decision)


class TestApprovalIsNotSufficient:
    """§11.5 — 승인은 필요조건이지 만능 override가 아니다."""

    def test_material_unresolved_item_holds_despite_approval(self) -> None:
        """B-012 — 점수와 승인이 있어도 미해결 결정이 남아 있으면 HOLD."""
        state = _answered_brief().note_unresolved(
            description="비로그인 사용자 정책 미정", is_material=True
        )
        state = _assessed(state, _assessment(), times=POLICY.required_stability)
        state = state.approve(statement="그래도 진행")

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"
        assert GateBlockingCondition.MATERIAL_UNRESOLVED_ITEM in _conditions(decision)

    def test_non_material_unresolved_item_does_not_hold(self) -> None:
        state = _answered_brief().note_unresolved(description="버튼 색상 미정", is_material=False)
        state = _assessed(state, _assessment(), times=POLICY.required_stability)
        state = state.approve(statement="진행")

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "CLEAR"

    def test_unverifiable_success_criteria_holds_despite_approval(self) -> None:
        """B-025 — 승인했어도 성공 조건을 검증할 수 없으면 진행하지 않는다."""
        state = _assessed(
            _answered_brief(),
            _assessment(goal=1.0, constraint=1.0, success=0.5),
            times=POLICY.required_stability,
        )
        state = state.approve(statement="진행")

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"
        assert decision.clarity_blockers != ()

    def test_completion_candidacy_alone_is_not_clear(self) -> None:
        """B-030 — 네 조건 충족은 승인을 요청할 자격이지 CLEAR가 아니다."""
        state = _assessed(_answered_brief(), _assessment(), times=POLICY.required_stability)
        candidacy = POLICY.assess_completion(
            assessment=state.assessment,
            answered_rounds=len(state.answered_rounds),
            stability_signal=state.stability_signal,
        )
        assert candidacy.is_candidate is True

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"


class TestClarityBlockersArePreserved:
    """HOLD 이유는 요약되지 않고 원래 조건 그대로 전달된다."""

    def test_clarity_blockers_are_reported_separately(self) -> None:
        state = _assessed(_answered_brief(), _assessment(goal=0.3, constraint=0.3, success=0.3))
        state = state.approve(statement="진행")

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"
        assert len(decision.clarity_blockers) >= 2

    def test_missing_assessment_holds(self) -> None:
        state = _answered_brief().approve(statement="진행")

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"
        assert decision.clarity_blockers != ()

    def test_blocking_reasons_are_human_readable(self) -> None:
        decision = evaluate_brief_gate(state=_answered_brief(), policy=POLICY)

        reasons = decision.blocking_reasons
        assert len(reasons) >= 2
        assert all(isinstance(reason, str) and reason for reason in reasons)


class TestAssessmentBelongsToTheRevision:
    """§8.1 규칙 10 — material 변경은 평가와 signal을 함께 무효화한다."""

    def test_answer_after_a_clear_state_invalidates_the_assessment(self) -> None:
        state = _ready_brief()
        assert evaluate_brief_gate(state=state, policy=POLICY).outcome == "CLEAR"

        reopened = state.record_answer(question="추가", answer="추가", authority="decision")

        assert reopened.assessment is None
        assert reopened.stability_signal == 0
        assert evaluate_brief_gate(state=reopened, policy=POLICY).outcome == "HOLD"
