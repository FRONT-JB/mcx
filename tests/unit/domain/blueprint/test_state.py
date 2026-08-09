"""Blueprint 상태 — revision 이력, 채점 허용 규칙, 승인 바인딩.

계약: docs/06_BLUEPRINT.md §7, §9 / docs/adr/0021-blueprint-state-and-revisions.md
Test Matrix: Approval·Mutation·QA loop 행 (docs/06_BLUEPRINT.md §14)
"""

import pytest

from mission_control.domain.blueprint.qa import QaAssessment, QaDimension, QaPolicy
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import (
    BlueprintState,
    QaAlreadyPassedError,
    QaBudgetExhaustedError,
    QaEscalatedError,
    QaLoopStillOpenError,
    UnassessedRevisionError,
)

POLICY = QaPolicy.blueprint_v1()


def _blueprint(*, revision: int = 1, goal: str = "댓글을 쓰고 볼 수 있다") -> Blueprint:
    return Blueprint(
        mission_id="m-1",
        revision=revision,
        brief_revision=5,
        goal=goal,
        constraints=("로그인 사용자만 작성",),
        non_goals=("수정·삭제는 이번 범위 아님",),
        acceptance_criteria=(
            AcceptanceCriterion(
                description="목록 맨 위에 새 댓글이 보인다",
                verify_command="pytest tests/test_comments.py",
            ),
        ),
    )


def _assessment(score: float, *, correctness: float | None = None) -> QaAssessment:
    dimensions = ((QaDimension.CORRECTNESS, correctness),) if correctness is not None else ()
    return QaAssessment(score=score, dimension_scores=dimensions)


def _started() -> BlueprintState:
    return BlueprintState.start(blueprint=_blueprint())


class TestRevisionHistory:
    def test_start_holds_revision_one(self) -> None:
        state = _started()
        assert state.revision == 1
        assert state.sequence == 1
        assert state.approval is None

    def test_state_needs_at_least_one_revision(self) -> None:
        with pytest.raises(ValueError, match="revision이 최소 하나"):
            BlueprintState(mission_id="m-1", revisions=())

    def test_revision_gaps_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="1부터 연속"):
            BlueprintState(mission_id="m-1", revisions=(_blueprint(revision=2),))

    def test_foreign_mission_revision_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="의 것이다"):
            BlueprintState(mission_id="m-2", revisions=(_blueprint(),))

    def test_revise_appends_without_touching_the_past(self) -> None:
        state = _started()
        revised = state.revise(blueprint=_blueprint(revision=2, goal="새 목표"))

        assert revised.revision == 2
        assert revised.revisions[0] == state.current
        assert state.revision == 1

    def test_revise_requires_the_next_revision_number(self) -> None:
        with pytest.raises(ValueError, match="revision 2이 와야"):
            _started().revise(blueprint=_blueprint(revision=3))

    def test_revise_rejects_a_foreign_mission(self) -> None:
        foreign = _blueprint(revision=2).model_copy(update={"mission_id": "m-2"})
        with pytest.raises(ValueError, match="의 것이다"):
            _started().revise(blueprint=foreign)


class TestQaPermissions:
    def test_recording_appends_to_the_current_revision(self) -> None:
        state = _started().record_qa(assessment=_assessment(0.85), policy=POLICY)

        assert len(state.qa_records) == 1
        assert state.qa_records[0].revision == 1
        assert state.sequence == 2

    def test_a_passed_revision_is_not_reassessed(self) -> None:
        state = _started().record_qa(assessment=_assessment(0.92), policy=POLICY)
        with pytest.raises(QaAlreadyPassedError):
            state.record_qa(assessment=_assessment(0.95), policy=POLICY)

    def test_the_loop_stops_after_a_fail_verdict(self) -> None:
        state = _started().record_qa(assessment=_assessment(0.30), policy=POLICY)
        with pytest.raises(QaEscalatedError):
            state.record_qa(assessment=_assessment(0.85), policy=POLICY)

    def test_the_budget_caps_total_iterations(self) -> None:
        state = _started()
        for _ in range(POLICY.max_iterations):
            state = state.record_qa(assessment=_assessment(0.85), policy=POLICY)
        with pytest.raises(QaBudgetExhaustedError):
            state.record_qa(assessment=_assessment(0.85), policy=POLICY)

    def test_a_revised_revision_may_be_assessed_after_a_pass(self) -> None:
        state = _started().record_qa(assessment=_assessment(0.92), policy=POLICY)
        state = state.revise(blueprint=_blueprint(revision=2, goal="다듬은 목표"))

        state = state.record_qa(assessment=_assessment(0.88), policy=POLICY)
        assert state.qa_records[-1].revision == 2

    def test_the_budget_spans_revisions(self) -> None:
        state = _started()
        for _ in range(POLICY.max_iterations - 1):
            state = state.record_qa(assessment=_assessment(0.85), policy=POLICY)
        state = state.revise(blueprint=_blueprint(revision=2, goal="다듬은 목표"))
        state = state.record_qa(assessment=_assessment(0.86), policy=POLICY)

        with pytest.raises(QaBudgetExhaustedError):
            state.record_qa(assessment=_assessment(0.87), policy=POLICY)


