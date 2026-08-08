"""Blueprint(Seed) — 승인되면 불변인 실행 명세.

Brief가 "무엇을 원하는가"를 정리했다면 Blueprint는 "무엇을 만들었다고 인정할
것인가"를 고정한다. 승인된 Blueprint revision은 실행 중 바뀌지 않는다
(``docs/adr/0002-approved-seed-is-immutable.md``).

이 모듈의 핵심 결정은 **acceptance criterion의 identity**다. AC를 목록의 몇 번째
항목이 아니라 **성공 계약의 내용**으로 식별한다. 순서로 식별하면 중간에 AC를
하나 끼워 넣는 순간 이후 AC들이 다른 계약의 증거를 물려받는다. Execute가 만든
결과와 Verify가 모은 증거는 "3번 AC"가 아니라 "이 계약"에 붙어야 한다.

identity 계산에서 목록 위치와 실행 세션 정보는 의도적으로 제외한다. 따라서
같은 계약은 재시도와 revision을 건너 같은 key를 유지하고, 계약이 바뀐 AC는
새 key를 받는다.

계약: ``docs/06_BLUEPRINT.md``
결정: ``docs/adr/0017-blueprint-schema-baseline.md``
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class AcceptanceCriterion(BaseModel):
    """하나의 수용 기준과 그것을 확인하는 방법.

    ``description``만으로는 Verify가 판정할 수 없다. "댓글이 잘 보인다"는 사람
    사이에서는 통하지만 무엇을 관찰해야 하는지 말하지 않는다. 나머지 세 필드가
    **성공 계약** — 무엇을 실행하고 무엇이 남아야 하며 결과에서 무엇을 확인하는지
    — 을 담는다.

    세 필드는 모두 선택이다. 기계적으로 확인할 수 없는 AC도 존재하며, 그것을
    금지하는 대신 **확인 수단이 없다는 사실이 드러나게** 한다. Blueprint Gate가
    검증 불가능한 AC를 어떻게 다룰지는 Blueprint Stage의 QA 정책이 정한다.
    """

    model_config = ConfigDict(frozen=True)

    description: str = Field(min_length=1)
    #: 확인을 위해 실행할 명령. Execute가 아니라 Verify가 실행한다.
    verify_command: str | None = None
    #: 실행 후 존재해야 하는 산출물 경로.
    expected_artifacts: tuple[str, ...] = ()
    #: 명령 출력에서 확인할 조건. 확인할 출력이 있으려면 명령이 있어야 한다.
    output_assertion: str | None = None

    @model_validator(mode="after")
    def _output_assertion_needs_a_command(self) -> AcceptanceCriterion:
        """출력 조건만 있고 실행할 명령이 없는 계약을 거부한다.

        검사할 출력을 만드는 것이 ``verify_command``이므로, 명령 없는
        ``output_assertion``은 무엇과도 대조되지 않는다. 검증 수단이 있는 것처럼
        보이지만 실제로는 아무것도 확인하지 않는 AC가 되며, 이는 확인 수단이
        아예 없는 AC보다 나쁘다 — 없다는 사실이 드러나지 않기 때문이다.
        """
        if self.output_assertion and not self.verify_command:
            raise ValueError("output_assertion requires verify_command")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def key(self) -> str:
        """성공 계약의 내용으로 계산한 안정적 identity.

        목록 위치, revision, 실행 세션을 포함하지 않는다. 계약이 같으면 어디에
        있든 같은 key이며, 계약이 바뀌면 다른 AC다.
        """
        payload = {
            "description": self.description,
            "verify_command": self.verify_command,
            "expected_artifacts": list(self.expected_artifacts),
            "output_assertion": self.output_assertion,
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return f"ac_{hashlib.sha256(encoded).hexdigest()[:16]}"

    @property
    def is_mechanically_verifiable(self) -> bool:
        """확인 수단이 하나라도 있는가.

        Verify가 사람의 판단 없이 확인할 수 있는지를 나타낸다. 거짓이라고 해서
        잘못된 AC는 아니지만, 그런 AC만으로 미션이 구성되면 완료를 증거로
        선언할 수 없다.
        """
        return bool(self.verify_command or self.expected_artifacts or self.output_assertion)


class Blueprint(BaseModel):
    """승인 대상이 되는 실행 명세 하나.

    Goal, Constraints, Non-goals, 수용 기준이 **방향(direction)** 이며 승인 이후
    불변이다. 방향이 바뀌면 수정이 아니라 새 revision이고 재승인이 필요하다
    (``docs/adr/0002-approved-seed-is-immutable.md``).

    선언되지 않은 필드를 허용하지 않는다. 승인의 의미는 "사용자가 이 내용을
    보았다"인데, 검토 경로를 거치지 않은 내용이 불변 산출물에 실릴 수 있으면
    그 의미가 성립하지 않는다.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mission_id: str
    #: Blueprint의 내용 버전. Brief revision과 별개이며, 어느 Brief에서 나왔는지는
    #: ``brief_revision``이 가리킨다.
    revision: int = 1
    #: 이 Blueprint를 만들어 낸 Brief revision. 승인 lineage를 잇는다.
    brief_revision: int

    goal: str = Field(min_length=1)
    constraints: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = ()

    @model_validator(mode="after")
    def _criterion_keys_are_unique(self) -> Blueprint:
        """같은 성공 계약이 두 번 실리는 것을 거부한다 (``docs/06_BLUEPRINT.md`` §7.2).

        key가 내용 digest이므로 중복 key는 중복 계약이다. 허용하면 Execute의
        결과와 Verify의 증거가 두 항목 중 어느 쪽에 붙는지 판정할 수 없고,
        ``criterion_for``가 조용히 첫 번째만 돌려준다.
        """
        seen: set[str] = set()
        for item in self.acceptance_criteria:
            if item.key in seen:
                raise ValueError(
                    f"duplicate acceptance criterion contract: {item.description!r}"
                )
            seen.add(item.key)
        return self

    @property
    def criterion_keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.acceptance_criteria)

    def criterion_for(self, key: str) -> AcceptanceCriterion | None:
        for item in self.acceptance_criteria:
            if item.key == key:
                return item
        return None

    @property
    def unverifiable_criteria(self) -> tuple[AcceptanceCriterion, ...]:
        """기계적 확인 수단이 없는 수용 기준."""
        return tuple(
            item for item in self.acceptance_criteria if not item.is_mechanically_verifiable
        )


