"""Answer authority와 requirement input 투영.

Brief의 모든 답변은 두 개의 직교하는 축을 가진다. 지식의 종류(fact / decision /
assumption)와 **requirement authority**다. 이 모듈은 후자를 다룬다.

authority의 기준은 인간이 입력했는지가 아니라 **결정인지 채택된 사실인지**다.
시스템이 사용자를 대신해 확정한 기본값은 ``decision``이고, 사용자가 직접 붙여
넣은 코드 스니펫은 ``observation``이다.

``observation``은 요구사항을 만들 권한이 없다. 이 규칙은 권고가 아니라
:func:`project_requirement_input` 투영으로 강제된다. 강제하지 않으면 "현재 코드는
3회 재시도한다"는 관찰이 추출 과정에서 "3회 재시도해야 한다"로 바뀌고, 아무도
결정한 적 없는 조건이 명세가 된다.

투영은 요약이나 검토 단계가 아니라 **입력 지점**에 적용한다. 추출기가 관찰
문장을 한 번 재작성하고 나면 결정과 구분할 수 없게 되기 때문이다.

authority는 답변이 상태에 기록되는 단일 지점에서 결정되고, 이후 소비자는 저장된
값을 읽기만 한다. 이 모듈의 어떤 함수도 답변 본문을 보고 authority를 다시
판정하지 않는다.

계약: ``docs/05_BRIEF.md`` §5.2, §9.1
결정: ``docs/adr/0010-answer-provenance-and-requirement-authority.md``
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: 답변이 요구사항을 만들 권한을 갖는지 나타낸다.
AnswerAuthority = Literal["decision", "observation"]

#: 보류된 관찰 답변 자리에 렌더링한다. 설명 없는 공백 대신 의도적인 placeholder를
#: 남겨, 추출기가 누락이 아니라 정책의 결과임을 알 수 있게 한다.
WITHHELD_ANSWER_NOTE = (
    "[관찰 보류 — 채택한 사실이며 결정이 아니다. 이후 질문을 구체화하는 데 사용되었다.]"
)


@dataclass(frozen=True, slots=True)
class BriefRound:
    """질문 하나와 그에 대한 답변, 그리고 답변의 requirement authority."""

    number: int
    question: str
    answer: str | None
    authority: AnswerAuthority


@dataclass(frozen=True, slots=True)
class RequirementInputRound:
    """요구사항을 도출하는 소비자가 읽어야 하는 형태의 라운드."""

    number: int
    question: str
    answer: str | None
    withheld: bool


def project_requirement_input(
    rounds: list[BriefRound] | tuple[BriefRound, ...],
) -> list[RequirementInputRound]:
    """Goal, Constraints, Non-goals, 성공 조건을 도출하는 입력으로 투영한다.

    ``observation`` 답변의 본문은 :data:`WITHHELD_ANSWER_NOTE`로 대체되어 결과에
    남지 않는다. 따라서 관찰을 요구사항으로 바꿔 쓰는 일이 나중에 탐지해야 할
    문제가 아니라 구조적으로 불가능해진다.

    질문 텍스트는 의도적으로 그대로 투영한다. 관찰이 도착해야 할 자리가 질문이며,
    다음 질문을 날카롭게 하는 것이 관찰을 수집한 이유이기 때문이다.

    아직 답변되지 않은 라운드는 숨길 답변이 없으므로 그대로 투영한다.
    """
    projected: list[RequirementInputRound] = []
    for item in rounds:
        withheld = item.answer is not None and item.authority == "observation"
        projected.append(
            RequirementInputRound(
                number=item.number,
                question=item.question,
                answer=WITHHELD_ANSWER_NOTE if withheld else item.answer,
                withheld=withheld,
            )
        )
    return projected


def observed_facts(
    rounds: list[BriefRound] | tuple[BriefRound, ...],
) -> list[BriefRound]:
    """관찰된 사실만 원문 그대로 반환한다.

    withholding은 사실을 숨기는 장치가 아니라 사실이 요구사항으로 승격되는 경로를
    끊는 장치다. Blueprint는 이 채널로 현재 상태와 제약을 읽는다. 이 구분이
    무너지면 명세가 제약을 모른 채 만들어지거나, 반대로 관찰이 요구사항으로
    둔갑한다.
    """
    return [item for item in rounds if item.answer is not None and item.authority == "observation"]
