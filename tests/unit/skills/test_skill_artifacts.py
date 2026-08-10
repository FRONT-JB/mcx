"""plugin 산출물 — skill과 매니페스트 (ADR-0042, Phase 8).

가장 중요한 검사는 **skill이 존재하지 않는 tool을 부르지 못하는 것**이다.
skill은 산문이라 컴파일되지 않는다 — CLI에서 명령 하나를 빼면 tool은 파서
파생이라 따라 사라지지만, 그것을 부르는 skill 문장은 남아 host가 런타임에
실패한다. 그 경로를 여기서 끊는다.
"""

import json
from pathlib import Path
import re

import pytest

from mission_control.mcp import server

REPO = Path(__file__).resolve().parents[3]
SKILLS = REPO / "skills"

#: 문서 어디에 있든 tool 이름처럼 보이는 토큰. ``mcx_brief_*`` 같은 glob은
#: 끝이 ``_``라 걸러진다.
_TOOL_TOKEN = re.compile(r"\bmcx_[a-z_]+\b")


def _skill_files() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    _, _, rest = text.partition("---\n")
    body, _, _ = rest.partition("\n---\n")
    fields: dict[str, str] = {}
    for line in body.splitlines():
        key, sep, value = line.partition(":")
        if sep and not key.startswith(" "):
            fields[key.strip()] = value.strip().strip('"')
    return fields


class TestSkillsExist:
    def test_every_stage_has_a_skill_plus_the_umbrella(self) -> None:
        names = {path.parent.name for path in _skill_files()}

        assert names == {"mcx", "brief", "blueprint", "execute", "verify", "recover"}

    @pytest.mark.parametrize("path", _skill_files(), ids=lambda p: p.parent.name)
    def test_the_frontmatter_declares_a_name_and_description(self, path: Path) -> None:
        fields = _frontmatter(path.read_text(encoding="utf-8"))

        assert fields.get("name"), path
        assert fields.get("description"), path

    def test_no_two_skills_claim_the_same_name(self) -> None:
        names = [_frontmatter(path.read_text(encoding="utf-8"))["name"] for path in _skill_files()]

        assert len(names) == len(set(names))

    @pytest.mark.parametrize("path", _skill_files(), ids=lambda p: p.parent.name)
    def test_each_skill_declares_the_capabilities_it_needs(self, path: Path) -> None:
        """무엇을 host에게 요구하는지가 skill 자신에 적혀 있어야 한다 (ADR-0042 §1)."""
        assert "## Required Skill Capabilities" in path.read_text(encoding="utf-8")


class TestSkillsOnlyCallToolsThatExist:
    def test_every_named_tool_is_registered(self) -> None:
        registered = {tool.name for tool in server.definitions()}
        unknown: dict[str, set[str]] = {}

        for path in _skill_files():
            named = {
                token
                for token in _TOOL_TOKEN.findall(path.read_text(encoding="utf-8"))
                if not token.endswith("_")
            }
            missing = named - registered
            if missing:
                unknown[path.parent.name] = missing

        assert unknown == {}

    def test_the_check_would_catch_a_typo(self) -> None:
        """검사 자체가 도는지 — 등록되지 않은 이름은 실제로 걸러져야 한다."""
        registered = {tool.name for tool in server.definitions()}

        assert "mcx_brief_aks" not in registered
        assert _TOOL_TOKEN.findall("call `mcx_brief_aks` now") == ["mcx_brief_aks"]

    def test_every_named_flag_exists_in_the_parser(self) -> None:
        """인자 이름도 tool 이름과 같은 종류의 거짓말을 할 수 있다.

        이 검사가 실제로 둘을 잡았다 — skill이 ``mcx_blueprint_revise``에 자유
        텍스트를 넘긴다고 적었지만 실물은 ``--draft-file``을 요구하고,
        임계 미달 승인에는 ``--accept-below-threshold``가 필요하다.
        """
        import argparse

        from mission_control.cli.main import build_parser

        options: set[str] = set()

        def _walk(parser: argparse.ArgumentParser) -> None:
            for action in parser._actions:  # noqa: SLF001
                options.update(action.option_strings)
                if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
                    for child in action.choices.values():
                        _walk(child)

        _walk(build_parser())

        flag = re.compile(r"(?<![\w-])--[a-z][a-z-]+")
        unknown: dict[str, set[str]] = {}
        for path in _skill_files():
            named = set(flag.findall(path.read_text(encoding="utf-8")))
            missing = named - options
            if missing:
                unknown[path.parent.name] = missing

        assert unknown == {}

    def test_a_glob_is_not_read_as_a_tool_name(self) -> None:
        found = {t for t in _TOOL_TOKEN.findall("the `mcx_brief_*` tools") if not t.endswith("_")}

        assert found == set()