class BlueprintApproval(BaseModel):
    """사용자가 특정 Blueprint revision으로 Execute 진행을 승인한 기록.

    **QA 결과를 Blueprint가 아니라 여기에 담는다.** Blueprint는 방향이고 승인
    이후 불변이다 (``docs/adr/0002-approved-seed-is-immutable.md``). 점수를
    Blueprint에 넣으면 채점 결과를 적는 것만으로 revision이 올라가고 재승인이
    필요해진다 — 방향은 하나도 바뀌지 않았는데.

    ``accepted_below_threshold``가 이 기록의 핵심이다. 이것이 남지 않으면
    나중에 "이 명세가 기준을 통과한 것인가, 사용자가 미달을 수락한 것인가"를
    물을 방법이 없다. 미달 명세에서 출발한 미션이 ``MISSION COMPLETE``에
    도달했을 때 그 사실이 어디에도 없으면 완료 선언의 근거가 비어 있다
    (``docs/adr/0005-evidence-over-reasoning.md``).

    결정: ``docs/adr/0019-blueprint-qa-loop.md`` §8
    """

    model_config = ConfigDict(frozen=True)

    #: 승인 대상 Blueprint revision. 오래된 revision에 대한 승인을 최신
    #: revision에 재사용하지 않는다.
    revision: int
    statement: str

    #: 채점에 쓰인 정책. 점수의 절대값은 정책과 채점자 구현에 의존하므로,
    #: 버전 없이 남은 점수는 나중에 해석할 수 없다.
    qa_policy_version: str
    qa_threshold: float = Field(ge=0.0, le=1.0)
    qa_best_score: float = Field(ge=0.0, le=1.0)
    qa_iterations: int = Field(ge=1)
    accepted_below_threshold: bool = False

    @model_validator(mode="after")
    def _acceptance_matches_the_score(self) -> BlueprintApproval:
        """미달 수락 표시가 실제 점수와 어긋나지 않는지 확인한다.

        이 검사가 없으면 통과하지 못한 명세가 통과한 것으로 기록될 수 있고,
        그 기록이 이후 모든 Gate 판단의 전제가 된다.
        """
        below = self.qa_best_score < self.qa_threshold
        if below and not self.accepted_below_threshold:
            raise ValueError("qa_best_score below threshold requires accepted_below_threshold")
        if not below and self.accepted_below_threshold:
            raise ValueError("accepted_below_threshold set while qa_best_score passed")
        return self
