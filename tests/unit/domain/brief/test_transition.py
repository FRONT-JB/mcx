"""Brief에서 나가는 전이 — 허용된 목적지와 금지된 목적지.

계약: docs/02_MISSION_LIFECYCLE.md §9, §9.1 / docs/05_BRIEF.md §9.2
Test Matrix: L-S01, L-B02, L-B04
"""

import pytest

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
from mission_control.domain.brief.gate import evaluate_brief_gate, next_stage_after_brief
from mission_control.domain.brief.state import BriefState
from mission_control.domain.errors import StaleGateDecisionError
from mission_control.domain.stage import Stage

POLICY = ClarityPolicy.greenfield_v1()


def _ready_audit() -> ClosureAudit:
    return ClosureAudit(
        closer=CloserReport(verdict=CloserVerdict.READY, reason="nothing material remains"),
        contrarian=AdvisoryReport(
            lane=AdvisoryLane.CONTRARIAN, severity=ClosureSeverity.LOW, finding="minor"
        ),
        gap_hunter=AdvisoryReport(
            lane=AdvisoryLane.GAP_HUNTER, severity=ClosureSeverity.LOW, finding="minor"
        ),
    )


def _assessment() -> ClarityAssessment:
    return ClarityAssessment(
        scores=(
            DimensionScore(dimension="goal", clarity=0.9, justification="t"),
            DimensionScore(dimension="constraint", clarity=0.9, justification="t"),
            DimensionScore(dimension="success_criteria", clarity=0.9, justification="t"),
        ),
        policy_version=POLICY.version,
    )


def _brief(*, rounds: int = 3) -> BriefState:
    state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    for index in range(rounds):
        state = state.record_answer(question=f"q{index}", answer=f"a{index}", authority="decision")
    return state


def _clear_brief() -> BriefState:
    state = _brief()
    for _ in range(POLICY.required_stability):
        state = state.record_assessment(assessment=_assessment(), policy=POLICY)
    return state.record_closure_audit(audit=_ready_audit()).approve(
        statement="이대로 진행해 주세요"
    )


class TestAllowedTransition:
    """L-S01 — Brief에서 나가는 정상 경로는 CLEAR 하나뿐이다."""

    def test_clear_moves_to_blueprint(self) -> None:
        state = _clear_brief()
        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert next_stage_after_brief(state=state, decision=decision) is Stage.BLUEPRINT

    def test_hold_stays_in_brief(self) -> None:
        """L-B02 — HOLD는 Stage exit가 아니라 Brief를 유지하는 판정이다."""
        state = _brief()
        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"
        assert next_stage_after_brief(state=state, decision=decision) is Stage.BRIEF


class TestForbiddenTransition:
    """§9.1 — Brief → Execute/Verify는 금지 전이다."""

    @pytest.mark.parametrize("rounds", [0, 1, 3])
    def test_no_gate_outcome_leads_past_blueprint(self, rounds: int) -> None:
        """어떤 상태에서도 Blueprint보다 앞선 Stage로 건너뛰지 않는다."""
        state = _brief(rounds=rounds)
        decision = evaluate_brief_gate(state=state, policy=POLICY)

        destination = next_stage_after_brief(state=state, decision=decision)

        assert destination not in {Stage.EXECUTE, Stage.VERIFY, Stage.RECOVER}

    def test_hold_never_reaches_blueprint(self) -> None:
        """승인 없이 점수만 충족해도 다음 Stage로 넘어가지 않는다."""
        state = _brief()
        for _ in range(POLICY.required_stability):
            state = state.record_assessment(assessment=_assessment(), policy=POLICY)

        decision = evaluate_brief_gate(state=state, policy=POLICY)

        assert decision.outcome == "HOLD"
        assert next_stage_after_brief(state=state, decision=decision) is Stage.BRIEF


class TestStaleDecisionIsRejected:
    """L-B04 — 판정과 전이 사이에 내용이 바뀌면 그 판정을 쓰지 않는다."""

    def test_decision_from_an_earlier_revision_is_rejected(self) -> None:
        state = _clear_brief()
        decision = evaluate_brief_gate(state=state, policy=POLICY)

        changed = state.record_answer(
            question="추가", answer="비로그인은 조회만", authority="decision"
        )

        with pytest.raises(StaleGateDecisionError):
            next_stage_after_brief(state=changed, decision=decision)

    def test_rejection_names_both_revisions(self) -> None:
        state = _clear_brief()
        decision = evaluate_brief_gate(state=state, policy=POLICY)
        changed = state.record_answer(question="추가", answer="추가", authority="decision")

        with pytest.raises(StaleGateDecisionError) as error:
            next_stage_after_brief(state=changed, decision=decision)

        assert error.value.decision_revision == state.revision
        assert error.value.current_revision == changed.revision

    def test_a_question_does_not_invalidate_the_decision(self) -> None:
        """질문은 요구사항을 바꾸지 않으므로 판정도 무효화하지 않는다."""
        state = _clear_brief()
        decision = evaluate_brief_gate(state=state, policy=POLICY)

        posed = state.pose_question(question="추가로 확인할 것이 있나요?")

        assert next_stage_after_brief(state=posed, decision=decision) is Stage.BLUEPRINT
