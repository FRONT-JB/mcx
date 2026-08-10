"""디스크 대조 — 제안은 확인되어야 명령이 된다 (ADR-0044 §3).

upstream 계약을 그대로 받는다: 대조에 실패한 제안은 버린다.
*"must never produce a phantom failure."*
"""

from pathlib import Path

from mission_control.adapters.verification.entry_points import manifests, validate
from mission_control.domain.mechanical import CommandKind, ProposedCommands


def _proposed(**kinds: str) -> ProposedCommands:
    return ProposedCommands(commands={CommandKind(key): value for key, value in kinds.items()})


class TestManifests:
    def test_an_empty_workspace_yields_nothing(self, tmp_path: Path) -> None:
        """근거가 없으면 AI 호출조차 하지 않는다."""
        assert manifests(tmp_path) == ()

    def test_what_is_there_is_read(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

        found = manifests(tmp_path)

        assert [name for name, _ in found] == ["pyproject.toml"]
        assert "[project]" in found[0][1]


class TestPackageScripts:
    def test_a_declared_script_survives(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest"}}', encoding="utf-8")

        result = validate(_proposed(test="npm run test"), workspace=tmp_path)

        assert result.commands[CommandKind.TEST] == "npm run test"
        assert result.dropped == ()

    def test_an_undeclared_script_is_dropped(self, tmp_path: Path) -> None:
        """이것이 phantom failure의 씨앗이다 — 있지도 않은 script를 Verify가 실행한다."""
        (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest"}}', encoding="utf-8")

        result = validate(_proposed(lint="npm run lint"), workspace=tmp_path)

        assert result.commands == {}
        assert len(result.dropped) == 1
        assert "lint" in result.dropped[0].reason

    def test_a_broken_package_json_drops_everything_rather_than_guessing(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "package.json").write_text("{ not json", encoding="utf-8")

        result = validate(_proposed(test="npm run test"), workspace=tmp_path)

        assert result.commands == {}


class TestMakeTargets:
    def test_a_declared_target_survives(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("check:\n\tpytest\n\n.PHONY: check\n", encoding="utf-8")

        result = validate(_proposed(test="make check"), workspace=tmp_path)

        assert result.commands[CommandKind.TEST] == "make check"

    def test_an_undeclared_target_is_dropped(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("check:\n\tpytest\n", encoding="utf-8")

        result = validate(_proposed(build="make dist"), workspace=tmp_path)

        assert result.commands == {}
        assert "dist" in result.dropped[0].reason

    def test_body_lines_are_not_targets(self, tmp_path: Path) -> None:
        """들여쓰기된 줄은 명령이지 target이 아니다."""
        (tmp_path / "Makefile").write_text("check:\n\tpytest tests:\n", encoding="utf-8")

        result = validate(_proposed(test="make pytest"), workspace=tmp_path)

        assert result.commands == {}


class TestExecutables:
    def test_a_binary_on_path_survives(self, tmp_path: Path) -> None:
        result = validate(_proposed(test="python -V"), workspace=tmp_path)

        assert result.commands[CommandKind.TEST] == "python -V"

    def test_a_binary_that_is_not_there_is_dropped(self, tmp_path: Path) -> None:
        result = validate(_proposed(test="totally-not-a-real-binary-xyz --run"), workspace=tmp_path)

        assert result.commands == {}
        assert "PATH" in result.dropped[0].reason


class TestWhatIsDropped:
    def test_dropping_is_recorded_not_silent(self, tmp_path: Path) -> None:
        """아무것도 못 찾은 것과 찾았는데 전부 버린 것은 다른 상황이다."""
        nothing = validate(ProposedCommands(), workspace=tmp_path)
        all_dropped = validate(_proposed(test="nope-xyz"), workspace=tmp_path)

        assert not nothing and nothing.dropped == ()
        assert not all_dropped and len(all_dropped.dropped) == 1

    def test_a_chained_command_cannot_be_checked_so_it_goes(self, tmp_path: Path) -> None:
        result = validate(_proposed(lint="ruff check . && mypy src"), workspace=tmp_path)

        assert result.commands == {}
        assert "판정할 수 없다" in result.dropped[0].reason
