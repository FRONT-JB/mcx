"""요구사항 후보와 승격 정책.

Brief가 모으는 것은 질문과 답변만이 아니다. 대화에서 **다음 Stage로 넘어갈
요구사항 후보**가 자란다. "로그인 사용자만 쓴다", "수정·삭제는 이번 범위가
아니다", "재시도는 3회다" 같은 진술이다.

이 진술들을 종류별로 나눈 목록 여러 개로 다루지 않는다. 하나의 후보에 네 개의
축이 붙는다.

- ``section`` — 이 진술이 요구사항의 **어느 칸**에 들어가는가. ``non_goal``은
  별도 개념이 아니라 이 칸 중 하나다.
- ``resolution`` — **확정 상태**. ``unknown``이 미해결이고 ``conflicting``이
  충돌이다.
- ``content_source`` — 내용이 **어디서 왔는가**. ``model_inferred``가 가정이다.
- ``confirmation_authority`` — **누가 확인했는가**.

Mission Control 문서(``docs/05_BRIEF.md`` §13.1)가 Non-goal, 충돌, 가정,
미해결을 각각 별도 조건으로 나열하는 것은 서술의 편의이며, 상태는 하나다.

:func:`evaluate_promotion`이 결정적 정책이다. clarity 점수와 **무관하게** 진행을
막는 두 번째 관문이며, 점수가 아무리 좋아도 충돌이 남아 있으면 통과하지 않는다
(``docs/05_BRIEF.md`` §11.5).

계약: ``docs/05_BRIEF.md`` §5, §13.1
결정: ``docs/adr/0015-requirement-candidate-model.md``
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RequirementSection(StrEnum):
    """후보가 겨냥하는 요구사항 칸.

    Brief v1이 실제로 만들어 내는 것은 ``GOAL``, ``CONSTRAINT``,
    ``EXISTING_CONSTRAINT``, ``ACCEPTANCE_CRITERION``, ``NON_GOAL``,
    ``CONTEXT``다. 나머지는 Blueprint가 Seed를 구성할 때 쓰는 칸이며, 어휘를
    잘라내면 이후 단계에서 축이 갈라지므로 그대로 둔다.
    """

    GOAL = "goal"
    CONSTRAINT = "constraint"
    EXISTING_CONSTRAINT = "existing_constraint"
    ACCEPTANCE_CRITERION = "acceptance_criterion"
    ONTOLOGY = "ontology"
    EVALUATION_PRINCIPLE = "evaluation_principle"
    EXIT_CONDITION = "exit_condition"
    NON_GOAL = "non_goal"
    CONTEXT = "context"


class CandidateContentSource(StrEnum):
    """후보의 내용이 어디서 왔는가.

    ``MODEL_INFERRED``가 가정(assumption)이다. 별도 개념으로 두지 않는 이유는
    가정이 다른 종류의 진술이 아니라 **출처가 모델인 진술**이기 때문이다.
    """

    USER_STATED = "user_stated"
    REFERENCE_DERIVED = "reference_derived"
    MODEL_INFERRED = "model_inferred"
    REPO_OBSERVED = "repo_observed"


class CandidateResolution(StrEnum):
    """후보의 확정 상태."""

    CONFIRMED = "confirmed"
    NEEDS_CONFIRMATION = "needs_confirmation"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


class ConfirmationAuthority(StrEnum):
    """후보를 확인한 권위. 내용 출처와 독립이다.

    사용자가 붙여 넣은 코드 스니펫은 출처가 사람이어도 권위는 저장소 증거이며,
    시스템이 제안한 기본값을 사용자가 받아들이면 출처가 모델이어도 권위는
    사용자다.
    """

    USER = "user"
    REPO_EVIDENCE = "repo_evidence"
    NONE = "none"


class RequirementCandidate(BaseModel):
    """대화에서 자란 요구사항 후보 하나."""

    model_config = ConfigDict(frozen=True)

    number: int
    section: RequirementSection
    text: str = Field(min_length=1)
    content_source: CandidateContentSource
    resolution: CandidateResolution = CandidateResolution.NEEDS_CONFIRMATION
    confirmation_authority: ConfirmationAuthority = ConfirmationAuthority.NONE
    #: 이 후보가 해소되지 않으면 다음 Stage의 판단이 달라지는가. 문서의
    #: "material"이 이 값이다.
    required: bool = False


class PromotionDisposition(StrEnum):
    """후보가 다음 Stage 구성에 참여하는 방식."""

    PROMOTE = "promote"
    OMIT = "omit"
    BLOCK = "block"


class PromotionReason(StrEnum):
    """그 처분이 내려진 이유."""

    PROMOTED = "promoted"
    CONFLICT_REQUIRES_TRADEOFF = "conflict_requires_tradeoff"
    REQUIRED_UNKNOWN = "required_unknown"
    OPTIONAL_UNKNOWN = "optional_unknown"
    CONFIRMATION_REQUIRED = "confirmation_required"
    OPTIONAL_UNCONFIRMED = "optional_unconfirmed"
    AUTHORITY_INSUFFICIENT = "authority_insufficient"
    OPTIONAL_AUTHORITY_INSUFFICIENT = "optional_authority_insufficient"


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    candidate: RequirementCandidate
    disposition: PromotionDisposition
    reason: PromotionReason


@dataclass(frozen=True, slots=True)
class PromotionResult:
    decisions: tuple[PromotionDecision, ...]

    @property
    def blockers(self) -> tuple[PromotionDecision, ...]:
        """진행을 막는 결정만. 비어 있어야 다음 Stage로 갈 수 있다."""
        return tuple(
            decision
            for decision in self.decisions
            if decision.disposition is PromotionDisposition.BLOCK
        )

    @property
    def promoted(self) -> tuple[RequirementCandidate, ...]:
        return tuple(
            decision.candidate
            for decision in self.decisions
            if decision.disposition is PromotionDisposition.PROMOTE
        )


#: 저장소에서 관찰한 사실만으로 채울 수 있는 칸. 이 두 칸은 "현재 무엇이
#: 그러한가"를 서술할 뿐 "무엇을 만들 것인가"를 정하지 않는다.
_REPO_CONFIRMABLE_SECTIONS = frozenset(
    {RequirementSection.CONTEXT, RequirementSection.EXISTING_CONSTRAINT}
)


def evaluate_promotion(candidates: Sequence[RequirementCandidate]) -> PromotionResult:
    """후보마다 승격·생략·차단을 판정한다. 결정적이며 모델을 호출하지 않는다.

    차단은 ``required``인 후보에만 적용된다. 필수가 아닌 후보는 조용히 사라지지
    않고 ``OMIT``으로 이유와 함께 남는다 — 왜 이 진술이 다음 Stage에 가지 않았는지
    나중에 설명할 수 있어야 한다.

    마지막 규칙이 이 정책의 핵심이다. **관찰만으로는 요구사항을 만들 수 없다.**
    저장소에서 읽은 사실은 ``context``와 ``existing_constraint``에만 스스로 들어갈
    수 있고, goal·constraint·non_goal·성공 조건이 되려면 사용자 확인이 필요하다.
    이것이 ``docs/adr/0010-answer-provenance-and-requirement-authority.md``의
    원칙이 규칙으로 강제되는 자리다.
    """
    decisions: list[PromotionDecision] = []

    for candidate in candidates:
        if candidate.resolution is CandidateResolution.CONFLICTING:
            # 충돌은 required 여부와 무관하게 막는다. 한쪽을 자동으로 고르는 것은
            # 사용자만 할 수 있는 tradeoff를 시스템이 대신하는 것이다.
            decisions.append(
                _decide(
                    candidate,
                    PromotionDisposition.BLOCK,
                    PromotionReason.CONFLICT_REQUIRES_TRADEOFF,
                )
            )
            continue

        if candidate.resolution is CandidateResolution.UNKNOWN:
            decisions.append(
                _by_requirement(
                    candidate,
                    required_reason=PromotionReason.REQUIRED_UNKNOWN,
                    optional_reason=PromotionReason.OPTIONAL_UNKNOWN,
                )
            )
            continue

        if candidate.resolution is not CandidateResolution.CONFIRMED:
            decisions.append(
                _by_requirement(
                    candidate,
                    required_reason=PromotionReason.CONFIRMATION_REQUIRED,
                    optional_reason=PromotionReason.OPTIONAL_UNCONFIRMED,
                )
            )
            continue

        if _has_sufficient_authority(candidate):
            decisions.append(
                _decide(candidate, PromotionDisposition.PROMOTE, PromotionReason.PROMOTED)
            )
        else:
            decisions.append(
                _by_requirement(
                    candidate,
                    required_reason=PromotionReason.AUTHORITY_INSUFFICIENT,
                    optional_reason=PromotionReason.OPTIONAL_AUTHORITY_INSUFFICIENT,
                )
            )

    return PromotionResult(decisions=tuple(decisions))


def _has_sufficient_authority(candidate: RequirementCandidate) -> bool:
    if candidate.section in _REPO_CONFIRMABLE_SECTIONS:
        return candidate.confirmation_authority in {
            ConfirmationAuthority.REPO_EVIDENCE,
            ConfirmationAuthority.USER,
        }
    return candidate.confirmation_authority is ConfirmationAuthority.USER


def _by_requirement(
    candidate: RequirementCandidate,
    *,
    required_reason: PromotionReason,
    optional_reason: PromotionReason,
) -> PromotionDecision:
    if candidate.required:
        return _decide(candidate, PromotionDisposition.BLOCK, required_reason)
    return _decide(candidate, PromotionDisposition.OMIT, optional_reason)


def _decide(
    candidate: RequirementCandidate,
    disposition: PromotionDisposition,
    reason: PromotionReason,
) -> PromotionDecision:
    return PromotionDecision(candidate=candidate, disposition=disposition, reason=reason)
