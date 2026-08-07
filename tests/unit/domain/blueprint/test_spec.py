"""Blueprint 명세와 acceptance criterion identity.

계약: docs/06_BLUEPRINT.md / docs/adr/0017-blueprint-schema-baseline.md
"""

from pydantic import ValidationError
import pytest

from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint


def _criterion(
    description: str = "댓글 작성 후 목록 맨 위에 보인다",
    *,
    verify_command: str | None = "pytest tests/test_comments.py",
    expected_artifacts: tuple[str, ...] = (),
    output_assertion: str | None = None,
) -> AcceptanceCriterion:
    return AcceptanceCriterion(
        description=description,
        verify_command=verify_command,
        expected_artifacts=expected_artifacts,
        output_assertion=output_assertion,
    )


def _blueprint(**overrides: object) -> Blueprint:
    defaults: dict[str, object] = {
        "mission_id": "m-1",
        "brief_revision": 4,
        "goal": "로그인 사용자가 댓글을 쓰고 볼 수 있다",
    }
    defaults.update(overrides)
    return Blueprint(**defaults)  # type: ignore[arg-type]


class TestCriterionIdentity:
    """AC는 목록의 위치가 아니라 성공 계약의 내용으로 식별된다."""

    def test_same_contract_yields_the_same_key(self) -> None:
        assert _criterion().key == _criterion().key

    def test_key_has_the_expected_shape(self) -> None:
        key = _criterion().key

        assert key.startswith("ac_")
        assert len(key) == len("ac_") + 16

    def test_position_does_not_affect_identity(self) -> None:
        """중간에 AC를 끼워 넣어도 기존 AC의 identity가 밀리지 않는다."""
        first = _criterion("A", verify_command="cmd-a")
        second = _criterion("B", verify_command="cmd-b")
        inserted = _criterion("C", verify_command="cmd-c")

        before = _blueprint(acceptance_criteria=(first, second))
        after = _blueprint(acceptance_criteria=(first, inserted, second))

        assert before.criterion_keys[0] == after.criterion_keys[0]
        assert second.key in after.criterion_keys

    @pytest.mark.parametrize(
        "changed",
        [
            {"description": "다른 설명"},
            {"verify_command": "pytest -k other"},
            {"expected_artifacts": ("build/report.json",)},
            {"output_assertion": "exit code is 0"},
        ],
    )
    def test_any_contract_change_yields_a_new_key(self, changed: dict[str, object]) -> None:
        """계약이 바뀌면 다른 AC다. 이전 AC의 증거를 물려받지 않는다."""
        original = _criterion()
        modified = original.model_copy(update=changed)

        assert modified.key != original.key

    def test_artifact_order_is_part_of_the_contract(self) -> None:
        """목록 순서를 정규화하지 않는다. 계약을 임의로 해석하지 않기 위해서다."""
        one = _criterion(expected_artifacts=("a.json", "b.json"))
        other = _criterion(expected_artifacts=("b.json", "a.json"))

        assert one.key != other.key

    def test_lookup_by_key_returns_the_criterion(self) -> None:
        criterion = _criterion()
        blueprint = _blueprint(acceptance_criteria=(criterion,))

        assert blueprint.criterion_for(criterion.key) == criterion
        assert blueprint.criterion_for("ac_0000000000000000") is None


class TestVerifiability:
    def test_criterion_without_any_check_is_not_verifiable(self) -> None:
        criterion = _criterion(verify_command=None)

        assert criterion.is_mechanically_verifiable is False

    @pytest.mark.parametrize(
        "given",
        [
            {"verify_command": "pytest"},
            {"verify_command": None, "expected_artifacts": ("build/out.json",)},
            {"verify_command": "pytest", "output_assertion": "OK"},
        ],
    )
    def test_any_single_check_makes_it_verifiable(self, given: dict[str, object]) -> None:
        criterion = _criterion(**given)  # type: ignore[arg-type]

        assert criterion.is_mechanically_verifiable is True

    def test_output_assertion_without_a_command_is_rejected(self) -> None:
        """검사할 출력을 만드는 것이 명령이므로, 명령 없는 출력 조건은 아무것도
        대조하지 않으면서 검증 수단이 있는 것처럼 보인다."""
        with pytest.raises(ValidationError, match="output_assertion requires verify_command"):
            _criterion(verify_command=None, output_assertion="출력에 OK가 있다")

    def test_unverifiable_criteria_are_reported(self) -> None:
        """검증 불가능한 AC를 금지하지 않고 드러낸다."""
        verifiable = _criterion("A", verify_command="cmd")
        bare = _criterion("B", verify_command=None)
        blueprint = _blueprint(acceptance_criteria=(verifiable, bare))

        assert blueprint.unverifiable_criteria == (bare,)


class TestImmutabilityAndShape:
    def test_blueprint_is_frozen(self) -> None:
        blueprint = _blueprint()

        with pytest.raises(ValidationError):
            blueprint.goal = "다른 목표"

    def test_undeclared_fields_are_rejected(self) -> None:
        """검토 경로를 거치지 않은 내용이 불변 산출물에 실리면 안 된다."""
        with pytest.raises(ValidationError):
            _blueprint(ontology_schema={"name": "임의"})

    def test_empty_goal_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _blueprint(goal="")

    def test_brief_revision_is_carried(self) -> None:
        """어느 Brief revision에서 나왔는지 없으면 승인 lineage가 끊긴다."""
        blueprint = _blueprint(brief_revision=7)

        assert blueprint.brief_revision == 7
        assert blueprint.revision == 1

    def test_non_goals_are_first_class(self) -> None:
        blueprint = _blueprint(non_goals=("수정·삭제는 이번 범위가 아니다",))

        assert blueprint.non_goals == ("수정·삭제는 이번 범위가 아니다",)
