"""작업 트리 관찰 결과 — 무엇이 바뀌었는가.

계약: ``docs/adr/0048-changed-files-collection.md``

git이 수단이지만 개념은 vendor 중립이다 — *"마지막 입증 지점 이후 손댄 것"* 이며,
Verify의 증거에 실려 사용자와 판정이 함께 본다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceChanges:
    """수집 결과.

    ``error``가 있으면 **빈 목록이 "변경 없음"을 뜻하지 않는다** — 관찰 자체가
    불가능했다는 뜻이다. 둘을 한 필드로 뭉치면 그 구분이 사라진다.
    """

    paths: tuple[str, ...] = ()
    error: str | None = None
