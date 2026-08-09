"""확인 명령이 성립하려면 무엇이 있어야 하는가 — 순수 판정 (ADR-0044 §3).

핵심은 하나다: **확인할 수 없는 것은 통과가 아니라 탈락이다.**
"""

import pytest

from mission_control.domain.mechanical import (
    EntryPointKind,
    required_entry_point,
)


class TestPackageScripts:
    @pytest.mark.parametrize(
        "command",
        ["npm run test", "yarn test", "pnpm test", "npm run  test", "bun run test"],
    )
    def test_a_package_manager_needs_the_script(self, command: str) -> None:
        requirement = required_entry_point(command)

        assert requirement is not None
        assert requirement.kind is EntryPointKind.PACKAGE_SCRIPT
        assert requirement.name == "test"

    def test_flags_do_not_become_the_script_name(self) -> None:
        requirement = required_entry_point("npm --silent run lint")

        assert requirement is not None
        assert requirement.name == "lint"


class TestMakeTargets:
    def test_make_needs_the_target(self) -> None:
        requirement = required_entry_point("make check")

        assert requirement is not None
        assert requirement.kind is EntryPointKind.MAKE_TARGET
        assert requirement.name == "check"

    def test_bare_make_is_not_judged(self) -> None:
        """기본 target이라 이름이 없다 — 확인할 수 없으면 탈락이다."""
        assert required_entry_point("make") is None


class TestExecutables:
    def test_a_plain_command_needs_its_binary(self) -> None:
        requirement = required_entry_point("pytest -q")

        assert requirement is not None
        assert requirement.kind is EntryPointKind.EXECUTABLE
        assert requirement.name == "pytest"

    def test_a_runner_points_at_what_it_runs(self) -> None:
        """`uv run pytest`가 요구하는 것은 uv가 아니라 pytest다."""
        requirement = required_entry_point("uv run pytest")

        assert requirement is not None
        assert requirement.name == "pytest"


class TestUnjudgeable:
    @pytest.mark.parametrize(
        "command",
        [
            "ruff check . && mypy src",
            "pytest | tee out.txt",
            "make lint; make test",
            "pytest > report.txt",
            "",
            "   ",
        ],
    )
    def test_what_cannot_be_judged_is_dropped(self, command: str) -> None:
        """복합 명령은 진입점 하나로 환원되지 않는다.

        upstream은 패키지 매니저별 플래그 파싱에 상당한 코드를 쓰지만 우리는 그
        범위를 도입하지 않는다 — 대가는 복합 명령을 못 받는 것이고, 이득은
        **틀린 통과가 없는 것**이다.
        """
        assert required_entry_point(command) is None
