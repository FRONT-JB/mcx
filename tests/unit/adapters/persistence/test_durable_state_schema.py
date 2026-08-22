"""다섯 durable JSON 문서의 schema version과 최상위 필드 계약."""

import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from mission_control.adapters.persistence.file_blueprint_repository import (
    FileBlueprintRepository,
)
from mission_control.adapters.persistence.file_brief_repository import FileBriefRepository
from mission_control.adapters.persistence.file_execute_repository import FileExecuteRepository
from mission_control.adapters.persistence.file_mission_repository import FileMissionRepository
from mission_control.adapters.persistence.file_verify_repository import FileVerifyRepository
from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.brief.state import BriefState
from mission_control.domain.execute.state import ExecuteState
from mission_control.domain.mission import MissionRecord
from mission_control.domain.verify.evidence import VerifyState

MISSION_ID = "m-1"


def _blueprint_state(mission_id: str) -> BlueprintState:
    blueprint = Blueprint(
        mission_id=mission_id,
        brief_revision=1,
        goal="댓글을 쓰고 볼 수 있다",
        acceptance_criteria=(
            AcceptanceCriterion(
                description="목록에 새 댓글이 보인다",
                verify_command="pytest",
                output_assertion="1 passed",
            ),
        ),
    )
    return BlueprintState.start(blueprint=blueprint)


def _repository_cases(tmp_path: Path):
    return (
        (
            "brief",
            FileBriefRepository(root=tmp_path),
            lambda mission_id: BriefState.start(
                mission_id=mission_id, initial_intent="댓글 기능을 추가하고 싶다"
            ),
            tmp_path / f"brief_{MISSION_ID}.json",
        ),
        (
            "blueprint",
            FileBlueprintRepository(root=tmp_path),
            _blueprint_state,
            tmp_path / f"blueprint_{MISSION_ID}.json",
        ),
        (
            "execute",
            FileExecuteRepository(root=tmp_path),
            lambda mission_id: ExecuteState.start(mission_id=mission_id),
            tmp_path / f"execute_{MISSION_ID}.json",
        ),
        (
            "verify",
            FileVerifyRepository(root=tmp_path),
            lambda mission_id: VerifyState.start(mission_id=mission_id),
            tmp_path / f"verify_{MISSION_ID}.json",
        ),
        (
            "mission",
            FileMissionRepository(root=tmp_path),
            lambda mission_id: MissionRecord.create(
                mission_id=mission_id, workspace="/tmp/mission"
            ),
            tmp_path / f"mission_{MISSION_ID}.json",
        ),
    )


@pytest.mark.parametrize(
    "case_index", range(5), ids=("brief", "blueprint", "execute", "verify", "mission")
)
async def test_repository_save_writes_schema_version(tmp_path: Path, case_index: int) -> None:
    _, repository, state_factory, path = _repository_cases(tmp_path)[case_index]

    await repository.save(state_factory(MISSION_ID))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1


@pytest.mark.parametrize(
    "case_index", range(5), ids=("brief", "blueprint", "execute", "verify", "mission")
)
async def test_repository_load_accepts_versionless_documents(
    tmp_path: Path, case_index: int
) -> None:
    _, repository, state_factory, path = _repository_cases(tmp_path)[case_index]
    payload = json.loads(state_factory(MISSION_ID).model_dump_json())
    payload.pop("schema_version")
    path.write_text(json.dumps(payload), encoding="utf-8")

    restored = await repository.load(MISSION_ID)

    assert restored is not None
    assert restored.schema_version == 1
    assert json.loads(restored.model_dump_json())["schema_version"] == 1


@pytest.mark.parametrize(
    "case_index", range(5), ids=("brief", "blueprint", "execute", "verify", "mission")
)
@pytest.mark.parametrize(
    "field, value",
    (("schema_version", 99), ("unknown_field", True)),
    ids=("unsupported-version", "unknown-field"),
)
async def test_repository_load_rejects_unknown_document_contract(
    tmp_path: Path, case_index: int, field: str, value: object
) -> None:
    _, repository, state_factory, path = _repository_cases(tmp_path)[case_index]
    payload = json.loads(state_factory(MISSION_ID).model_dump_json())
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        await repository.load(MISSION_ID)
