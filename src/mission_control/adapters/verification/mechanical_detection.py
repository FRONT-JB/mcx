"""제안과 검증을 잇는 자리 (ADR-0044 §3).

port(:class:`~mission_control.application.ports.MechanicalCommandDetector`)는
**검증된 명령만** 돌려주기로 계약한다. 그 계약을 지키는 곳이 여기다 — 모델에게
묻고(``adapters/text/mechanical_detector.py``), 디스크와 대조하고
(``entry_points.py``), 통과한 것만 내보낸다.

application이 두 조각을 직접 조립하지 않는 이유는 계층 방향이다. 대조는
파일시스템을 읽으므로 adapter의 일이고, application은 port 하나만 안다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from mission_control.adapters.verification.entry_points import manifests, validate
from mission_control.application.ports import MechanicalDetectionRequest
from mission_control.domain.mechanical import MechanicalCommands, ProposedCommands


class MechanicalProposer(Protocol):
    """모델에게 묻는 쪽. 이 결과는 **아직 명령이 아니다**."""

    async def propose(self, request: MechanicalDetectionRequest) -> ProposedCommands:
        """manifest에서 확인 명령 후보를 제안한다. 검증하지 않는다."""
        ...


class VerifiedMechanicalDetector:
    """제안 → 디스크 대조 → 통과분만. 실패는 빈 결과다."""

    def __init__(self, *, proposer: MechanicalProposer) -> None:
        self._proposer = proposer

    async def detect(self, workspace: str) -> MechanicalCommands:
        """확인 명령을 찾는다. 모델 호출은 최대 **1회**다 (ADR-0044 §3).

        manifest가 하나도 없으면 모델을 부르지 않는다 — 근거 없이 묻는 것은
        비용만 쓰고 추측을 부른다 (upstream ``no_manifests``).
        """
        root = Path(workspace)
        found = manifests(root)
        if not found:
            return MechanicalCommands()

        try:
            proposed = await self._proposer.propose(
                MechanicalDetectionRequest(workspace=workspace, manifests=found)
            )
        except Exception:  # noqa: BLE001 — 검출 실패가 미션을 죽이지 않는다
            return MechanicalCommands()

        return validate(proposed, workspace=root)
