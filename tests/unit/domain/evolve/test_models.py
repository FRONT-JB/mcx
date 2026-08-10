"""Evolve의 vendor-neutral proposal·checkpoint 모델 (ADR-0051 §4·§8)."""

from pydantic import ValidationError
import pytest

from mission_control.domain.evolve.models import (
    AcceptanceCriterionPatch,
    AcPatchOperation,
    ChallengeKind,
    CriterionOutcomeSnapshot,
    EvolutionPhase,
    EvolutionRecord,
    EvolveSourceSnapshot,
    ReflectOutput,
    WonderChallenge,
    WonderOutput,
)


def _source() -> EvolveSourceSnapshot:
    return EvolveSourceSnapshot(
        mission_id="m-1",
        blueprint_revision=3,
        blueprint_generation=1,
        verify_sequence=7,
        gate_blockers=("ac_b failed",),
        execution_attempt_numbers=(4, 5),
        criteria=(
            CriterionOutcomeSnapshot(
                ac_key="ac_a",
                mechanical_passed=True,
                semantic_passed=True,
                semantic_score=0.92,
                semantic_uncertainty=0.05,
                reward_hacking_risk=0.02,
                semantic_reasoning="계약과 evidence가 일치한다",
                evidence_refs=("verify/a",),
                proven=True,
            ),
            CriterionOutcomeSnapshot(
                ac_key="ac_b",
                mechanical_passed=False,
                mechanical_detail="pytest status 1",
                semantic_passed=False,
                semantic_score=0.35,
                semantic_uncertainty=0.1,
                reward_hacking_risk=0.05,
                semantic_reasoning="Retry-After 경계가 충족되지 않았다",
                evidence_refs=("verify/b",),
                proven=False,
            ),
        ),
    )


def _wonder() -> WonderOutput:
    return WonderOutput(
        challenges=(
            WonderChallenge(
                kind=ChallengeKind.CHALLENGE,
                parent_ac_key="ac_b",
                detail="실패 경계가 빠졌다",
            ),
        ),
        reasoning="실패한 AC만 다시 본다",
    )


def _reflect() -> ReflectOutput:
    return ReflectOutput(
        refined_goal="같은 목표",
        refined_constraints=(),
        ac_patches=(
            AcceptanceCriterionPatch(operation=AcPatchOperation.KEEP, parent_ac_key="ac_a"),
            AcceptanceCriterionPatch(
                operation=AcPatchOperation.REVISE,
                parent_ac_key="ac_b",
                description="실패 경계를 명시한다",
            ),
        ),
        reasoning="명시적으로 parent를 매핑한다",
    )


class TestSourceSnapshot:
    def test_only_active_hold_can_be_constructed(self) -> None:
        with pytest.raises(ValidationError):
            EvolveSourceSnapshot.model_validate(
                _source().model_dump() | {"verify_gate": "CLEAR"}
            )

        with pytest.raises(ValidationError):
            EvolveSourceSnapshot.model_validate(
                _source().model_dump() | {"mission_status": "complete"}
            )

    def test_duplicate_ac_outcomes_are_rejected(self) -> None:
        source = _source()
        with pytest.raises(ValidationError, match="같은 AC outcome"):
            EvolveSourceSnapshot.model_validate(
                source.model_dump() | {"criteria": (source.criteria[0], source.criteria[0])}
            )

    def test_proven_requires_the_available_layers_to_pass(self) -> None:
        with pytest.raises(ValidationError, match="proven AC"):
            CriterionOutcomeSnapshot(
                ac_key="ac_x",
                mechanical_passed=False,
                mechanical_detail="command failed",
                semantic_passed=True,
                semantic_score=0.9,
                semantic_uncertainty=0.1,
                reward_hacking_risk=0.0,
                semantic_reasoning="semantic 결과는 통과했다",
                proven=True,
            )

    def test_failure_details_are_masked_at_the_state_boundary(self) -> None:
        outcome = CriterionOutcomeSnapshot(
            ac_key="ac_x",
            mechanical_passed=False,
            mechanical_detail="Bearer ghp_abcdefghijklmnopqrstuvwxyz0123",
            semantic_passed=False,
            semantic_score=0.2,
            semantic_uncertainty=0.1,
            reward_hacking_risk=0.0,
            semantic_reasoning="api_key=hunter2 was exposed",
            proven=False,
        )

        assert "ghp_" not in (outcome.mechanical_detail or "")
        assert "hunter2" not in outcome.semantic_reasoning


class TestProposalShapes:
    def test_challenge_needs_a_parent_but_gap_does_not(self) -> None:
        with pytest.raises(ValidationError, match="parent_ac_key"):
            WonderChallenge(kind=ChallengeKind.CHALLENGE, detail="근거 없음")
        with pytest.raises(ValidationError, match="gap"):
            WonderChallenge(
                kind=ChallengeKind.GAP,
                parent_ac_key="ac_a",
                detail="새 빈틈",
            )

    def test_patch_fields_follow_the_operation(self) -> None:
        with pytest.raises(ValidationError, match="keep"):
            AcceptanceCriterionPatch(operation=AcPatchOperation.KEEP)
        with pytest.raises(ValidationError, match="add"):
            AcceptanceCriterionPatch(
                operation=AcPatchOperation.ADD,
                parent_ac_key="ac_a",
                description="새 AC",
            )


class TestEvolutionRecord:
    def test_phase_outputs_are_replayable(self) -> None:
        started = EvolutionRecord.start(source=_source())
        reflected = started.record_wonder(_wonder()).record_reflect(_reflect())
        completed = reflected.complete(result_blueprint_revision=4)

        assert started.phase is EvolutionPhase.WONDERING
        assert reflected.phase is EvolutionPhase.SEEDING
        assert completed.phase is EvolutionPhase.COMPLETED
        assert completed.result_blueprint_revision == 4
        assert EvolutionRecord.model_validate_json(completed.model_dump_json()) == completed

    def test_phase_cannot_skip_wonder(self) -> None:
        with pytest.raises(ValueError, match="Reflect output"):
            EvolutionRecord.start(source=_source()).record_reflect(_reflect())
