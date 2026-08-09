"""Verify의 mechanical 증거 — 명령을 직접 실행해서 얻은 기록.

Flight Controller의 "완료했습니다"는 여기 등장하지 않는다. 증거는 Verify가
직접 실행한 명령의 exit code와 출력뿐이다 — upstream의 배치("not the worker,
so a failing check cannot be self-reported away")와 같다
(``docs/research/VERIFY_UPSTREAM_FINDINGS.md`` §1).

원문 출력은 상태 문서에 담지 않는다. 파일로 보존하고 참조(``output_ref``)와
판정용 발췌(``output_tail``)만 남긴다 (ADR-0027 §1, ADR-0028 §4).

계약: ``docs/08_VERIFY.md`` §5.1, §7
결정: ``docs/adr/0028-verify-v1-mechanical-contract.md``
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mission_control.domain.blueprint.spec import AcceptanceCriterion
from mission_control.domain.errors import MissionControlError
from mission_control.domain.verify.verdict import SemanticAssessment
from mission_control.security import redact_credentials

#: 판정용 발췌 길이. upstream `_VERIFY_OUTPUT_TAIL_CHARS`와 같다
#: (VERIFY_UPSTREAM_FINDINGS §2).
OUTPUT_TAIL_CHARS = 2_000

#: verify_command 하나의 실행 제한. upstream 기본값 채택 (ADR-0028 §3).
VERIFY_COMMAND_TIMEOUT_SECONDS = 600


class VerdictWithoutEvidenceError(MissionControlError):
    """같은 revision의 mechanical 증거 없이 semantic 판정을 기록하려 했다.

    verdict는 검증된 증거에 바인딩된다 (ADR-0030 §4). 증거 없는 판정을
    받아들이면 semantic이 mechanical을 대체하는 문이 열린다.
    """

    def __init__(self, *, mission_id: str, assessed_revision: int) -> None:
        super().__init__(
            f"mission {mission_id} has no mechanical evidence for blueprint "
            f"revision {assessed_revision}; semantic verdicts need that evidence first"
        )
        self.mission_id = mission_id
        self.assessed_revision = assessed_revision


class UnverifiableCriterionError(MissionControlError):
    """성공 계약이 없는 AC에 대해 mechanical 판정을 만들려 했다.

    판정 불가는 run이 없는 상태로 표현된다 — 통과도 실패도 아닌 run을
    만들면 집계 어딘가에서 반드시 한쪽으로 세어진다 (ADR-0028 §3).
    """

    def __init__(self, *, ac_key: str) -> None:
        super().__init__(
            f"criterion {ac_key} has no success contract; it cannot produce "
            "a mechanical verification run"
        )
        self.ac_key = ac_key


class CommandExecution(BaseModel):
    """runner가 돌려주는 명령 실행의 원시 결과."""

    model_config = ConfigDict(frozen=True)

    exit_code: int | None = None
    timed_out: bool = False
    output: str = ""

    @model_validator(mode="after")
    def _timeout_has_no_exit_code(self) -> CommandExecution:
        if self.timed_out and self.exit_code is not None:
            raise ValueError("a timed out execution cannot carry an exit code")
        if not self.timed_out and self.exit_code is None:
            raise ValueError("a completed execution requires an exit code")
        return self


class VerificationRun(BaseModel):
    """AC 하나에 대한 mechanical 검증 한 번 (ADR-0028 §4).

    ``command``는 **실행한** 명령이다 — artifacts 누락으로 명령까지 가지
    않았으면 ``None``이고, 그 사실 자체가 기록이다.
    """

    model_config = ConfigDict(frozen=True)

    ac_key: str = Field(min_length=1)
    command: str | None = None
    exit_code: int | None = None
    passed: bool
    timed_out: bool = False
    missing_artifacts: tuple[str, ...] = ()
    output_ref: str | None = None
    output_tail: str = ""

    @field_validator("output_tail", "command", mode="after")
    @classmethod
    def _mask_credentials(cls, value: str | None) -> str | None:
        """자격증명은 생성 시점에 가린다 — 부르는 곳이 아니라 경계에서 (ADR-0040 §3).

        경로는 남긴다. 이 발췌는 Recover를 거쳐 worker에게 전달되며, 어느
        파일이 실패했는지 모르는 worker는 같은 실패를 반복한다.
        """
        return value if value is None else redact_credentials(value)

    @model_validator(mode="after")
    def _the_fields_tell_one_story(self) -> VerificationRun:
        """서로 모순되는 기록을 생성 시점에 거부한다.

        통과했는데 누락 artifacts가 있거나 exit code가 0이 아니면, 어느 쪽이
        진실인지 판정할 수 없는 증거가 된다.
        """
        if self.missing_artifacts and self.command is not None:
            raise ValueError("missing artifacts preclude command execution")
        if self.command is None:
            if self.exit_code is not None or self.timed_out or self.output_tail:
                raise ValueError("an unexecuted command cannot carry execution results")
        else:
            if self.timed_out and self.exit_code is not None:
                raise ValueError("a timed out run cannot carry an exit code")
            if not self.timed_out and self.exit_code is None:
                raise ValueError("a completed run requires an exit code")
        if self.passed:
            if self.missing_artifacts:
                raise ValueError("a passed run cannot have missing artifacts")
            if self.timed_out:
                raise ValueError("a passed run cannot have timed out")
            if self.command is not None and self.exit_code != 0:
                raise ValueError("a passed run requires exit code 0")
        return self


def judge_run(
    *,
    criterion: AcceptanceCriterion,
    missing_artifacts: tuple[str, ...],
    execution: CommandExecution | None,
    output_ref: str | None,
) -> VerificationRun:
    """검사 결과를 하나의 run으로 판정한다 (ADR-0028 §3의 순서).

    artifacts 누락이 있으면 명령은 실행되지 않았어야 하고(``execution=None``),
    통과는 exit code 0에 더해 ``output_assertion``이 합류 출력에 존재할 것을
    요구한다.
    """
    if not criterion.is_mechanically_verifiable:
        raise UnverifiableCriterionError(ac_key=criterion.key)

    if missing_artifacts:
        return VerificationRun(
            ac_key=criterion.key,
            passed=False,
            missing_artifacts=missing_artifacts,
        )

    if criterion.verify_command is None:
        # artifacts만으로 완결되는 계약 — 전부 존재했으므로 통과다.
        return VerificationRun(ac_key=criterion.key, passed=True)

    if execution is None:
        raise ValueError(
            f"criterion {criterion.key} has a verify command but no execution was supplied"
        )

    asserted = criterion.output_assertion
    passed = (
        not execution.timed_out
        and execution.exit_code == 0
        and (asserted is None or asserted in execution.output)
    )
    return VerificationRun(
        ac_key=criterion.key,
        command=criterion.verify_command,
        exit_code=execution.exit_code,
        passed=passed,
        timed_out=execution.timed_out,
        output_ref=output_ref,
        output_tail=execution.output[-OUTPUT_TAIL_CHARS:],
    )


class VerificationEvidence(BaseModel):
    """mission 하나의 mechanical 검증 묶음 (ADR-0028 §4).

    ``blueprint_revision``과 ``execution_attempt_numbers``가 lineage다 — 어느
    계약을, 어느 실행 위에서 검증했는가 (ADR-0026).
    """

    model_config = ConfigDict(frozen=True)

    mission_id: str = Field(min_length=1)
    blueprint_revision: int = Field(ge=1)
    execution_attempt_numbers: tuple[int, ...] = Field(min_length=1)
    runs: tuple[VerificationRun, ...] = ()

    @model_validator(mode="after")
    def _one_run_per_criterion(self) -> VerificationEvidence:
        keys = [run.ac_key for run in self.runs]
        if len(keys) != len(set(keys)):
            raise ValueError("evidence carries more than one run for the same criterion")
        return self

    def run_for(self, ac_key: str) -> VerificationRun | None:
        for run in self.runs:
            if run.ac_key == ac_key:
                return run
        return None


class VerifyState(BaseModel):
    """하나의 Mission에 대한 Verify durable 상태.

    v1은 최신 evidence·verdicts 하나씩만 유지한다. 재검증 이력의 보존은 실패
    packet을 설계하는 Recover와 함께 결정한다 (progress README 알려진 한계).
    """

    model_config = ConfigDict(frozen=True)

    mission_id: str
    #: 쓰기 순서. 저장소는 이 값으로 덮어쓰기를 판정한다 (ADR-0014와 같은 축).
    sequence: int = 1
    evidence: VerificationEvidence | None = None
    verdicts: SemanticAssessment | None = None

    @classmethod
    def start(cls, *, mission_id: str) -> VerifyState:
        return cls(mission_id=mission_id)

    def record(self, evidence: VerificationEvidence) -> VerifyState:
        """새 검증 묶음으로 교체한다. 이전 evidence는 유지하지 않는다.

        기존 semantic verdicts도 함께 무효가 된다 — verdict는 판정 당시의
        증거 위에서 내려진 것이고, 재검증은 그 증거를 교체하기 때문이다
        (ADR-0030 §4의 바인딩).
        """
        if evidence.mission_id != self.mission_id:
            raise ValueError(
                f"evidence for mission {evidence.mission_id} cannot be recorded "
                f"on mission {self.mission_id}"
            )
        return self.model_copy(
            update={"sequence": self.sequence + 1, "evidence": evidence, "verdicts": None}
        )

    def record_verdicts(self, assessment: SemanticAssessment) -> VerifyState:
        """semantic 판정 묶음을 기록한다.

        판정은 mechanical 증거 위에서만 내려진다 — 같은 blueprint revision의
        evidence가 없으면 verdict가 딛고 설 근거가 없다 (ADR-0030 §3~§4).
        """
        if (
            self.evidence is None
            or self.evidence.blueprint_revision != assessment.blueprint_revision
        ):
            raise VerdictWithoutEvidenceError(
                mission_id=self.mission_id,
                assessed_revision=assessment.blueprint_revision,
            )
        return self.model_copy(update={"sequence": self.sequence + 1, "verdicts": assessment})
