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
from mission_control.domain.brief.provenance import AnswerAuthority, BriefRound


class BriefApproval(BaseModel):
    """사용자가 특정 revision으로 진행을 승인한 기록.

    승인은 Brief 전체가 아니라 **그 시점의 revision**을 가리킨다. 오래된 revision에
    대한 승인을 최신 revision에 재사용하지 않는다.
    """

    model_config = ConfigDict(frozen=True)

    revision: int
    statement: str


class UnresolvedItem(BaseModel):
    """아직 해소되지 않은 결정, 충돌, 또는 확인되지 않은 가정.

    ``is_material``은 이 항목이 다음 Stage의 판단을 실제로 바꾸는지를 나타낸다.
    material한 항목이 남아 있으면 clarity 점수가 아무리 좋아도 ``CLEAR``하지
    않는다 (``docs/05_BRIEF.md`` §11.5). 점수는 "얼마나 명확해 보이는가"를
    측정할 뿐, 아직 아무도 답하지 않은 질문이 있다는 사실을 대신하지 못한다.
    """

    model_config = ConfigDict(frozen=True)

    description: str
    is_material: bool


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
    unresolved_items: tuple[UnresolvedItem, ...] = ()
    #: 현재 revision에 대한 clarity 평가. ``None``은 "평가하지 않았다"이며
    #: "평가했으나 통과하지 못했다"와 다르다 (``docs/05_BRIEF.md`` §10 Step 8).
    assessment: ClarityAssessment | None = None
    #: 종료 조건을 연속으로 만족한 횟수. 평가와 짝이며 따로 살아남지 않는다.
    stability_signal: int = 0
    history: tuple[BriefRevisionSnapshot, ...] = Field(default=())

    @property
    def material_unresolved_items(self) -> tuple[UnresolvedItem, ...]:
        return tuple(item for item in self.unresolved_items if item.is_material)

    @classmethod
    def start(cls, *, mission_id: str, initial_intent: str) -> BriefState:
        """사용자의 원문 의도를 보존한 채 Brief를 시작한다."""
        return cls(mission_id=mission_id, initial_intent=initial_intent)

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
            raise ValueError("question must not be empty")
        if self.pending_question is not None:
            raise ValueError("a question is already awaiting an answer")

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
            raise ValueError("answer must not be empty; an unanswered round is not a recorded one")

        pending = self.pending_question
        if pending is not None:
            filled = pending.model_copy(update={"answer": answer, "authority": authority})
            rounds = (*self.rounds[:-1], filled)
        else:
            if question is None:
                raise ValueError("no pending question; question is required to record an answer")
            rounds = (
                *self.rounds,
                BriefRound(
                    number=len(self.rounds) + 1,
                    question=question,
                    answer=answer,
                    authority=authority,
                ),
            )

        return self.model_copy(
            update={
                "revision": self.revision + 1,
                "sequence": self.sequence + 1,
                "rounds": rounds,
                "assessment": None,
                "stability_signal": 0,
                "history": (*self.history, self._current_snapshot()),
            }
        )

    def note_unresolved(self, *, description: str, is_material: bool) -> BriefState:
        """미해결 항목을 기록하고 revision을 올린다.

        미해결 항목의 추가는 material 변경이다. 승인 이후에 발견된 항목이 기존
        승인을 그대로 통과시키면, 사용자가 보지 못한 gap을 승인한 것이 된다.
        """
        item = UnresolvedItem(description=description, is_material=is_material)
        return self.model_copy(
            update={
                "revision": self.revision + 1,
                "sequence": self.sequence + 1,
                "unresolved_items": (*self.unresolved_items, item),
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
