"""Blueprint use case — 생성, 채점, 수정, 승인, Gate 판정의 조율.

:class:`~mission_control.application.brief_service.BriefService`와 같은 규칙을
따른다 — 도메인 규칙은 여기 두지 않고, **저장이 성공한 뒤에만 전이가 일어났다고
보고한다**.

이 계층이 추가로 지키는 것은 **위임 호출 전의 허용 검사**다. 채점은 위임이므로
기록 시점에만 규칙을 검사하면 일어나지 말았어야 할 채점이 이미 수행된 뒤에
거부된다. 상한이 호출 자체를 막아야 upstream의 "6회째 반복 금지"가 성립한다
(ADR-0019 §6, ADR-0021 §4).

handoff는 저장하지 않고 매번 현재 Brief 상태에서 재파생한다 (ADR-0016). 호출자가
건네준 handoff를 믿으면 판정 이후 바뀐 Brief의 옛 투영으로 Blueprint가 만들어지는
경로가 열린다.

계약: ``docs/06_BLUEPRINT.md`` §7, §8
결정: ``docs/adr/0021-blueprint-state-and-revisions.md``
"""

from __future__ import annotations

from dataclasses import dataclass

from mission_control.application.brief_service import BriefNotFoundError
from mission_control.application.ports import (
    BlueprintGenerationRequest,
    BlueprintGenerator,
    BlueprintQaJudge,
    BlueprintRepository,
    BriefRepository,
    MechanicalCommandDetector,
    QaIteration,
    QaRequest,
)
from mission_control.domain.blueprint.assembly import BlueprintDraft, assemble_blueprint
from mission_control.domain.blueprint.gate import (
    BlueprintGateDecision,
    evaluate_blueprint_gate,
)
from mission_control.domain.blueprint.qa import QaFinding, QaPolicy
from mission_control.domain.blueprint.spec import initial_ontology
from mission_control.domain.blueprint.state import BlueprintState
from mission_control.domain.brief.clarity import ClarityPolicy
from mission_control.domain.brief.gate import evaluate_brief_gate
from mission_control.domain.brief.handoff import BriefHandoff, build_brief_handoff
from mission_control.domain.errors import MissionControlError


class BlueprintNotFoundError(LookupError):
    """존재하지 않는 Mission의 Blueprint를 조작하려 했다."""

    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}의 Blueprint가 없다")
        self.mission_id = mission_id


class BlueprintAlreadyExistsError(ValueError):
    """이미 생성된 Blueprint를 다시 생성하려 했다.

    첫 생성은 정확히 한 번이고 이후 수정은 재생성이 아니라 편집이다
    (ADR-0021 §2, upstream ``skills/seed/SKILL.md``). 재생성을 허용하면 축적된
    채점 기록·승인과 새 내용의 연결이 끊긴다.
    """

    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}의 Blueprint가 이미 있다")
        self.mission_id = mission_id


class StaleBriefRevisionError(MissionControlError):
    """Blueprint가 나온 Brief revision이 더 이상 현재가 아니다.

    그 사이 Brief가 바뀌었으므로 기존 Blueprint 위의 수정은 어느 Brief를
    구체화한 것인지 말할 수 없다. 수정이 아니라 재평가가 필요하다.
    """

    def __init__(self, *, mission_id: str, built_from: int, current: int) -> None:
        super().__init__(
            f"mission {mission_id}의 Blueprint는 Brief revision {built_from}에서 나왔는데 "
            f"현재 Brief revision은 {current}이다"
        )
        self.mission_id = mission_id
        self.built_from = built_from
        self.current = current


class QaAssessmentError(RuntimeError):
    """QA 채점이 결과를 만들어 내지 못했다.

    채점 실패를 낮은 점수나 높은 점수 어느 쪽으로도 해석하지 않는다. 기록은
    성공한 채점에만 추가되므로 상태는 바뀌지 않으며, 실패한 호출은 반복 상한을
    소모하지 않는다.
    """

    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}의 QA 평가가 결과를 내지 못했다")
        self.mission_id = mission_id


