from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from repaso.config.settings import Settings
from repaso.core.harness.calendar import is_scheduled, mask_to_scheduled
from repaso.core.harness.escalation_triggers import (
    DEFAULT_MIN_ACTIVE_DAYS,
    DEFAULT_SILENT_DAYS,
    engagement_trigger,
    trailing_silent_days,
)
from repaso.schemas.channel import ChannelKind
from repaso.schemas.family import Family

WEEKEND = [5, 6]
CARNAVAL = [date(2026, 9, 14), date(2026, 9, 15)]
MONDAY = date(2026, 9, 7)
SATURDAY = date(2026, 9, 5)
SUNDAY = date(2026, 9, 6)


def window(last_day: date, length: int = 14) -> list[date]:
    return [last_day - timedelta(days=offset) for offset in range(length - 1, -1, -1)]


def make_family(**overrides) -> Family:
    defaults = dict(
        id="f1",
        channel=ChannelKind.TELEGRAM,
        chat_ref="100",
        invite_code="PILOT1",
        created_at=date(2026, 9, 1),
    )
    defaults.update(overrides)
    return Family(**defaults)


def test_an_ordinary_weekday_is_scheduled():
    assert is_scheduled(MONDAY, WEEKEND, CARNAVAL)


def test_rest_weekdays_are_not_scheduled():
    assert not is_scheduled(SATURDAY, WEEKEND, CARNAVAL)
    assert not is_scheduled(SUNDAY, WEEKEND, CARNAVAL)


def test_a_holiday_on_a_weekday_is_not_scheduled():
    assert not is_scheduled(CARNAVAL[0], WEEKEND, CARNAVAL)
    assert is_scheduled(CARNAVAL[0], WEEKEND, [])


def test_an_empty_calendar_schedules_every_day():
    assert all(is_scheduled(day, [], []) for day in window(date(2026, 9, 28)))


def test_masking_drops_rest_days_and_preserves_order():
    days = window(date(2026, 9, 8))
    counts = list(range(len(days)))

    masked = mask_to_scheduled(days, counts, WEEKEND, [])

    kept = [count for day, count in zip(days, counts, strict=True) if day.weekday() < 5]
    assert masked == kept
    assert masked == sorted(masked)


def test_masking_refuses_a_window_whose_counts_do_not_line_up():
    with pytest.raises(ValueError):
        mask_to_scheduled(window(MONDAY), [1, 2, 3], WEEKEND, [])


def test_a_long_weekend_is_silence_on_the_calendar_and_nothing_on_the_schedule():
    days = window(date(2026, 9, 15))
    answered = {date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11)}
    counts = [1 if day in answered else 0 for day in days]

    assert trailing_silent_days(counts) == 4
    assert engagement_trigger(counts, DEFAULT_MIN_ACTIVE_DAYS, DEFAULT_SILENT_DAYS)

    masked = mask_to_scheduled(days, counts, WEEKEND, CARNAVAL)

    assert trailing_silent_days(masked) == 0
    assert not engagement_trigger(masked, DEFAULT_MIN_ACTIVE_DAYS, DEFAULT_SILENT_DAYS)


def test_a_real_dropout_still_trips_the_trigger_under_masking():
    days = window(date(2026, 9, 17))
    answered = {date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10)}
    counts = [1 if day in answered else 0 for day in days]

    masked = mask_to_scheduled(days, counts, WEEKEND, CARNAVAL)

    assert masked[-3:] == [0, 0, 0]
    assert trailing_silent_days(masked) == 3
    assert engagement_trigger(masked, DEFAULT_MIN_ACTIVE_DAYS, DEFAULT_SILENT_DAYS)


def test_a_family_rests_on_the_weekdays_it_declares():
    family = make_family(rest_weekdays=[5, 6])

    assert family.rest_weekdays == [5, 6]
    assert not is_scheduled(SATURDAY, family.rest_weekdays, [])


def test_a_family_without_a_calendar_practices_every_day():
    assert make_family().rest_weekdays == []


@pytest.mark.parametrize("weekday", [-1, 7, 12])
def test_a_weekday_outside_the_week_is_refused(weekday):
    with pytest.raises(ValidationError):
        make_family(rest_weekdays=[weekday])


def test_holidays_reach_settings_as_dates_from_iso_strings():
    settings = Settings(local_mode=True, holiday_dates=["2026-09-14", "2026-09-15"])

    assert settings.holiday_dates == CARNAVAL


def test_settings_without_a_school_calendar_block_nothing():
    settings = Settings(local_mode=True)

    assert settings.holiday_dates == []
    assert is_scheduled(CARNAVAL[0], [], settings.holiday_dates)
