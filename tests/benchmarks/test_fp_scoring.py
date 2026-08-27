import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from score_fp_ground_truth import (
    COHORT_START,
    CRITERION,
    DETECTOR_NOISE,
    LOW_ABILITY,
    MEASUREMENT_CORRECT,
    TRUE_POSITIVE,
    ability_at,
    adjusted_precision,
    classify_fire,
    day_index,
    justified_cohort_fires,
    tally,
)

from repaso.simulator.archetypes import PROFILES, Archetype
from repaso.simulator.student_sim import ability_on_day

SECTION_A = "colegio-demo-4-a"
SECTION_CLUSTER = "colegio-demo-4-b"
DAY_ZERO = date(2026, 9, 1)


def make_row(archetypes, sections, fires, signals=()):
    return {
        "seed": 1,
        "archetypes": archetypes,
        "sections": sections,
        "struggle_fires": fires,
        "cohort_signals": list(signals),
    }


def steady_row(students, fires, signals=(), archetype="steady_mastery"):
    return make_row(
        {student: archetype for student in students},
        {student: SECTION_A for student in students},
        fires,
        signals,
    )


def test_day_index_counts_from_cohort_start():
    assert day_index(COHORT_START) == 0
    assert day_index(date(2026, 9, 15)) == 14


def test_ability_at_matches_simulator_ground_truth():
    assert ability_at("forgetting", date(2026, 9, 3)) == ability_on_day(
        PROFILES[Archetype.FORGETTING], 2
    )
    assert ability_at("steady_mastery", DAY_ZERO) == 0.65


def test_low_ability_archetypes_are_true_positives():
    for archetype in sorted(LOW_ABILITY):
        assert classify_fire(archetype, DAY_ZERO, 0.0) == TRUE_POSITIVE
        assert classify_fire(archetype, date(2026, 9, 14), 1.0) == TRUE_POSITIVE


def test_classification_splits_on_criterion():
    assert classify_fire("steady_mastery", DAY_ZERO, 0.70) == MEASUREMENT_CORRECT
    assert classify_fire("steady_mastery", DAY_ZERO, 0.50) == DETECTOR_NOISE


def test_criterion_boundary_is_strict():
    assert classify_fire("steady_mastery", DAY_ZERO, 0.65) == DETECTOR_NOISE
    assert classify_fire("steady_mastery", DAY_ZERO, 0.651) == MEASUREMENT_CORRECT


def test_no_simulated_archetype_dips_below_the_default_criterion():
    for archetype in Archetype:
        if archetype.value in LOW_ABILITY:
            continue
        for day in range(14):
            assert ability_on_day(PROFILES[archetype], day) >= CRITERION


def test_tally_counts_fires_not_students():
    row = make_row(
        {"stu01": "struggling", "stu02": "steady_mastery"},
        {"stu01": SECTION_A, "stu02": SECTION_A},
        {"stu01": ["2026-09-02", "2026-09-09"], "stu02": ["2026-09-05"]},
    )
    totals, per_archetype = tally([row], CRITERION)
    assert totals[TRUE_POSITIVE] == 2
    assert totals[DETECTOR_NOISE] == 1
    assert per_archetype["steady_mastery"][DETECTOR_NOISE] == 1


def test_adjusted_precision_credits_measurement_correct_fires():
    row = make_row(
        {"stu01": "struggling", "stu02": "steady_mastery"},
        {"stu01": SECTION_A, "stu02": SECTION_A},
        {"stu01": ["2026-09-02"], "stu02": ["2026-09-05"]},
    )
    strict, _ = tally([row], CRITERION)
    lenient, _ = tally([row], 0.99)
    assert adjusted_precision(strict)[0] == 0.5
    assert adjusted_precision(lenient)[0] == 1.0


def test_cluster_section_signals_are_not_rescored():
    row = steady_row(
        ["stu01"],
        {"stu01": ["2026-09-05"]},
        [f"{SECTION_CLUSTER}#math.g4.decimals.tenths_hundredths#2026-09-06"],
    )
    assert justified_cohort_fires([row]) == []


def test_cohort_fire_is_justified_by_three_credited_families():
    students = ["stu01", "stu02", "stu03"]
    row = make_row(
        {student: "struggling" for student in students},
        {student: SECTION_A for student in students},
        {student: ["2026-09-05"] for student in students},
        [f"{SECTION_A}#math.g4.decimals.tenths_hundredths#2026-09-06"],
    )
    assert justified_cohort_fires([row]) == [
        (1, f"{SECTION_A}#math.g4.decimals.tenths_hundredths#2026-09-06", 3, True)
    ]


def test_detector_noise_fires_never_justify_a_cohort_fire():
    students = ["stu01", "stu02", "stu03"]
    row = steady_row(
        students,
        {student: ["2026-09-05"] for student in students},
        [f"{SECTION_A}#math.g4.fractions.equivalence#2026-09-06"],
    )
    seed, _, families, justified = justified_cohort_fires([row])[0]
    assert (seed, families, justified) == (1, 0, False)


def test_measurement_correct_fires_count_toward_the_cohort_floor():
    students = ["stu01", "stu02", "stu03"]
    row = steady_row(
        students,
        {student: ["2026-09-05"] for student in students},
        [f"{SECTION_A}#math.g4.fractions.equivalence#2026-09-06"],
    )
    assert justified_cohort_fires([row], 0.99)[0][2:] == (3, True)


def test_fires_outside_the_window_do_not_count():
    students = ["stu01", "stu02", "stu03", "stu04"]
    fires = {
        "stu01": ["2026-09-02"],
        "stu02": ["2026-09-09"],
        "stu03": ["2026-09-01"],
        "stu04": ["2026-09-12"],
    }
    row = make_row(
        {student: "struggling" for student in students},
        {student: SECTION_A for student in students},
        fires,
        [f"{SECTION_A}#math.g4.fractions.equivalence#2026-09-09"],
    )
    assert justified_cohort_fires([row])[0][2:] == (2, False)


def test_repeat_fires_by_one_family_count_once():
    row = make_row(
        {"stu01": "struggling"},
        {"stu01": SECTION_A},
        {"stu01": ["2026-09-04", "2026-09-05", "2026-09-06"]},
        [f"{SECTION_A}#math.g4.fractions.equivalence#2026-09-07"],
    )
    assert justified_cohort_fires([row])[0][2:] == (1, False)


def test_fires_in_another_section_do_not_justify_the_signal():
    row = make_row(
        {"stu01": "struggling", "stu02": "struggling", "stu03": "struggling"},
        {"stu01": SECTION_A, "stu02": SECTION_A, "stu03": "colegio-demo-4-c"},
        {student: ["2026-09-05"] for student in ["stu01", "stu02", "stu03"]},
        [f"{SECTION_A}#math.g4.fractions.equivalence#2026-09-06"],
    )
    assert justified_cohort_fires([row])[0][2:] == (2, False)
