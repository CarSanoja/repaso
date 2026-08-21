import pytest

from repaso.core.harness.budgets import (
    CLOSED,
    HALF_OPEN,
    OPEN,
    BoundedAttempts,
    CircuitBreaker,
    DailyBudget,
)

OPENING_STEP = 10


def make_budget(**overrides) -> DailyBudget:
    defaults = dict(limit_calls=3)
    defaults.update(overrides)
    return DailyBudget(**defaults)


def make_breaker(**overrides) -> CircuitBreaker:
    defaults = dict(failure_threshold=2, recovery_steps=5)
    defaults.update(overrides)
    return CircuitBreaker(**defaults)


def open_breaker(breaker: CircuitBreaker, step: int = OPENING_STEP) -> CircuitBreaker:
    for _ in range(breaker.failure_threshold):
        breaker.record_failure(step)
    return breaker


def test_budget_spends_until_the_limit_then_refuses():
    budget = make_budget()
    assert [budget.try_spend() for _ in range(4)] == [True, True, True, False]
    assert budget.exhausted()


def test_refused_spend_leaves_the_budget_unchanged():
    budget = make_budget(limit_calls=5, spent=4)
    assert not budget.try_spend(2)
    assert budget.spent == 4
    assert budget.remaining() == 1
    assert budget.try_spend(1)


def test_snapshot_reports_limit_spent_and_remaining():
    budget = make_budget(limit_calls=4)
    budget.try_spend(3)
    assert budget.snapshot() == {"limit": 4, "spent": 3, "remaining": 1}


def test_budget_rejects_non_positive_spend():
    with pytest.raises(ValueError):
        make_budget().try_spend(0)


def test_budget_rejects_spent_above_limit():
    with pytest.raises(ValueError):
        make_budget(limit_calls=2, spent=3)


def test_zero_limit_budget_is_exhausted_from_the_start():
    budget = make_budget(limit_calls=0)
    assert budget.exhausted()
    assert not budget.try_spend()


def test_breaker_opens_after_consecutive_failures():
    breaker = make_breaker()
    breaker.record_failure(OPENING_STEP - 1)
    assert breaker.state() == CLOSED
    breaker.record_failure(OPENING_STEP)
    assert breaker.state() == OPEN
    assert not breaker.allow(OPENING_STEP)


def test_open_breaker_blocks_until_recovery_steps_elapse():
    breaker = open_breaker(make_breaker())
    assert not breaker.allow(OPENING_STEP + 4)
    assert breaker.state() == OPEN
    assert breaker.allow(OPENING_STEP + 5)
    assert breaker.state() == HALF_OPEN


def test_success_in_half_open_closes_the_breaker_and_resets_failures():
    breaker = open_breaker(make_breaker())
    breaker.allow(OPENING_STEP + 5)
    breaker.record_success(OPENING_STEP + 5)
    assert breaker.state() == CLOSED
    assert breaker.consecutive_failures == 0
    assert breaker.allow(OPENING_STEP + 6)


def test_failure_in_half_open_reopens_at_that_step():
    breaker = open_breaker(make_breaker())
    breaker.allow(OPENING_STEP + 5)
    breaker.record_failure(OPENING_STEP + 5)
    assert breaker.state() == OPEN
    assert breaker.opened_step == OPENING_STEP + 5
    assert not breaker.allow(OPENING_STEP + 9)
    assert breaker.allow(OPENING_STEP + 10)


def test_success_resets_consecutive_failures_while_closed():
    breaker = make_breaker(failure_threshold=3)
    breaker.record_failure(1)
    breaker.record_failure(2)
    breaker.record_success(3)
    breaker.record_failure(4)
    breaker.record_failure(5)
    assert breaker.state() == CLOSED
    assert breaker.consecutive_failures == 2


def test_success_while_open_does_not_close_before_recovery():
    breaker = open_breaker(make_breaker())
    breaker.record_success(OPENING_STEP + 1)
    assert breaker.state() == OPEN
    assert not breaker.allow(OPENING_STEP + 1)


def test_breaker_snapshot_tracks_state_and_opening_step():
    breaker = make_breaker()
    assert breaker.snapshot() == {
        "state": CLOSED,
        "consecutive_failures": 0,
        "opened_step": None,
    }
    open_breaker(breaker)
    assert breaker.snapshot() == {
        "state": OPEN,
        "consecutive_failures": 2,
        "opened_step": OPENING_STEP,
    }


def test_breaker_rejects_non_positive_recovery_steps():
    with pytest.raises(ValueError):
        make_breaker(recovery_steps=0)


def test_bounded_attempts_refuses_after_max_and_reports_usage():
    attempts = BoundedAttempts(max_attempts=2)
    assert [attempts.try_attempt() for _ in range(3)] == [True, True, False]
    assert attempts.attempts_used() == 2
    assert attempts.exhausted()
    assert attempts.snapshot() == {"max_attempts": 2, "used": 2, "remaining": 0}


def test_zero_max_attempts_refuses_the_first_attempt():
    attempts = BoundedAttempts(max_attempts=0)
    assert not attempts.try_attempt()
    assert attempts.attempts_used() == 0