class TestManifests:
    def test_both_hosts_are_shipped(self) -> None:
        assert (REPO / ".claude-plugin" / "plugin.json").is_file()
        assert (REPO / ".codex-plugin" / "plugin.json").is_file()

    @pytest.mark.parametrize("directory", [".claude-plugin", ".codex-plugin"])
    def test_a_manifest_points_at_the_shared_skills(self, directory: str) -> None:
        """skill 본문은 host별로 갈라지지 않는다 — upstream 정렬."""
        manifest = json.loads((REPO / directory / "plugin.json").read_text(encoding="utf-8"))

        assert manifest["skills"] == "./skills/"
        assert manifest["name"] == "mcx"

    def test_each_host_points_at_its_bootstrap(self) -> None:
        """공유 server와 host별 plugin-root 해석을 혼동하지 않는다 (ADR-0042 §1.1)."""
        claude = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        codex = json.loads((REPO / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

        assert claude["mcpServers"] == "./.mcp.json"
        assert codex["mcpServers"] == "./.mcp.codex.json"

    @pytest.mark.parametrize("path", [".mcp.json", ".mcp.codex.json"])
    def test_both_bootstraps_start_the_same_server(self, path: str) -> None:
        mcp = json.loads((REPO / path).read_text(encoding="utf-8"))
        entry = mcp["mcpServers"]["mcx"]

        assert entry["command"] == "uvx"
        assert entry["args"][-1] == "mcx-mcp"

    def test_the_server_is_built_from_the_plugin_itself(self) -> None:
        """PyPI 배포 없이 완결된다 — 자기참조다.

        upstream은 소스를 플러그인에 다 넣고도 서버는 PyPI에서 가져오고
        (``uvx --from ouroboros-ai[mcp]``), ``${CLAUDE_PLUGIN_ROOT}``는 hooks
        에만 쓴다. 우리 선택은 등록된 divergence이며, 실물로 확인했다
        (2026-08-09: 설치 후 ``plugin:mcx:mcx ... ✔ Connected``).

        이 검사가 지키는 것: 배포판 이름으로 되돌리면 배포 전까지 플러그인이
        조용히 죽는다.
        """
        claude = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
        codex = json.loads((REPO / ".mcp.codex.json").read_text(encoding="utf-8"))

        assert claude["mcpServers"]["mcx"]["args"][1] == "${CLAUDE_PLUGIN_ROOT}[mcp]"
        assert codex["mcpServers"]["mcx"]["args"][1] == ".[mcp]"
        assert codex["mcpServers"]["mcx"]["cwd"] == "."

    def test_the_marketplace_makes_the_repo_installable(self) -> None:
        """저장소가 곧 marketplace다 (upstream 정렬, `source: "./"`)."""
        market = json.loads(
            (REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        (entry,) = market["plugins"]

        assert entry["name"] == "mcx"
        assert entry["source"] == "./"

    def test_the_plugin_declares_a_version(self) -> None:
        """`claude plugin validate`가 없으면 경고한다."""
        for directory in (".claude-plugin", ".codex-plugin"):
            manifest = json.loads((REPO / directory / "plugin.json").read_text(encoding="utf-8"))
            assert manifest["version"] == "0.1.0", directory

    def test_the_registered_entry_point_is_the_one_we_ship(self) -> None:
        """``mcx-mcp``는 별도 실행 파일이다 — CLI에 붙이면 순환이다 (ADR-0041 §1)."""
        pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")

        assert 'mcx-mcp = "mission_control.mcp.server:main"' in pyproject
