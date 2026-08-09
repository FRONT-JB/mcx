"""backend 호출 설정 — 모델과 reasoning effort (ADR-0042 §6).

worker는 사용자 codex 설정을 상속하지 않는다 (``--ignore-user-config``). 그것이
재귀 경계다 — 상속하면 그 설정에 등록된 MCP 서버가 worker에게 보이고, 거기
``mcx-mcp``가 있으면 worker가 Mission Control을 되부를 수 있다
([ADR-0004](../../../docs/adr/0004-stage-scoped-minimum-capability.md)).

상속을 끊으면 모델이 우리 손에 있어야 한다. 값은 설정 파일에 적혀 있어야 하고,
**없으면 사용자가 지금 쓰는 값을 읽어 채택하되 그것을 기록한다** (사용자 결정
2026-08-09). 동작은 그대로이고 기록만 생긴다 — 지금은 worker의 모델을 주변
설정이 정하는데 그 사실이 어디에도 남지 않는다.

모델을 끝내 알 수 없어도 실행을 막지 않는다. 상속만 끊고 모델을 넘기지 않으면
codex 자기 기본값으로 가며, 그것은 애초에 모델을 고정하지 않은 사용자가 이미
쓰던 값이다 — 재귀 경계는 어느 쪽이든 서 있다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from mission_control.cli.routing import CONFIG_FILENAME

#: 사용자 codex 설정. 처음 한 번 여기서 값을 읽어 우리 설정으로 옮긴다.
CODEX_CONFIG = Path.home() / ".codex" / "config.toml"

#: 우리 설정에서 이 backend의 호출 설정을 담는 표 이름.
CODEX_BACKEND = "codex_cli"


@dataclass(frozen=True)
class BackendProfile:
    """한 backend를 부를 때 명시할 값. 둘 다 ``None``이면 vendor 기본값이다."""

    model: str | None = None
    reasoning_effort: str | None = None

    def __bool__(self) -> bool:
        return self.model is not None or self.reasoning_effort is not None


def load_codex_profile(root: Path, *, codex_config: Path | None = None) -> BackendProfile:
    """``<root>/config.toml``의 ``[backends.codex_cli]``를 읽는다.

    Args:
        root: ``--state-dir`` 값.
        codex_config: seeding 원천. **``None``이면 seeding하지 않는다** — 저장된
            값만 읽는 순수 조회다. 기본을 ``None``으로 둔 이유는 이 함수가 기계
            바깥(사용자 홈)을 조용히 읽으면 안 되기 때문이다. 실제로 임시
            디렉토리 테스트가 개발자의 실물 ``~/.codex``를 읽는 것을
            ``test_routed_adapters_keep_the_injected_base_when_no_config``가
            잡았다.

    저장된 값이 없고 ``codex_config``가 주어지면 거기서 읽어 **그 결과를 파일에
    적는다.** 적는 이유는 다음 실행이 같은 값을 쓰기 위해서가 아니라(그건 부수
    효과다) 어떤 모델이 미션을 수행했는지가 기록으로 남아야 하기 때문이다.

    설정 파일 자체의 파싱 오류는 여기서 다루지 않는다 — 같은 파일을
    :func:`~mission_control.cli.routing.load_routing`이 먼저 읽고 fail-fast한다.
    """
    stored = _stored(root)
    if stored is not None:
        return stored
    if codex_config is None:
        return BackendProfile()

    seeded = _seed(codex_config)
    if seeded:
        _append(root, seeded)
    return seeded


def _stored(root: Path) -> BackendProfile | None:
    """우리 설정에 이미 적혀 있으면 그것이 이긴다."""
    path = root / CONFIG_FILENAME
    if not path.is_file():
        return None
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None

    backends = raw.get("backends")
    if not isinstance(backends, dict):
        return None
    table = backends.get(CODEX_BACKEND)
    if not isinstance(table, dict):
        return None
    return BackendProfile(
        model=_text(table.get("model")),
        reasoning_effort=_text(table.get("reasoning_effort")),
    )


def _seed(codex_config: Path) -> BackendProfile:
    """사용자가 지금 쓰는 값을 읽는다. 읽을 수 없으면 빈 프로필이다."""
    try:
        raw = tomllib.loads(codex_config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return BackendProfile()
    return BackendProfile(
        model=_text(raw.get("model")),
        reasoning_effort=_text(raw.get("model_reasoning_effort")),
    )


def _append(root: Path, profile: BackendProfile) -> None:
    """표 하나를 덧붙인다. 기존 내용은 건드리지 않는다.

    없을 때만 부르므로 덧붙이기로 충분하고, 파싱 후 재작성하지 않으므로
    사용자가 쓴 주석과 배치가 보존된다.
    """
    path = root / CONFIG_FILENAME
    lines = [f"\n[backends.{CODEX_BACKEND}]"]
    if profile.model is not None:
        lines.append(f'model = "{profile.model}"')
    if profile.reasoning_effort is not None:
        lines.append(f'reasoning_effort = "{profile.reasoning_effort}"')
    block = "\n".join(lines) + "\n"

    try:
        root.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(block)
    except OSError:
        # 기록에 실패해도 실행은 막지 않는다 — 재귀 경계는 모델과 무관하게 선다.
        return


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None
