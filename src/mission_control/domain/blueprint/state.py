"""Blueprint의 durable state — revision 이력, QA 채점 기록, 사용자 승인.

이 모듈이 강제하는 핵심 불변 조건은 세 개다.

**승인은 채점된 현재 revision에만 성립한다.** 채점되지 않은 내용을 승인하면
승인 기록이 담아야 할 QA 근거(ADR-0019 §8)가 없고, 이전 revision의 점수를
빌리면 승인된 내용과 기록된 점수의 대상이 어긋난다. 승인 뒤 내용이 바뀌면
승인은 이전 revision에 묶인 채 stale이 된다.

예외는 **상한 소진 뒤의 최종 수정 1회** 하나다 (ADR-0019 §6.1). upstream은
그 수정을 재채점하지 말라고 명시하므로(``skills/seed/SKILL.md:113``) 점수를
물려받을 수밖에 없고, 대신 어긋남을 숨기지 않는다 —
``BlueprintApproval.qa_scored_revision``이 **어느 revision의 점수인지**를
기록에 남긴다. 이 예외가 없으면 소진 뒤 명세를 고치는 순간 미션이 잠긴다
(도그푸딩 0005 §4가 관측했다).

**채점 예산은 generation별 durable 상태에 있다.** 반복 상한(ADR-0019 §6)이
메모리에만 있으면 세션을 다시 시작하는 것만으로 횟수가 초기화된다. 같은
generation의 revision들은 기록을 공유하고, Execute→Verify 뒤 Evolve가 연 다음
generation만 새 예산을 갖는다 (ADR-0051 §7).

**Evolve checkpoint와 successor revision은 한 상태 문서에 있다.** Wonder·Reflect
중단은 완료한 phase 다음부터 재개하고, 마지막 record와 새 revision은 한 번의
상태 변경으로 붙는다. 진행 중에는 parent revision을 다른 수정으로 움직이지
않는다 (ADR-0051 §8).

점수에서 판정과 최선을 계산하는 기계는
:class:`~mission_control.domain.blueprint.qa.QaLoopState`를 그대로 쓴다. 이
모듈이 더하는 것은 **어느 revision을 채점했는가**의 연결이다 — upstream이
추적하는 것은 점수가 아니라 최고 점수의 seed 내용이므로, 연결을 잃으면 상한
도달 시 제시할 "최선의 시도"가 재구성되지 않는다.

계약: ``docs/06_BLUEPRINT.md`` §7, §9, §12
결정: ``docs/adr/0021-blueprint-state-and-revisions.md``
"""

from __future__ import annotations

from typing import Literal

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
from mission_control.domain.evolve.models import (
    EvolutionPhase,
    EvolutionRecord,
    EvolveSourceSnapshot,
    ReflectOutput,
    ScopeChangeFinding,
    WonderOutput,
)


class QaBudgetExhaustedError(MissionControlError):
    """반복 상한에 도달한 뒤 채점을 요청했다.

    상한 도달의 출구는 추가 반복이 아니라 사용자 결정이다 — 최선의 시도를
    수락하거나 에스컬레이션한다 (ADR-0019 §6, upstream은 6회째 반복을 금지한다).
    """

    def __init__(self, *, mission_id: str, max_iterations: int) -> None:
        super().__init__(
            f"mission {mission_id}의 QA 예산이 소진됐다 "
            f"({max_iterations}회); 사용자 결정이 필요하다"
        )
        self.mission_id = mission_id
        self.max_iterations = max_iterations


class FinalEditAlreadyUsedError(MissionControlError):
    """상한 소진 뒤의 최종 수정을 두 번째로 하려 했다.

    upstream이 허용하는 것은 *"one final manual edit"* 하나다
    (``skills/seed/SKILL.md:113``). 둘째를 허용하면 채점 없는 revision을 쌓으며
    상한을 우회하게 된다 (ADR-0019 §6.1).
    """

    def __init__(self, *, mission_id: str, revision: int) -> None:
        super().__init__(
            f"mission {mission_id}의 revision {revision}이 이미 상한 소진 뒤의 "
            "최종 수정이다; 수정은 한 번뿐이며 지금은 승인하거나 에스컬레이션한다"
        )
        self.mission_id = mission_id
        self.revision = revision


