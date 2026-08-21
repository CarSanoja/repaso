from datetime import UTC, date, datetime

import pytest

from repaso.core.harness.clock import Clock, SimClock, SystemClock

START = datetime(2026, 9, 1, 7, 0, tzinfo=UTC)


def test_sim_clock_is_frozen_until_advanced():
    clock = SimClock(START)
    assert clock.now() == START
    assert clock.now() == START
    assert clock.today() == date(2026, 9, 1)


def test_advance_moves_days_and_time():
    clock = SimClock(START)
    clock.advance(days=13, hours=12)
    assert clock.today() == date(2026, 9, 14)
    assert clock.now().hour == 19


def test_set_time_keeps_the_day():
    clock = SimClock(START)
    clock.set_time(hour=19, minute=30)
    assert clock.today() == date(2026, 9, 1)
    assert (clock.now().hour, clock.now().minute) == (19, 30)


def test_naive_start_is_rejected():
    with pytest.raises(ValueError):
        SimClock(datetime(2026, 9, 1, 7, 0))


def test_both_implementations_satisfy_the_protocol():
    assert isinstance(SimClock(START), Clock)
    assert isinstance(SystemClock(), Clock)
