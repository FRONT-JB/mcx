"""Brief handoff — Blueprint가 읽는 Stage 경계 산출물.

계약: docs/05_BRIEF.md §9, §9.1, §9.2 / docs/adr/0016-brief-handoff-projection.md
Test Matrix: B-026, B-031
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
from mission_control.domain.brief.gate import evaluate_brief_gate
from mission_control.domain.brief.handoff import (
    BriefHandoff,
    HandoffNotClearedError,
    build_brief_handoff,
)
from mission_control.domain.brief.provenance import WITHHELD_ANSWER_NOTE
from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    ConfirmationAuthority,
    RequirementSection,
)
from mission_control.domain.brief.state import BriefState

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


def _confirmed(
    state: BriefState,
    *,
    section: RequirementSection,
    text: str,
    content_source: CandidateContentSource = CandidateContentSource.USER_STATED,
    authority: ConfirmationAuthority = ConfirmationAuthority.USER,
) -> BriefState:
    return state.record_candidate(
        section=section,
        text=text,
        content_source=content_source,
        resolution=CandidateResolution.CONFIRMED,
        confirmation_authority=authority,
    )


def _cleared_brief() -> BriefState:
    state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")
    state = state.record_answer(
        question="댓글은 누가 쓸 수 있나요?", answer="로그인 사용자만", authority="decision"
    )
    state = state.record_answer(
        question="현재 인증 방식은?", answer="JWT를 쓰고 있다", authority="observation"
    )
    state = state.record_answer(
        question="완료 확인은?", answer="목록에 보이면 완료", authority="decision"
    )
    state = _confirmed(state, section=RequirementSection.GOAL, text="댓글을 쓰고 볼 수 있다")
    state = _confirmed(state, section=RequirementSection.CONSTRAINT, text="로그인 사용자만 작성")
    state = _confirmed(
        state, section=RequirementSection.NON_GOAL, text="수정·삭제는 이번 범위 아님"
    )
    state = _confirmed(
        state,
        section=RequirementSection.ACCEPTANCE_CRITERION,
        text="목록 맨 위에 새 댓글이 보인다",
    )
    state = _confirmed(
        state,
        section=RequirementSection.CONTEXT,
        text="현재 인증은 JWT",
        content_source=CandidateContentSource.REPO_OBSERVED,
        authority=ConfirmationAuthority.REPO_EVIDENCE,
    )
    for _ in range(POLICY.required_stability):
        state = state.record_assessment(assessment=_assessment(), policy=POLICY)
    return state.record_closure_audit(audit=_ready_audit()).approve(
        statement="이대로 진행해 주세요"
    )


def _handoff_of(state: BriefState) -> BriefHandoff:
    return build_brief_handoff(
        state=state, decision=evaluate_brief_gate(state=state, policy=POLICY)
    )


class TestSectionsAreSeparated:
    """B-026 — Blueprint가 대화를 재해석하지 않고 칸별로 읽을 수 있다."""

    def test_each_section_lands_in_its_own_list(self) -> None:
        handoff = _handoff_of(_cleared_brief())

        assert handoff.goals == ("댓글을 쓰고 볼 수 있다",)
        assert handoff.constraints == ("로그인 사용자만 작성",)
        assert handoff.non_goals == ("수정·삭제는 이번 범위 아님",)
        assert handoff.success_criteria == ("목록 맨 위에 새 댓글이 보인다",)
        assert handoff.context == ("현재 인증은 JWT",)

    def test_approval_and_revision_are_carried(self) -> None:
        state = _cleared_brief()

        handoff = _handoff_of(state)

        assert handoff.revision == state.revision
        assert handoff.approval.revision == state.revision
        assert handoff.policy_version == POLICY.version

    def test_original_intent_is_preserved(self) -> None:
        handoff = _handoff_of(_cleared_brief())

        assert handoff.initial_intent == "댓글 기능을 추가하고 싶다"

    def test_unpromoted_candidates_are_reported_with_reasons(self) -> None:
        """승격되지 않은 후보가 조용히 사라지지 않는다."""
        state = _cleared_brief().record_candidate(
            section=RequirementSection.CONSTRAINT,
            text="버튼 색상 미정",
            content_source=CandidateContentSource.USER_STATED,
            resolution=CandidateResolution.UNKNOWN,
            required=False,
        )
        for _ in range(POLICY.required_stability):
            state = state.record_assessment(assessment=_assessment(), policy=POLICY)
        state = state.record_closure_audit(audit=_ready_audit()).approve(statement="진행")

        handoff = _handoff_of(state)

        assert [item.candidate.text for item in handoff.omitted] == ["버튼 색상 미정"]
        assert "버튼 색상 미정" not in handoff.constraints


class TestTwoChannels:
    """B-031 — 관찰은 요구사항 입력에서 빠지고 사실 채널에는 남는다."""

    def test_observation_body_is_withheld_from_requirement_input(self) -> None:
        handoff = _handoff_of(_cleared_brief())

        withheld = [item for item in handoff.requirement_input if item.withheld]
        assert len(withheld) == 1
        assert withheld[0].answer == WITHHELD_ANSWER_NOTE
        assert withheld[0].question == "현재 인증 방식은?"

    def test_observed_facts_keep_the_original_text(self) -> None:
        handoff = _handoff_of(_cleared_brief())

        assert [item.answer for item in handoff.observed_facts] == ["JWT를 쓰고 있다"]

    def test_decision_answers_are_intact_in_requirement_input(self) -> None:
        handoff = _handoff_of(_cleared_brief())

        answers = [item.answer for item in handoff.requirement_input if not item.withheld]
        assert answers == ["로그인 사용자만", "목록에 보이면 완료"]


class TestHandoffRequiresClear:
    """§9.2 — Brief에서의 정상 exit는 저장된 CLEAR 하나뿐이다."""

    def test_hold_is_rejected(self) -> None:
        state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능")

        with pytest.raises(HandoffNotClearedError):
            _handoff_of(state)

    def test_blocked_candidate_prevents_a_handoff(self) -> None:
        state = _cleared_brief().record_candidate(
            section=RequirementSection.CONSTRAINT,
            text="비로그인 정책 미정",
            content_source=CandidateContentSource.USER_STATED,
            resolution=CandidateResolution.UNKNOWN,
            required=True,
        )
        for _ in range(POLICY.required_stability):
            state = state.record_assessment(assessment=_assessment(), policy=POLICY)
        state = state.approve(statement="그래도 진행")

        with pytest.raises(HandoffNotClearedError):
            _handoff_of(state)

    def test_decision_from_another_revision_is_rejected(self) -> None:
        state = _cleared_brief()
        decision = evaluate_brief_gate(state=state, policy=POLICY)
        changed = state.record_answer(question="추가", answer="추가", authority="decision")

        with pytest.raises(HandoffNotClearedError):
            build_brief_handoff(state=changed, decision=decision)