class QaAlreadyPassedError(MissionControlError):
    """이미 통과 점수를 받은 revision을 다시 채점하려 했다.

    통과한 내용의 재채점은 명세를 좋게 만들지 않고 점수만 갱신한다. 낮아지면
    통과가 사라지고 높아져도 얻는 것이 없다 — 어느 쪽도 판정 기준을 흔드는
    것 외의 효과가 없다.
    """

    def __init__(self, *, mission_id: str, revision: int) -> None:
        super().__init__(
            f"mission {mission_id}의 Blueprint revision {revision}은 이미 QA를 통과했다"
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
            f"mission {mission_id}의 QA가 FAIL 판정으로 escalate됐다; 루프를 이어가지 않는다"
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
            f"mission {mission_id}의 Blueprint revision {revision}에 QA 평가가 없다; "
            "승인에는 QA 평가가 필요하다"
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
            f"mission {mission_id}의 Blueprint revision {revision}이 QA 임계값 미만이고 "
            "반복 예산도 남아 있다; 먼저 다듬는다"
        )
        self.mission_id = mission_id
        self.revision = revision


class EvolutionNotAllowedError(MissionControlError):
    """현재 Blueprint 상태가 successor generation을 열 수 없다."""


class EvolutionAlreadyCompletedError(MissionControlError):
    """같은 parent revision에서 successor를 다시 만들려 했다."""


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

    model_config = ConfigDict(frozen=True, extra="forbid")

    mission_id: str
    schema_version: Literal[1] = 1
    #: 쓰기 순서. 상태가 바뀌는 모든 경우에 올라간다. 저장소는 이 값으로
    #: 덮어쓰기를 판정한다 (ADR-0014와 같은 두 축 구분).
    sequence: int = 1
    #: revision 1부터의 전체 이력. 마지막 항목이 현재 revision이다.
    revisions: tuple[Blueprint, ...]
    #: 채점 기록. Mission 전체 chronological 이력이며 예산은 generation별로 계산한다.
    qa_records: tuple[BlueprintQaRecord, ...] = ()
    approval: BlueprintApproval | None = None
    #: Wonder→Reflect→Seed partial phase와 완료 lineage. 같은 JSON에 원자 저장한다.
    evolutions: tuple[EvolutionRecord, ...] = ()

    @model_validator(mode="after")
    def _revisions_are_contiguous(self) -> BlueprintState:
        """revision 번호가 1부터 빈틈없이 이어지는지 확인한다.

        번호에 빈틈이 있으면 승인·채점 기록이 가리키는 revision을 이력에서
        찾을 수 없게 되고, 그 순간 기록이 검증 불가능해진다.
        """
        if not self.revisions:
            raise ValueError("Blueprint 상태에는 revision이 최소 하나 있어야 한다")
        for index, item in enumerate(self.revisions):
            if item.revision != index + 1:
                raise ValueError(
                    f"Blueprint revision은 1부터 연속이어야 한다: "
                    f"{index}번 자리에 revision {item.revision}이 있다"
                )
            if item.mission_id != self.mission_id:
                raise ValueError(
                    f"revision {item.revision}은 mission {item.mission_id}의 것이다 — "
                    f"{self.mission_id}가 아니다"
                )
            if index == 0:
                if item.generation != 1 or item.evolved_from_revision is not None:
                    raise ValueError("첫 Blueprint revision은 generation 1이어야 한다")
                continue
            previous = self.revisions[index - 1]
            if item.generation == previous.generation:
                if item.evolved_from_revision != previous.evolved_from_revision:
                    raise ValueError(
                        "같은 generation의 revision은 evolve lineage를 이어받아야 한다"
                    )
            elif item.generation == previous.generation + 1:
                if item.evolved_from_revision != previous.revision:
                    raise ValueError("새 generation은 직전 parent revision을 가리켜야 한다")
            else:
                raise ValueError("Blueprint generation은 유지되거나 1씩만 증가할 수 있다")

        for qa_record in self.qa_records:
            if qa_record.revision < 1 or qa_record.revision > len(self.revisions):
                raise ValueError(f"QA record가 없는 revision {qa_record.revision}을 가리킨다")

        active_records = [
            item for item in self.evolutions if item.phase is not EvolutionPhase.COMPLETED
        ]
        if len(active_records) > 1:
            raise ValueError("동시에 진행 중인 EvolutionRecord는 하나만 허용한다")
        if active_records and self.evolutions[-1] is not active_records[0]:
            raise ValueError("진행 중인 EvolutionRecord 뒤에 다른 record를 붙일 수 없다")
        if active_records and active_records[0].parent_blueprint_revision != self.revision:
            raise ValueError("진행 중인 EvolutionRecord의 parent는 current revision이어야 한다")
        seen_parents: set[int] = set()
        for evolution_record in self.evolutions:
            if evolution_record.source.mission_id != self.mission_id:
                raise ValueError("EvolutionRecord가 다른 mission의 source를 가리킨다")
            parent_revision = evolution_record.parent_blueprint_revision
            if parent_revision < 1 or parent_revision > len(self.revisions):
                raise ValueError("EvolutionRecord parent revision이 Blueprint 이력에 없다")
            if parent_revision in seen_parents:
                raise ValueError("같은 parent revision의 EvolutionRecord가 둘 이상이다")
            seen_parents.add(parent_revision)
            parent = self.revisions[parent_revision - 1]
            if evolution_record.source.blueprint_generation != parent.generation:
                raise ValueError("EvolutionRecord source generation이 parent와 다르다")
            if evolution_record.phase is EvolutionPhase.COMPLETED:
                result_revision = evolution_record.result_blueprint_revision
                if result_revision is None or result_revision > len(self.revisions):
                    raise ValueError("완료 EvolutionRecord의 result revision이 이력에 없다")
                result = self.revisions[result_revision - 1]
                if (
                    result.generation != evolution_record.successor_generation
                    or result.evolved_from_revision != parent_revision
                ):
                    raise ValueError("EvolutionRecord와 successor Blueprint lineage가 다르다")
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
    def generation(self) -> int:
        return self.current.generation

    @property
    def has_current_approval(self) -> bool:
        """현재 revision에 유효한 승인이 있는가.

        승인 이후 revise가 있었다면 ``False``다. 승인 기록 자체는 남아 있되
        현재 내용에 대한 권한은 아니다.
        """
        return self.approval is not None and self.approval.revision == self.revision

    def loop(self, *, policy: QaPolicy) -> QaLoopState:
        """현재 generation의 채점 기록만 판정 기계에 얹는다."""
        records = self.records_for_generation(self.generation)
        return QaLoopState(
            policy=policy,
            attempts=tuple(
                QaAttempt(iteration=index + 1, assessment=item.assessment)
                for index, item in enumerate(records)
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
        return self.records_for_generation(self.generation)[best.iteration - 1]

    def records_for(self, revision: int) -> tuple[BlueprintQaRecord, ...]:
        return tuple(item for item in self.qa_records if item.revision == revision)

    def records_for_generation(self, generation: int) -> tuple[BlueprintQaRecord, ...]:
        revisions = {item.revision for item in self.revisions if item.generation == generation}
        return tuple(item for item in self.qa_records if item.revision in revisions)

    def ensure_qa_allowed(self, *, policy: QaPolicy) -> None:
        """채점이 허용되는 상태인지 확인한다. 아니면 예외를 올린다.

        허용 규칙은 ADR-0021 §4다 — FAIL 뒤에는 계속하지 않고, 이미 통과한
        revision을 다시 채점하지 않으며, 상한을 넘겨 한 번 더 돌지 않는다.
        통과 후 revise된 새 revision은 잔여 상한 안에서 채점할 수 있다.

        :meth:`record_qa`와 분리되어 있는 이유는 채점이 위임 호출이기 때문이다.
        기록 시점에만 검사하면 규칙상 일어나지 말았어야 할 채점(예: 6회째)이
        이미 수행된 뒤에 거부된다 — 호출자는 위임 전에 이것을 먼저 묻는다.
        """
        generation_records = self.records_for_generation(self.generation)
        if generation_records:
            latest_verdict = policy.verdict_for(generation_records[-1].assessment.score)
            if latest_verdict is QaVerdict.FAIL:
                raise QaEscalatedError(mission_id=self.mission_id)
        for item in self.records_for(self.revision):
            if policy.verdict_for(item.assessment.score) is QaVerdict.PASS:
                raise QaAlreadyPassedError(mission_id=self.mission_id, revision=self.revision)
        if len(generation_records) >= policy.max_iterations:
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

    def final_edit_carry(self, *, policy: QaPolicy) -> BlueprintQaRecord | None:
        """이 revision이 **상한 소진 뒤의 최종 수정 1회**라면 물려받을 채점.

        upstream ``skills/seed/SKILL.md:113``이 정하는 경로다 — 소진 뒤 사용자가
        최종 수정 하나를 고르면 그것을 적용하고 **재채점 없이** 임계 미달 수락을
        받는다 (*"do not start a sixth QA iteration, rerun QA"*).

        우리는 상한을 skill이 아니라 코드로 강제했으므로(ADR-0019 §1, Constitution
        §6.5) 그 문장의 나머지 절반도 코드가 들고 있어야 한다. 들고 있지 않으면
        소진 뒤 명세를 고치는 순간 미션이 잠긴다 (도그푸딩 0005 §4).
        """
        if self.records_for(self.revision):
            return None
        generation_records = self.records_for_generation(self.generation)
        if len(generation_records) < policy.max_iterations:
            return None
        if not generation_records:
            return None
        carried = max(generation_records, key=lambda item: item.assessment.score)
        if policy.verdict_for(carried.assessment.score) is not QaVerdict.REVISE:
            # PASS는 그 revision을 승인하면 되고 FAIL은 에스컬레이션이다.
            # 최종 수정 경로는 `EXHAUSTED`(재작업 점수 + 상한 도달) 하나를 위한 것이다.
            return None
        return carried

    def revise(self, *, blueprint: Blueprint, policy: QaPolicy | None = None) -> BlueprintState:
        """수정된 내용을 새 revision으로 붙인다. 이전 revision은 바뀌지 않는다.

        기존 승인이 있어도 막지 않는다 — 승인은 이전 revision에 묶인 채 stale이
        되고, Gate가 그것을 ``HOLD`` 사유로 드러낸다 (ADR-0002: 변경은 수정이
        아니라 새 revision + 재승인이다).

        ``policy``가 주어지면 **최종 수정은 한 번뿐**이라는 상한을 강제한다
        (ADR-0019 §6.1 — upstream *"one final manual edit"*). 두 번째를 허용하면
        채점 없는 revision을 무한히 쌓으며 상한을 우회하게 된다.
        """
        if self.active_evolution is not None:
            raise EvolutionNotAllowedError("Evolve 진행 중에는 parent Blueprint를 revise할 수 없다")
        if policy is not None and self.final_edit_carry(policy=policy) is not None:
            raise FinalEditAlreadyUsedError(mission_id=self.mission_id, revision=self.revision)
        if blueprint.mission_id != self.mission_id:
            raise ValueError(
                f"이 revision은 mission {blueprint.mission_id}의 것이다 — "
                f"{self.mission_id}가 아니다"
            )
        if blueprint.revision != self.revision + 1:
            raise ValueError(
                f"revision {self.revision + 1}이 와야 하는데 {blueprint.revision}이 왔다"
            )
        if blueprint.generation != self.generation:
            raise ValueError("수동 revise는 Blueprint generation을 바꿀 수 없다")
        if blueprint.evolved_from_revision != self.current.evolved_from_revision:
            raise ValueError("수동 revise는 evolve lineage를 바꿀 수 없다")
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
        scored_revision: int | None = None
        if not scores:
            # 상한 소진 뒤의 최종 수정이면 직전 채점을 물려받는다 (ADR-0019 §6.1).
            # 그 밖에는 채점 없는 승인이며 거부한다.
            carried = self.final_edit_carry(policy=policy)
            if carried is None:
                raise UnassessedRevisionError(mission_id=self.mission_id, revision=self.revision)
            scores = (carried.assessment.score,)
            scored_revision = carried.revision

        best_score = max(scores)
        verdict = policy.verdict_for(best_score)
        if verdict is QaVerdict.FAIL:
            raise QaEscalatedError(mission_id=self.mission_id)
        generation_records = self.records_for_generation(self.generation)
        if verdict is QaVerdict.REVISE and len(generation_records) < policy.max_iterations:
            raise QaLoopStillOpenError(mission_id=self.mission_id, revision=self.revision)

        approval = BlueprintApproval(
            revision=self.revision,
            statement=statement,
            qa_policy_version=policy.version,
            qa_threshold=policy.pass_threshold,
            qa_best_score=best_score,
            qa_iterations=len(generation_records),
            accepted_below_threshold=accept_below_threshold,
            qa_scored_revision=scored_revision,
        )
        return self.model_copy(update={"sequence": self.sequence + 1, "approval": approval})

    @property
    def active_evolution(self) -> EvolutionRecord | None:
        if self.evolutions and self.evolutions[-1].phase is not EvolutionPhase.COMPLETED:
            return self.evolutions[-1]
        return None

    def begin_evolution(self, *, source: EvolveSourceSnapshot) -> BlueprintState:
        """승인된 current revision에서 successor checkpoint를 연다."""

        if not self.has_current_approval:
            raise EvolutionNotAllowedError("Evolve에는 승인된 current Blueprint가 필요하다")
        if self.active_evolution is not None:
            raise EvolutionNotAllowedError("이미 진행 중인 Evolve checkpoint가 있다")
        if any(item.parent_blueprint_revision == self.revision for item in self.evolutions):
            raise EvolutionAlreadyCompletedError(
                f"Blueprint revision {self.revision}의 successor가 이미 기록됐다"
            )
        if (
            source.mission_id != self.mission_id
            or source.blueprint_revision != self.revision
            or source.blueprint_generation != self.generation
        ):
            raise EvolutionNotAllowedError("Evolve source가 current Blueprint와 일치하지 않는다")
        if {item.ac_key for item in source.criteria} != set(self.current.criterion_keys):
            raise EvolutionNotAllowedError("Evolve source가 current AC outcome 전부를 갖지 않는다")

        record = EvolutionRecord.start(source=source)
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "evolutions": (*self.evolutions, record),
            }
        )

    def record_wonder(self, *, output: WonderOutput) -> BlueprintState:
        record = self.active_evolution
        if record is None:
            raise EvolutionNotAllowedError("Wonder output을 기록할 Evolve checkpoint가 없다")
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "evolutions": (*self.evolutions[:-1], record.record_wonder(output)),
            }
        )

    def record_reflect(self, *, output: ReflectOutput) -> BlueprintState:
        record = self.active_evolution
        if record is None:
            raise EvolutionNotAllowedError("Reflect output을 기록할 Evolve checkpoint가 없다")
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "evolutions": (*self.evolutions[:-1], record.record_reflect(output)),
            }
        )

    def hold_evolution_for_scope(
        self, *, findings: tuple[ScopeChangeFinding, ...]
    ) -> BlueprintState:
        record = self.active_evolution
        if record is None:
            raise EvolutionNotAllowedError("scope finding을 기록할 Evolve checkpoint가 없다")
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "evolutions": (*self.evolutions[:-1], record.hold_for_scope(findings)),
            }
        )

    def complete_evolution(self, *, blueprint: Blueprint) -> BlueprintState:
        """successor revision과 completed record를 한 state 변경으로 묶는다."""

        record = self.active_evolution
        if record is None or record.phase is not EvolutionPhase.SEEDING:
            raise EvolutionNotAllowedError("완료할 seeding checkpoint가 없다")
        if blueprint.mission_id != self.mission_id or blueprint.revision != self.revision + 1:
            raise EvolutionNotAllowedError("successor Blueprint identity가 현재 상태와 다르다")
        if (
            blueprint.generation != record.successor_generation
            or blueprint.evolved_from_revision != record.parent_blueprint_revision
        ):
            raise EvolutionNotAllowedError("successor Blueprint generation lineage가 다르다")

        completed = record.complete(result_blueprint_revision=blueprint.revision)
        return self.model_copy(
            update={
                "sequence": self.sequence + 1,
                "revisions": (*self.revisions, blueprint),
                "evolutions": (*self.evolutions[:-1], completed),
            }
        )
