"""Closure 감사 — 점수는 감사의 자격이지 종료의 자격이 아니다.

clarity 점수가 종료 후보 조건을 만족해도 material한 미해결 결정이 남아 있을 수
있다. 점수는 "얼마나 명확해 보이는가"를 재지만 "남은 것이 구현을 실질적으로
바꾸는가"는 재지 않기 때문이다. 이 감사가 그 질문을 따로 판정한다.

세 관점(lane)이 독립적으로 본다 — closer는 closure gate 기준(6축 점검표 포함)을
적용해 verdict를 내고, contrarian과 gap_hunter는 각자의 각도에서 gap을 공격한다.
**판정력은 다르다.** closer의 verdict는 그 자체로 gate이고, advisory 두 lane은
HIGH 심각도일 때만 차단한다.

합성(:attr:`ClosureAudit.decision`)은 LLM 없는 순수 함수다. 무엇이 차단하는지가
코드로 고정되어 있어야 "감사를 통과했다"가 테스트 가능한 주장이 된다.

계약 문장 상수들은 **upstream 영어 원문 그대로**다. 문장이 곧 계약인 곳에서
번역은 변형이다 (ADR-0020 §4 — quality bar 번역 이탈의 재발 방지).

계약: ``docs/05_BRIEF.md`` §11.6
결정: ``docs/adr/0020-brief-closure-audit.md``
Upstream: ``agents/seed-closer.md``, ``mcp/tools/subagent.py:2629-2801``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: closer lane에 전달하는 closure gate 기준.
#: upstream ``agents/seed-closer.md`` "CLOSURE GATE SUMMARY" 원문.
#: (소스 줄나눔만 다르고 문자열 값은 원문과 동일하다.)
CLOSURE_GATE_SUMMARY = (
    "- Treat a low ambiguity score as permission to audit closure, "
    "not permission to close.\n"
    "- Do not close if any unresolved decision would materially change implementation.\n"
    "- For brownfield or system-level work, check ownership/SSoT, protocol or API "
    "contract, lifecycle/recovery, migration, cross-client impact, and verification.\n"
    "- If code, research, or architecture context reveals a materially different path, "
    "ask for the needed human decision instead of closing."
)

#: closer lane의 과제. upstream ``SEED_CLOSER_TRIPANEL_LANES`` 원문.
CLOSER_TASK = (
    "Apply the canonical Seed Closer closure gate. Return a closure verdict "
    "and the single highest-impact follow-up question if a material decision "
    "remains unresolved."
)

#: contrarian lane의 과제. upstream 원문.
CONTRARIAN_TASK = (
    "Challenge the interview's conclusions. Surface hidden assumptions, "
    "overloaded terms, and decisions the interview may have skipped. Rate the "
    "severity of the most material gap you find."
)

#: gap_hunter lane의 과제. upstream 원문.
GAP_HUNTER_TASK = (
    "Hunt for missing requirements, unlisted constraints, unhandled edge "
    "cases, and unverifiable acceptance criteria. Rate the severity of the "
    "most material gap you find."
)

#: advisory lane의 심각도 판정 규칙. upstream 원문.
SEVERITY_RULE = (
    'Rate "high" ONLY when the gap would materially change the implementation if left unresolved.'
)


class CloserVerdict(StrEnum):
    """closer lane의 판정.

    upstream 값은 ``seed_ready``/``not_ready``다. "Seed"는 내부·upstream
    용어이고 이 enum은 판정 의미만 나르므로 접두어를 뺐다. 비교는 문자열이
    아니라 enum identity로 하므로 상호운용 문제가 없다.
    """

    READY = "ready"
    NOT_READY = "not_ready"


class ClosureSeverity(StrEnum):
    """advisory lane이 찾은 gap의 심각도. HIGH만 차단한다."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AdvisoryLane(StrEnum):
    """판정력 없이 관점 공격만 하는 두 lane."""

    CONTRARIAN = "contrarian"
    GAP_HUNTER = "gap_hunter"


