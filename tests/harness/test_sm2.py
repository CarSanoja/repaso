from datetime import date, timedelta

import pytest

from repaso.core.harness.sm2 import MIN_EASE, due_items, grade_to_quality, is_due, review
from repaso.schemas.schedule import SpacedItemState

TODAY = date(2026, 9, 1)


def make_state(**overrides) -> SpacedItemState:
    defaults = dict(student_id="s1", item_id="i1", due_date=TODAY)
    defaults.update(overrides)
    return SpacedItemState(**defaults)


def test_failure_resets_repetitions_and_schedules_tomorrow():
    state = make_state(repetitions=4, interval_days=10, lapses=0)
    reviewed = review(state, quality=1, today=TODAY)
    assert reviewed.repetitions == 0
    assert reviewed.lapses == 1
    assert reviewed.due_date == TODAY + timedelta(days=1)


def test_intervals_grow_with_successful_reviews():
    state = make_state()
    first = review(state, quality=5, today=TODAY)
    second = review(first, quality=5, today=first.due_date)
    third = review(second, quality=5, today=second.due_date)
    assert first.interval_days == 1
    assert second.interval_days == 3
    assert third.interval_days > second.interval_days


def test_ease_never_drops_below_floor():
    state = make_state(ease=MIN_EASE)
    reviewed = review(state, quality=3, today=TODAY)
    assert reviewed.ease >= MIN_EASE


def test_review_rejects_out_of_range_quality():
    with pytest.raises(ValueError):
        review(make_state(), quality=6, today=TODAY)


def test_due_items_orders_by_date_then_lapses():
    late = make_state(item_id="late", due_date=TODAY - timedelta(days=3))
    lapsed = make_state(item_id="lapsed", due_date=TODAY, lapses=2)
    fresh = make_state(item_id="fresh", due_date=TODAY)
    future = make_state(item_id="future", due_date=TODAY + timedelta(days=2))
    picked = due_items([fresh, future, lapsed, late], today=TODAY, limit=2)
    assert [state.item_id for state in picked] == ["late", "lapsed"]
    assert not is_due(future, TODAY)


def test_quality_mapping_rewards_speed_and_punishes_errors():
    assert grade_to_quality(correct=False, latency_seconds=5, expected_seconds=30) == 1
    assert grade_to_quality(correct=True, latency_seconds=20, expected_seconds=30) == 5
    assert grade_to_quality(correct=True, latency_seconds=50, expected_seconds=30) == 4
    assert grade_to_quality(correct=True, latency_seconds=120, expected_seconds=30) == 3
