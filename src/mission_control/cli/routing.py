"""Stage→backend 라우팅 테이블과 설정 로드 (ADR-0039).

키는 **닫힌 Stage enum**이고 값은 **lane별 backend 이름 쌍**이다. 해석은 3단
(``stages[stage][lane]`` → ``default[lane]`` → 조립 기본값)이고, 검증은
fail-fast다 — 설정이 존재하는데 읽히지 않으면 조용히 기본 조립으로 넘어가지
않고 예외를 올린다. 운용자의 라우팅 실수가 조용한 재라우팅이 되면 사용자는
자기가 지정하지 않은 AI가 미션을 수행한 것을 모른다 (§4).

backend 이름은 vendor가 아니라 **vendor×전송**이다 (§7) — 실행 lane의 이름이
``codex``가 아니라 ``codex_cli``인 이유이며, upstream이 같은 바이너리를
``codex``/``codex_mcp``로 나눠 등록하는 것과 같은 축이다.

계약: ``docs/adr/0039-stage-runtime-routing-table.md``
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import tomllib

from mission_control.domain.errors import MissionControlError
from mission_control.domain.stage import Stage

#: 설정 파일 이름. 위치는 ``--state-dir`` 바로 아래다 (§5).
CONFIG_FILENAME = "config.toml"


class Lane(StrEnum):
    """한 Stage가 vendor를 부르는 두 통로."""

    TEXT = "text"
    EXECUTION = "execution"


#: Stage가 실제로 쓰는 lane. Execute는 dependency analysis text + worker
#: execution을 함께 쓰고, Recover는 실행만 쓴다. 안 쓰는 lane을 조회하는 것은
#: 프로그래밍 오류이며 조용히 기본값을
#: 주지 않는다 (§2).
STAGE_LANES: Mapping[Stage, frozenset[Lane]] = {
    Stage.BRIEF: frozenset({Lane.TEXT}),
    Stage.BLUEPRINT: frozenset({Lane.TEXT}),
    Stage.EXECUTE: frozenset({Lane.TEXT, Lane.EXECUTION}),
    Stage.VERIFY: frozenset({Lane.TEXT}),
    Stage.RECOVER: frozenset({Lane.EXECUTION}),
}


class RoutingConfigError(MissionControlError):
    """설정이 존재하는데 라우팅으로 읽을 수 없다 (§4).

    파일 부재는 여기 해당하지 않는다 — 그것만이 정당한 "프로필 없음"이다.
    """


@dataclass(frozen=True)
class RoutingTable:
    """Stage×lane → backend 이름. 이름을 담을 뿐 adapter를 만들지 않는다."""

    stages: Mapping[Stage, Mapping[Lane, str]]
    default: Mapping[Lane, str]

    @classmethod
    def empty(cls) -> RoutingTable:
        """프로필 없음 — 모든 조회가 조립 기본값으로 내려간다."""
        return cls(stages={}, default={})

    def backend(self, stage: Stage, lane: Lane) -> str | None:
        """3단 해석. ``None``은 "조립 기본값을 쓰라"는 뜻이다.

        Raises:
            RoutingConfigError: ``stage``가 구조적으로 쓰지 않는 lane 조회.
        """
        if lane not in STAGE_LANES[stage]:
            raise RoutingConfigError(
                f"{stage.value} Stage는 {lane.value} lane을 쓰지 않는다 — 조회 자체가 오류다"
            )
        bound = self.stages.get(stage)
        if bound is not None and lane in bound:
            return bound[lane]
        return self.default.get(lane)


def load_routing(root: Path, *, known: Mapping[Lane, Collection[str]]) -> RoutingTable:
    """``<root>/config.toml``을 읽는다. 파일이 없으면 빈 테이블이다.

    Args:
        root: ``--state-dir`` 값. ``state/``·``outputs/``와 같은 층이다.
        known: lane별로 등록된 backend 이름. 이 밖의 이름은 로드에서 거부된다.

    Raises:
        RoutingConfigError: 파일이 존재하는데 파싱·검증에 실패한 모든 경우.
    """
    path = root / CONFIG_FILENAME
    if not path.is_file():
        return RoutingTable.empty()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise RoutingConfigError(f"{path}를 읽을 수 없다: {exc}") from exc
    return _parse(raw, path=path, known=known)


def _parse(
    raw: Mapping[str, object], *, path: Path, known: Mapping[Lane, Collection[str]]
) -> RoutingTable:
    default = _lanes(raw.get("default", {}), where="default", path=path, known=known)

    stages_raw = raw.get("stages", {})
    if not isinstance(stages_raw, Mapping):
        raise RoutingConfigError(f"{path}: [stages]는 표여야 한다")

    stages: dict[Stage, Mapping[Lane, str]] = {}
    for key, value in stages_raw.items():
        try:
            stage = Stage(key)
        except ValueError as exc:
            names = ", ".join(member.value for member in Stage)
            raise RoutingConfigError(
                f"{path}: 알 수 없는 Stage `{key}` — 가능한 이름은 {names}"
            ) from exc
        stages[stage] = _lanes(
            value, where=f"stages.{stage.value}", path=path, known=known, stage=stage
        )
    return RoutingTable(stages=stages, default=default)


def _lanes(
    raw: object,
    *,
    where: str,
    path: Path,
    known: Mapping[Lane, Collection[str]],
    stage: Stage | None = None,
) -> Mapping[Lane, str]:
    if not isinstance(raw, Mapping):
        raise RoutingConfigError(f"{path}: [{where}]는 표여야 한다")

    lanes: dict[Lane, str] = {}
    for key, value in raw.items():
        try:
            lane = Lane(key)
        except ValueError as exc:
            names = ", ".join(member.value for member in Lane)
            raise RoutingConfigError(
                f"{path}: [{where}]의 알 수 없는 lane `{key}` — 가능한 이름은 {names}"
            ) from exc
        if stage is not None and lane not in STAGE_LANES[stage]:
            raise RoutingConfigError(
                f"{path}: [{where}]는 {lane.value} lane을 쓰지 않는다 — 이 줄은 효과가 없다"
            )
        if not isinstance(value, str):
            raise RoutingConfigError(
                f"{path}: [{where}].{lane.value}는 backend 이름 문자열이어야 한다"
            )
        registered = known.get(lane, ())
        if value not in registered:
            names = ", ".join(sorted(registered)) or "(등록된 backend 없음)"
            raise RoutingConfigError(
                f"{path}: [{where}].{lane.value}의 알 수 없는 backend `{value}` — "
                f"등록된 이름은 {names}"
            )
        lanes[lane] = value
    return lanes
