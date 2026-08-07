"""Blueprint QA — 생성된 명세를 품질 기준으로 채점하고 반복을 통제한다.

생성 직후의 명세는 최종본이 아니다. QA가 통과시키거나 사용자가 기준 미달을
명시적으로 수락하기 전까지 최종본으로 제시하지 않는다.

이 모듈이 정하는 것은 **반복의 규칙**이다. 채점 자체는 판단이므로 위임하고
(:class:`~mission_control.application.ports.BlueprintQaJudge`), 몇 점이면
통과인지·언제 멈추는지·무엇을 최선으로 기억하는지는 여기서 결정적으로 정한다.

세 가지가 이 모듈의 존재 이유다.

**점수만 보고 끝내지 않는다.** 반복마다 점수가 오르내리므로 마지막 점수가
최선이 아닐 수 있다. 가장 높았던 시도를 따로 기억한다.

**무한히 고치지 않는다.** 상한에 도달하면 최선의 시도를 사용자에게 제시하고
결정을 요청한다. 상한을 넘겨 한 번 더 돌지 않는다.

**품질 기준을 채점자가 정하지 않는다.** 무엇이 좋은 명세인지는 정책이 문장으로
고정하고, 채점자는 그 기준으로 점수만 매긴다.

계약: ``docs/06_BLUEPRINT.md``
결정: ``docs/adr/0019-blueprint-qa-loop.md``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

#: Blueprint 품질 기준. 채점자에게 문장 그대로 전달한다.
#:
#: granularity 항목이 이 기준의 핵심이다. 수단을 수용 기준에 남기면 아무도 그
#: 경로가 옳은지 검증하기 전에 명세가 경로를 확정한다. upstream은 이것을 "빠진
#: 조각을 지적하는 것만큼 중요하다"고 규정한다.
BLUEPRINT_QUALITY_BAR = """\
명세는 내부적으로 일관되어야 한다. 수용 기준은 측정하고 확인할 수 있어야 하고,
제약은 모호한 표현 없이 구체적이어야 하며, 필드 사이에 모순이 없어야 한다.

수용 기준은 존재론적으로 인색해야 한다. 하나의 기준은 **완성된 결과의 상태**를
가리켜야 하며, 그 상태로 가는 **수단**은 기준이 아니다. 각 기준을 형제 항목
옆에 놓고 읽어라 — 형제 항목으로 가는 이동으로만 이해되는 기준은 그 형제의
수단이며 형제에 병합되어야 한다. 그것을 지적하는 일은 빠진 요구사항을 지적하는
일만큼 중요하다. 수단을 남기면 명세가 검증되지 않은 경로를 확정해 버린다.