class CloserReport(BaseModel):
    """closer lane의 결과. verdict가 gate다.

    verdict를 반환하는 것이 "채점자는 판정하지 않는다"(ADR-0019 §3)와 충돌하지
    않는 이유: 그 원칙은 점수와 통과선의 분리다. closer의 판단("구현을
    실질적으로 바꿀 미해결 결정이 있는가")은 임계 비교가 아니라 판단 그
    자체이고, 숨길 통과선이 존재하지 않는다 (ADR-0020 §8).
    """

    model_config = ConfigDict(frozen=True)

    verdict: CloserVerdict
    reason: str = Field(min_length=1)
    #: 차단 시 다음 round가 던질 가장 임팩트 큰 질문. 없으면 reason이 대신한다.
    blocking_question: str | None = None


class AdvisoryReport(BaseModel):
    """advisory lane 하나의 결과. HIGH일 때만 차단한다."""

    model_config = ConfigDict(frozen=True)

    lane: AdvisoryLane
    severity: ClosureSeverity
    finding: str = Field(min_length=1)
    #: 차단 시 다음 round가 던질 질문. 없으면 finding이 대신한다.
    question: str | None = None


@dataclass(frozen=True, slots=True)
class ClosureDecision:
    """감사 세 lane의 결정적 합성 결과."""

    ready: bool
    closer_verdict: CloserVerdict
    blocking_questions: tuple[str, ...]
    high_severity_lanes: tuple[AdvisoryLane, ...]


class ClosureAudit(BaseModel):
    """한 번의 closure 감사 — 세 lane의 결과 전부.

    세 report가 모두 필수다. upstream 합성은 lane 결과가 하나라도 없으면
    차단하는데(missing-lane 규칙), 여기서는 그 규칙이 검사가 아니라 생성
    조건으로 성립한다 — 세 결과가 없으면 이 객체를 만들 수 없다.
    """

    model_config = ConfigDict(frozen=True)

    closer: CloserReport
    contrarian: AdvisoryReport
    gap_hunter: AdvisoryReport

    @model_validator(mode="after")
    def _lanes_must_not_be_swapped(self) -> ClosureAudit:
        """뒤바뀐 lane을 거부한다.

        contrarian 자리에 gap_hunter 결과가 앉으면 어느 관점이 실제로 공격했는지
        기록이 거짓이 된다. 차단 판정은 같아도 감사의 근거가 오염된다.
        """
        if self.contrarian.lane is not AdvisoryLane.CONTRARIAN:
            raise ValueError("contrarian slot carries a different lane's report")
        if self.gap_hunter.lane is not AdvisoryLane.GAP_HUNTER:
            raise ValueError("gap_hunter slot carries a different lane's report")
        return self

    @property
    def decision(self) -> ClosureDecision:
        """결정적 합성. upstream ``synthesize_seed_closer_tripanel``과 같은 규칙.

        - closer가 ``not_ready`` → 차단. 질문은 blocking_question, 없으면 reason.
        - advisory가 HIGH → 차단. 질문은 question, 없으면 finding.
        - MEDIUM/LOW는 차단하지 않는다.
        """
        blocking_questions: list[str] = []
        high_lanes: list[AdvisoryLane] = []

        if self.closer.verdict is not CloserVerdict.READY:
            blocking_questions.append(self.closer.blocking_question or self.closer.reason)

        for report in (self.contrarian, self.gap_hunter):
            if report.severity is ClosureSeverity.HIGH:
                high_lanes.append(report.lane)
                blocking_questions.append(report.question or report.finding)

        return ClosureDecision(
            ready=self.closer.verdict is CloserVerdict.READY and not high_lanes,
            closer_verdict=self.closer.verdict,
            blocking_questions=tuple(blocking_questions),
            high_severity_lanes=tuple(high_lanes),
        )


class ClosureAuditRecord(BaseModel):
    """특정 Brief revision에 대해 수행된 감사.

    승인과 같은 방식으로 revision에 묶인다. material 변경이 revision을 올리므로
    오래된 감사는 자동으로 stale이 되고, 상태 전이마다 초기화 코드를 둘 필요가
    없다 (ADR-0020 §6).
    """

    model_config = ConfigDict(frozen=True)

    revision: int
    audit: ClosureAudit
