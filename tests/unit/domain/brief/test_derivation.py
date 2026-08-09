"""요구사항 후보의 자동 파생 (ADR-0050 §1).

도그푸딩 0004가 관측한 것: 답변 17라운드를 채우고 Gate가 `CLEAR`였는데
handoff의 칸이 전부 비어 있었다. 후보 기록이 **빠뜨릴 수 있는 별도 명령**이었기
때문이다. 이 파일은 그 경로가 닫혔다는 것을 고정한다.

파생이 **보수적**이라는 것도 함께 고정한다 — upstream 정규식을 자간 그대로
옮겼으므로 요구사항임을 스스로 선언하지 않는 답변은 후보가 되지 않는다. 우리는
전사를 끊었으므로(ADR-0016·0018) 그 몫을 수동 경로가 갚는다 (ADR-0050 §2).
"""

import pytest

from mission_control.domain.brief.derivation import derive_from_answer, derive_from_intent
from mission_control.domain.brief.requirement import (
    CandidateResolution,
    ConfirmationAuthority,
    RequirementSection,
)
from mission_control.domain.brief.state import BriefState


class TestTheIntentBecomesAGoal:
    """upstream ``initial-goal``. goal이 비는 경로가 없다."""

    def test_start_records_the_intent_as_a_promoted_goal(self) -> None:
        state = BriefState.start(mission_id="m-1", initial_intent="댓글 기능을 추가하고 싶다")

        assert len(state.candidates) == 1
        candidate = state.candidates[0]
        assert candidate.section is RequirementSection.GOAL
        assert candidate.text == "댓글 기능을 추가하고 싶다"
        assert candidate.resolution is CandidateResolution.CONFIRMED
        assert candidate.confirmation_authority is ConfirmationAuthority.USER
        assert [item.text for item in state.promotion.promoted] == ["댓글 기능을 추가하고 싶다"]

    def test_the_text_is_the_users_own_words(self) -> None:
        """사이에 LLM이 없다 — 그래서 CONFIRMED/USER가 안전하다."""
        intent = "  확장자별 파일 개수를 센다  "
        state = BriefState.start(mission_id="m-1", initial_intent=intent)

        assert state.candidates[0].text == intent.strip()

    def test_a_blank_intent_makes_no_candidate(self) -> None:
        assert derive_from_intent("   ") is None


class TestAnswersBecomeCandidatesConservatively:
    @pytest.mark.parametrize(
        ("answer", "section"),
        [
            ("검증은 unittest로 해야 한다", RequirementSection.ACCEPTANCE_CRITERION),
            ("표준 라이브러리만 쓰는 것이 필수다", RequirementSection.ACCEPTANCE_CRITERION),
            ("BrokenPipe는 반드시 0으로 끝난다", RequirementSection.ACCEPTANCE_CRITERION),
            ("this constraint must hold", RequirementSection.CONSTRAINT),
            ("stdlib only — it must take at most one argument", RequirementSection.CONSTRAINT),
        ],
    )
    def test_requirement_wording_produces_a_candidate(
        self, answer: str, section: RequirementSection
    ) -> None:
        derived = derive_from_answer(answer)

        assert derived is not None
        assert derived.section is section
        assert derived.text == answer

    @pytest.mark.parametrize(
        "answer",
        [
            "확장자는 마지막 점 뒤 한 조각이다",
            "출력은 탭으로 구분한다",
            "숨김 디렉터리는 건너뛴다",
        ],
    )
    def test_a_plain_decision_is_not_a_candidate(self, answer: str) -> None:
        """보수적이라는 것이 이 층의 성질이다 — 나머지는 수동 경로가 맡는다."""
        assert derive_from_answer(answer) is None

    def test_a_decision_answer_lands_in_the_state(self) -> None:
        state = BriefState.start(mission_id="m-1", initial_intent="도구를 만든다")

        state = state.record_answer(
            question="검증은?", answer="검증은 unittest로 해야 한다", authority="decision"
        )

        assert [item.section for item in state.candidates] == [
            RequirementSection.GOAL,
            RequirementSection.ACCEPTANCE_CRITERION,
        ]

    def test_an_observation_never_becomes_a_candidate(self) -> None:
        """사실이지 결정이 아니다 — upstream이 같은 자리에서 같은 이유로 건너뛴다."""
        state = BriefState.start(mission_id="m-1", initial_intent="도구를 만든다")

        state = state.record_answer(
            question="현재는?", answer="JWT를 반드시 쓰고 있다", authority="observation"
        )

        assert len(state.candidates) == 1  # 파생 goal 하나뿐
