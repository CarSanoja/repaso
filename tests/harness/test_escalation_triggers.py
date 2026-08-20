from repaso.core.harness.escalation_triggers import (
    DEFAULT_COOLDOWN_DAYS,
    DEFAULT_MIN_ACTIVE_DAYS,
    DEFAULT_SILENT_DAYS,
    FAST_GUESS_RATIO,
    engagement_trigger,
    fast_guess_flag,
    streak_slope,
    struggle_trigger,
)
from repaso.schemas.mastery import MasteryLevel, MasteryState

MIN_SAMPLES = 5
EXPECTED_SECONDS = 40.0


def make_state(**overrides) -> MasteryState:
    defaults = dict(
        student_id="s1",
        competency_id="c1",
        ema_accuracy=0.2,
        attempts=MIN_SAMPLES,
        correct=1,
        level=MasteryLevel.STRUGGLING,
    )
    defaults.update(overrides)
    return MasteryState(**defaults)


def test_struggling_student_with_enough_samples_escalates():
    assert struggle_trigger(
        make_state(),
        min_samples=MIN_SAMPLES,
        last_escalated_days_ago=None,
        cooldown_days=DEFAULT_COOLDOWN_DAYS,
    )


def test_few_attempts_never_escalate_even_when_struggling():
    for attempts in range(MIN_SAMPLES):
        assert not struggle_trigger(
            make_state(attempts=attempts),
            min_samples=MIN_SAMPLES,
            last_escalated_days_ago=None,
            cooldown_days=DEFAULT_COOLDOWN_DAYS,
        )


def test_levels_other_than_struggling_never_escalate():
    for level in (MasteryLevel.UNKNOWN, MasteryLevel.DEVELOPING, MasteryLevel.MASTERED):
        assert not struggle_trigger(
            make_state(level=level, attempts=50),
            min_samples=MIN_SAMPLES,
            last_escalated_days_ago=None,
            cooldown_days=DEFAULT_COOLDOWN_DAYS,
        )


def test_cooldown_blocks_refire_until_it_expires():
    inside = struggle_trigger(
        make_state(),
        min_samples=MIN_SAMPLES,
        last_escalated_days_ago=DEFAULT_COOLDOWN_DAYS - 1,
        cooldown_days=DEFAULT_COOLDOWN_DAYS,
    )
    at_boundary = struggle_trigger(
        make_state(),
        min_samples=MIN_SAMPLES,
        last_escalated_days_ago=DEFAULT_COOLDOWN_DAYS,
        cooldown_days=DEFAULT_COOLDOWN_DAYS,
    )
    assert not inside
    assert at_boundary


def test_silence_after_activity_escalates():
    counts = [3, 2, 0, 0, 0]
    assert engagement_trigger(
        counts,
        min_active_days=DEFAULT_MIN_ACTIVE_DAYS,
        silent_days_threshold=DEFAULT_SILENT_DAYS,
    )


def test_student_who_never_engaged_is_not_escalated():
    assert not engagement_trigger(
        [0, 0, 0, 0, 0, 0],
        min_active_days=DEFAULT_MIN_ACTIVE_DAYS,
        silent_days_threshold=DEFAULT_SILENT_DAYS,
    )


def test_single_active_day_falls_below_activity_floor():
    assert not engagement_trigger(
        [4, 0, 0, 0],
        min_active_days=DEFAULT_MIN_ACTIVE_DAYS,
        silent_days_threshold=DEFAULT_SILENT_DAYS,
    )


def test_short_trailing_silence_does_not_escalate():
    assert not engagement_trigger(
        [1, 1, 0, 0],
        min_active_days=DEFAULT_MIN_ACTIVE_DAYS,
        silent_days_threshold=DEFAULT_SILENT_DAYS,
    )


def test_earlier_gaps_do_not_count_as_trailing_silence():
    assert not engagement_trigger(
        [1, 0, 0, 0, 1],
        min_active_days=DEFAULT_MIN_ACTIVE_DAYS,
        silent_days_threshold=DEFAULT_SILENT_DAYS,
    )


def test_fast_guess_uses_median_not_extremes():
    rushed = [1.0, 2.0, 1.5, 90.0, 2.0]
    assert fast_guess_flag(rushed, expected_seconds=EXPECTED_SECONDS, min_samples=MIN_SAMPLES)


def test_deliberate_answers_are_not_flagged():
    thoughtful = [30.0, 25.0, 41.0, 38.0, 33.0]
    assert not fast_guess_flag(
        thoughtful, expected_seconds=EXPECTED_SECONDS, min_samples=MIN_SAMPLES
    )


def test_median_exactly_at_ratio_is_not_flagged():
    boundary = EXPECTED_SECONDS * FAST_GUESS_RATIO
    assert not fast_guess_flag(
        [boundary] * MIN_SAMPLES, expected_seconds=EXPECTED_SECONDS, min_samples=MIN_SAMPLES
    )


def test_too_few_latencies_never_flag():
    assert not fast_guess_flag(
        [0.5, 0.5], expected_seconds=EXPECTED_SECONDS, min_samples=MIN_SAMPLES
    )
    assert not fast_guess_flag([], expected_seconds=EXPECTED_SECONDS, min_samples=0)


def test_slope_is_negative_for_decaying_activity():
    assert streak_slope([8, 6, 4, 2, 0]) < 0


def test_slope_is_positive_for_growing_activity():
    assert streak_slope([0, 1, 3, 5, 9]) > 0


def test_flat_and_short_windows_have_zero_slope():
    assert streak_slope([4, 4, 4, 4]) == 0.0
    assert streak_slope([7]) == 0.0
    assert streak_slope([]) == 0.0
