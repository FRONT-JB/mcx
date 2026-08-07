"""Closure 감사 — 3-lane 합성의 결정적 차단 규칙.

계약: docs/05_BRIEF.md §11.6 / docs/adr/0020-brief-closure-audit.md
Test Matrix: B-040 ~ B-043 (upstream: mcp/tools/subagent.py:2732 합성 규칙)
"""

from pydantic import ValidationError
import pytest

from mission_control.domain.brief.closure import (
    CLOSER_TASK,
    CLOSURE_GATE_SUMMARY,
    CONTRARIAN_TASK,
    GAP_HUNTER_TASK,
    SEVERITY_RULE,
    AdvisoryLane,
    AdvisoryReport,
    CloserReport,
    CloserVerdict,
    ClosureAudit,
    ClosureSeverity,
)


def _closer(
    verdict: CloserVerdict = CloserVerdict.READY,
    *,
    reason: str = "no material decision remains",
    blocking_question: str | None = None,
) -> CloserReport:
    return CloserReport(verdict=verdict, reason=reason, blocking_question=blocking_question)


def _advisory(
    lane: AdvisoryLane,
    severity: ClosureSeverity = ClosureSeverity.LOW,
    *,
    finding: str = "minor wording polish",
    question: str | None = None,
) -> AdvisoryReport:
    return AdvisoryReport(lane=lane, severity=severity, finding=finding, question=question)


def _audit(
    closer: CloserReport | None = None,
    contrarian: AdvisoryReport | None = None,
    gap_hunter: AdvisoryReport | None = None,
) -> ClosureAudit:
    return ClosureAudit(
        closer=closer or _closer(),
        contrarian=contrarian or _advisory(AdvisoryLane.CONTRARIAN),
        gap_hunter=gap_hunter or _advisory(AdvisoryLane.GAP_HUNTER),
    )


class TestCloserGates:
    """closer의 verdict만이 gate다."""

    def test_ready_closer_with_calm_advisories_is_ready(self) -> None:
        decision = _audit().decision

        assert decision.ready is True
        assert decision.blocking_questions == ()
        assert decision.high_severity_lanes == ()

    def test_not_ready_closer_blocks_with_its_question(self) -> None:
        audit = _audit(
            closer=_closer(
                CloserVerdict.NOT_READY,
                reason="ownership is undecided",
                blocking_question="who owns the derived cache?",
            )
        )

        decision = audit.decision
        assert decision.ready is False
        assert decision.blocking_questions == ("who owns the derived cache?",)

    def test_question_falls_back_to_the_reason(self) -> None:
        """upstream 합성과 같다 — blocking_question이 없으면 reason이 질문이 된다."""
        audit = _audit(closer=_closer(CloserVerdict.NOT_READY, reason="verification is absent"))

        assert audit.decision.blocking_questions == ("verification is absent",)


class TestAdvisorySeverity:
    """advisory lane은 HIGH일 때만 차단한다."""

    @pytest.mark.parametrize("severity", [ClosureSeverity.MEDIUM, ClosureSeverity.LOW])
    def test_medium_and_low_do_not_block(self, severity: ClosureSeverity) -> None:
        audit = _audit(contrarian=_advisory(AdvisoryLane.CONTRARIAN, severity))

        assert audit.decision.ready is True

    def test_high_contrarian_blocks_even_when_the_closer_is_ready(self) -> None:
        audit = _audit(
            contrarian=_advisory(
                AdvisoryLane.CONTRARIAN,
                ClosureSeverity.HIGH,
                finding="'interactive' is overloaded",
                question="which of the four meanings applies?",
            )
        )

        decision = audit.decision
        assert decision.ready is False
        assert decision.high_severity_lanes == (AdvisoryLane.CONTRARIAN,)
        assert decision.blocking_questions == ("which of the four meanings applies?",)

    def test_high_gap_hunter_blocks(self) -> None:
        audit = _audit(
            gap_hunter=_advisory(
                AdvisoryLane.GAP_HUNTER, ClosureSeverity.HIGH, finding="no failure path"
            )
        )

        assert audit.decision.ready is False
        assert audit.decision.high_severity_lanes == (AdvisoryLane.GAP_HUNTER,)

    def test_advisory_question_falls_back_to_the_finding(self) -> None:
        audit = _audit(
            contrarian=_advisory(
                AdvisoryLane.CONTRARIAN, ClosureSeverity.HIGH, finding="hidden assumption"
            )
        )

        assert audit.decision.blocking_questions == ("hidden assumption",)

    def test_every_blocker_contributes_a_question(self) -> None:
        """차단 사유가 셋이면 질문도 셋이다 — 합쳐서 뭉개지 않는다."""
        audit = _audit(
            closer=_closer(CloserVerdict.NOT_READY, reason="r"),
            contrarian=_advisory(AdvisoryLane.CONTRARIAN, ClosureSeverity.HIGH, finding="c"),
            gap_hunter=_advisory(AdvisoryLane.GAP_HUNTER, ClosureSeverity.HIGH, finding="g"),
        )

        assert audit.decision.blocking_questions == ("r", "c", "g")


class TestAuditShape:
    def test_swapped_lanes_are_rejected(self) -> None:
        """뒤바뀐 lane을 받아들이면 어느 관점이 공격했는지 기록이 거짓이 된다."""
        with pytest.raises(ValidationError):
            ClosureAudit(
                closer=_closer(),
                contrarian=_advisory(AdvisoryLane.GAP_HUNTER),
                gap_hunter=_advisory(AdvisoryLane.CONTRARIAN),
            )

    def test_contract_texts_are_upstream_verbatim(self) -> None:
        """계약 문장이 원문임을 고정한다 — 번역은 변형이다 (ADR-0020 §4)."""
        assert "permission to audit closure, not permission to close" in CLOSURE_GATE_SUMMARY
        assert "ownership/SSoT" in CLOSURE_GATE_SUMMARY
        assert CLOSER_TASK.startswith("Apply the canonical Seed Closer closure gate.")
        assert CONTRARIAN_TASK.startswith("Challenge the interview's conclusions.")
        assert GAP_HUNTER_TASK.startswith("Hunt for missing requirements")
        assert SEVERITY_RULE.startswith('Rate "high" ONLY when')

    def test_reports_are_frozen(self) -> None:
        report = _closer()

        with pytest.raises(ValidationError):
            report.verdict = CloserVerdict.NOT_READY
