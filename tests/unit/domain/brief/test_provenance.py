"""Brief answer provenance와 requirement authority 투영.

계약: docs/05_BRIEF.md §5.2, §9.1 / docs/adr/0010-answer-provenance-and-requirement-authority.md
Test Matrix: B-031, B-032, B-033
"""

from mission_control.domain.brief.provenance import (
    WITHHELD_ANSWER_NOTE,
    BriefRound,
    observed_facts,
    project_requirement_input,
)


def _round(
    number: int,
    question: str,
    answer: str | None,
    authority: str = "decision",
) -> BriefRound:
    return BriefRound(
        number=number,
        question=question,
        answer=answer,
        authority=authority,  # type: ignore[arg-type]
    )


class TestRequirementInputProjection:
    """B-031 — observation의 답변 본문은 요구사항 도출 입력에 포함되지 않는다."""

    def test_observation_answer_body_is_withheld(self) -> None:
        rounds = [
            _round(1, "재시도 정책은 어떻게 되어야 합니까?", "실패하면 사용자에게 알린다"),
            _round(2, "현재 재시도 설정은?", "3회, 2s/4s/8s 백오프", authority="observation"),
        ]

        projected = project_requirement_input(rounds)

        assert projected[1].answer == WITHHELD_ANSWER_NOTE
        assert "3회" not in projected[1].answer
        assert projected[1].withheld is True

    def test_observation_question_text_is_preserved(self) -> None:
        """관찰은 다음 질문을 날카롭게 하려고 수집한 것이므로 질문은 남는다."""
        rounds = [_round(1, "현재 재시도 설정은?", "3회", authority="observation")]

        projected = project_requirement_input(rounds)

        assert projected[0].question == "현재 재시도 설정은?"

    def test_decision_answer_is_projected_unchanged(self) -> None:
        rounds = [_round(1, "댓글 작성 권한은?", "로그인 사용자만")]

        projected = project_requirement_input(rounds)

        assert projected[0].answer == "로그인 사용자만"
        assert projected[0].withheld is False

    def test_unanswered_round_is_projected_as_is(self) -> None:
        """숨길 답변이 없는 라운드는 그대로 둔다."""
        rounds = [_round(1, "삭제 기능이 필요합니까?", None)]

        projected = project_requirement_input(rounds)

        assert projected[0].answer is None
        assert projected[0].withheld is False

    def test_projection_preserves_round_order_and_numbers(self) -> None:
        rounds = [
            _round(1, "q1", "a1"),
            _round(2, "q2", "a2", authority="observation"),
            _round(3, "q3", None),
        ]

        projected = project_requirement_input(rounds)

        assert [item.number for item in projected] == [1, 2, 3]


class TestObservedFactsChannel:
    """B-031 — withholding은 사실을 숨기는 장치가 아니다. 사실 채널은 온전하다."""

    def test_observation_content_remains_available_as_fact(self) -> None:
        rounds = [
            _round(1, "권한은?", "로그인 사용자만"),
            _round(2, "현재 재시도 설정은?", "3회, 2s/4s/8s 백오프", authority="observation"),
        ]

        facts = observed_facts(rounds)

        assert len(facts) == 1
        assert facts[0].answer == "3회, 2s/4s/8s 백오프"
        assert facts[0].number == 2

    def test_decision_is_not_a_fact(self) -> None:
        rounds = [_round(1, "권한은?", "로그인 사용자만")]

        assert observed_facts(rounds) == []

    def test_unanswered_observation_is_not_a_fact(self) -> None:
        rounds = [_round(1, "현재 설정은?", None, authority="observation")]

        assert observed_facts(rounds) == []


class TestAuthorityIsReadNotReinterpreted:
    """B-032, B-033 — 저장된 authority 값이 권위를 결정한다."""

    def test_machine_confirmed_default_counts_as_decision(self) -> None:
        """시스템이 사용자를 대신해 확정한 값은 사람이 입력하지 않았어도 결정이다."""
        rounds = [
            _round(1, "타임아웃 기본값을 30초로 둘까요?", "예 (기본값 채택)", authority="decision"),
        ]

        projected = project_requirement_input(rounds)

        assert projected[0].withheld is False
        assert projected[0].answer == "예 (기본값 채택)"

    def test_pasted_code_marked_as_observation_is_withheld(self) -> None:
        """사람이 직접 붙여 넣었어도 채택한 사실이면 observation이다."""
        rounds = [
            _round(1, "현재 구현은?", "def retry(n=3): ...", authority="observation"),
        ]

        projected = project_requirement_input(rounds)

        assert projected[0].withheld is True
        assert projected[0].answer == WITHHELD_ANSWER_NOTE

    def test_projection_does_not_inspect_answer_text(self) -> None:
        """답변 본문에 출처처럼 보이는 문자열이 있어도 authority가 바뀌지 않는다."""
        rounds = [
            _round(1, "권한은?", "[from-code] 로그인 사용자만", authority="decision"),
        ]

        projected = project_requirement_input(rounds)

        assert projected[0].withheld is False
        assert projected[0].answer == "[from-code] 로그인 사용자만"
