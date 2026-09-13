from datetime import UTC, datetime

from repaso.core.harness.mastery import update_mastery
from repaso.core.harness.progress import (
    ProgressBucket,
    ProgressReadout,
    bucket_of,
    read_progress,
)
from repaso.schemas.mastery import MasteryLevel, MasteryState

PRACTISED_AT = datetime(2026, 9, 13, 19, 0, tzinfo=UTC)


def cell(competency_id: str, correct: int, attempts: int, level: MasteryLevel) -> MasteryState:
    return MasteryState(
        student_id="s1",
        competency_id=competency_id,
        ema_accuracy=0.5,
        attempts=attempts,
        correct=correct,
        level=level,
    )


def test_a_cell_answered_once_or_twice_is_not_yet_known():
    assert bucket_of(1, 1) is ProgressBucket.NOT_YET_KNOWN
    assert bucket_of(2, 2) is ProgressBucket.NOT_YET_KNOWN
    assert bucket_of(0, 1) is ProgressBucket.NOT_YET_KNOWN
    assert bucket_of(0, 2) is ProgressBucket.NOT_YET_KNOWN


def history(outcomes: str) -> MasteryState:
    state = cell("c1", correct=0, attempts=0, level=MasteryLevel.UNKNOWN)
    for outcome in outcomes:
        state = update_mastery(state, outcome == "C", PRACTISED_AT)
    return state


def test_the_order_of_the_answers_cannot_change_the_bucket():
    first_right, last_right = history("CXX"), history("XXC")
    assert first_right.level is MasteryLevel.DEVELOPING
    assert last_right.level is MasteryLevel.STRUGGLING
    assert bucket_of(first_right.correct, first_right.attempts) is ProgressBucket.NOT_YET_KNOWN
    assert bucket_of(last_right.correct, last_right.attempts) is ProgressBucket.NOT_YET_KNOWN


def test_going_well_needs_enough_answers_to_rule_out_a_coin_flip():
    assert bucket_of(3, 3) is ProgressBucket.NOT_YET_KNOWN
    assert bucket_of(4, 4) is ProgressBucket.HOLDS
    assert bucket_of(8, 9) is ProgressBucket.HOLDS
    assert bucket_of(10, 10) is ProgressBucket.HOLDS


def test_needing_help_needs_the_same_evidence_in_the_other_direction():
    assert bucket_of(0, 3) is ProgressBucket.NOT_YET_KNOWN
    assert bucket_of(0, 4) is ProgressBucket.NEEDS_HELP
    assert bucket_of(1, 9) is ProgressBucket.NEEDS_HELP


def test_a_recency_weighted_level_cannot_promote_a_failing_cell():
    failing = cell("c1", correct=12, attempts=22, level=MasteryLevel.MASTERED)
    assert bucket_of(failing.correct, failing.attempts) is ProgressBucket.NOT_YET_KNOWN


def test_the_readout_carries_every_denominator_and_sums_to_the_topics():
    states = [
        cell("c1", 4, 4, MasteryLevel.MASTERED),
        cell("c2", 0, 4, MasteryLevel.STRUGGLING),
        cell("c3", 1, 2, MasteryLevel.UNKNOWN),
    ]
    readout = read_progress(states)
    assert readout == ProgressReadout(
        practised=3, answers=10, correct=5, holds=1, needs_help=1, not_yet_known=1
    )
    assert readout.holds + readout.needs_help + readout.not_yet_known == readout.practised


def test_a_topic_with_no_answers_is_not_counted_as_practised():
    readout = read_progress([cell("c1", 0, 0, MasteryLevel.UNKNOWN)])
    assert readout == ProgressReadout(
        practised=0, answers=0, correct=0, holds=0, needs_help=0, not_yet_known=0
    )


def test_no_states_reads_as_nothing_practised():
    assert read_progress([]) == ProgressReadout(
        practised=0, answers=0, correct=0, holds=0, needs_help=0, not_yet_known=0
    )