목표 하나에 기준이 몇 개인지는 정해져 있지 않다. 위 판단에서 따라 나온다.\
"""


class QaVerdict(StrEnum):
    """채점 결과가 루프에 지시하는 다음 행동."""

    PASS = "pass"
    REVISE = "revise"
    FAIL = "fail"


class QaDimension(StrEnum):
    """채점 축.

    다섯 축 모두 upstream ``skills/qa/SKILL.md:25``의 것이다. 축을 임의로 줄이면
    채점자가 무엇을 보고 있는지가 우리 쪽에서 달라진다.
    """

    CORRECTNESS = "correctness"
    COMPLETENESS = "completeness"
    QUALITY = "quality"
    INTENT_ALIGNMENT = "intent_alignment"
    #: 대상 도메인에 특수한 판단. 총점이 같은 두 시도를 가르는 데 실제로
    #: 기여한다 (`SEED_UPSTREAM_FINDINGS` §12의 관측: 0.74 → 0.90).
    DOMAIN_SPECIFIC = "domain_specific"


class QaFinding(BaseModel):
    """채점자가 지적한 항목 하나."""

    model_config = ConfigDict(frozen=True)

    detail: str = Field(min_length=1)
    suggestion: str | None = None


class QaAssessment(BaseModel):
    """한 번의 채점 결과.

    판정(:class:`QaVerdict`)을 담지 않는다. 몇 점이면 통과인지는 정책이 정하며,
    채점자가 자기 점수의 합격 여부까지 판단하면 기준을 스스로 조정할 여지가
    생긴다.
    """

    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=1.0)
    dimension_scores: tuple[tuple[QaDimension, float], ...] = ()
    findings: tuple[QaFinding, ...] = ()

    @property
    def dimension_average(self) -> float:
        """축별 점수의 평균. 총점이 같은 두 시도를 가르는 데 쓴다.

        축 점수가 없으면 ``0.0``이다. 한 루프의 채점은 같은 judge가 같은 요청
        형식으로 만들므로 한쪽만 비어 있는 경우를 따로 다루지 않는다 — 둘 다
        비면 값이 같아지고 판정은 다음 기준으로 넘어간다.
        """
        if not self.dimension_scores:
            return 0.0
        return sum(score for _, score in self.dimension_scores) / len(self.dimension_scores)


@dataclass(frozen=True, slots=True)
class QaPolicy:
    """버전이 붙는 QA 정책.

    ``pass_threshold``가 일반 기준보다 높은 이유는 Blueprint가 구조적 명세이기
    때문이다. 이후 모든 Stage가 이 명세를 근거로 판단하므로 여기서의 부정확함이
    그대로 전파된다.
    """

    version: str
    quality_bar: str
    pass_threshold: float
    fail_threshold: float
    max_iterations: int

    @classmethod
    def blueprint_v1(cls) -> QaPolicy:
        """upstream baseline 값으로 시작하는 Blueprint 정책."""
        return cls(
            version="blueprint-qa-v1",
            quality_bar=BLUEPRINT_QUALITY_BAR,
            pass_threshold=0.90,
            fail_threshold=0.40,
            max_iterations=5,
        )

    def verdict_for(self, score: float) -> QaVerdict:
        if score >= self.pass_threshold:
            return QaVerdict.PASS
        if score < self.fail_threshold:
            return QaVerdict.FAIL
        return QaVerdict.REVISE


class LoopAction(StrEnum):
    """반복 루프의 다음 동작."""

    #: 통과. 승인 요청 단계로 넘어간다.
    DONE = "done"
    #: 고쳐서 다시 채점한다.
    CONTINUE = "continue"
    #: 명세 수준의 문제다. 루프로 해결하지 않고 위로 올린다.
    ESCALATE = "escalate"
    #: 상한에 도달했다. 최선의 시도로 사용자 결정을 요청한다.
    EXHAUSTED = "exhausted"


@dataclass(frozen=True, slots=True)
class QaAttempt:
    """한 번의 반복 기록."""

    iteration: int
    assessment: QaAssessment


@dataclass(frozen=True, slots=True)
class QaLoopState:
    """반복 이력과 그로부터 나오는 판정.

    불변이다. 한 번의 채점이 새 상태를 만들고 이전 상태를 그대로 둔다 — 이력이
    나중 변경에 오염되면 "가장 좋았던 시도"를 신뢰할 수 없다.
    """

    policy: QaPolicy
    attempts: tuple[QaAttempt, ...] = ()

    def record(self, assessment: QaAssessment) -> QaLoopState:
        """채점 결과를 이력에 추가한 새 상태를 반환한다."""
        attempt = QaAttempt(iteration=len(self.attempts) + 1, assessment=assessment)
        return QaLoopState(policy=self.policy, attempts=(*self.attempts, attempt))

    @property
    def latest(self) -> QaAttempt | None:
        return self.attempts[-1] if self.attempts else None

    @property
    def best(self) -> QaAttempt | None:
        """가장 높은 점수를 받은 시도.

        마지막 시도가 아니다. 고치다가 점수가 내려가는 일이 실제로 일어나므로,
        상한에 도달했을 때 사용자에게 보여 줄 것은 마지막이 아니라 최선이다.

        총점이 같으면 **축별 평균이 높은 쪽**이다. 총점은 반올림 한 자리에서
        같아지지만 축 점수는 다를 수 있고, 그때 총점만 보면 실제로 더 나은
        명세를 버린다. 축 평균까지 같으면 먼저 나온 것을 유지한다 — 구별할
        정보가 없을 때는 덜 고친 쪽이 낫다.
        """
        if not self.attempts:
            return None
        return max(
            self.attempts,
            key=lambda item: (
                item.assessment.score,
                item.assessment.dimension_average,
                -item.iteration,
            ),
        )

    @property
    def score_history(self) -> tuple[float, ...]:
        return tuple(item.assessment.score for item in self.attempts)

    @property
    def regressed(self) -> bool:
        """마지막 채점이 직전보다 낮은가. 사용자에게 보여 줄 정보다."""
        history = self.score_history
        return len(history) >= 2 and history[-1] < history[-2]

    @property
    def action(self) -> LoopAction:
        """다음에 무엇을 할지.

        상한 판정이 통과 판정보다 뒤에 온다. 상한에 도달한 마지막 채점이 통과라면
        통과다 — 횟수를 다 썼다는 이유로 합격을 취소하지 않는다.
        """
        latest = self.latest
        if latest is None:
            return LoopAction.CONTINUE

        verdict = self.policy.verdict_for(latest.assessment.score)
        if verdict is QaVerdict.PASS:
            return LoopAction.DONE
        if verdict is QaVerdict.FAIL:
            return LoopAction.ESCALATE
        if len(self.attempts) >= self.policy.max_iterations:
            return LoopAction.EXHAUSTED
        return LoopAction.CONTINUE

    @property
    def is_open(self) -> bool:
        """아직 고칠 여지가 있는가."""
        return self.action is LoopAction.CONTINUE
