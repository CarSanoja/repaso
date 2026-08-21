import pytest

from repaso.core.harness.psychometrics import (
    DISCRIMINATION_FLOOR,
    MIN_OBSERVATIONS,
    ItemObservation,
    item_discrimination,
    item_p_value,
    should_retire,
    summarize,
)

DISCRIMINATING = [(True, 0.9), (True, 0.85), (True, 0.8), (False, 0.3), (False, 0.2), (False, 0.1)]
INDEPENDENT = [(True, 0.2), (False, 0.8), (False, 0.2), (True, 0.8), (True, 0.5), (False, 0.5)]


def make_observation(**overrides) -> ItemObservation:
    defaults = dict(item_id="i1", student_id="s1", correct=True, student_total_score=0.5)
    defaults.update(overrides)
    return ItemObservation(**defaults)


def make_observations(outcomes: list[tuple[bool, float]]) -> list[ItemObservation]:
    return [
        make_observation(student_id=f"s{index}", correct=correct, student_total_score=score)
        for index, (correct, score) in enumerate(outcomes)
    ]


def test_p_value_is_the_proportion_correct():
    observations = make_observations([(True, 0.6), (True, 0.4), (False, 0.5), (False, 0.5)])
    assert item_p_value(observations) == 0.5
    assert item_p_value(make_observations([(True, 0.6)])) == 1.0


def test_p_value_rejects_empty_observations():
    with pytest.raises(ValueError):
        item_p_value([])


def test_discrimination_is_positive_when_strong_students_succeed():
    assert item_discrimination(make_observations(DISCRIMINATING)) > 0.9


def test_discrimination_is_negative_when_weak_students_succeed():
    flipped = [(not correct, score) for correct, score in DISCRIMINATING]
    assert item_discrimination(make_observations(flipped)) < -0.9


def test_discrimination_is_zero_when_success_is_independent_of_ability():
    assert item_discrimination(make_observations(INDEPENDENT)) == pytest.approx(0.0, abs=1e-9)


def test_discrimination_is_zero_without_variance_in_either_variable():
    same_score = [(index % 2 == 0, 0.6) for index in range(MIN_OBSERVATIONS + 1)]
    all_correct = [(True, score / 10) for score in range(MIN_OBSERVATIONS + 1)]
    assert item_discrimination(make_observations(same_score)) == 0.0
    assert item_discrimination(make_observations(all_correct)) == 0.0


def test_discrimination_is_zero_below_minimum_observations():
    scarce = make_observations(DISCRIMINATING[: MIN_OBSERVATIONS - 1])
    assert len(scarce) == MIN_OBSERVATIONS - 1
    assert item_discrimination(scarce) == 0.0


def test_retires_item_everyone_answers_correctly():
    assert should_retire(make_observations([(True, 0.5)] * 6), min_attempts=5)


def test_retires_item_nobody_answers_correctly():
    assert should_retire(make_observations([(False, 0.5)] * 6), min_attempts=5)


def test_retires_item_that_separates_nobody():
    observations = make_observations(INDEPENDENT)
    assert abs(item_discrimination(observations)) < DISCRIMINATION_FLOOR
    assert should_retire(observations, min_attempts=5)


def test_keeps_item_that_separates_strong_from_weak_students():
    assert not should_retire(make_observations(DISCRIMINATING), min_attempts=5)


def test_keeps_item_until_it_has_enough_attempts():
    observations = make_observations([(True, 0.5)] * 4)
    assert not should_retire(observations, min_attempts=5)
    assert should_retire(observations + [make_observation(student_id="s4")], min_attempts=5)


def test_summarize_reports_counts_and_measures():
    summary = summarize(make_observations(DISCRIMINATING))
    assert summary["n"] == 6
    assert summary["p_value"] == pytest.approx(0.5)
    assert summary["discrimination"] > 0.9


def test_summarize_leaves_p_value_none_without_observations():
    assert summarize([]) == {"n": 0, "p_value": None, "discrimination": 0.0}
