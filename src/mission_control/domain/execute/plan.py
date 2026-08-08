"""Execute 실행 순서 — 다음에 실행할 AC의 결정적 선택.

v1은 dependency 파생이 없으므로 순서는 승인된 Blueprint의 **선언 순서**다
(``docs/adr/0024-execute-v1-execution-model.md`` §3). 이 모듈은 목록을 앞에서
부터 훑어 아직 실행되지 않은 첫 AC를 고르는 순수 함수 하나다 — 계산이 이렇게
작은데도 모듈로 분리한 이유는, dependency 파생이 도입될 때 바뀌는 곳이 상태나
use case가 아니라 **이 선택 함수**임을 위치로 못박기 위해서다.

계약: ``docs/07_EXECUTE.md`` §6.3, §6.4
"""

from __future__ import annotations

from mission_control.domain.blueprint.spec import AcceptanceCriterion, Blueprint
from mission_control.domain.execute.state import AttemptStatus, ExecuteState


def next_criterion(*, blueprint: Blueprint, state: ExecuteState) -> AcceptanceCriterion | None:
    """선언 순서에서 아직 실행되지 않은 첫 AC. 전부 실행됐으면 ``None``.

    "실행됨"의 기준은 **현재 Blueprint revision**의 ``EXECUTED_UNVERIFIED``
    attempt다. 이전 revision의 실행은 세지 않는다 — 새 revision이 승인되면
    이전 결과를 자동 재사용하지 않는다 (``docs/06_BLUEPRINT.md`` §9).

    실패한 AC는 여전히 "실행되지 않음"이므로 다시 선택된다. 실패 후 재시도가
    자연스럽게 첫 순위가 되고, 다른 AC로의 진행은 상태의 실패 중단 규칙이
    막는다 (ADR-0024 §3).
    """
    for criterion in blueprint.acceptance_criteria:
        latest = state.latest_for(ac_key=criterion.key, blueprint_revision=blueprint.revision)
        if latest is None or latest.status is not AttemptStatus.EXECUTED_UNVERIFIED:
            return criterion
    return None
