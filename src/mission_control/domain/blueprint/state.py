"""Blueprint의 durable state — revision 이력, QA 채점 기록, 사용자 승인.

이 모듈이 강제하는 핵심 불변 조건은 두 개다.

**승인은 채점된 현재 revision에만 성립한다.** 채점되지 않은 내용을 승인하면
승인 기록이 담아야 할 QA 근거(ADR-0019 §8)가 없고, 이전 revision의 점수를
빌리면 승인된 내용과 기록된 점수의 대상이 어긋난다. 승인 뒤 내용이 바뀌면
승인은 이전 revision에 묶인 채 stale이 된다.

**채점 예산은 durable 상태에 있다.** 반복 상한(ADR-0019 §6)이 메모리에만 있으면
세션을 다시 시작하는 것만으로 횟수가 초기화된다. 채점 기록이 상태에 남으므로
상한 판정이 재시작을 건너 유지된다.

점수에서 판정과 최선을 계산하는 기계는
:class:`~mission_control.domain.blueprint.qa.QaLoopState`를 그대로 쓴다. 이
모듈이 더하는 것은 **어느 revision을 채점했는가**의 연결이다 — upstream이
추적하는 것은 점수가 아니라 최고 점수의 seed 내용이므로, 연결을 잃으면 상한
도달 시 제시할 "최선의 시도"가 재구성되지 않는다.

계약: ``docs/06_BLUEPRINT.md`` §7, §9, §12
결정: ``docs/adr/0021-blueprint-state-and-revisions.md``
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from mission_control.domain.blueprint.qa import (
    QaAssessment,
    QaAttempt,
    QaLoopState,
    QaPolicy,
    QaVerdict,
)
from mission_control.domain.blueprint.spec import Blueprint, BlueprintApproval
from mission_control.domain.errors import MissionControlError


class QaBudgetExhaustedError(MissionControlError):
    """반복 상한에 도달한 뒤 채점을 요청했다.

    상한 도달의 출구는 추가 반복이 아니라 사용자 결정이다 — 최선의 시도를
    수락하거나 에스컬레이션한다 (ADR-0019 §6, upstream은 6회째 반복을 금지한다).
    """

    def __init__(self, *, mission_id: str, max_iterations: int) -> None:
        super().__init__(
            f"QA budget for mission {mission_id} is exhausted "
            f"({max_iterations} iterations); a user decision is required"
        )
        self.mission_id = mission_id
        self.max_iterations = max_iterations


class QaAlreadyPassedError(MissionControlError):
    """이미 통과 점수를 받은 revision을 다시 채점하려 했다.

    통과한 내용의 재채점은 명세를 좋게 만들지 않고 점수만 갱신한다. 낮아지면
    통과가 사라지고 높아져도 얻는 것이 없다 — 어느 쪽도 판정 기준을 흔드는
    것 외의 효과가 없다.
    """

    def __init__(self, *, mission_id: str, revision: int) -> None:
        super().__init__(
            f"blueprint revision {revision} for mission {mission_id} already passed QA"
        )
        self.mission_id = mission_id
        self.revision = revision


class QaEscalatedError(MissionControlError):
    """FAIL 판정 뒤에 루프를 계속하려 했다.

    FAIL은 재작업 점수가 아니라 명세 수준의 문제다. 반복이나 승인으로 해결하지
    않고 위로 올린다 (ADR-0019 §6 ``ESCALATE``). FAIL 후 루프 폐쇄가 upstream
    성문 규칙인지는 미확인이다 (ADR-0022).
    """

    def __init__(self, *, mission_id: str) -> None:
        super().__init__(
            f"QA for mission {mission_id} escalated on a FAIL verdict; the loop does not continue"
        )
        self.mission_id = mission_id


class UnassessedRevisionError(MissionControlError):
    """채점된 적 없는 revision을 승인하려 했다.

    승인 기록은 QA 근거(정책 버전·임계값·점수)를 담아야 한다 (ADR-0019 §8).
    채점 없는 승인을 허용하면 QA를 거치지 않은 내용이 "QA 근거를 담은 승인"으로
    기록된다.
    """

    def __init__(self, *, mission_id: str, revision: int) -> None:
        super().__init__(
            f"blueprint revision {revision} for mission {mission_id} has no QA assessment; "
            "approval requires one"
        )
        self.mission_id = mission_id
        self.revision = revision


class QaLoopStillOpenError(MissionControlError):
    """반복 예산이 남아 있는데 기준 미달 명세를 승인하려 했다.

    미달 수락은 상한이 소진된 뒤의 선택지다 (ADR-0021 §5, upstream은 5회 이후에만
    세 선택지를 제시한다). 이르게 허용하면 반복 예산이 장식이 된다.
    """

    def __init__(self, *, mission_id: str, revision: int) -> None:
        super().__init__(
            f"blueprint revision {revision} for mission {mission_id} is below the QA "
            "threshold and the iteration budget is not exhausted; refine it instead"
        )
        self.mission_id = mission_id
        self.revision = revision


class BlueprintQaRecord(BaseModel):
    """한 번의 채점과 그것이 본 revision.

    :class:`~mission_control.domain.blueprint.qa.QaAttempt`에 revision을 넣지
    않는 이유는 점수-판정 기계가 revision을 알 필요가 없기 때문이다. 연결은
    이 상태가 소유한다 (ADR-0021 §3).
    """

    model_config = ConfigDict(frozen=True)

    revision: int
    assessment: QaAssessment


class BlueprintState(BaseModel):
    """하나의 Mission에 대한 Blueprint 상태.

    모든 revision을 순서대로 보존한다. 수정은 이전 revision을 바꾸지 않고 새
    revision을 뒤에 붙인다 — 승인된 revision이 불변이어야(ADR-0002) Execute와
    Verify가 참조하는 명세가 흔들리지 않는다.
    """

    model_config = ConfigDict(frozen=True)

    mission_id: str
    #: 쓰기 순서. 상태가 바뀌는 모든 경우에 올라간다. 저장소는 이 값으로
    #: 덮어쓰기를 판정한다 (ADR-0014와 같은 두 축 구분).
    sequence: int = 1
    #: revision 1부터의 전체 이력. 마지막 항목이 현재 revision이다.
    revisions: tuple[Blueprint, ...]
    #: 채점 기록. 루프 전체에 걸친 순서가 곧 iteration 순서다.
    qa_records: tuple[BlueprintQaRecord, ...] = ()
    approval: BlueprintApproval | None = None

    @model_validator(mode="after")
    def _revisions_are_contiguous(self) -> BlueprintState:
        """revision 번호가 1부터 빈틈없이 이어지는지 확인한다.

        번호에 빈틈이 있으면 승인·채점 기록이 가리키는 revision을 이력에서
        찾을 수 없게 되고, 그 순간 기록이 검증 불가능해진다.
        """
        if not self.revisions:
            raise ValueError("a blueprint state must hold at least one revision")
        for index, item in enumerate(self.revisions):
            if item.revision != index + 1:
                raise ValueError(
                    f"blueprint revisions must be contiguous from 1: "
                    f"position {index} holds revision {item.revision}"
                )
            if item.mission_id != self.mission_id:
                raise ValueError(
                    f"revision {item.revision} belongs to mission {item.mission_id}, "
                    f"not {self.mission_id}"
                )
        return self

    @classmethod
    def start(cls, *, blueprint: Blueprint) -> BlueprintState:
        """첫 생성 결과로 상태를 시작한다. 첫 생성은 정확히 한 번이다 (ADR-0021 §2)."""
        return cls(mission_id=blueprint.mission_id, revisions=(blueprint,))

    @property
    def current(self) -> Blueprint:
        return self.revisions[-1]

    @property
    def revision(self) -> int:
        return self.current.revision

    @property
    def has_current_approval(self) -> bool:
        """현재 revision에 유효한 승인이 있는가.

        승인 이후 revise가 있었다면 ``False``다. 승인 기록 자체는 남아 있되
        현재 내용에 대한 권한은 아니다.
        """
        return self.approval is not None and self.approval.revision == self.revision

    def loop(self, *, policy: QaPolicy) -> QaLoopState:
        """채점 기록을 판정 기계에 얹는다. 기록 순서가 iteration 순서다."""
        return QaLoopState(
            policy=policy,
            attempts=tuple(
                QaAttempt(iteration=index + 1, assessment=item.assessment)
                for index, item in enumerate(self.qa_records)
            ),
        )

    def best_record(self, *, policy: QaPolicy) -> BlueprintQaRecord | None:
        """최고 점수의 채점과 그 revision. 동점 규칙은 판정 기계의 것을 따른다.

        상한 도달 시 사용자에게 제시하는 것은 마지막이 아니라 이것이다
        (ADR-0019 §5).
        """
        best = self.loop(policy=policy).best
        if best is None:
            return None
        return self.qa_records[best.iteration - 1]

    def records_for(self, revision: int) -> tuple[BlueprintQaRecord, ...]:
        return tuple(item for item in self.qa_records if item.revision == revision)

    def ensure_qa_allowed(self, *, policy: QaPolicy) -> None:
        """채점이 허용되는 상태인지 확인한다. 아니면 예외를 올린다.

        허용 규칙은 ADR-0021 §4다 — FAIL 뒤에는 계속하지 않고, 이미 통과한
        revision을 다시 채점하지 않으며, 상한을 넘겨 한 번 더 돌지 않는다.
        통과 후 revise된 새 revision은 잔여 상한 안에서 채점할 수 있다.

        :meth:`record_qa`와 분리되어 있는 이유는 채점이 위임 호출이기 때문이다.
        기록 시점에만 검사하면 규칙상 일어나지 말았어야 할 채점(예: 6회째)이
        이미 수행된 뒤에 거부된다 — 호출자는 위임 전에 이것을 먼저 묻는다.
        """
        if self.qa_records:
            latest_verdict = policy.verdict_for(self.qa_records[-1].assessment.score)
            if latest_verdict is QaVerdict.FAIL:
                raise QaEscalatedError(mission_id=self.mission_id)
        for item in self.records_for(self.revision):
            if policy.verdict_for(item.assessment.score) is QaVerdict.PASS:
                raise QaAlreadyPassedError(mission_id=self.mission_id, revision=self.revision)
        if len(self.qa_records) >= policy.max_iterations:
            raise QaBudgetExhaustedError(
                mission_id=self.mission_id, max_iterations=policy.max_iterations
            )

    def record_qa(self, *, assessment: QaAssessment, policy: QaPolicy) -> BlueprintState:
        """현재 revision에 대한 채점을 기록한다. 허용 규칙은 :meth:`ensure_qa_allowed`."""
        self.ensure_qa_allowed(policy=policy)

        record = BlueprintQaRecord(revision=self.revision, assessment=assessment)
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "qa_records": (*self.qa_records, record),
            }
        )

    def revise(self, *, blueprint: Blueprint) -> BlueprintState:
        """수정된 내용을 새 revision으로 붙인다. 이전 revision은 바뀌지 않는다.

        기존 승인이 있어도 막지 않는다 — 승인은 이전 revision에 묶인 채 stale이
        되고, Gate가 그것을 ``HOLD`` 사유로 드러낸다 (ADR-0002: 변경은 수정이
        아니라 새 revision + 재승인이다).
        """
        if blueprint.mission_id != self.mission_id:
            raise ValueError(
                f"revision belongs to mission {blueprint.mission_id}, not {self.mission_id}"
            )
        if blueprint.revision != self.revision + 1:
            raise ValueError(f"expected revision {self.revision + 1}, got {blueprint.revision}")
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "revisions": (*self.revisions, blueprint),
            }
        )

    def approve(
        self,
        *,
        statement: str,
        policy: QaPolicy,
        accept_below_threshold: bool = False,
    ) -> BlueprintState:
        """현재 revision에 대한 사용자 승인을 기록한다.

        점수 기준은 **승인 대상 revision의 최고 점수**다 (ADR-0021 §5). 루프
        전체의 최고 점수를 쓰면 승인된 내용과 기록된 점수의 대상이 어긋날 수
        있고, 그 순간 미달 수락 표시의 일관성 검사가 지키는 것이 무너진다.

        점수와 미달 수락 표시의 일관성은 :class:`BlueprintApproval`의 validator가
        강제한다 — 미달인데 표시가 없거나, 통과인데 표시가 있으면 여기서가
        아니라 기록 생성 자체가 거부된다.
        """
        scores = tuple(item.assessment.score for item in self.records_for(self.revision))
        if not scores:
            raise UnassessedRevisionError(mission_id=self.mission_id, revision=self.revision)

        best_score = max(scores)
        verdict = policy.verdict_for(best_score)
        if verdict is QaVerdict.FAIL:
            raise QaEscalatedError(mission_id=self.mission_id)
        if verdict is QaVerdict.REVISE and len(self.qa_records) < policy.max_iterations:
            raise QaLoopStillOpenError(mission_id=self.mission_id, revision=self.revision)

        approval = BlueprintApproval(
            revision=self.revision,
            statement=statement,
            qa_policy_version=policy.version,
            qa_threshold=policy.pass_threshold,
            qa_best_score=best_score,
            qa_iterations=len(self.qa_records),
            accepted_below_threshold=accept_below_threshold,
        )
        return self.model_copy(update={"sequence": self.sequence + 1, "approval": approval})
