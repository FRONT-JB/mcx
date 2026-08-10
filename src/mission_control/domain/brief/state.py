"""Brief의 durable state — round 축적, revision, 사용자 승인.

Brief는 대화가 아니라 상태다. 세션이 사라져도 다음 세션이 이어갈 수 있어야 하고,
각 변경의 원인과 이전 값을 추적할 수 있어야 한다.

이 모듈이 강제하는 핵심 불변 조건은 **승인이 특정 revision에 묶인다**는 것이다.
승인 이후 내용이 바뀌면 그 승인은 현재 revision에 유효하지 않다. 이것이 없으면
사용자가 A를 승인했는데 B가 실행되는 상황을 구조적으로 막을 수 없다.

상태 객체는 불변이다. 변경 메서드는 새 상태를 반환하고 이전 객체를 그대로 둔다.
revision 스냅샷이 나중 변경에 오염되지 않아야 감사가 성립한다.

시각(timestamp)은 아직 다루지 않는다. 도메인이 직접 현재 시각을 읽으면 테스트가
비결정적이 되므로, 필요해지는 시점에 Clock port와 함께 도입한다
(``docs/01_ARCHITECTURE.md`` §6.4, §13.1).

계약: ``docs/05_BRIEF.md`` §8, §8.1, §12.2
결정: ``docs/adr/0013-brief-durable-state-baseline.md``
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from mission_control.domain.brief.clarity import ClarityAssessment, ClarityPolicy
from mission_control.domain.brief.closure import ClosureAudit, ClosureAuditRecord
from mission_control.domain.brief.derivation import (
    DERIVED_AUTHORITY,
    DERIVED_CONTENT_SOURCE,
    DERIVED_REQUIRED,
    DERIVED_RESOLUTION,
    DerivedCandidate,
    derive_from_answer,
    derive_from_intent,
)
from mission_control.domain.brief.provenance import AnswerAuthority, BriefRound
from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    ConfirmationAuthority,
    PromotionResult,
    RequirementCandidate,
    RequirementSection,
    evaluate_promotion,
)
from mission_control.domain.errors import MissionControlError


class DuplicateRequirementCandidateError(MissionControlError):
    """같은 section과 exact 원문인 후보가 이미 있다."""

    def __init__(self, *, existing_number: int, section: RequirementSection) -> None:
        super().__init__(f"{section.value}의 같은 요구사항 후보가 이미 {existing_number}번에 있다")
        self.existing_number = existing_number
        self.section = section


class BriefApproval(BaseModel):
    """사용자가 특정 revision으로 진행을 승인한 기록.

    승인은 Brief 전체가 아니라 **그 시점의 revision**을 가리킨다. 오래된 revision에
    대한 승인을 최신 revision에 재사용하지 않는다.
    """

    model_config = ConfigDict(frozen=True)

    revision: int
    statement: str


class BriefRevisionSnapshot(BaseModel):
    """한 revision 시점의 round 구성.

    Gate decision과 승인이 참조한 revision을 나중에 그대로 조회할 수 있어야 하므로
    보존한다. 별도 파일로 나누지 않고 같은 문서 안에 둔다 (ADR-0013 §2).
    """

    model_config = ConfigDict(frozen=True)

    revision: int
    rounds: tuple[BriefRound, ...]


class BriefState(BaseModel):
    """하나의 Mission에 대한 Brief 상태."""

    model_config = ConfigDict(frozen=True)

    mission_id: str
    initial_intent: str
    #: 내용 버전. 요구사항에 영향을 주는 변경에서만 올라가며, 승인이 여전히
    #: 유효한지 판정하는 기준이다.
    revision: int = 1
    #: 쓰기 순서. 상태가 바뀌는 모든 경우에 올라간다. 질문을 던지는 것처럼
    #: 요구사항을 바꾸지 않는 변경도 저장은 되어야 하므로 revision과 분리한다.
    #: 저장소는 이 값으로 덮어쓰기를 판정한다.
    sequence: int = 1
    rounds: tuple[BriefRound, ...] = ()
    approval: BriefApproval | None = None
    #: 대화에서 자란 요구사항 후보. Non-goal, 충돌, 가정, 미해결이 별도 목록이
    #: 아니라 이 하나의 목록 안에서 축으로 구분된다.
    candidates: tuple[RequirementCandidate, ...] = ()
    #: 현재 revision에 대한 clarity 평가. ``None``은 "평가하지 않았다"이며
    #: "평가했으나 통과하지 못했다"와 다르다 (``docs/05_BRIEF.md`` §10 Step 8).
    assessment: ClarityAssessment | None = None
    #: 종료 조건을 연속으로 만족한 횟수. 평가와 짝이며 따로 살아남지 않는다.
    stability_signal: int = 0
    #: 가장 최근의 closure 감사. 승인처럼 revision에 묶이며, material 변경이
    #: revision을 올리면 자동으로 stale이 된다 (ADR-0020 §6).
    closure_audit: ClosureAuditRecord | None = None
    history: tuple[BriefRevisionSnapshot, ...] = Field(default=())

    @property
    def promotion(self) -> PromotionResult:
        """후보 목록에 대한 결정적 승격 판정.

        clarity 점수와 무관한 두 번째 관문이다. 점수가 통과 범위여도 여기에
        blocker가 있으면 진행하지 않는다 (``docs/05_BRIEF.md`` §11.5).
        """
        return evaluate_promotion(self.candidates)

    def candidates_in(self, section: RequirementSection) -> tuple[RequirementCandidate, ...]:
        return tuple(item for item in self.candidates if item.section is section)

    @classmethod
    def start(cls, *, mission_id: str, initial_intent: str) -> BriefState:
        """사용자의 원문 의도를 보존한 채 Brief를 시작한다.

        의도는 **동시에 GOAL 후보가 된다** (ADR-0050 §1, upstream
        ``initial-goal``). 후보 기록을 별도 명령에 맡기면 그것을 빠뜨린 채
        Gate를 통과해 빈 handoff에 도달한다 — 도그푸딩 0004가 관측한 경로다.
        """
        state = cls(mission_id=mission_id, initial_intent=initial_intent)
        derived = derive_from_intent(initial_intent)
        if derived is None:
            return state
        return state.model_copy(update={"candidates": (_as_candidate(derived, number=1),)})

    @property
    def has_current_approval(self) -> bool:
        """현재 revision에 유효한 승인이 있는가.

        승인 이후 material 변경이 있었다면 ``False``다. 승인 기록 자체는 남아 있되
        현재 내용에 대한 권한은 아니다.
        """
        return self.approval is not None and self.approval.revision == self.revision

    @property
    def pending_question(self) -> BriefRound | None:
        """아직 답변되지 않은 마지막 질문. 없으면 ``None``."""
        if self.rounds and self.rounds[-1].answer is None:
            return self.rounds[-1]
        return None

    @property
    def answered_rounds(self) -> tuple[BriefRound, ...]:
        return tuple(item for item in self.rounds if item.answer is not None)

    def pose_question(self, *, question: str) -> BriefState:
        """답변을 기다리는 질문을 기록한다.

        질문 생성 직후 세션이 끊겨도 같은 질문으로 재개할 수 있어야 하므로 답변을
        받기 전에 저장한다 (``docs/05_BRIEF.md`` §14.1). 답변 슬롯은 비어 있으므로
        미답변 질문이 답변된 것처럼 다뤄지지 않는다 (§8.1 규칙 5).

        revision을 올리지 않는다. 답변 없는 질문은 요구사항을 바꾸지 않으므로
        기존 승인의 의미도 바꾸지 않는다. revision은 내용이 실제로 달라지는
        시점에만 올린다.

        이미 대기 중인 질문이 있으면 거부한다. 두 질문을 동시에 열어 두면 도착한
        답변이 어느 질문의 것인지 알 수 없다.
        """
        if not question.strip():
            raise ValueError("질문이 비어 있을 수 없다")
        if self.pending_question is not None:
            raise ValueError("이미 답변을 기다리는 질문이 있다")

        posed = BriefRound(
            number=len(self.rounds) + 1,
            question=question,
            answer=None,
            authority="decision",
        )
        return self.model_copy(
            update={"sequence": self.sequence + 1, "rounds": (*self.rounds, posed)}
        )

    def record_answer(
        self,
        *,
        answer: str,
        authority: AnswerAuthority,
        question: str | None = None,
    ) -> BriefState:
        """답변을 기록하고 revision을 올린다.

        대기 중인 질문이 있으면 그 round를 채우고, 없으면 ``question``과 함께 새
        round를 만든다. 두 경로가 하나의 메서드로 모이는 이유는 authority가
        결정되는 지점을 하나로 유지하기 위해서다
        (``docs/adr/0010-answer-provenance-and-requirement-authority.md``).

        빈 답변은 거부한다. 미답변 질문을 답변된 것처럼 저장하면 이후 clarity 평가와
        요구사항 추출이 존재하지 않는 근거를 사실로 다루게 된다 (§8.1 규칙 5).
        """
        if not answer.strip():
            raise ValueError(
                "답변이 비어 있을 수 없다; 답하지 않은 라운드는 기록된 라운드가 아니다"
            )

        pending = self.pending_question
        if pending is not None:
            filled = pending.model_copy(update={"answer": answer, "authority": authority})
            rounds = (*self.rounds[:-1], filled)
        else:
            if question is None:
                raise ValueError("대기 중인 질문이 없다; 답변을 기록하려면 질문이 필요하다")
            rounds = (
                *self.rounds,
                BriefRound(
                    number=len(self.rounds) + 1,
                    question=question,
                    answer=answer,
                    authority=authority,
                ),
            )

        # 결정 답변이 요구사항 어휘를 담고 있으면 후보가 함께 생긴다
        # (ADR-0050 §1). observation은 사실이지 결정이 아니므로 어휘와 무관하게
        # 건너뛴다 — upstream이 같은 자리에서 같은 이유로 건너뛴다.
        candidates = self.candidates
        if authority == "decision":
            derived = derive_from_answer(answer)
            if derived is not None:
                candidates = (*candidates, _as_candidate(derived, number=len(candidates) + 1))

        return self.model_copy(
            update={
                "revision": self.revision + 1,
                "sequence": self.sequence + 1,
                "rounds": rounds,
                "candidates": candidates,
                "assessment": None,
                "stability_signal": 0,
                "history": (*self.history, self._current_snapshot()),
            }
        )

    def record_candidate(
        self,
        *,
        section: RequirementSection,
        text: str,
        content_source: CandidateContentSource,
        resolution: CandidateResolution = CandidateResolution.NEEDS_CONFIRMATION,
        confirmation_authority: ConfirmationAuthority = ConfirmationAuthority.NONE,
        required: bool = False,
    ) -> BriefState:
        """요구사항 후보를 기록하고 revision을 올린다.

        후보의 추가는 material 변경이다. 승인 이후에 발견된 미해결 후보가 기존
        승인을 그대로 통과시키면, 사용자가 보지 못한 gap을 승인한 것이 된다.

        기본값은 "아직 확인되지 않았고 권위가 없음"이다. 확인은 별도의 사건이며
        기록과 동시에 일어나지 않는다.
        """
        normalized = text.strip()
        if not normalized:
            raise ValueError("후보 문장이 비어 있을 수 없다")
        existing = next(
            (
                item
                for item in self.candidates
                if item.section is section and item.text.strip() == normalized
            ),
            None,
        )
        if existing is not None:
            raise DuplicateRequirementCandidateError(
                existing_number=existing.number, section=section
            )

        candidate = RequirementCandidate(
            number=len(self.candidates) + 1,
            section=section,
            text=normalized,
            content_source=content_source,
            resolution=resolution,
            confirmation_authority=confirmation_authority,
            required=required,
        )
        return self.model_copy(
            update={
                "revision": self.revision + 1,
                "sequence": self.sequence + 1,
                "candidates": (*self.candidates, candidate),
                "assessment": None,
                "stability_signal": 0,
                "history": (*self.history, self._current_snapshot()),
            }
        )

    def resolve_candidate(
        self,
        *,
        number: int,
        resolution: CandidateResolution,
        confirmation_authority: ConfirmationAuthority,
    ) -> BriefState:
        """후보의 확정 상태와 확인 권위를 갱신한다.

        내용이 아니라 상태가 바뀌는 것이지만 material 변경이다. 미해결이던 후보가
        확정되면 Gate 판정이 달라지므로 기존 승인과 평가를 그대로 둘 수 없다.
        """
        matched = [item for item in self.candidates if item.number == number]
        if not matched:
            raise ValueError(f"{number}번 요구사항 후보가 없다")

        updated = tuple(
            item.model_copy(
                update={
                    "resolution": resolution,
                    "confirmation_authority": confirmation_authority,
                }
            )
            if item.number == number
            else item
            for item in self.candidates
        )
        return self.model_copy(
            update={
                "revision": self.revision + 1,
                "sequence": self.sequence + 1,
                "candidates": updated,
                "assessment": None,
                "stability_signal": 0,
                "history": (*self.history, self._current_snapshot()),
            }
        )

    def record_assessment(
        self, *, assessment: ClarityAssessment | None, policy: ClarityPolicy
    ) -> BriefState:
        """clarity 평가 결과와 그에 따른 stability signal을 기록한다.

        revision을 올리지 않는다. 평가는 요구사항을 바꾸지 않으므로 기존 승인의
        의미도 바꾸지 않는다. 반대 방향은 성립한다 — 요구사항이 바뀌면 평가와
        signal이 함께 무효화된다 (``docs/05_BRIEF.md`` §8.1 규칙 10).

        signal을 인자로 받지 않고 정책에서 직접 계산하는 이유는 갱신 지점을 하나로
        유지하기 위해서다. 호출자가 값을 정할 수 있으면 한 턴에 두 번 올라 단일
        평가로 종료되는 회귀가 다시 열린다 (upstream #405).

        ``assessment``가 ``None``이면 "결과 없음"이다. 평가 실패를 낮은 점수나
        높은 점수 어느 쪽으로도 해석하지 않고 signal만 초기화한다 (§11.3).
        """
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "assessment": assessment,
                "stability_signal": policy.next_stability_signal(
                    current=self.stability_signal,
                    assessment=assessment,
                    answered_rounds=len(self.answered_rounds),
                ),
            }
        )

    def record_closure_audit(self, *, audit: ClosureAudit) -> BriefState:
        """현재 revision에 대한 closure 감사 결과를 기록한다.

        revision을 올리지 않는다 — 감사는 요구사항을 바꾸지 않는다. 반대
        방향은 revision 바인딩으로 성립한다: 이후 material 변경이 revision을
        올리면 이 기록은 자동으로 현재 내용에 대한 감사가 아니게 된다.
        """
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "closure_audit": ClosureAuditRecord(revision=self.revision, audit=audit),
            }
        )

    @property
    def has_current_closure_audit(self) -> bool:
        """현재 revision에 대한 감사가 있는가. 통과 여부는 보지 않는다."""
        return self.closure_audit is not None and self.closure_audit.revision == self.revision

    def approve(self, *, statement: str) -> BriefState:
        """현재 revision에 대한 사용자 승인을 기록한다.

        승인은 Gate를 대신하지 않는다. 필수 gap이 남아 있으면 승인이 있어도
        ``HOLD``다 (``docs/05_BRIEF.md`` §11.5).
        """
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "approval": BriefApproval(revision=self.revision, statement=statement),
            }
        )

    def snapshot_at(self, *, revision: int) -> BriefRevisionSnapshot | None:
        """해당 revision 시점의 round 구성을 반환한다. 없으면 ``None``."""
        if revision == self.revision:
            return self._current_snapshot()
        for snapshot in self.history:
            if snapshot.revision == revision:
                return snapshot
        return None

    def _current_snapshot(self) -> BriefRevisionSnapshot:
        return BriefRevisionSnapshot(revision=self.revision, rounds=self.rounds)


def _as_candidate(derived: DerivedCandidate, *, number: int) -> RequirementCandidate:
    """파생 재료를 저장 형태로. 값은 ADR-0050 §1이 고정한 것뿐이다."""
    return RequirementCandidate(
        number=number,
        section=derived.section,
        text=derived.text,
        content_source=DERIVED_CONTENT_SOURCE,
        resolution=DERIVED_RESOLUTION,
        confirmation_authority=DERIVED_AUTHORITY,
        required=DERIVED_REQUIRED,
    )
