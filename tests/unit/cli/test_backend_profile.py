"""backend 호출 설정 — 모델 seeding과 기록 (ADR-0042 §6).

핵심은 둘이다: **기계 바깥을 조용히 읽지 않는다**, 그리고 **읽은 값은 적는다**.
"""

from pathlib import Path

from mission_control.cli.backend_profile import (
    BackendProfile,
    load_codex_profile,
)
from mission_control.cli.composition import default_adapters, routed_adapters


def _codex_config(root: Path, body: str) -> Path:
    path = root / "codex.toml"
    path.write_text(body, encoding="utf-8")
    return path


class TestSeedingIsOptIn:
    def test_without_a_source_nothing_is_read_or_written(self, tmp_path: Path) -> None:
        """기본값이 seeding 없음인 이유 — 임시 디렉토리 테스트가 개발자의 실물
        ``~/.codex``를 읽는 것을 라우팅 테스트가 잡았다."""
        profile = load_codex_profile(tmp_path)

        assert profile == BackendProfile()
        assert not (tmp_path / "config.toml").exists()

    def test_a_missing_source_is_not_an_error(self, tmp_path: Path) -> None:
        profile = load_codex_profile(tmp_path, codex_config=tmp_path / "없다.toml")

        assert profile == BackendProfile()


class TestSeeding:
    def test_the_current_setting_is_adopted(self, tmp_path: Path) -> None:
        source = _codex_config(
            tmp_path, 'model = "gpt-5.6-sol"\nmodel_reasoning_effort = "xhigh"\n'
        )

        profile = load_codex_profile(tmp_path, codex_config=source)

        assert profile.model == "gpt-5.6-sol"
        assert profile.reasoning_effort == "xhigh"

    def test_what_was_adopted_is_written_down(self, tmp_path: Path) -> None:
        """기록이 목적이다 — 지금은 어떤 모델이 미션을 수행했는지 남지 않는다."""
        source = _codex_config(tmp_path, 'model = "gpt-5.6-sol"\n')

        load_codex_profile(tmp_path, codex_config=source)

        written = (tmp_path / "config.toml").read_text(encoding="utf-8")
        assert "[backends.codex_cli]" in written
        assert 'model = "gpt-5.6-sol"' in written

    def test_the_stored_value_wins_and_the_source_is_not_consulted(self, tmp_path: Path) -> None:
        """한 번 적히면 사용자 설정 변경이 미션을 조용히 바꾸지 않는다."""
        (tmp_path / "config.toml").write_text(
            '[backends.codex_cli]\nmodel = "고정"\n', encoding="utf-8"
        )
        source = _codex_config(tmp_path, 'model = "다른것"\n')

        assert load_codex_profile(tmp_path, codex_config=source).model == "고정"

    def test_an_existing_config_is_appended_to_not_rewritten(self, tmp_path: Path) -> None:
        """사용자가 쓴 주석과 배치를 보존한다."""
        (tmp_path / "config.toml").write_text(
            "# 내 주석\n[stages.execute]\nexecution = 'codex_cli'\n", encoding="utf-8"
        )
        source = _codex_config(tmp_path, 'model = "m"\n')

        load_codex_profile(tmp_path, codex_config=source)

        written = (tmp_path / "config.toml").read_text(encoding="utf-8")
        assert "# 내 주석" in written
        assert "[stages.execute]" in written

    def test_a_source_without_a_model_writes_nothing(self, tmp_path: Path) -> None:
        source = _codex_config(tmp_path, 'approval_policy = "never"\n')

        assert load_codex_profile(tmp_path, codex_config=source) == BackendProfile()
        assert not (tmp_path / "config.toml").exists()


class TestComposition:
    def test_the_model_reaches_the_runtime(self, tmp_path: Path) -> None:
        source = _codex_config(tmp_path, 'model = "gpt-5.6-sol"\n')

        adapters = routed_adapters(tmp_path, default_adapters(), codex_config=source)
        command = adapters.runtime.build_command(  # type: ignore[attr-defined]
            workspace="/w", last_message_path="/l"
        )

        assert "--model" in command
        assert "gpt-5.6-sol" in command

    def test_a_non_codex_runtime_is_left_alone(self, tmp_path: Path) -> None:
        """모델 축은 vendor마다 이름이 다르므로 공통 port에 올리지 않는다."""
        base = default_adapters()
        source = _codex_config(tmp_path, 'model = "m"\n')

        class _Fake:
            backend = "fake"

        adapters = routed_adapters(
            tmp_path,
            __import__("dataclasses").replace(base, runtime=_Fake()),  # type: ignore[arg-type]
            codex_config=source,
        )

        assert isinstance(adapters.runtime, _Fake)