@dataclass(frozen=True, slots=True)
class BlueprintService:
    """Blueprint Stage의 application 경계."""

    briefs: BriefRepository
    brief_policy: ClarityPolicy
    repository: BlueprintRepository
    generator: BlueprintGenerator
    qa_judge: BlueprintQaJudge
    qa_policy: QaPolicy
    #: 기존 저장소의 확인 명령을 찾아 생성기의 ``context``에 얹는다 (ADR-0044 §3).
    #: 둘 다 있어야 동작한다 — 없으면 greenfield처럼 handoff의 context만 간다.
    detector: MechanicalCommandDetector | None = None
    workspace: str | None = None

    async def generate(self, *, mission_id: str) -> BlueprintState:
        """``CLEAR``된 Brief의 handoff에서 첫 Blueprint revision을 만들고 저장한다.

        범위를 벗어난 초안은 :func:`assemble_blueprint`가 거부하므로 저장되지
        않는다 — 계약이 프롬프트 문구가 아니라 결정적 검사로 강제된다
        (ADR-0018).
        """
        if await self.repository.load(mission_id) is not None:
            raise BlueprintAlreadyExistsError(mission_id)

        handoff = await self._handoff(mission_id)
        request = self._generation_request(handoff)
        detected = await self._detect_mechanical()
        if detected:
            request = request.model_copy(update={"context": request.context + detected})
        draft = await self.generator.generate(request)
        # Gen 1 ontology는 generator output이 아니라 결정적 초기값이 소유한다
        # (ADR-0051 §3). 수동 replacement는 Gen 2+ revise에서만 열린다.
        blueprint = assemble_blueprint(
            draft=draft,
            handoff=handoff,
            revision=1,
            ontology=initial_ontology(),
        )
        state = BlueprintState.start(blueprint=blueprint)
        await self.repository.save(state)
        return state

    async def assess_qa(self, *, mission_id: str) -> BlueprintState:
        """현재 revision을 채점하고 기록을 저장한다.

        허용 검사가 채점 호출보다 먼저다. 채점이 실패하면 상태는 바뀌지 않고
        :class:`QaAssessmentError`가 올라간다 — 실패는 낮은 점수가 아니라 결과
        없음이다.
        """
        state = await self._require(mission_id)
        state.ensure_qa_allowed(policy=self.qa_policy)

        try:
            assessment = await self.qa_judge.assess(self._qa_request(state))
        except Exception as error:
            raise QaAssessmentError(mission_id) from error

        recorded = state.record_qa(assessment=assessment, policy=self.qa_policy)
        await self.repository.save(recorded)
        return recorded

    async def revise(self, *, mission_id: str, draft: BlueprintDraft) -> BlueprintState:
        """사용자가 채택한 수정을 새 revision으로 확정하고 저장한다.

        수정 후보를 제시하고 선택받는 UX는 surface(Phase 6·7)가 다루지만,
        채택된 결과가 들어오는 진입점은 여기다. 수정도 생성과 같은 범위 검사를
        거친다 — QA의 제안이라고 해서 handoff 경계를 벗어날 수는 없다.

        Brief가 그 사이 바뀌었으면 거부한다. 어느 Brief를 구체화한 것인지 말할
        수 없는 revision을 만들지 않기 위해서다.
        """
        state = await self._require(mission_id)
        handoff = await self._handoff(mission_id)
        if handoff.revision != state.current.brief_revision:
            raise StaleBriefRevisionError(
                mission_id=mission_id,
                built_from=state.current.brief_revision,
                current=handoff.revision,
            )

        blueprint = assemble_blueprint(
            draft=draft,
            handoff=handoff,
            revision=state.revision + 1,
            generation=state.generation,
            evolved_from_revision=state.current.evolved_from_revision,
            ontology=draft.ontology or state.current.ontology,
        )
        # 상한 소진 뒤의 최종 수정은 한 번뿐이다 (ADR-0019 §6.1).
        revised = state.revise(blueprint=blueprint, policy=self.qa_policy)
        await self.repository.save(revised)
        return revised

    async def approve(
        self,
        *,
        mission_id: str,
        statement: str,
        accept_below_threshold: bool = False,
    ) -> BlueprintState:
        """현재 revision에 대한 사용자 승인을 기록하고 저장한다.

        승인 가능 조건(채점된 현재 revision, PASS 또는 상한 소진)은 상태가
        판정한다. 저장이 실패하면 승인받지 않은 것으로 취급한다.
        """
        state = await self._require(mission_id)
        approved = state.approve(
            statement=statement,
            policy=self.qa_policy,
            accept_below_threshold=accept_below_threshold,
        )
        await self.repository.save(approved)
        return approved

    async def decide_gate(self, *, mission_id: str) -> BlueprintGateDecision:
        """저장된 상태로 Execute 진입 Gate를 판정한다.

        현재 Brief revision을 저장소에서 읽어 대조한다. Blueprint가 나온 뒤
        Brief가 바뀌었다면 승인이 있어도 ``HOLD``다.
        """
        state = await self._require(mission_id)
        brief = await self.briefs.load(mission_id)
        if brief is None:
            raise BriefNotFoundError(mission_id)
        return evaluate_blueprint_gate(state=state, brief_revision=brief.revision)

    async def _require(self, mission_id: str) -> BlueprintState:
        state = await self.repository.load(mission_id)
        if state is None:
            raise BlueprintNotFoundError(mission_id)
        return state

    async def _handoff(self, mission_id: str) -> BriefHandoff:
        """현재 Brief 상태에서 handoff를 재파생한다.

        ``CLEAR``가 아니면 :class:`~mission_control.domain.brief.handoff.HandoffNotClearedError`가
        올라가고 생성은 시작되지 않는다 (Entry Contract, ``docs/06_BLUEPRINT.md`` §3).

        :class:`~mission_control.application.brief_service.BriefService`에
        의존하지 않고 같은 파생을 직접 수행한다 — 필요한 것은 저장소와 정책이지
        질문 생성기까지 포함한 Brief 구성 전체가 아니다.
        """
        brief = await self.briefs.load(mission_id)
        if brief is None:
            raise BriefNotFoundError(mission_id)
        decision = evaluate_brief_gate(state=brief, policy=self.brief_policy)
        return build_brief_handoff(state=brief, decision=decision)

    @staticmethod
    def _generation_request(handoff: BriefHandoff) -> BlueprintGenerationRequest:
        """생성기에 전달할 handoff의 칸들을 옮긴다.

        대화 원문(``requirement_input``·``observed_facts``)과 revision 이력은
        전달하지 않는다. 생성기가 대화를 다시 읽을 수 있으면 Brief에서 합의되지
        않은 것을 요구사항으로 되살릴 수 있다 (ADR-0016, ADR-0018).
        """
        return BlueprintGenerationRequest(
            goals=handoff.goals,
            constraints=handoff.constraints,
            non_goals=handoff.non_goals,
            success_criteria=handoff.success_criteria,
            context=handoff.context,
        )

    async def _detect_mechanical(self) -> tuple[str, ...]:
        """기존 저장소의 확인 명령을 찾아 context 줄로 만든다 (ADR-0044 §3).

        **한 번만 부른다** — ``generate``는 미션당 한 번이고(이미 있으면
        거부한다) 검출은 그 안에서만 일어난다. upstream이 파일로 얻는
        idempotency를 우리는 호출 지점 하나로 얻으므로 캐시 파일이 없다.

        검출 실패는 예외가 아니라 빈 결과다. 확인 명령을 못 찾은 것이 Blueprint
        생성을 막아서는 안 된다 — 못 찾으면 greenfield처럼 진행하고, 그래도
        확인 수단이 하나도 없으면 Gate가 막는다
        (``NO_VERIFIABLE_CRITERION``, ADR-0043 §3).

        **버려진 제안은 생성기에 가지 않는다.** 검증되지 않은 명령이 AC에
        박히면 Verify가 없는 진입점을 실행하고, 그 실패는 코드의 문제로 보인다.
        """
        if self.detector is None or self.workspace is None:
            return ()

        verified = await self.detector.detect(self.workspace)
        return tuple(
            f"the project's {kind.value} command is `{command}`"
            for kind, command in sorted(verified.commands.items())
        )

    def _qa_request(self, state: BlueprintState) -> QaRequest:
        """채점자에게 전달할 context를 구성한다.

        품질 기준·통과 점수·이전 반복 궤적은 정책과 기록에서 가져온다 —
        upstream QA 프롬프트 정렬이다 (ADR-0019 §3 개정, ADR-0035 §3). 반복
        상한은 전달하지 않는다. 직전 채점의 지적을 함께 전달해 반복이
        수렴하는지 채점자가 알 수 있게 한다.
        """
        current = state.current
        return QaRequest(
            goal=current.goal,
            constraints=current.constraints,
            non_goals=current.non_goals,
            acceptance_criteria=current.acceptance_criteria,
            ontology=current.ontology,
            quality_bar=self.qa_policy.quality_bar,
            pass_threshold=self.qa_policy.pass_threshold,
            previous_iterations=tuple(
                QaIteration(
                    iteration=index + 1,
                    score=record.assessment.score,
                    verdict=self.qa_policy.verdict_for(record.assessment.score).value,
                )
                for index, record in enumerate(
                    state.records_for_generation(state.generation)
                )
            ),
            previous_findings=self._previous_findings(state),
        )

    @staticmethod
    def _previous_findings(state: BlueprintState) -> tuple[QaFinding, ...]:
        records = state.records_for_generation(state.generation)
        if not records:
            return ()
        return records[-1].assessment.findings
