"""Verify Gate — MISSION COMPLETE를 선언할 수 있는 유일한 판정.

``CLEAR``가 곧 ``MISSION COMPLETE``다. 조건은 넷이다 (ADR-0030 §4) — 기계
검증 가능한 AC의 mechanical 통과, 모든 AC의 verdict 통과, 불확신 없음,
게이밍 의심 없음. mechanical과 semantic은 서로의 실패를 뒤집지 못한다.

``uncertainty``가 임계를 넘는 verdict는 실패가 아니라 **escalation 대상**
이다 — v1에 consensus가 없으므로 escalation 대기로 ``HOLD``한다. 불확실한
판정을 통과로도 실패로도 세지 않는다.

계약: ``docs/08_VERIFY.md`` §9
결정: ``docs/adr/0026-verify-entry-requires-lineage.md``,
``docs/adr/0028-verify-v1-mechanical-contract.md``,
``docs/adr/0030-verify-semantic-verdict-contract.md``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mission_control.domain.blueprint.spec import Blueprint
from mission_control.domain.brief.gate import GateOutcome
from mission_control.domain.verify.evidence import VerificationEvidence, VerificationRun
from mission_control.domain.verify.verdict import SemanticAssessment, SemanticPolicy


class VerifyGateBlockingCondition(StrEnum):
    """MISSION COMPLETE 선언을 막은 조건."""

    CRITERION_UNVERIFIED = "criterion_unverified"
    VERIFICATION_FAILED = "verification_failed"
    SEMANTIC_VERDICT_MISSING = "semantic_verdict_missing"
    CRITERION_NOT_SATISFIED = "criterion_not_satisfied"
    ESCALATION_REQUIRED = "escalation_required"
    REWARD_HACKING_SUSPECTED = "reward_hacking_suspected"


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
    def mission_complete(self) -> bool:
        """``CLEAR``가 곧 MISSION COMPLETE다 — 이 Gate만 선언할 수 있다."""
        return self.outcome == "CLEAR"

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        """사람이 읽을 수 있는 이유 목록. 표시용이며 판정 근거는 원본 blocker다."""
        return tuple(blocker.detail for blocker in self.gate_blockers)


def _mechanical_failure_reason(ac_key: str, run: VerificationRun) -> str:
    """run의 필드에서 실패 이유를 결정적으로 파생한다.

    exit code 0인데 실패라면 남은 가능성은 output_assertion 불일치뿐이다 —
    별도 reason 필드를 두지 않는 이유다 (ADR-0028 §4).
    """
    if run.missing_artifacts:
        return f"{ac_key}: 선언된 artifact가 없다: " + ", ".join(
            run.missing_artifacts
        )
    if run.timed_out:
        return f"{ac_key}: 확인 명령이 시간을 초과했다"
    if run.exit_code not in (0, None):
        return f"{ac_key}: 확인 명령이 status {run.exit_code}로 종료됐다"
    return f"{ac_key}: 확인 명령 출력에서 기대한 문구를 찾지 못했다"


def evaluate_verify_gate(
    *,
    evidence: VerificationEvidence | None,
    verdicts: SemanticAssessment | None,
    blueprint: Blueprint,
    policy: SemanticPolicy,
) -> VerifyGateDecision:
    """두 층의 증거가 MISSION COMPLETE를 지지하는지 판정한다.

    이 함수는 순수 함수다. 진입 조건(Blueprint Gate와 Execute Gate의
    ``CLEAR``)은 호출하는 application 계층이 이 판정 **전에** 확인한다.

    다른 revision의 evidence·verdicts는 없는 것과 같다 — 새 revision이
    승인되면 이전 결과를 자동 재사용하지 않는다 (``docs/06_BLUEPRINT.md`` §9).
    """
    current_evidence = (
        evidence
        if evidence is not None and evidence.blueprint_revision == blueprint.revision
        else None
    )
    current_verdicts = (
        verdicts
        if verdicts is not None and verdicts.blueprint_revision == blueprint.revision
        else None
    )

    gate_blockers: list[VerifyGateBlocker] = []
    for criterion in blueprint.acceptance_criteria:
        if criterion.is_mechanically_verifiable:
            run = current_evidence.run_for(criterion.key) if current_evidence else None
            if run is None:
                gate_blockers.append(
                    VerifyGateBlocker(
                        condition=VerifyGateBlockingCondition.CRITERION_UNVERIFIED,
                        detail=(f"{criterion.key}가 기계적으로 확인되지 않았다"),
                    )
                )
            elif not run.passed:
                gate_blockers.append(
                    VerifyGateBlocker(
                        condition=VerifyGateBlockingCondition.VERIFICATION_FAILED,
                        detail=_mechanical_failure_reason(criterion.key, run),
                    )
                )

        verdict = current_verdicts.verdict_for(criterion.key) if current_verdicts else None
        if verdict is None:
            gate_blockers.append(
                VerifyGateBlocker(
                    condition=VerifyGateBlockingCondition.SEMANTIC_VERDICT_MISSING,
                    detail=f"{criterion.key}에 semantic 판정이 없다",
                )
            )
            continue
        if verdict.reward_hacking_risk >= policy.reward_hacking_veto:
            gate_blockers.append(
                VerifyGateBlocker(
                    condition=VerifyGateBlockingCondition.REWARD_HACKING_SUSPECTED,
                    detail=(
                        f"{criterion.key}: reward hacking 위험도 "
                        f"{verdict.reward_hacking_risk:.2f}가 거부 임계값 "
                        f"{policy.reward_hacking_veto:.2f} 이상이다"
                    ),
                )
            )
        if verdict.uncertainty > policy.uncertainty_threshold:
            gate_blockers.append(
                VerifyGateBlocker(
                    condition=VerifyGateBlockingCondition.ESCALATION_REQUIRED,
                    detail=(
                        f"{criterion.key}: 판정 불확실성 "
                        f"{verdict.uncertainty:.2f}가 {policy.uncertainty_threshold:.2f}를 넘는다; "
                        "v1에는 escalation 경로가 없다"
                    ),
                )
            )
        elif not verdict.passes(policy):
            gate_blockers.append(
                VerifyGateBlocker(
                    condition=VerifyGateBlockingCondition.CRITERION_NOT_SATISFIED,
                    detail=(
                        f"{criterion.key}: "
                        + (
                            f"점수 {verdict.score:.2f}가 {policy.pass_score:.2f} 미만이다"
                            if verdict.satisfied
                            else f"충족되지 않았다 — {verdict.reasoning}"
                        )
                    ),
                )
            )

    cleared = not gate_blockers
    return VerifyGateDecision(
        outcome="CLEAR" if cleared else "HOLD",
        blueprint_revision=blueprint.revision,
        gate_blockers=tuple(gate_blockers),
    )
