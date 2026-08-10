"""Wonder/Reflect CompletionEngine adapter의 prompt·transport 계약."""

from __future__ import annotations

from typing import Any

import pytest

from mission_control.adapters.text.evolve_backends import (
    REFLECT_SCHEMA,
    WONDER_SCHEMA,
    EvolveAdapterError,
    PromptedEvolveReflector,
    PromptedEvolveWonderer,
)
from mission_control.application.ports import ReflectRequest, WonderRequest
from mission_control.domain.blueprint.spec import (
    AcceptanceCriterion,
    OntologyField,
    OntologySchema,
)
from mission_control.domain.evolve.models import (
    AcPatchOperation,
    ChallengeKind,
    CriterionOutcomeSnapshot,
    EvolveSourceSnapshot,
    OntologyMutationOperation,
    WonderChallenge,
    WonderOutput,
)


class RecordingCompletion:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []

    @property
    def backend(self) -> str:
        return "recording"

    async def complete_json(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        workspace: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((prompt, schema, workspace))
        return self.response


def _criteria() -> tuple[AcceptanceCriterion, AcceptanceCriterion]:
    return (
        AcceptanceCriterion(
            description="동일 요청은 한 번만 반영된다",
            verify_command="pytest tests/test_idempotency.py",
            expected_artifacts=("reports/idempotency.json",),
        ),
        AcceptanceCriterion(
            description="429 응답은 재시도한다",
            verify_command="pytest tests/test_retry.py",
            output_assertion="1 passed",
        ),
    )


def _ontology() -> OntologySchema:
    return OntologySchema(
        name="RequestHandling",
        description="요청 처리 경계",
        fields=(
            OntologyField(
                name="request_id",
                field_type="string",
                description="중복 판별 키",
                required=True,
            ),
        ),
    )


def _source(
    criteria: tuple[AcceptanceCriterion, AcceptanceCriterion],
) -> EvolveSourceSnapshot:
    return EvolveSourceSnapshot(
        mission_id="m-1",
        blueprint_revision=3,
        blueprint_generation=1,
        verify_sequence=8,
        gate_blockers=(f"{criteria[1].key} failed",),
        execution_attempt_numbers=(3, 4),
        criteria=(
            CriterionOutcomeSnapshot(
                ac_key=criteria[0].key,
                mechanical_passed=True,
                semantic_passed=True,
                semantic_score=0.94,
                semantic_uncertainty=0.04,
                reward_hacking_risk=0.01,
                semantic_reasoning="중복 요청이 한 번만 반영된다",
                evidence_refs=("verify/first",),
                proven=True,
            ),
            CriterionOutcomeSnapshot(
                ac_key=criteria[1].key,
                mechanical_passed=False,
                mechanical_detail="retry test status 1",
                semantic_passed=False,
                semantic_score=0.4,
                semantic_uncertainty=0.12,
                reward_hacking_risk=0.03,
                semantic_reasoning="Retry-After와 jitter를 지키지 않는다",
                evidence_refs=("verify/second",),
                proven=False,
            ),
        ),
    )


def _wonder_request() -> WonderRequest:
    criteria = _criteria()
    return WonderRequest(
        goal="요청이 중복돼도 한 번만 처리한다",
        constraints=("기존 API를 유지한다",),
        non_goals=("새 큐 도입은 제외",),
        acceptance_criteria=criteria,
        ontology=_ontology(),
        source=_source(criteria),
        previous_wonders=(
            WonderOutput(
                challenges=(
                    WonderChallenge(
                        kind=ChallengeKind.GAP,
                        detail="재시도 소진의 관측 계약이 없다",
                    ),
                ),
                reasoning="이전 세대의 미해결 질문",
            ),
        ),
    )


def _reflect_request() -> ReflectRequest:
    criteria = _criteria()
    return ReflectRequest(
        goal="요청이 중복돼도 한 번만 처리한다",
        constraints=("기존 API를 유지한다",),
        non_goals=("새 큐 도입은 제외",),
        acceptance_criteria=criteria,
        ontology=_ontology(),
        source=_source(criteria),
        wonder=WonderOutput(
            challenges=(
                WonderChallenge(
                    kind=ChallengeKind.CHALLENGE,
                    parent_ac_key=criteria[1].key,
                    detail="Retry-After와 jitter 경계가 없다",
                ),
                WonderChallenge(
                    kind=ChallengeKind.GAP,
                    detail="재시도 소진의 관측 계약이 없다",
                ),
            ),
            reasoning="실패한 retry 계약만 다듬는다",
        ),
    )


def _reflect_response(
    *,
    patches: list[dict[str, Any]] | None = None,
    mutations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "refined_goal": "요청이 중복돼도 한 번만 처리한다",
        "refined_constraints": ["기존 API를 유지한다"],
        "ac_patches": patches
        if patches is not None
        else [
            {"op": "keep", "index": 0, "content": "", "reason": "이미 증명됨"},
            {
                "op": "revise",
                "index": 1,
                "content": "429 응답은 Retry-After와 jitter를 지켜 재시도한다",
                "reason": "실패 evidence를 반영",
            },
            {
                "op": "add",
                "index": -1,
                "content": "재시도 소진이 관측 가능하다",
                "reason": "Wonder gap을 반영",
            },
        ],
        "ontology_mutations": mutations
        if mutations is not None
        else [
            {
                "action": "add",
                "field_name": "retry_after",
                "field_type": "duration",
                "description": "서버가 지시한 대기 시간",
                "required": False,
                "reason": "수정 AC가 참조하는 개념",
            }
        ],
        "reasoning": "통과 계약은 보존하고 실패 계약만 명시화한다",
    }


class TestWonderAdapter:
    async def test_display_refs_become_content_keys_without_workspace(self) -> None:
        request = _wonder_request()
        completion = RecordingCompletion(
            {
                "questions": [
                    {
                        "question": "Retry-After와 jitter 경계가 필요한가?",
                        "kind": "challenge",
                        "ac_refs": [2],
                    },
                    {
                        "question": "재시도 소진은 어떻게 관측되는가?",
                        "kind": "gap",
                        "ac_refs": [],
                    },
                ],
                "reasoning": "Verify 실패와 Goal의 빈틈에 근거한다",
            }
        )

        result = await PromptedEvolveWonderer(completion=completion).wonder(request)

        assert result.challenges[0].parent_ac_key == request.acceptance_criteria[1].key
        assert result.challenges[1].parent_ac_key is None
        prompt, schema, workspace = completion.calls[0]
        assert workspace is None
        assert schema is WONDER_SCHEMA
        assert "AC 1 (Reflect index 0)" in prompt
        assert "retry test status 1" in prompt
        assert "immutable verify_command: pytest tests/test_retry.py" in prompt
        assert "Previous Wonder lineage" in prompt
        assert "새 큐 도입은 제외" in prompt

    @pytest.mark.parametrize(
        "questions",
        [
            [{"question": "범위 밖", "kind": "challenge", "ac_refs": [3]}],
            [{"question": "근거 없음", "kind": "challenge", "ac_refs": []}],
            [{"question": "AC에 가장한 gap", "kind": "gap", "ac_refs": [1]}],
        ],
    )
    async def test_invalid_reference_shapes_are_rejected(
        self, questions: list[dict[str, Any]]
    ) -> None:
        completion = RecordingCompletion({"questions": questions, "reasoning": "왜 그런가"})

        with pytest.raises(EvolveAdapterError):
            await PromptedEvolveWonderer(completion=completion).wonder(_wonder_request())


class TestReflectAdapter:
    async def test_ordered_indices_become_keyed_patch_and_mutation(self) -> None:
        request = _reflect_request()
        completion = RecordingCompletion(_reflect_response())

        result = await PromptedEvolveReflector(completion=completion).reflect(request)

        first, second, added = result.ac_patches
        assert (first.operation, first.parent_ac_key) == (
            AcPatchOperation.KEEP,
            request.acceptance_criteria[0].key,
        )
        assert (second.operation, second.parent_ac_key) == (
            AcPatchOperation.REVISE,
            request.acceptance_criteria[1].key,
        )
        assert added.operation is AcPatchOperation.ADD
        assert added.parent_ac_key is None
        assert result.settled_ac_keys == (request.acceptance_criteria[0].key,)
        assert result.ontology_mutations[0].operation is OntologyMutationOperation.ADD
        assert result.ontology_mutations[0].field_name == "retry_after"

        prompt, schema, workspace = completion.calls[0]
        assert workspace is None
        assert schema is REFLECT_SCHEMA
        assert "Address parent ACs by 0-based index" in prompt
        assert "challenge[" + request.acceptance_criteria[1].key + "]" in prompt
        assert schema["additionalProperties"] is False
        assert schema["properties"]["ac_patches"]["items"]["required"] == [
            "op",
            "index",
            "content",
            "reason",
        ]

    async def test_protected_revise_is_forced_to_keep(self) -> None:
        request = _reflect_request()
        response = _reflect_response(
            patches=[
                {
                    "op": "revise",
                    "index": 0,
                    "content": "동일 요청을 빠르게 한 번만 반영한다",
                    "reason": "불필요한 개선",
                },
                {"op": "keep", "index": 1, "content": "", "reason": "유지"},
            ],
            mutations=[],
        )

        result = await PromptedEvolveReflector(completion=RecordingCompletion(response)).reflect(
            request
        )

        assert result.ac_patches[0].operation is AcPatchOperation.KEEP
        assert result.ac_patches[0].parent_ac_key == request.acceptance_criteria[0].key
        assert result.ac_patches[0].description is None
        assert result.settled_ac_keys == (request.acceptance_criteria[0].key,)

    @pytest.mark.parametrize(
        "patches",
        [
            [{"op": "keep", "index": 0, "content": "", "reason": "누락"}],
            [
                {"op": "keep", "index": 1, "content": "", "reason": "역순"},
                {"op": "keep", "index": 0, "content": "", "reason": "역순"},
            ],
            [
                {"op": "add", "index": -1, "content": "새 계약", "reason": "중간 add"},
                {"op": "keep", "index": 0, "content": "", "reason": "add 뒤 parent"},
                {"op": "keep", "index": 1, "content": "", "reason": "add 뒤 parent"},
            ],
        ],
    )
    async def test_incomplete_reordered_or_interleaved_parent_patch_is_rejected(
        self, patches: list[dict[str, Any]]
    ) -> None:
        completion = RecordingCompletion(_reflect_response(patches=patches, mutations=[]))

        with pytest.raises(EvolveAdapterError):
            await PromptedEvolveReflector(completion=completion).reflect(_reflect_request())

    async def test_invalid_ontology_target_is_rejected_before_return(self) -> None:
        mutation = {
            "action": "add",
            "field_name": "request_id",
            "field_type": "string",
            "description": "이미 존재하는 필드",
            "required": True,
            "reason": "잘못된 중복 add",
        }
        completion = RecordingCompletion(_reflect_response(mutations=[mutation]))

        with pytest.raises(EvolveAdapterError, match="이미 있는 ontology field"):
            await PromptedEvolveReflector(completion=completion).reflect(_reflect_request())

    async def test_duplicate_ontology_target_is_rejected_as_adapter_error(self) -> None:
        mutation = {
            "action": "add",
            "field_name": "retry_after",
            "field_type": "duration",
            "description": "서버가 지시한 대기 시간",
            "required": False,
            "reason": "필요한 개념",
        }
        completion = RecordingCompletion(_reflect_response(mutations=[mutation, mutation]))

        with pytest.raises(EvolveAdapterError, match="두 번 바꿀 수 없다"):
            await PromptedEvolveReflector(completion=completion).reflect(_reflect_request())
