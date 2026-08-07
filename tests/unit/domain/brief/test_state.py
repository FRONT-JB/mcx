"""Brief state의 round 축적, revision, 승인 stale 처리.

계약: docs/05_BRIEF.md §8, §8.1, §12.2 / docs/adr/0013-brief-durable-state-baseline.md
Test Matrix: B-008, B-014
"""

import pytest

from mission_control.domain.brief.state import BriefState


def _started() -> BriefState:
    return BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")


class TestRoundAccumulation:
    """B-008 — 답변은 질문·authority·revision과 연결되어 축적된다."""

    def test_start_has_no_rounds_and_first_revision(self) -> None:
        state = _started()

        assert state.rounds == ()
        assert state.revision == 1
        assert state.initial_intent == "댓글 기능을 추가하고 싶다"

    def test_record_answer_appends_linked_round(self) -> None:
        state = _started().record_answer(
            question="댓글은 누가 쓸 수 있나요?",
            answer="로그인 사용자만",
            authority="decision",
        )

        assert len(state.rounds) == 1
        assert state.rounds[0].number == 1
        assert state.rounds[0].question == "댓글은 누가 쓸 수 있나요?"
        assert state.rounds[0].answer == "로그인 사용자만"
        assert state.rounds[0].authority == "decision"

    def test_record_answer_advances_revision(self) -> None:
        state = _started()
        assert state.revision == 1

        state = state.record_answer(question="q1", answer="a1", authority="decision")
        assert state.revision == 2

        state = state.record_answer(question="q2", answer="a2", authority="observation")
        assert state.revision == 3

    def test_round_numbers_are_sequential(self) -> None:
        state = _started()
        for index in range(3):
            state = state.record_answer(
                question=f"q{index}", answer=f"a{index}", authority="decision"
            )

        assert [item.number for item in state.rounds] == [1, 2, 3]

    def test_empty_answer_is_rejected(self) -> None:
        """§8.1 규칙 5 — 미답변 질문을 답변된 것처럼 저장하지 않는다."""
        state = _started()

        with pytest.raises(ValueError, match="answer"):
            state.record_answer(question="q", answer="   ", authority="decision")

    def test_state_is_immutable(self) -> None:
        """이전 상태 객체가 변경되지 않아야 감사가 가능하다."""
        original = _started()

        original.record_answer(question="q", answer="a", authority="decision")

        assert original.rounds == ()
        assert original.revision == 1


class TestApprovalBindsToRevision:
    """B-014 — 승인은 특정 revision을 참조하고, 내용이 바뀌면 무효가 된다."""

    def test_approval_records_the_revision_it_saw(self) -> None:
        state = _started().record_answer(question="q", answer="a", authority="decision")

        approved = state.approve(statement="이대로 진행해 주세요")

        assert approved.approval is not None
        assert approved.approval.revision == state.revision
        assert approved.approval.statement == "이대로 진행해 주세요"

    def test_fresh_approval_is_current(self) -> None:
        state = _started().record_answer(question="q", answer="a", authority="decision")

        approved = state.approve(statement="진행")

        assert approved.has_current_approval is True

    def test_answer_after_approval_makes_it_stale(self) -> None:
        approved = (
            _started()
            .record_answer(question="q1", answer="a1", authority="decision")
            .approve(statement="진행")
        )
        assert approved.has_current_approval is True

        changed = approved.record_answer(question="q2", answer="a2", authority="decision")

        assert changed.approval is not None
        assert changed.approval.revision < changed.revision
        assert changed.has_current_approval is False

    def test_stale_approval_is_not_discarded(self) -> None:
        """무효가 된 승인도 기록으로 남는다. 승인 사실 자체가 증거다."""
        changed = (
            _started()
            .record_answer(question="q1", answer="a1", authority="decision")
            .approve(statement="진행")
            .record_answer(question="q2", answer="a2", authority="decision")
        )

        assert changed.approval is not None
        assert changed.approval.statement == "진행"

    def test_reapproval_restores_current_approval(self) -> None:
        changed = (
            _started()
            .record_answer(question="q1", answer="a1", authority="decision")
            .approve(statement="진행")
            .record_answer(question="q2", answer="a2", authority="decision")
        )

        reapproved = changed.approve(statement="다시 확인했습니다")

        assert reapproved.has_current_approval is True
        assert reapproved.approval is not None
        assert reapproved.approval.revision == changed.revision

    def test_unstarted_brief_has_no_approval(self) -> None:
        assert _started().has_current_approval is False


class TestRevisionHistory:
    """ADR-0013 — 승인이 참조한 revision을 이후에도 조회할 수 있다."""

    def test_previous_revision_rounds_are_retained(self) -> None:
        state = (
            _started()
            .record_answer(question="q1", answer="a1", authority="decision")
            .record_answer(question="q2", answer="a2", authority="decision")
        )

        snapshot = state.snapshot_at(revision=2)

        assert snapshot is not None
        assert len(snapshot.rounds) == 1
        assert snapshot.rounds[0].question == "q1"

    def test_current_revision_is_queryable(self) -> None:
        state = _started().record_answer(question="q1", answer="a1", authority="decision")

        snapshot = state.snapshot_at(revision=state.revision)

        assert snapshot is not None
        assert len(snapshot.rounds) == 1

    def test_unknown_revision_returns_none(self) -> None:
        assert _started().snapshot_at(revision=99) is None
