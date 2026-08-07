"""파일 기반 Brief 저장소.

계약: docs/adr/0013-brief-durable-state-baseline.md / docs/05_BRIEF.md §14.1
Test Matrix: B-017, B-019
"""

from pathlib import Path
import stat

import pytest

from mission_control.adapters.persistence.file_brief_repository import FileBriefRepository
from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    RequirementSection,
)
from mission_control.domain.brief.state import BriefState
from mission_control.domain.errors import StaleWriteError


@pytest.fixture
def repository(tmp_path: Path) -> FileBriefRepository:
    return FileBriefRepository(root=tmp_path)


def _brief() -> BriefState:
    return BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")


class TestRoundTrip:
    """B-019 — 프로세스가 끊겨도 이전 rounds와 미해결 항목을 잃지 않는다."""

    async def test_load_returns_none_when_absent(self, repository: FileBriefRepository) -> None:
        assert await repository.load("m-unknown") is None

    async def test_saved_state_is_restored(self, repository: FileBriefRepository) -> None:
        state = _brief().record_answer(
            question="댓글은 누가 쓸 수 있나요?",
            answer="로그인 사용자만",
            authority="decision",
        )
        await repository.save(state)

        restored = await repository.load("m-1")

        assert restored is not None
        assert restored.revision == state.revision
        assert restored.initial_intent == state.initial_intent
        assert len(restored.rounds) == 1
        assert restored.rounds[0].question == "댓글은 누가 쓸 수 있나요?"
        assert restored.rounds[0].authority == "decision"

    async def test_approval_and_candidates_survive(self, repository: FileBriefRepository) -> None:
        state = (
            _brief()
            .record_answer(question="q", answer="a", authority="decision")
            .record_candidate(
                section=RequirementSection.CONSTRAINT,
                text="비로그인 정책 미정",
                content_source=CandidateContentSource.USER_STATED,
                resolution=CandidateResolution.UNKNOWN,
                required=True,
            )
            .approve(statement="이대로 진행")
        )
        await repository.save(state)

        restored = await repository.load("m-1")

        assert restored is not None
        assert restored.approval is not None
        assert restored.approval.revision == state.approval.revision  # type: ignore[union-attr]
        assert len(restored.candidates) == 1
        assert restored.candidates[0].resolution is CandidateResolution.UNKNOWN
        assert restored.promotion.blockers != ()

    async def test_revision_history_survives(self, repository: FileBriefRepository) -> None:
        state = (
            _brief()
            .record_answer(question="q1", answer="a1", authority="decision")
            .record_answer(question="q2", answer="a2", authority="decision")
        )
        await repository.save(state)

        restored = await repository.load("m-1")

        assert restored is not None
        snapshot = restored.snapshot_at(revision=2)
        assert snapshot is not None
        assert len(snapshot.rounds) == 1

    async def test_missions_are_isolated(self, repository: FileBriefRepository) -> None:
        first = BriefState.start(mission_id="m-1", initial_intent="첫 번째")
        second = BriefState.start(mission_id="m-2", initial_intent="두 번째")
        await repository.save(first)
        await repository.save(second)

        restored = await repository.load("m-2")

        assert restored is not None
        assert restored.initial_intent == "두 번째"


class TestStaleWriteRejection:
    """B-017 — 지난 상태 기반 갱신이 최신 상태를 덮어쓰지 않는다."""

    async def test_posing_a_question_advances_without_changing_revision(
        self, repository: FileBriefRepository
    ) -> None:
        """요구사항을 바꾸지 않는 변경도 저장은 되어야 한다."""
        state = _brief()
        await repository.save(state)

        posed = state.pose_question(question="댓글은 누가 쓸 수 있나요?")
        await repository.save(posed)

        restored = await repository.load("m-1")
        assert restored is not None
        assert restored.revision == state.revision
        assert restored.pending_question is not None

    async def test_same_state_is_rejected(self, repository: FileBriefRepository) -> None:
        state = _brief().record_answer(question="q", answer="a", authority="decision")
        await repository.save(state)

        with pytest.raises(StaleWriteError):
            await repository.save(state)

    async def test_older_revision_is_rejected(self, repository: FileBriefRepository) -> None:
        first = _brief().record_answer(question="q1", answer="a1", authority="decision")
        second = first.record_answer(question="q2", answer="a2", authority="decision")
        await repository.save(second)

        with pytest.raises(StaleWriteError):
            await repository.save(first)

    async def test_rejected_write_leaves_stored_state_intact(
        self, repository: FileBriefRepository
    ) -> None:
        first = _brief().record_answer(question="q1", answer="a1", authority="decision")
        second = first.record_answer(question="q2", answer="a2", authority="decision")
        await repository.save(second)

        with pytest.raises(StaleWriteError):
            await repository.save(first)

        restored = await repository.load("m-1")
        assert restored is not None
        assert restored.revision == second.revision
        assert len(restored.rounds) == 2

    async def test_advancing_revision_is_accepted(self, repository: FileBriefRepository) -> None:
        first = _brief().record_answer(question="q1", answer="a1", authority="decision")
        await repository.save(first)

        second = first.record_answer(question="q2", answer="a2", authority="decision")
        await repository.save(second)

        restored = await repository.load("m-1")
        assert restored is not None
        assert len(restored.rounds) == 2


class TestWriteSafety:
    async def test_file_is_owner_only(
        self, repository: FileBriefRepository, tmp_path: Path
    ) -> None:
        """Brief에는 사용자의 의도와 제약이 담긴다. 다른 사용자가 읽지 못하게 한다."""
        await repository.save(_brief())

        written = next(tmp_path.rglob("*.json"))
        mode = stat.S_IMODE(written.stat().st_mode)
        assert mode == 0o600

    async def test_no_temporary_file_is_left_behind(
        self, repository: FileBriefRepository, tmp_path: Path
    ) -> None:
        await repository.save(_brief())

        leftovers = [path for path in tmp_path.rglob("*") if path.suffix not in {".json", ""}]
        assert leftovers == []

    async def test_root_is_created_on_demand(self, tmp_path: Path) -> None:
        repository = FileBriefRepository(root=tmp_path / "nested" / "state")

        await repository.save(_brief())

        assert await repository.load("m-1") is not None


class TestMissionIdValidation:
    """저장 경로가 mission id로 조작되지 않아야 한다."""

    @pytest.mark.parametrize("mission_id", ["../escape", "a/b", "", "with space", "dot.dot"])
    async def test_unsafe_mission_id_is_rejected(
        self, repository: FileBriefRepository, mission_id: str
    ) -> None:
        with pytest.raises(ValueError, match="mission id"):
            await repository.load(mission_id)

    async def test_safe_mission_id_is_accepted(self, repository: FileBriefRepository) -> None:
        state = BriefState.start(mission_id="mission-2026-08-07_01", initial_intent="x")

        await repository.save(state)

        assert await repository.load("mission-2026-08-07_01") is not None
