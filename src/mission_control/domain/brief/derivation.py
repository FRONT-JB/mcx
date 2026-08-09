"""요구사항 후보의 자동 파생 (ADR-0050 §1).

upstream ``build_requirement_distillation``의 두 갈래를 옮긴 것이다 — 초기
의도는 GOAL 후보가 되고, 답변은 **요구사항임을 스스로 선언할 때만** 후보가
된다. 그 판정은 upstream 정규식이 하며 **자간 그대로** 옮겼다: 무엇이
요구사항인지의 정의를 우리가 발명하면 upstream과 대조가 끊긴다.

값이 ``CONFIRMED``/``USER``인 것이 안전한 근거는 텍스트가 **사용자가 친 원문
그대로**라는 것이다. 사이에 LLM이 없다.

``observation`` 답변은 건너뛴다 — upstream이 같은 자리에서 같은 이유로
건너뛴다 (*"An adopted fact, not a decision."*). ADR-0010의 축과 같다.

**보수적이라는 것이 이 층의 성질이다.** upstream은 놓친 것을 전사가 받쳐주지만
우리는 전사를 끊었으므로 (ADR-0016·0018) 수동 경로가 함께 남는다 (ADR-0050 §2).
"""

from __future__ import annotations

import re

from mission_control.domain.brief.requirement import (
    CandidateContentSource,
    CandidateResolution,
    ConfirmationAuthority,
    RequirementSection,
)

#: upstream ``_EXPLICIT_REQUIREMENT_RE`` — 한국어·일본어 어휘가 원본에 있다.
EXPLICIT_REQUIREMENT = re.compile(
    r"(?:"
    r"\b(?:must|need(?:s|ed)? to|required?|requirement|acceptance criteri(?:on|a)|"
    r"confirm(?:ed|ing)?|shall)\b"
    r"|(?:확인|확정)(?:된|한)?\s*(?:요구\s*사항|조건)"
    r"|요구\s*사항|필수|반드시|해야\s*(?:한다|합니다|함)|되어야\s*(?:한다|합니다|함)"
    r"|確認済み|確定(?:した|済み)?|要件|必須|必要(?:です|がある)|"
    r"なければならない|べき(?:です|だ)?"
    r")",
    re.IGNORECASE,
)

#: upstream ``_CONSTRAINT_RE``. 영어뿐인 것도 원본 그대로다.
CONSTRAINT_WORDING = re.compile(
    r"\b(?:constraint|must not|cannot|can't|no external|only|at most|at least)\b",
    re.IGNORECASE,
)


class DerivedCandidate:
    """파생된 후보 하나의 재료. 저장 형태로 만드는 것은 상태 층이 한다."""

    __slots__ = ("section", "text")

    def __init__(self, *, section: RequirementSection, text: str) -> None:
        self.section = section
        self.text = text


#: 파생 후보가 갖는 고정 값. 원문 그대로이므로 사용자 권위로 확정된 것으로 본다.
DERIVED_CONTENT_SOURCE = CandidateContentSource.USER_STATED
DERIVED_RESOLUTION = CandidateResolution.CONFIRMED
DERIVED_AUTHORITY = ConfirmationAuthority.USER
DERIVED_REQUIRED = True


def derive_from_intent(initial_intent: str) -> DerivedCandidate | None:
    """초기 의도를 GOAL 후보로 만든다 (upstream ``initial-goal``).

    이것이 있어 **goal이 비는 경로가 없다** — 빠뜨릴 명령이 아니라 ``brief
    start``의 산물이기 때문이다.
    """
    text = initial_intent.strip()
    if not text:
        return None
    return DerivedCandidate(section=RequirementSection.GOAL, text=text)


def derive_from_answer(answer: str) -> DerivedCandidate | None:
    """결정 답변에서 후보를 만든다 — 요구사항 어휘가 있을 때만.

    호출자가 ``observation`` 답변을 걸러서 부른다. 여기서 authority를 보지
    않는 이유는 그 축이 상태 층의 것이기 때문이다.
    """
    text = answer.strip()
    if not text or not EXPLICIT_REQUIREMENT.search(text):
        return None
    section = (
        RequirementSection.CONSTRAINT
        if CONSTRAINT_WORDING.search(text)
        else RequirementSection.ACCEPTANCE_CRITERION
    )
    return DerivedCandidate(section=section, text=text)
