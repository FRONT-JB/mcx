"""Clarity 평가와 질문 루프 종료 후보 판정.

점수는 질문 루프를 통제하는 수단이지 진실이 아니다. 이 모듈은 **언제 질문을
멈출 수 있는지**만 판정하며, 멈춰도 되는 상태와 다음 Stage로 진행해도 되는
상태는 다르다. 종료 후보 판정은 사용자에게 승인을 물어볼 자격이지 ``CLEAR``가
아니다.

네 조건이 모두 필요하다.

1. 전체 ambiguity가 threshold 이하
2. 각 dimension이 최소 floor 이상
3. 조건 충족이 연속으로 이어짐 (stability signal)
4. 최소 round 수 도달

2번이 별도로 필요한 이유는 집계 방식 때문이다. 가중 평균만 쓰면 성공 조건이
전혀 검증 불가능해도 goal과 constraint 점수가 높아 전체 threshold를 통과할 수
있다. floor는 그 상쇄를 막는다. upstream은 이 floor를 코드로만 가지고 있고
회귀 테스트가 없어서, 여기서는 경계를 명시적으로 검증한다.

3번은 LLM 평가의 분산에 대한 방어다. 같은 대화라도 호출마다 점수가 흔들리므로
우연히 낮게 나온 한 번으로 종료하면 실제로는 모호한 요구사항이 통과한다.

metric의 방향이 서로 반대라는 점에 주의한다. dimension은 **clarity**로 평가하며
높을수록 명확하고, 집계된 canonical metric은 **ambiguity**로 낮을수록 명확하다.

계약: ``docs/05_BRIEF.md`` §11
결정: ``docs/adr/0009-brief-completion-gate-policy.md``
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: 평가 대상 축. ``context``는 brownfield 전용이며 v1 첫 구현에서는 자리만
#: 예약한다 (``docs/adr/0011-brief-deliberate-divergences.md`` §6).
ClarityDimension = Literal["goal", "constraint", "success_criteria", "context"]


class BlockingCondition(StrEnum):
    """종료 후보가 되지 못한 이유."""

    ASSESSMENT_MISSING = "assessment_missing"
    MINIMUM_ROUNDS_NOT_REACHED = "minimum_rounds_not_reached"
    AMBIGUITY_ABOVE_THRESHOLD = "ambiguity_above_threshold"
    DIMENSION_FLOOR_NOT_MET = "dimension_floor_not_met"
    STABILITY_NOT_ESTABLISHED = "stability_not_established"


class DimensionScore(BaseModel):
    """한 축의 clarity 평가. 높을수록 명확하다."""

    model_config = ConfigDict(frozen=True)

    dimension: ClarityDimension
    clarity: float = Field(ge=0.0, le=1.0)
    justification: str


class ClarityAssessment(BaseModel):
    """한 시점의 clarity 평가 결과.

    사용한 policy version을 함께 남긴다. 정책이 바뀌면 과거 판정의 기준을 추적할
    수 있어야 한다 (``docs/00_MISSION_CONTROL.md`` §10).
    """

    model_config = ConfigDict(frozen=True)

    scores: tuple[DimensionScore, ...]
    policy_version: str

    def clarity_of(self, dimension: ClarityDimension) -> float | None:
        for score in self.scores:
            if score.dimension == dimension:
                return score.clarity
        return None


@dataclass(frozen=True, slots=True)
class CompletionBlocker:
    """종료를 막은 조건 하나와 사람이 읽을 설명."""

    condition: BlockingCondition
    detail: str


@dataclass(frozen=True, slots=True)
class CompletionCandidacy:
    """질문 루프를 멈출 수 있는 상태인지에 대한 판정.

    ``is_candidate``가 참이어도 Gate ``CLEAR``가 아니다. 사용자 승인과 나머지
    hard condition을 함께 평가해야 한다 (``docs/05_BRIEF.md`` §11.5).
    """

    is_candidate: bool
    blockers: tuple[CompletionBlocker, ...]


_GREENFIELD_WEIGHTS: Mapping[ClarityDimension, float] = MappingProxyType(
    {"goal": 0.40, "constraint": 0.30, "success_criteria": 0.30}
)
_GREENFIELD_FLOORS: Mapping[ClarityDimension, float] = MappingProxyType(
    {"goal": 0.75, "constraint": 0.65, "success_criteria": 0.70}
)


@dataclass(frozen=True, slots=True)
class ClarityPolicy:
    """주입 가능한 versioned 정책.

    threshold와 weight를 prompt 안의 magic number로 숨기지 않는다. 값이 정책
    객체로 존재해야 경계값을 독립적으로 테스트할 수 있다.
    """

    version: str
    weights: Mapping[ClarityDimension, float]
    floors: Mapping[ClarityDimension, float]
    max_ambiguity: float
    required_stability: int
    minimum_rounds: int

    @classmethod
    def greenfield_v1(cls) -> ClarityPolicy:
        """upstream baseline 값으로 시작하는 greenfield 정책."""
        return cls(
            version="greenfield-v1",
            weights=_GREENFIELD_WEIGHTS,
            floors=_GREENFIELD_FLOORS,
            max_ambiguity=0.20,
            required_stability=2,
            minimum_rounds=3,
        )

    def ambiguity_of(self, assessment: ClarityAssessment) -> float:
        """``1 − Σ(clarity × weight)``.

        정책이 가중치를 부여한 dimension 중 평가되지 않은 것이 있으면 거부한다.
        누락을 0으로 간주하면 평가하지 않은 축이 조용히 최악의 점수로 반영되고,
        1로 간주하면 반대로 통과를 만들어 낸다. 둘 다 근거 없는 추정이다.
        """
        weighted = 0.0
        for dimension, weight in self.weights.items():
            clarity = assessment.clarity_of(dimension)
            if clarity is None:
                raise ValueError(f"평가에 가중치가 걸린 축이 빠졌다: {dimension}")
            weighted += clarity * weight
        return round(1.0 - weighted, 4)

    def assess_completion(
        self,
        *,
        assessment: ClarityAssessment | None,
        answered_rounds: int,
        stability_signal: int,
    ) -> CompletionCandidacy:
        """네 조건을 평가하고 막고 있는 조건을 **전부** 보고한다.

        첫 실패에서 멈추지 않는 이유는 ``HOLD``가 부족한 조건 전체를 제시해야
        하기 때문이다 (``docs/05_BRIEF.md`` §13.2). 하나씩 알려주면 사용자가
        같은 루프를 여러 번 돌게 된다.
        """
        blockers: list[CompletionBlocker] = []

        if answered_rounds < self.minimum_rounds:
            blockers.append(
                CompletionBlocker(
                    condition=BlockingCondition.MINIMUM_ROUNDS_NOT_REACHED,
                    detail=f"최소 {self.minimum_rounds}라운드 중 {answered_rounds}라운드만 답했다",
                )
            )

        if assessment is None:
            blockers.append(
                CompletionBlocker(
                    condition=BlockingCondition.ASSESSMENT_MISSING,
                    detail="현재 revision에 대한 명확도 평가가 없다",
                )
            )
        else:
            blockers.extend(self._score_blockers(assessment))

        if stability_signal < self.required_stability:
            blockers.append(
                CompletionBlocker(
                    condition=BlockingCondition.STABILITY_NOT_ESTABLISHED,
                    detail=(f"안정성 {stability_signal} — 필요한 값은 {self.required_stability}다"),
                )
            )

        return CompletionCandidacy(is_candidate=not blockers, blockers=tuple(blockers))

    def next_stability_signal(
        self,
        *,
        current: int,
        assessment: ClarityAssessment | None,
        answered_rounds: int,
    ) -> int:
        """평가 하나당 signal을 정확히 한 번 갱신한다.

        조건을 만족하면 1 증가하고, 만족하지 못하거나 평가 결과가 없으면 0으로
        초기화한다. upstream은 한 턴에 signal이 두 번 올라 단일 신호로 종료되는
        회귀를 겪었으므로(#405) 갱신 지점을 이 함수 하나로 유지한다.
        """
        if assessment is None or self._score_blockers(assessment):
            return 0
        if answered_rounds < self.minimum_rounds:
            return 0
        return min(current + 1, self.required_stability)

    def _score_blockers(self, assessment: ClarityAssessment) -> list[CompletionBlocker]:
        """점수에서 비롯된 blocker만 계산한다. round와 stability는 제외."""
        blockers: list[CompletionBlocker] = []

        ambiguity = self.ambiguity_of(assessment)
        if ambiguity > self.max_ambiguity:
            blockers.append(
                CompletionBlocker(
                    condition=BlockingCondition.AMBIGUITY_ABOVE_THRESHOLD,
                    detail=f"모호함 {ambiguity}가 상한 {self.max_ambiguity}를 넘는다",
                )
            )

        for dimension, floor in self.floors.items():
            clarity = assessment.clarity_of(dimension)
            if clarity is not None and clarity < floor:
                blockers.append(
                    CompletionBlocker(
                        condition=BlockingCondition.DIMENSION_FLOOR_NOT_MET,
                        detail=f"{dimension} 명확도 {clarity}가 하한 {floor} 미만이다",
                    )
                )

        return blockers
