"""진행 관측이 실제로 설치되는가 — CLI 배선 (ADR-0049 §5, Verification).

파서와 꼬리 파일 자체는 각자의 테스트가 본다. 여기서 보는 것은
*"명령이 도는 동안 adapter가 보고한 것이 원장 옆에 남는가"* 다. 설치 지점이
원장 구간을 여는 자리여야 sequence가 정해져 있고 둘의 생명주기가 어긋나지
않는다.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_control.cli import composition
from mission_control.cli.composition import default_adapters
from mission_control.cli.main import amain
from mission_control.cli.progress import last_activity
from mission_control.progress import RuntimeActivity, observed, record


class ReportingExecute:
    """실행 중 진행을 보고하는 stub — 실제 runtime adapter가 하는 일과 같다."""

    async def dispatch_next(self, *, mission_id: str) -> SimpleNamespace:
        assert observed() is True, "명령이 도는 동안 관측이 설치되어 있어야 한다"
        record(
            RuntimeActivity(kind="tool", tool="command_execution", detail="pytest tests/unit")
        )
        record(RuntimeActivity(kind="tool", tool="file_change", detail="src/app.py"))
        return SimpleNamespace(attempts=[SimpleNamespace(number=1)])

    async def decide_gate(self, *, mission_id: str) -> SimpleNamespace:
        return SimpleNamespace(outcome="CLEAR")


async def _mission(tmp_path: Path) -> list[str]:
    """진행 관측만 보므로 workspace는 git이 아닌 평범한 디렉터리로 둔다."""
    workspace = tmp_path / "plain"
    workspace.mkdir()
    argv = ["--mission", "m-1", "--state-dir", str(tmp_path / "state")]
    adapters = default_adapters()
    assert await amain(["brief", "start", "g", "--workspace", str(workspace), *argv], adapters) == 0
    return argv


async def test_progress_lands_next_to_the_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    argv = await _mission(tmp_path)
    monkeypatch.setattr(composition, "execute_service", lambda *a, **k: ReportingExecute())

    assert await amain(["execute", "next", *argv], default_adapters()) == 0

    line = last_activity(root=tmp_path / "state" / "state", mission_id="m-1", sequence=2)
    assert line is not None
    assert line.render() == "file_change src/app.py"


async def test_the_sink_is_removed_when_the_command_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """설치가 명령 밖으로 새면 다음 명령의 진행이 엉뚱한 파일로 간다."""
    argv = await _mission(tmp_path)
    monkeypatch.setattr(composition, "execute_service", lambda *a, **k: ReportingExecute())

    await amain(["execute", "next", *argv], default_adapters())

    assert observed() is False
