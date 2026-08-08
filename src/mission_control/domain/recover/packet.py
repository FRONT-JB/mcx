"""실패 packet — "다시 해라"가 아니라 구조화된 실패.

packet은 이미 저장된 기록(Execute attempt, VerificationRun, verdict)에서
**결정적으로 파생**된다 — 새 관찰이나 추론을 만들지 않는다. 파생이므로
저장하지 않는다: 원본 기록이 이미 durable하고, 파생본을 따로 저장하면 두
진실이 생긴다.

분류는 결정적으로 인식 가능한 둘뿐이다 (ADR-0031 §3) — ``BLOCKED``(권한·
도구·환경의 hard precondition, upstream 패턴 채택)와 ``STALL``(동일 오류
해시의 반복). 매길 수 없는 분류를 흉내 내지 않는다.

계약: ``docs/09_RECOVER.md`` §4, §6, §8
결정: ``docs/adr/0031-recover-v1-failure-and-retry-contract.md``
"""

from __future__ import annotations

from enum import StrEnum
import hashlib
import re

from pydantic import BaseModel, ConfigDict, Field

from mission_control.domain.blueprint.spec import Blueprint
from mission_control.domain.execute.state import AttemptStatus, ExecuteState
from mission_control.domain.verify.evidence import VerificationRun, VerifyState
from mission_control.domain.verify.verdict import SemanticPolicy

#: hard precondition 인식 패턴 — upstream `_HARD_PRECONDITION_PATTERNS` 채택
#: (REPAIR_UPSTREAM_FINDINGS §1).
_BLOCKED_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\b(?:permission|access) denied\b",
        r"\b(?:unauthorized|forbidden|authentication required)\b",
        r"\bmissing (?:required )?(?:tool|access|authority|credential|credentials|"
        r"configuration|config|environment variable|env var)\b",
        r"\b(?:tool|access|authority|credential|credentials|configuration|config|"
        r"environment variable|env var) (?:is |are )?(?:required|unavailable|"
        r"not available|not configured)\b",
    )
)


class FailureSource(StrEnum):
    """실패가 관측된 층 (ADR-0031 §2)."""

    EXECUTION_FAILED = "execution_failed"
    MECHANICAL_FAILED = "mechanical_failed"
    SEMANTIC_NOT_SATISFIED = "semantic_not_satisfied"
    ESCALATION_PENDING = "escalation_pending"


class FailureClassification(StrEnum):
    """결정적으로 인식 가능한 분류 (ADR-0031 §3).

    upstream의 세밀한 분류(FABRICATION_SUSPECTED 등)는 verifier 증거 계약
    위의 것이라 v1 대응물이 없다 — ADR-0032 보류.
    """

    BLOCKED = "blocked"
    STALL = "stall"
    UNCLASSIFIED = "unclassified"


