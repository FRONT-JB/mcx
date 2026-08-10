"""status 저장 상태 조립 — revision lineage를 섞지 않는다."""

from types import SimpleNamespace

from mission_control.cli.status_view import GateView, _correction_count, _summaries
from mission_control.domain.stage import Stage


def _attempt(*, revision: int, ac_key: str, error: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(blueprint_revision=revision, ac_key=ac_key, error=error)


def _blueprint() -> SimpleNamespace:
    return SimpleNamespace(
        revision=4,
        current=SimpleNamespace(acceptance_criteria=(object(), object(), object())),
        qa_records=(),
        has_current_approval=True,
    )


def _verify(*, revision: int) -> SimpleNamespace:
    return SimpleNamespace(
        evidence=SimpleNamespace(blueprint_revision=revision, runs=()),
        verdicts=None,
    )


def test_execute_summary_counts_only_the_current_blueprint_revision() -> None:
    execute = SimpleNamespace(
        attempts=(
            _attempt(revision=1, ac_key="old-a"),
            _attempt(revision=1, ac_key="old-b"),
            _attempt(revision=4, ac_key="new-a"),
            _attempt(revision=4, ac_key="new-b"),
            _attempt(revision=4, ac_key="new-c"),
        )
    )

    summaries = _summaries(
        brief=None,
        blueprint=_blueprint(),
        execute=execute,
        verify=_verify(revision=4),
        corrections=0,
        stored={stage: True for stage in Stage},
        gates={Stage.VERIFY: GateView(outcome="CLEAR")},
    )

    assert summaries[Stage.EXECUTE] == "AC 3개 실행 · 시도 3회 — 검증 완료"


def test_execute_summary_does_not_reuse_stale_verify_evidence() -> None:
    execute = SimpleNamespace(attempts=(_attempt(revision=4, ac_key="new-a"),))

    summaries = _summaries(
        brief=None,
        blueprint=_blueprint(),
        execute=execute,
        verify=_verify(revision=1),
        corrections=0,
        stored={stage: True for stage in Stage},
        gates={Stage.VERIFY: GateView(outcome="CLEAR")},
    )

    assert summaries[Stage.EXECUTE] == "AC 1개 실행 · 시도 1회 — 검증 전"


def test_reexecution_in_a_new_revision_is_not_counted_as_recover_correction() -> None:
    assert _correction_count(((1, "same-ac"), (4, "same-ac"))) == 0
    assert _correction_count(((4, "same-ac"), (4, "same-ac"))) == 1
