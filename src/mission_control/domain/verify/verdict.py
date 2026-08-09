"""semantic verdict — "테스트는 통과하지만 AC는 미충족"을 판정하는 층.

verdict는 mechanical 증거를 대체하지 않는다. 두 층은 서로 다른 질문에
답한다 — mechanical은 "명령이 통과했는가", semantic은 "요구가 충족됐는가".
어느 쪽도 다른 쪽의 실패를 뒤집지 못한다 (ADR-0028 §1, ADR-0030 §4).

임계 셋(통과 0.8, escalation 0.3, veto 0.7)은 발명이 아니라 upstream
채택이다 (``docs/research/VERIFY_UPSTREAM_FINDINGS.md`` §6).

계약: ``docs/08_VERIFY.md`` §5.2
결정: ``docs/adr/0030-verify-semantic-verdict-contract.md``
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SemanticPolicy(BaseModel):
    """semantic 판정의 versioned 임계 (ADR-0030 §2)."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1)
    #: 통과에 필요한 최소 score — upstream `score >= 0.8`.
    pass_score: float = Field(ge=0.0, le=1.0)
    #: 이 값을 넘는 불확신은 통과도 실패도 아니라 escalation 대상이다.
    uncertainty_threshold: float = Field(ge=0.0, le=1.0)
    #: 이 값 이상의 게이밍 의심은 다른 조건이 전부 통과여도 거부한다.
    reward_hacking_veto: float = Field(ge=0.0, le=1.0)

    @classmethod
    def verify_v1(cls) -> SemanticPolicy:
        """upstream 값 채택 (VERIFY_UPSTREAM_FINDINGS §6)."""
        return cls(
            version="verify-semantic-v1",
            pass_score=0.8,
            uncertainty_threshold=0.3,
            reward_hacking_veto=0.7,
        )


class CriterionVerdict(BaseModel):
    """AC 하나에 대한 semantic 판정 (ADR-0030 §1).

    ``satisfied``는 bool이고 ``uncertainty``는 별도 축이다 — "충족인데
    불확실"과 "미충족인데 불확실"은 다른 상태이며, status enum에 접으면 그
    구분이 사라진다. ``questions_used``는 평가자가 실제로 물은 질문이다 —
    일을 보였다는 증거이며 upstream의 anti-reward-hacking 장치다.
    """

    model_config = ConfigDict(frozen=True)

    ac_key: str = Field(min_length=1)
    satisfied: bool
    score: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    reward_hacking_risk: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1)
    evidence: tuple[str, ...] = ()
    questions_used: tuple[str, ...] = ()

    def passes(self, policy: SemanticPolicy) -> bool:
        """정책 기준의 통과 여부 — escalation·veto 판정은 Gate의 몫이다."""
        return self.satisfied and self.score >= policy.pass_score


class SemanticAssessment(BaseModel):
    """mission 하나의 semantic 판정 묶음.

    ``blueprint_revision``이 stale 판정의 축이다 — 이전 revision 위에서 내린
    verdict는 현재 revision을 지지하지 않는다 (ADR-0030 §4).
    """

    model_config = ConfigDict(frozen=True)

    blueprint_revision: int = Field(ge=1)
    policy_version: str = Field(min_length=1)
    verdicts: tuple[CriterionVerdict, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_verdict_per_criterion(self) -> SemanticAssessment:
        keys = [verdict.ac_key for verdict in self.verdicts]
        if len(keys) != len(set(keys)):
            raise ValueError("같은 수용 기준에 대한 verdict가 둘 이상이다")
        return self

    def verdict_for(self, ac_key: str) -> CriterionVerdict | None:
        for verdict in self.verdicts:
            if verdict.ac_key == ac_key:
                return verdict
        return None
