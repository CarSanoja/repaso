import pytest

from repaso.tools.proportion import wilson_interval


def test_an_empty_denominator_bounds_nothing():
    interval = wilson_interval(0, 0)
    assert (interval.low, interval.high) == (0.0, 1.0)
    assert interval.line() == "0/0"


def test_eight_of_eight_does_not_reach_certainty():
    interval = wilson_interval(8, 8)
    assert interval.point == 1.0
    assert interval.low == pytest.approx(0.676, abs=0.001)
    assert interval.high == 1.0


def test_five_of_eight_overlaps_eight_of_eight():
    five = wilson_interval(5, 8)
    eight = wilson_interval(8, 8)
    assert five.high > eight.low


def test_none_of_three_leaves_room_above_a_half():
    interval = wilson_interval(0, 3)
    assert interval.low == 0.0
    assert interval.high == pytest.approx(0.562, abs=0.001)


def test_the_interval_narrows_as_the_denominator_grows():
    small = wilson_interval(8, 8)
    large = wilson_interval(80, 80)
    assert large.low > small.low


def test_the_line_names_the_denominator():
    assert wilson_interval(5, 8).line().startswith("5/8 [")


def test_counts_that_cannot_describe_a_proportion_are_refused():
    with pytest.raises(ValueError):
        wilson_interval(9, 8)
    with pytest.raises(ValueError):
        wilson_interval(-1, 8)