class TestBestRecord:
    def test_best_is_linked_back_to_its_revision(self) -> None:
        state = _started().record_qa(assessment=_assessment(0.89), policy=POLICY)
        state = state.revise(blueprint=_blueprint(revision=2, goal="다듬은 목표"))
        state = state.record_qa(assessment=_assessment(0.85), policy=POLICY)

        best = state.best_record(policy=POLICY)
        assert best is not None
        assert best.revision == 1
        assert best.assessment.score == 0.89

    def test_without_records_there_is_no_best(self) -> None:
        assert _started().best_record(policy=POLICY) is None


class TestApproval:
    def test_an_unassessed_revision_cannot_be_approved(self) -> None:
        with pytest.raises(UnassessedRevisionError):
            _started().approve(statement="진행", policy=POLICY)

    def test_a_passing_revision_is_approved_with_its_qa_evidence(self) -> None:
        state = _started().record_qa(assessment=_assessment(0.92), policy=POLICY)
        approved = state.approve(statement="이대로 진행", policy=POLICY)

        assert approved.approval is not None
        assert approved.approval.revision == 1
        assert approved.approval.qa_policy_version == POLICY.version
        assert approved.approval.qa_threshold == POLICY.pass_threshold
        assert approved.approval.qa_best_score == 0.92
        assert approved.approval.qa_iterations == 1
        assert approved.approval.accepted_below_threshold is False
        assert approved.has_current_approval

    def test_a_below_threshold_approval_needs_an_exhausted_budget(self) -> None:
        state = _started().record_qa(assessment=_assessment(0.85), policy=POLICY)
        with pytest.raises(QaLoopStillOpenError):
            state.approve(statement="그냥 진행", policy=POLICY, accept_below_threshold=True)

    def test_an_exhausted_loop_accepts_below_threshold_explicitly(self) -> None:
        state = _started()
        for _ in range(POLICY.max_iterations):
            state = state.record_qa(assessment=_assessment(0.85), policy=POLICY)
        approved = state.approve(
            statement="미달이지만 수락", policy=POLICY, accept_below_threshold=True
        )

        assert approved.approval is not None
        assert approved.approval.accepted_below_threshold is True
        assert approved.approval.qa_best_score == 0.85

    def test_an_exhausted_loop_without_the_flag_is_rejected(self) -> None:
        state = _started()
        for _ in range(POLICY.max_iterations):
            state = state.record_qa(assessment=_assessment(0.85), policy=POLICY)
        with pytest.raises(ValueError, match="accepted_below_threshold"):
            state.approve(statement="진행", policy=POLICY)

    def test_a_failed_revision_cannot_be_approved(self) -> None:
        state = _started().record_qa(assessment=_assessment(0.30), policy=POLICY)
        with pytest.raises(QaEscalatedError):
            state.approve(statement="진행", policy=POLICY, accept_below_threshold=True)

    def test_the_recorded_score_belongs_to_the_approved_revision(self) -> None:
        """루프 전체 최고점이 아니라 승인 대상 revision의 최고점이 남는다.

        rev1이 통과 점수를 받았어도 rev2를 승인하면 기록은 rev2의 점수다.
        섞이면 미달 수락 표시의 일관성 검사가 무력화된다 (ADR-0021 §5).
        """
        state = _started().record_qa(assessment=_assessment(0.92), policy=POLICY)
        state = state.revise(blueprint=_blueprint(revision=2, goal="다듬은 목표"))
        for _ in range(POLICY.max_iterations - 1):
            state = state.record_qa(assessment=_assessment(0.85), policy=POLICY)

        approved = state.approve(
            statement="rev2를 수락", policy=POLICY, accept_below_threshold=True
        )
        assert approved.approval is not None
        assert approved.approval.revision == 2
        assert approved.approval.qa_best_score == 0.85
        assert approved.approval.accepted_below_threshold is True

    def test_revising_makes_the_approval_stale(self) -> None:
        state = _started().record_qa(assessment=_assessment(0.92), policy=POLICY)
        approved = state.approve(statement="진행", policy=POLICY)
        revised = approved.revise(blueprint=_blueprint(revision=2, goal="다듬은 목표"))

        assert revised.approval is not None
        assert revised.approval.revision == 1
        assert not revised.has_current_approval
