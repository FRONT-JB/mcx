"""Blueprint 파일 저장소 — 왕복 보존, stale write 거부, 경로 안전성.

계약: docs/adr/0021-blueprint-state-and-revisions.md §1,
docs/adr/0013-brief-durable-state-baseline.md §3
Test Matrix: Persistence 행 (docs/06_BLUEPRINT.md §14)
"""

from pathlib import Path

import pytest

from mission_control.adapters.persistence.file_blueprint_repository import (
    FileBlueprintRepository,
)
from mission_control.domain.blueprint.qa import QaAssessment, QaPolicy
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.errors import StaleWriteError

POLICY = QaPolicy.blueprint_v1()


def _blueprint(*, mission_id: str = "m-1", revision: int = 1) -> Blueprint:
    return Blueprint(
        mission_id=mission_id,
        revision=revision,
        brief_revision=5,
        goal="댓글을 쓰고 볼 수 있다",
        constraints=("로그인 사용자만 작성",),
        non_goals=("수정·삭제는 이번 범위 아님",),
        acceptance_criteria=(
            AcceptanceCriterion(
                description="목록에 새 댓글이 보인다",
                verify_command="pytest",
                output_assertion="1 passed",
            ),
        ),
    )


def _approved_state(mission_id: str = "m-1") -> BlueprintState:
    state = BlueprintState.start(blueprint=_blueprint(mission_id=mission_id))
    state = state.record_qa(assessment=QaAssessment(score=0.92), policy=POLICY)
    return state.approve(statement="이대로 진행", policy=POLICY)


@pytest.fixture
def repository(tmp_path: Path) -> FileBlueprintRepository:
    return FileBlueprintRepository(root=tmp_path)


class TestRoundTrip:
    async def test_load_returns_none_when_absent(self, repository: FileBlueprintRepository) -> None:
        assert await repository.load("m-1") is None

    async def test_revisions_qa_and_approval_survive_together(
        self, repository: FileBlueprintRepository
    ) -> None:
        state = _approved_state()
        await repository.save(state)

        restored = await repository.load("m-1")
        assert restored == state
        assert restored is not None
        assert restored.approval is not None
        assert restored.qa_records[0].assessment.score == 0.92
        assert restored.current.acceptance_criteria[0].key == (
            state.current.acceptance_criteria[0].key
        )

    async def test_missions_are_isolated(self, repository: FileBlueprintRepository) -> None:
        await repository.save(_approved_state("m-1"))
        await repository.save(_approved_state("m-2"))

        first = await repository.load("m-1")
        assert first is not None
        assert first.mission_id == "m-1"


class TestStaleWrites:
    async def test_same_sequence_is_rejected(self, repository: FileBlueprintRepository) -> None:
        state = _approved_state()
        await repository.save(state)
        with pytest.raises(StaleWriteError):
            await repository.save(state)

    async def test_rejected_write_leaves_stored_state_intact(
        self, repository: FileBlueprintRepository
    ) -> None:
        base = BlueprintState.start(blueprint=_blueprint())
        advanced = base.record_qa(assessment=QaAssessment(score=0.92), policy=POLICY)
        await repository.save(advanced)

        with pytest.raises(StaleWriteError):
            await repository.save(base)
        assert await repository.load("m-1") == advanced

    async def test_an_advancing_sequence_is_accepted(
        self, repository: FileBlueprintRepository
    ) -> None:
        base = BlueprintState.start(blueprint=_blueprint())
        await repository.save(base)
        advanced = base.record_qa(assessment=QaAssessment(score=0.92), policy=POLICY)
        await repository.save(advanced)

        assert await repository.load("m-1") == advanced


class TestFileSafety:
    async def test_unsafe_mission_id_is_rejected(self, repository: FileBlueprintRepository) -> None:
        with pytest.raises(ValueError, match="쓸 수 없는 mission id"):
            await repository.load("../escape")

    async def test_file_is_owner_only(
        self, repository: FileBlueprintRepository, tmp_path: Path
    ) -> None:
        await repository.save(_approved_state())
        mode = (tmp_path / "blueprint_m-1.json").stat().st_mode & 0o777
        assert mode == 0o600

    async def test_no_temporary_file_is_left_behind(
        self, repository: FileBlueprintRepository, tmp_path: Path
    ) -> None:
        await repository.save(_approved_state())
        assert [item.name for item in tmp_path.iterdir()] == ["blueprint_m-1.json"]

    async def test_root_is_created_on_demand(self, tmp_path: Path) -> None:
        repository = FileBlueprintRepository(root=tmp_path / "nested" / "store")
        await repository.save(_approved_state())
        assert await repository.load("m-1") is not None
