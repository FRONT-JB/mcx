"""checkpoint — 증거로 입증된 변경을 되돌릴 수 있는 기준점으로 고정한 결과.

계약: ``docs/adr/0046-verified-checkpoint-commits.md``

git이 그 수단이지만 **개념은 vendor 중립이다** — *"여기까지는 증거가 지지한다"*
는 표식이며, rollback 범위(ADR-0032)와 ``changed_files`` 수집(ADR-0029)이 딛고
설 자리다. 그래서 결과 타입이 domain에 있고 커밋 수단은 adapter에 있다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Checkpoint:
    """checkpoint 시도 하나의 결과. ``commit``이 ``None``이면 남긴 것이 없다."""

    committed: bool
    commit: str | None = None
    ac_keys: tuple[str, ...] = ()
    #: 남기지 않은 이유. 조용한 누락을 만들지 않는다 — 사용자가 "커밋됐겠지"로
    #: 읽으면 되돌릴 지점이 없다는 것을 실패한 뒤에 알게 된다.
    skipped: str | None = None
    #: 비밀 경로 규칙으로 스테이징에서 뺀 파일들 (ADR-0046 §4).
    excluded: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rollback:
    """마지막 입증 지점으로 되돌린 결과 (ADR-0047).

    ``reverted``가 거짓이면 트리는 그대로다 — 되돌릴 지점이 없었거나 되돌리기
    자체가 실패했다는 뜻이며, 어느 쪽인지는 ``skipped``에 남는다.
    """

    reverted: bool
    #: 되돌아간 지점. 우리 브랜치의 커밋은 checkpoint뿐이므로 곧 HEAD다.
    commit: str | None = None
    #: 되돌리지 않은 이유. 실패는 미션을 죽이지 않으므로 여기로만 드러난다.
    skipped: str | None = None