class RecoverPolicy(BaseModel):
    """Recover의 versioned 한계값 — 전부 upstream 채택 (ADR-0031 §3~§4)."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1)
    #: AC당 교정 재시도 상한 — upstream `ac_retry_attempts` 기본값.
    retry_budget: int = Field(ge=1)
    #: 동일 오류 해시가 이 횟수 반복되면 재시도는 무의미하다 — SPINNING 임계.
    stall_threshold: int = Field(ge=2)
    #: 재시도에 실어 보내는 오류 발췌 한도 — upstream retry prompt와 동일.
    error_excerpt_chars: int = Field(ge=1)

    @classmethod
    def recover_v1(cls) -> RecoverPolicy:
        return cls(
            version="recover-v1",
            retry_budget=2,
            stall_threshold=3,
            error_excerpt_chars=500,
        )


class PreviousFailure(BaseModel):
    """교정 재시도가 가지고 가는 실패 증거 (ADR-0031 §5).

    upstream 재시도 프롬프트의 세 요소와 정렬한다 — 분류, 오류 tail, 그리고
    마지막 시도에만 붙는 접근 전환 지시(``change_approach``).
    """

    model_config = ConfigDict(frozen=True)

    source: FailureSource
    classification: FailureClassification
    error_excerpt: str
    #: 마지막 예산의 시도인가 — "같은 접근을 반복하지 말라"의 신호.
    change_approach: bool = False


class FailurePacket(BaseModel):
    """AC 하나의 실패에 대한 구조화된 기술 (ADR-0031 §1)."""

    model_config = ConfigDict(frozen=True)

    mission_id: str = Field(min_length=1)
    blueprint_revision: int = Field(ge=1)
    ac_key: str = Field(min_length=1)
    source: FailureSource
    classification: FailureClassification
    error_excerpt: str = ""
    evidence_refs: tuple[str, ...] = ()
    #: 이 AC에서 이미 소진된 교정 재시도 수 (첫 실행 제외).
    retries_used: int = Field(ge=0)

    def budget_exhausted(self, policy: RecoverPolicy) -> bool:
        return self.retries_used >= policy.retry_budget

    def retryable(self, policy: RecoverPolicy) -> bool:
        """교정 재시도가 의미 있는가.

        BLOCKED는 재시도가 아니라 사용자 결정이고(권한을 우회하지 않는다),
        STALL은 같은 재시도의 반복이 무의미하다는 판정 그 자체다.
        escalation 대기는 실패가 아니라 판정 불확실 — 사용자 결정이다.
        """
        return (
            self.classification is FailureClassification.UNCLASSIFIED
            and self.source is not FailureSource.ESCALATION_PENDING
            and not self.budget_exhausted(policy)
        )


def _classify(error_texts: tuple[str, ...], policy: RecoverPolicy) -> FailureClassification:
    """오류 이력에서 BLOCKED·STALL을 결정적으로 인식한다."""
    latest = error_texts[-1] if error_texts else ""
    lowered = latest.lower()
    if any(pattern.search(lowered) for pattern in _BLOCKED_PATTERNS):
        return FailureClassification.BLOCKED
    if len(error_texts) >= policy.stall_threshold:
        recent = error_texts[-policy.stall_threshold :]
        digests = {hashlib.sha256(text.encode("utf-8")).hexdigest() for text in recent}
        if len(digests) == 1:
            return FailureClassification.STALL
    return FailureClassification.UNCLASSIFIED


def _mechanical_excerpt(run: VerificationRun) -> str:
    if run.missing_artifacts:
        return "expected artifacts missing: " + ", ".join(run.missing_artifacts)
    if run.timed_out:
        return "verify command timed out"
    if run.exit_code not in (0, None):
        return f"verify command exited with status {run.exit_code}: {run.output_tail}"
    return f"output assertion not found in verify command output: {run.output_tail}"


def derive_failure_packets(
    *,
    blueprint: Blueprint,
    execute_state: ExecuteState,
    verify_state: VerifyState,
    semantic_policy: SemanticPolicy,
    policy: RecoverPolicy,
) -> tuple[FailurePacket, ...]:
    """저장된 기록에서 현재 revision의 실패 packet들을 파생한다.

    교정이 이미 재실행되어 아직 재검증되지 않은 AC — 최신 실행 attempt가
    evidence의 ``execution_attempt_numbers`` 밖에 있는 경우 — 는 실패가
    아니라 "재검증 대기"이므로 packet을 만들지 않는다. 그 처분은 Recover
    Gate의 ``CLEAR — Clear for Verify``다.
    """
    revision = blueprint.revision
    evidence = (
        verify_state.evidence
        if verify_state.evidence is not None
        and verify_state.evidence.blueprint_revision == revision
        else None
    )
    verdicts = (
        verify_state.verdicts
        if verify_state.verdicts is not None
        and verify_state.verdicts.blueprint_revision == revision
        else None
    )

    packets: list[FailurePacket] = []
    for criterion in blueprint.acceptance_criteria:
        attempts = tuple(
            attempt
            for attempt in execute_state.attempts
            if attempt.ac_key == criterion.key and attempt.blueprint_revision == revision
        )
        if not attempts:
            continue  # 미실행 — Execute의 일이지 Recover의 실패가 아니다.
        retries_used = len(attempts) - 1
        latest = attempts[-1]

        if latest.status is AttemptStatus.EXECUTION_FAILED:
            errors = tuple(
                attempt.error or ""
                for attempt in attempts
                if attempt.status is AttemptStatus.EXECUTION_FAILED
            )
            packets.append(
                FailurePacket(
                    mission_id=execute_state.mission_id,
                    blueprint_revision=revision,
                    ac_key=criterion.key,
                    source=FailureSource.EXECUTION_FAILED,
                    classification=_classify(errors, policy),
                    error_excerpt=(latest.error or "")[-policy.error_excerpt_chars :],
                    evidence_refs=(latest.execution_id,),
                    retries_used=retries_used,
                )
            )
            continue

        if latest.status is not AttemptStatus.EXECUTED_UNVERIFIED:
            continue  # DISPATCHED — 결과 불명은 Execute Gate의 blocker다.

        verified_numbers = evidence.execution_attempt_numbers if evidence else ()
        if latest.number not in verified_numbers:
            continue  # 교정 재실행됨 — 재검증 대기이지 실패가 아니다.

        run = evidence.run_for(criterion.key) if evidence else None
        if run is not None and not run.passed:
            packets.append(
                FailurePacket(
                    mission_id=execute_state.mission_id,
                    blueprint_revision=revision,
                    ac_key=criterion.key,
                    source=FailureSource.MECHANICAL_FAILED,
                    classification=_classify((_mechanical_excerpt(run),), policy),
                    error_excerpt=_mechanical_excerpt(run)[-policy.error_excerpt_chars :],
                    evidence_refs=tuple(ref for ref in (run.output_ref,) if ref),
                    retries_used=retries_used,
                )
            )
            continue

        verdict = verdicts.verdict_for(criterion.key) if verdicts else None
        if verdict is None:
            continue  # 판정 전 — Verify의 일이다.
        if verdict.uncertainty > semantic_policy.uncertainty_threshold:
            packets.append(
                FailurePacket(
                    mission_id=execute_state.mission_id,
                    blueprint_revision=revision,
                    ac_key=criterion.key,
                    source=FailureSource.ESCALATION_PENDING,
                    classification=FailureClassification.UNCLASSIFIED,
                    error_excerpt=verdict.reasoning[-policy.error_excerpt_chars :],
                    retries_used=retries_used,
                )
            )
        elif not verdict.passes(semantic_policy):
            packets.append(
                FailurePacket(
                    mission_id=execute_state.mission_id,
                    blueprint_revision=revision,
                    ac_key=criterion.key,
                    source=FailureSource.SEMANTIC_NOT_SATISFIED,
                    classification=FailureClassification.UNCLASSIFIED,
                    error_excerpt=verdict.reasoning[-policy.error_excerpt_chars :],
                    retries_used=retries_used,
                )
            )
    return tuple(packets)
