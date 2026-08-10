"""Stage→backend 라우팅 테이블 — ADR-0039 Verification 항목."""

from pathlib import Path

import pytest

from mission_control.cli.calls import CallCounter
from mission_control.cli.composition import (
    EXECUTION_BACKENDS,
    TEXT_BACKENDS,
    StateLayout,
    default_adapters,
    evolve_service,
    routed_adapters,
)
from mission_control.cli.routing import (
    STAGE_LANES,
    Lane,
    RoutingConfigError,
    RoutingTable,
    load_routing,
)
from mission_control.domain.stage import Stage

_KNOWN = {
    Lane.TEXT: frozenset(TEXT_BACKENDS),
    Lane.EXECUTION: frozenset(EXECUTION_BACKENDS),
}


def _write(root: Path, body: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_no_config_file_means_no_profile(tmp_path: Path) -> None:
    """파일 부재만이 정당한 '프로필 없음'이다 (§4)."""
    table = load_routing(tmp_path, known=_KNOWN)

    assert table == RoutingTable.empty()
    assert table.backend(Stage.BRIEF, Lane.TEXT) is None


def test_an_unknown_stage_key_is_rejected_at_load(tmp_path: Path) -> None:
    _write(tmp_path, '[stages.reflect]\ntext = "claude"\n')

    with pytest.raises(RoutingConfigError) as caught:
        load_routing(tmp_path, known=_KNOWN)
    assert "reflect" in str(caught.value)


def test_an_unknown_backend_name_is_rejected_at_load(tmp_path: Path) -> None:
    _write(tmp_path, '[default]\ntext = "gemini"\n')

    with pytest.raises(RoutingConfigError) as caught:
        load_routing(tmp_path, known=_KNOWN)
    assert "gemini" in str(caught.value)


def test_a_malformed_present_file_raises_instead_of_falling_back(tmp_path: Path) -> None:
    """조용한 재라우팅 금지 — 사용자가 지정하지 않은 AI가 도는 것보다 멈추는 게 낫다."""
    _write(tmp_path, "[stages.brief\ntext =")

    with pytest.raises(RoutingConfigError):
        load_routing(tmp_path, known=_KNOWN)


def test_resolution_prefers_stage_then_default(tmp_path: Path) -> None:
    _write(
        tmp_path,
        '[default]\ntext = "claude"\n\n[stages.verify]\ntext = "codex"\n',
    )
    table = load_routing(tmp_path, known=_KNOWN)

    assert table.backend(Stage.VERIFY, Lane.TEXT) == "codex"
    assert table.backend(Stage.BRIEF, Lane.TEXT) == "claude"


def test_resolution_falls_through_to_the_assembly_default(tmp_path: Path) -> None:
    """3단의 마지막은 설정이 아니라 조립 기본값이므로 ``None``이다."""
    _write(tmp_path, '[stages.verify]\ntext = "codex"\n')
    table = load_routing(tmp_path, known=_KNOWN)

    assert table.backend(Stage.BRIEF, Lane.TEXT) is None


def test_reading_a_lane_a_stage_does_not_use_is_an_error() -> None:
    with pytest.raises(RoutingConfigError):
        RoutingTable.empty().backend(Stage.BRIEF, Lane.EXECUTION)
    assert RoutingTable.empty().backend(Stage.EXECUTE, Lane.TEXT) is None


def test_binding_a_lane_a_stage_does_not_use_is_rejected(tmp_path: Path) -> None:
    """효과 없는 줄을 조용히 받아들이면 운용자가 라우팅했다고 오해한다."""
    _write(tmp_path, '[stages.brief]\nexecution = "codex_cli"\n')

    with pytest.raises(RoutingConfigError):
        load_routing(tmp_path, known=_KNOWN)


def test_every_stage_declares_its_lanes() -> None:
    """Stage enum이 늘면 라우팅 표도 같이 늘어야 한다 — 조용한 누락 금지."""
    assert set(STAGE_LANES) == set(Stage)
    assert all(lanes for lanes in STAGE_LANES.values())


def test_registered_names_match_the_adapter_declarations() -> None:
    """레지스트리 키는 adapter가 스스로 말하는 backend 이름과 같아야 한다 (§7)."""
    for name, factory in TEXT_BACKENDS.items():
        assert factory().backend == name
    for name, factory in EXECUTION_BACKENDS.items():
        assert factory().backend == name
    assert "codex_cli" in EXECUTION_BACKENDS
    assert "codex" not in EXECUTION_BACKENDS


def test_routed_adapters_swap_only_the_routed_stage(tmp_path: Path) -> None:
    _write(tmp_path, '[stages.verify]\ntext = "codex"\n')

    adapters = routed_adapters(tmp_path, default_adapters())

    assert adapters.completion_for(Stage.VERIFY).backend == "codex"
    assert adapters.completion_for(Stage.BRIEF).backend == "claude"
    assert adapters.runtime_for(Stage.EXECUTE).backend == "codex_cli"


def test_evolve_shares_the_blueprint_text_lane(tmp_path: Path) -> None:
    """Evolve routing 축을 새로 만들지 않고 후속 Blueprint 생산자 둘이 한 lane을 쓴다."""
    _write(tmp_path, '[stages.blueprint]\ntext = "codex"\n')
    service = evolve_service(
        StateLayout.under(tmp_path), routed_adapters(tmp_path, default_adapters())
    )

    wonder_completion = vars(service.wonderer)["_completion"]
    reflect_completion = vars(service.reflector)["_completion"]
    assert wonder_completion is reflect_completion
    assert wonder_completion.backend == "codex"


def test_routed_adapters_keep_the_injected_base_when_no_config(tmp_path: Path) -> None:
    """설정이 없으면 주입된 조립이 그대로다 — 테스트 조립이 조용히 실물로 바뀌지 않는다."""
    base = default_adapters()

    adapters = routed_adapters(tmp_path, base)

    assert adapters.completion is base.completion
    assert adapters.runtime is base.runtime
    assert adapters.routed_completion == {}


def test_the_call_counter_wraps_routed_engines_too(tmp_path: Path) -> None:
    """라우팅된 실물이 계수에서 빠지면 그 Stage 사용량만 조용히 사라진다."""
    _write(tmp_path, '[stages.verify]\ntext = "codex"\n')
    adapters = CallCounter().wrap(routed_adapters(tmp_path, default_adapters()))

    routed = adapters.completion_for(Stage.VERIFY)

    assert type(routed).__name__ == "_CountedCompletion"
    assert routed.backend == "codex"


def test_recover_routes_its_own_execution_lane(tmp_path: Path) -> None:
    """Recover의 재투입은 Execute 행이 아니라 Recover 행을 쓴다."""
    _write(tmp_path, '[stages.recover]\nexecution = "codex_cli"\n')

    adapters = routed_adapters(tmp_path, default_adapters())

    assert Stage.RECOVER in adapters.routed_runtime
    assert Stage.EXECUTE not in adapters.routed_runtime
