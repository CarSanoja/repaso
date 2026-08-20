from datetime import UTC, datetime

from repaso.core.harness.mastery import MIN_ATTEMPTS_FOR_LEVEL, update_mastery
from repaso.schemas.mastery import MasteryLevel, MasteryState

NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


def make_state(**overrides) -> MasteryState:
    defaults = dict(student_id="s1", competency_id="c1", ema_accuracy=0.0, attempts=0, correct=0)
    defaults.update(overrides)
    return MasteryState(**defaults)


def test_level_stays_unknown_before_minimum_attempts():
    state = make_state()
    for _ in range(MIN_ATTEMPTS_FOR_LEVEL - 1):
        state = update_mastery(state, correct=True, practiced_at=NOW)
    assert state.level is MasteryLevel.UNKNOWN


def test_persistent_failure_classifies_as_struggling():
    state = make_state()
    for _ in range(5):
        state = update_mastery(state, correct=False, practiced_at=NOW)
    assert state.level is MasteryLevel.STRUGGLING
    assert state.streak == -5


def test_consistent_success_reaches_mastered():
    state = make_state()
    for _ in range(8):
        state = update_mastery(state, correct=True, practiced_at=NOW)
    assert state.level is MasteryLevel.MASTERED
    assert state.streak == 8


def test_failure_flips_positive_streak_to_negative():
    state = make_state()
    state = update_mastery(state, correct=True, practiced_at=NOW)
    state = update_mastery(state, correct=False, practiced_at=NOW)
    assert state.streak == -1


def test_ema_moves_toward_recent_outcomes():
    state = make_state()
    for _ in range(6):
        state = update_mastery(state, correct=True, practiced_at=NOW)
    high = state.ema_accuracy
    state = update_mastery(state, correct=False, practiced_at=NOW)
    assert state.ema_accuracy < high
