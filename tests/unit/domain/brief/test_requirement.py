"""요구사항 후보와 승격 정책.

Non-goal, 충돌, 가정, 미해결이 하나의 모델에서 축으로 구분되는지, 그리고
점수와 무관한 두 번째 관문이 결정적으로 동작하는지 검증한다.

계약: docs/05_BRIEF.md §5, §13.1 / docs/adr/0015-requirement-candidate-model.md
Test Matrix: B-006, B-007, B-009
"""

import pytest

from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    ConfirmationAuthority,
    PromotionDisposition,
    PromotionReason,
    RequirementCandidate,
    RequirementSection,
    evaluate_promotion,
)


def _candidate(
    *,
    section: RequirementSection = RequirementSection.CONSTRAINT,
    text: str = "로그인 사용자만 작성",
    content_source: CandidateContentSource = CandidateContentSource.USER_STATED,
    resolution: CandidateResolution = CandidateResolution.CONFIRMED,
    confirmation_authority: ConfirmationAuthority = ConfirmationAuthority.USER,
    required: bool = False,
    number: int = 1,
) -> RequirementCandidate:
    return RequirementCandidate(
        number=number,
        section=section,
        text=text,
        content_source=content_source,
        resolution=resolution,
        confirmation_authority=confirmation_authority,
        required=required,
    )


def _only(candidate: RequirementCandidate) -> tuple[PromotionDisposition, PromotionReason]:
    result = evaluate_promotion([candidate])
    assert len(result.decisions) == 1
    decision = result.decisions[0]
    return decision.disposition, decision.reason


class TestDefaults:
    def test_new_candidate_is_unconfirmed_and_unauthorized(self) -> None:
        """기록과 확인은 다른 사건이다. 적어 넣는 순간 확정되지 않는다."""
        candidate = RequirementCandidate(
            number=1,
            section=RequirementSection.GOAL,
            text="댓글을 쓰고 볼 수 있다",
            content_source=CandidateContentSource.USER_STATED,
        )

        assert candidate.resolution is CandidateResolution.NEEDS_CONFIRMATION
        assert candidate.confirmation_authority is ConfirmationAuthority.NONE
        assert candidate.required is False

    def test_empty_text_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            _candidate(text="")


class TestConflictAlwaysBlocks:
    """충돌은 required 여부와 무관하다. tradeoff는 사용자만 고를 수 있다."""

    @pytest.mark.parametrize("required", [True, False])
    def test_conflicting_blocks(self, required: bool) -> None:
        disposition, reason = _only(
            _candidate(resolution=CandidateResolution.CONFLICTING, required=required)
        )

        assert disposition is PromotionDisposition.BLOCK
        assert reason is PromotionReason.CONFLICT_REQUIRES_TRADEOFF


class TestUnresolvedDependsOnRequirement:
    """B-007 — 필수 미해결은 막고, 선택 항목은 이유를 남기고 생략한다."""

    def test_required_unknown_blocks(self) -> None:
        disposition, reason = _only(
            _candidate(resolution=CandidateResolution.UNKNOWN, required=True)
        )

        assert disposition is PromotionDisposition.BLOCK
        assert reason is PromotionReason.REQUIRED_UNKNOWN

    def test_optional_unknown_is_omitted_not_dropped(self) -> None:
        """왜 다음 Stage에 가지 않았는지 나중에 설명할 수 있어야 한다."""
        disposition, reason = _only(
            _candidate(resolution=CandidateResolution.UNKNOWN, required=False)
        )

        assert disposition is PromotionDisposition.OMIT
        assert reason is PromotionReason.OPTIONAL_UNKNOWN

    def test_required_needs_confirmation_blocks(self) -> None:
        disposition, reason = _only(
            _candidate(resolution=CandidateResolution.NEEDS_CONFIRMATION, required=True)
        )

        assert disposition is PromotionDisposition.BLOCK
        assert reason is PromotionReason.CONFIRMATION_REQUIRED


class TestObservationCannotCreateRequirements:
    """ADR-0010의 원칙이 승격 규칙으로 강제되는 자리다."""

    @pytest.mark.parametrize(
        "section",
        [
            RequirementSection.GOAL,
            RequirementSection.CONSTRAINT,
            RequirementSection.NON_GOAL,
            RequirementSection.ACCEPTANCE_CRITERION,
        ],
    )
    def test_repo_evidence_cannot_confirm_a_requirement_section(
        self, section: RequirementSection
    ) -> None:
        disposition, reason = _only(
            _candidate(
                section=section,
                content_source=CandidateContentSource.REPO_OBSERVED,
                confirmation_authority=ConfirmationAuthority.REPO_EVIDENCE,
                required=True,
            )
        )

        assert disposition is PromotionDisposition.BLOCK
        assert reason is PromotionReason.AUTHORITY_INSUFFICIENT

    @pytest.mark.parametrize(
        "section",
        [RequirementSection.CONTEXT, RequirementSection.EXISTING_CONSTRAINT],
    )
    def test_repo_evidence_confirms_descriptive_sections(self, section: RequirementSection) -> None:
        """이 두 칸은 '현재 무엇이 그러한가'를 서술할 뿐 무엇을 만들지 정하지 않는다."""
        disposition, reason = _only(
            _candidate(
                section=section,
                content_source=CandidateContentSource.REPO_OBSERVED,
                confirmation_authority=ConfirmationAuthority.REPO_EVIDENCE,
            )
        )

        assert disposition is PromotionDisposition.PROMOTE
        assert reason is PromotionReason.PROMOTED

    def test_user_confirmation_promotes_an_observed_fact(self) -> None:
        """관찰이 승격되는 경로는 사용자 확인뿐이다."""
        disposition, _ = _only(
            _candidate(
                section=RequirementSection.CONSTRAINT,
                content_source=CandidateContentSource.REPO_OBSERVED,
                confirmation_authority=ConfirmationAuthority.USER,
            )
        )

        assert disposition is PromotionDisposition.PROMOTE

    def test_model_inference_needs_user_confirmation(self) -> None:
        """B-006 — 가정은 사용자 확인 없이 요구사항이 되지 않는다."""
        disposition, reason = _only(
            _candidate(
                content_source=CandidateContentSource.MODEL_INFERRED,
                confirmation_authority=ConfirmationAuthority.NONE,
                required=True,
            )
        )

        assert disposition is PromotionDisposition.BLOCK
        assert reason is PromotionReason.AUTHORITY_INSUFFICIENT


class TestResultViews:
    def test_blockers_and_promoted_are_separated(self) -> None:
        result = evaluate_promotion(
            [
                _candidate(number=1, text="확정된 제약"),
                _candidate(
                    number=2,
                    text="충돌",
                    resolution=CandidateResolution.CONFLICTING,
                ),
                _candidate(
                    number=3,
                    text="선택 미해결",
                    resolution=CandidateResolution.UNKNOWN,
                ),
            ]
        )

        assert len(result.blockers) == 1
        assert result.blockers[0].candidate.number == 2
        assert [item.number for item in result.promoted] == [1]

    def test_empty_candidates_produce_no_blockers(self) -> None:
        result = evaluate_promotion([])

        assert result.blockers == ()
        assert result.promoted == ()
