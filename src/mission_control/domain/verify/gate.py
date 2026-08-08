"""Verify Gate — MISSION COMPLETE를 선언할 수 있는 유일한 판정.

``CLEAR``가 곧 ``MISSION COMPLETE``다. v1(mechanical만 구현)에서는 semantic
verdict가 존재하지 않으므로 **CLEAR에 도달할 수 없다** — 그 사실을 숨기지
않고 ``SEMANTIC_VERDICT_MISSING`` blocker로 드러낸다. semantic slice가
들어오면 이 blocker가 실제 verdict 요구로 바뀐다.

성공 계약이 없는 AC는 mechanical 층이 판정할 수 없다 — 통과로도 실패로도
세지 않고 ``NOT_MECHANICALLY_VERIFIABLE``로 구분한다 (ADR-0028 §3). 그런
AC의 완료 판정은 semantic 층의 몫이다.

계약: ``docs/08_VERIFY.md`` §9
결정: ``docs/adr/0026-verify-entry-requires-lineage.md``,
``docs/adr/0028-verify-v1-mechanical-contract.md``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mission_control.domain.blueprint.spec import Blueprint
from mission_control.domain.brief.gate import GateOutcome
from mission_control.domain.verify.evidence import VerificationEvidence, VerificationRun


class VerifyGateBlockingCondition(StrEnum):
    """MISSION COMPLETE 선언을 막은 조건."""

    CRITERION_UNVERIFIED = "criterion_unverified"
    VERIFICATION_FAILED = "verification_failed"
    NOT_MECHANICALLY_VERIFIABLE = "not_mechanically_verifiable"
    SEMANTIC_VERDICT_MISSING = "semantic_verdict_missing"


@dataclass(frozen=True, slots=True)
class VerifyGateBlocker:
    condition: VerifyGateBlockingCondition
    detail: str


@dataclass(frozen=True, slots=True)
class VerifyGateDecision:
    """한 Blueprint revision에 대한 Verify Gate 판정과 그 근거."""

    outcome: GateOutcome
    blueprint_revision: int
    gate_blockers: tuple[VerifyGateBlocker, ...]

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        """사람이 읽을 수 있는 이유 목록. 표시용이며 판정 근거는 원본 blocker다."""
        return tuple(blocker.detail for blocker in self.gate_blockers)


def _failure_reason(ac_key: str, run: VerificationRun) -> str:
    """run의 필드에서 실패 이유를 결정적으로 파생한다.

    exit code 0인데 실패라면 남은 가능성은 output_assertion 불일치뿐이다 —
    별도 reason 필드를 두지 않는 이유다 (ADR-0028 §4).
    """
    if run.missing_artifacts:
        return f"criterion {ac_key}: expected artifacts missing: " + ", ".join(
            run.missing_artifacts
        )
    if run.timed_out:
        return f"criterion {ac_key}: verify command timed out"
    if run.exit_code not in (0, None):
        return f"criterion {ac_key}: verify command exited with status {run.exit_code}"
    return f"criterion {ac_key}: output assertion not found in verify command output"


def evaluate_verify_gate(
    *, evidence: VerificationEvidence | None, blueprint: Blueprint
) -> VerifyGateDecision:
    """mechanical 증거가 MISSION COMPLETE를 지지하는지 판정한다.

    이 함수는 순수 함수다. 진입 조건(Blueprint Gate와 Execute Gate의
    ``CLEAR``)은 호출하는 application 계층이 이 판정 **전에** 확인한다 —
    Execute Gate와 같은 배치다.

    다른 revision의 evidence는 없는 것과 같다 — 새 revision이 승인되면
    이전 검증 결과를 자동 재사용하지 않는다 (``docs/06_BLUEPRINT.md`` §9).
    """
    current = (
        evidence
        if evidence is not None and evidence.blueprint_revision == blueprint.revision
        else None
    )

    gate_blockers: list[VerifyGateBlocker] = []
    for criterion in blueprint.acceptance_criteria:
        if not criterion.is_mechanically_verifiable:
            gate_blockers.append(
                VerifyGateBlocker(
                    condition=VerifyGateBlockingCondition.NOT_MECHANICALLY_VERIFIABLE,
                    detail=(
                        f"criterion {criterion.key} has no mechanical success contract; "
                        "its completion needs a semantic verdict"
                    ),
                )
            )
            continue

        run = current.run_for(criterion.key) if current is not None else None
        if run is None:
            gate_blockers.append(
                VerifyGateBlocker(
                    condition=VerifyGateBlockingCondition.CRITERION_UNVERIFIED,
                    detail=f"criterion {criterion.key} has not been mechanically verified",
                )
            )
        elif not run.passed:
            gate_blockers.append(
                VerifyGateBlocker(
                    condition=VerifyGateBlockingCondition.VERIFICATION_FAILED,
                    detail=_failure_reason(criterion.key, run),
                )
            )

    # v1에는 semantic 층이 없다. MISSION COMPLETE는 mechanical 통과만으로
    # 선언될 수 없으므로(08_VERIFY §9), 그 부재가 항상 판정에 드러난다.
    gate_blockers.append(
        VerifyGateBlocker(
            condition=VerifyGateBlockingCondition.SEMANTIC_VERDICT_MISSING,
            detail="semantic verdicts are not implemented yet; MISSION COMPLETE needs them",
        )
    )

    return VerifyGateDecision(
        outcome="HOLD",
        blueprint_revision=blueprint.revision,
        gate_blockers=tuple(gate_blockers),
    )
