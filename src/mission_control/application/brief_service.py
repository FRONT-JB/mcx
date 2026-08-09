"""Brief use case — 질문, 답변, 승인, clarity 평가, Gate 판정의 조율.

도메인 규칙은 여기에 두지 않는다. 이 계층은 **순서와 경계**를 담당한다. 무엇을
읽고, 누구에게 무엇을 위임하고, 언제 저장하고, 무엇을 호출자에게 돌려줄지를
결정한다.

가장 중요한 규칙은 **저장이 성공한 뒤에만 전이가 일어났다고 보고한다**는 것이다.
메모리의 새 상태를 반환해 놓고 저장이 실패하면, 호출자는 기록되지 않은 답변을
기록된 것으로 취급하게 된다. 그래서 저장 실패는 예외로 드러나며 이 계층은 그것을
삼키지 않는다 (``docs/05_BRIEF.md`` §14.1, Appendix A 9번).

계약: ``docs/05_BRIEF.md`` §4.2, §10
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from mission_control.application.ports import (
    AskedRound,
    AssessmentRequest,
    BriefRepository,
    ClarityAssessor,
    CloserAuditRequest,
    ClosureAssessor,
    ClosureChallenger,
    ClosureChallengeRequest,
    GeneratedQuestion,
    QuestionGenerator,
    QuestionRequest,
    RequirementView,
)
from mission_control.domain.brief.clarity import ClarityPolicy
from mission_control.domain.brief.closure import (
    CLOSURE_GATE_SUMMARY,
    CONTRARIAN_TASK,
    GAP_HUNTER_TASK,
    SEVERITY_RULE,
    AdvisoryLane,
    AdvisoryReport,
    ClosureAudit,
)
from mission_control.domain.brief.gate import BriefGateDecision, evaluate_brief_gate
from mission_control.domain.brief.handoff import BriefHandoff, build_brief_handoff
from mission_control.domain.brief.provenance import AnswerAuthority
from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    ConfirmationAuthority,
    RequirementSection,
)
from mission_control.domain.brief.state import BriefState


class BriefNotFoundError(LookupError):
    """존재하지 않는 Mission의 Brief를 조작하려 했다."""

    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}의 Brief가 없다")
        self.mission_id = mission_id


class BriefAlreadyExistsError(ValueError):
    """이미 시작된 Brief를 다시 시작하려 했다.

    덮어쓰면 기존 대화와 승인이 사라진다. 재개는 시작이 아니라 로드다.
    """

    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}의 Brief가 이미 있다")
        self.mission_id = mission_id


class QuestionContractError(RuntimeError):
    """질문 생성기가 계약을 위반한 결과를 반환했다.

    빈 질문을 상태에 저장하면 사용자에게 보여 줄 것이 없는 round가 남고, 이후
    clarity 평가가 그 round를 정상적인 근거로 셈한다.
    """


class ClarityAssessmentError(RuntimeError):
    """clarity 평가가 결과를 만들어 내지 못했다.

    평가 실패를 낮은 점수나 높은 점수 어느 쪽으로도 해석하지 않는다. 저장된
    평가와 stability signal은 초기화되고, 호출자는 이번 턴에 종료 후보 판단이
    없었던 것으로 처리한다 (``docs/05_BRIEF.md`` §11.3).
    """

    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}의 clarity 평가가 결과를 내지 못했다")
        self.mission_id = mission_id


class ClosureAuditError(RuntimeError):
    """closure 감사의 lane 하나가 결과를 만들어 내지 못했다.

    실패를 ready로도 차단으로도 해석하지 않는다. 상태는 바뀌지 않으며 —
    같은 revision에 대한 이전의 완결된 감사가 있다면 내용이 같으므로 그대로
    유효하다 — 감사가 없던 상태라면 없는 채로 남아 Gate가 막는다.
    """

    def __init__(self, mission_id: str) -> None:
        super().__init__(f"mission {mission_id}의 closure 감사가 결과를 내지 못했다")
        self.mission_id = mission_id


class ClosureContractError(RuntimeError):
    """closure 역할이 계약을 위반한 결과를 반환했다.

    요청한 lane과 다른 lane의 결과를 받아들이면 어느 관점이 실제로 공격했는지
    기록이 거짓이 된다.
    """


@dataclass(frozen=True, slots=True)
class BriefService:
    """Brief Stage의 application 경계."""

    repository: BriefRepository
    question_generator: QuestionGenerator
    clarity_assessor: ClarityAssessor
    closure_assessor: ClosureAssessor
    closure_challenger: ClosureChallenger
    policy: ClarityPolicy

    async def start(self, *, mission_id: str, initial_intent: str) -> BriefState:
        """새 Brief를 시작하고 저장한다."""
        if await self.repository.load(mission_id) is not None:
            raise BriefAlreadyExistsError(mission_id)

        state = BriefState.start(mission_id=mission_id, initial_intent=initial_intent)
        await self.repository.save(state)
        return state

    async def ask_next_question(self, *, mission_id: str) -> GeneratedQuestion:
        """다음 질문 하나를 생성하고 답변 대기 상태로 저장한다.

        이미 대기 중인 질문이 있으면 생성기를 호출하지 않고 그 질문을 다시
        돌려준다. 세션이 끊겼다 재개된 경우 같은 질문이 두 번 생성되어 사용자가
        비슷한 질문을 연달아 받는 일을 막는다.

        생성기는 dispatch당 정확히 한 번 호출된다.
        """
        state = await self._require(mission_id)

        pending = state.pending_question
        if pending is not None:
            return GeneratedQuestion(question=pending.question, targeted_gap="resumed")

        generated = await self.question_generator.generate(self._request_for(state))
        if not generated.question.strip():
            raise QuestionContractError("질문 생성기가 빈 질문을 돌려주었다")

        posed = state.pose_question(question=generated.question)
        await self.repository.save(posed)
        return generated

    async def record_answer(
        self,
        *,
        mission_id: str,
        answer: str,
        authority: AnswerAuthority,
        question: str | None = None,
    ) -> BriefState:
        """답변을 기록하고 저장한다.

        저장에 실패하면 예외가 전파되고 저장소는 이전 상태를 유지한다. 호출자는
        답변이 기록되지 않은 것으로 처리해야 한다.
        """
        state = await self._require(mission_id)
        updated = state.record_answer(answer=answer, authority=authority, question=question)
        await self.repository.save(updated)
        return updated

    async def record_candidate(
        self,
        *,
        mission_id: str,
        section: RequirementSection,
        text: str,
        content_source: CandidateContentSource,
        resolution: CandidateResolution = CandidateResolution.NEEDS_CONFIRMATION,
        confirmation_authority: ConfirmationAuthority = ConfirmationAuthority.NONE,
        required: bool = False,
    ) -> BriefState:
        """요구사항 후보를 기록하고 저장한다.

        Non-goal, 충돌, 가정, 미해결이 모두 이 경로로 들어온다. 별도 진입점을
        만들지 않는 이유는 넷이 서로 다른 종류의 물건이 아니라 같은 후보의 다른
        축이기 때문이다 (``docs/adr/0015-requirement-candidate-model.md``).
        """
        state = await self._require(mission_id)
        updated = state.record_candidate(
            section=section,
            text=text,
            content_source=content_source,
            resolution=resolution,
            confirmation_authority=confirmation_authority,
            required=required,
        )
        await self.repository.save(updated)
        return updated

    async def resolve_candidate(
        self,
        *,
        mission_id: str,
        number: int,
        resolution: CandidateResolution,
        confirmation_authority: ConfirmationAuthority,
    ) -> BriefState:
        """후보의 확정 상태와 확인 권위를 갱신하고 저장한다."""
        state = await self._require(mission_id)
        updated = state.resolve_candidate(
            number=number,
            resolution=resolution,
            confirmation_authority=confirmation_authority,
        )
        await self.repository.save(updated)
        return updated

    async def approve(self, *, mission_id: str, statement: str) -> BriefState:
        """현재 revision에 대한 사용자 승인을 기록하고 저장한다.

        승인은 Gate를 대신하지 않는다. 저장이 실패하면 승인받지 않은 것으로
        취급한다 (``docs/05_BRIEF.md`` §12.2).
        """
        state = await self._require(mission_id)
        approved = state.approve(statement=statement)
        await self.repository.save(approved)
        return approved

    async def assess_clarity(self, *, mission_id: str) -> BriefState:
        """현재 Brief의 clarity를 평가하고 결과와 signal을 저장한다.

        최소 round에 도달하기 전에는 평가를 **수행하지 않는다**. 그 구간에서는
        어떤 점수가 나와도 종료 후보가 될 수 없으므로 호출이 순수 낭비다. 평가를
        생략한 구간은 상태에 결과가 없는 것으로 남아 "평가했으나 통과하지 못한"
        구간과 구분된다 (``docs/05_BRIEF.md`` §10 Step 8).

        평가가 실패하면 저장된 평가와 signal을 초기화한 뒤
        :class:`ClarityAssessmentError`를 올린다. 초기화를 저장하지 않으면 이전의
        통과 결과가 남아 다음 Gate가 그것으로 ``CLEAR``할 수 있다.
        """
        state = await self._require(mission_id)
        if len(state.answered_rounds) < self.policy.minimum_rounds:
            return state

        try:
            assessment = await self.clarity_assessor.assess(self._assessment_request(state))
            assessed = state.record_assessment(assessment=assessment, policy=self.policy)
        except Exception as error:
            await self.repository.save(state.record_assessment(assessment=None, policy=self.policy))
            raise ClarityAssessmentError(mission_id) from error

        await self.repository.save(assessed)
        return assessed

    async def audit_closure(self, *, mission_id: str) -> BriefState:
        """세 lane의 closure 감사를 수행하고 현재 revision에 기록한다.

        점수는 감사의 자격이지 종료의 자격이 아니다 — 종료 후보 조건이 충족된
        뒤, 승인을 요청하기 전에 호출한다 (``docs/05_BRIEF.md`` §11.6).

        어느 lane이든 실패하면 상태를 바꾸지 않고
        :class:`ClosureAuditError`를 올린다. 같은 revision의 이전 감사가 있다면
        내용이 같으므로 그대로 유효하고, 없었다면 없는 채로 남아 Gate가 막는다.
        """
        state = await self._require(mission_id)

        try:
            # 세 lane은 서로의 결과를 보지 않으므로 동시에 수행한다 — upstream이
            # tripanel을 한 병렬 배치로 spawn하는 것과 같은 배치다 (ADR-0035 §2).
            closer, contrarian, gap_hunter = await asyncio.gather(
                self.closure_assessor.audit(
                    CloserAuditRequest(
                        initial_intent=state.initial_intent,
                        previous_rounds=BriefService._asked_rounds(state),
                        requirement_candidates=BriefService._requirement_candidates(state),
                        gate_summary=CLOSURE_GATE_SUMMARY,
                    )
                ),
                self._challenge(state, AdvisoryLane.CONTRARIAN, CONTRARIAN_TASK),
                self._challenge(state, AdvisoryLane.GAP_HUNTER, GAP_HUNTER_TASK),
            )
        except ClosureContractError:
            raise
        except Exception as error:
            raise ClosureAuditError(mission_id) from error

        audited = state.record_closure_audit(
            audit=ClosureAudit(closer=closer, contrarian=contrarian, gap_hunter=gap_hunter)
        )
        await self.repository.save(audited)
        return audited

    async def _challenge(self, state: BriefState, lane: AdvisoryLane, task: str) -> AdvisoryReport:
        report = await self.closure_challenger.challenge(
            ClosureChallengeRequest(
                lane=lane,
                challenge=task,
                severity_rule=SEVERITY_RULE,
                initial_intent=state.initial_intent,
                previous_rounds=BriefService._asked_rounds(state),
                requirement_candidates=BriefService._requirement_candidates(state),
            )
        )
        if report.lane is not lane:
            raise ClosureContractError(
                f"challenger에게 {lane.value} lane을 요청했는데 "
                f"{report.lane.value} lane을 돌려주었다"
            )
        return report

    async def decide_gate(self, *, mission_id: str) -> BriefGateDecision:
        """저장된 상태로 Gate를 판정한다.

        평가를 다시 수행하지 않고 signal도 건드리지 않는다. Gate 조회가 signal을
        올리면 판정을 한 번 더 요청하는 것만으로 종료 조건이 충족되어, 평가
        하나당 한 번이라는 규칙이 우회된다 (§11.4).
        """
        state = await self._require(mission_id)
        return evaluate_brief_gate(state=state, policy=self.policy)

    async def build_handoff(self, *, mission_id: str) -> BriefHandoff:
        """``CLEAR``된 Brief에서 Blueprint 입력을 만든다.

        저장된 상태로 Gate를 다시 판정한 뒤 그 판정으로 handoff를 만든다. 호출자가
        건네준 판정을 믿지 않는 이유는, 판정 이후 내용이 바뀌었는데 옛 판정으로
        handoff가 만들어지는 경로를 열지 않기 위해서다.

        handoff는 저장하지 않는다. 파생 투영이므로 상태가 곧 진실이다.
        """
        state = await self._require(mission_id)
        decision = evaluate_brief_gate(state=state, policy=self.policy)
        return build_brief_handoff(state=state, decision=decision)

    async def _require(self, mission_id: str) -> BriefState:
        state = await self.repository.load(mission_id)
        if state is None:
            raise BriefNotFoundError(mission_id)
        return state

    @staticmethod
    def _request_for(state: BriefState) -> QuestionRequest:
        """생성기에 전달할 최소 context를 구성한다.

        authority와 revision 이력은 전달하지 않는다. 생성기는 무엇을 더 물어야
        하는지만 판단하면 되고, 저장 구조를 알면 그것을 근거로 요구사항을 지어낼
        여지가 생긴다.
        """
        return QuestionRequest(
            initial_intent=state.initial_intent,
            previous_rounds=BriefService._asked_rounds(state),
            requirement_candidates=BriefService._requirement_candidates(state),
        )

    def _assessment_request(self, state: BriefState) -> AssessmentRequest:
        """평가자에게 전달할 최소 context를 구성한다.

        채점 대상 축은 정책에서 가져온다. 평가자가 축 목록을 스스로 정하면 누락된
        축이 조용히 집계에서 빠진다.
        """
        return AssessmentRequest(
            initial_intent=state.initial_intent,
            previous_rounds=BriefService._asked_rounds(state),
            requirement_candidates=BriefService._requirement_candidates(state),
            dimensions=tuple(self.policy.weights),
        )

    @staticmethod
    def _asked_rounds(state: BriefState) -> tuple[AskedRound, ...]:
        return tuple(
            AskedRound(question=item.question, answer=item.answer) for item in state.rounds
        )

    @staticmethod
    def _requirement_candidates(state: BriefState) -> tuple[RequirementView, ...]:
        """후보 전체를 resolution과 함께 투영한다 (ADR-0035 §1).

        확정된 후보를 감추면 위임 역할이 이미 결정된 사안을 다시 차단한다 —
        도그푸딩 0001에서 감사 2순환이 이렇게 낭비되었다. upstream 감사는
        전체 관점에서 수행되므로 같은 가시성을 준다. 확인 권위와 내용 출처는
        전달하지 않는다 — 승격 판정의 재료이지 질문의 재료가 아니다.
        """
        return tuple(
            RequirementView(
                section=item.section,
                text=item.text,
                resolution=item.resolution,
                required=item.required,
            )
            for item in state.candidates
        )
