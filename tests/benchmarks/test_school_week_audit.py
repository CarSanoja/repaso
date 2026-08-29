import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from run_school_week_audit import (
    CHECKPOINTS,
    DAYS,
    HOLIDAYS,
    LATENCY_GATE,
    RECALL_GATE,
    REST_WEEKDAYS,
    START,
    complete_recall_seeds,
    detection_row,
    latencies,
    percentile,
    recall_at,
    scheduled_index,
    school_day,
    spread,
)

SECTION_A = "colegio-demo-4-a"


def row(fired_on: date | None, archetype: str = "struggling") -> dict:
    return detection_row("stu11", archetype, SECTION_A, fired_on)


def run(*rows: dict) -> dict:
    return {"seed": 1, "students": list(rows)}


def test_the_term_opens_on_a_school_day():
    assert START == date(2026, 9, 1)
    assert school_day(START)
    assert scheduled_index(START) == 1


def test_a_weekend_adds_no_scheduled_days():
    assert scheduled_index(date(2026, 9, 4)) == 4
    assert scheduled_index(date(2026, 9, 6)) == 4


def test_carnaval_adds_no_scheduled_days():
    assert scheduled_index(date(2026, 9, 11)) == 9
    assert scheduled_index(date(2026, 9, 15)) == 9


def test_the_school_days_behind_the_low_ability_window():
    assert scheduled_index(date(2026, 9, 8)) == 6
    assert scheduled_index(date(2026, 9, 10)) == 8
    assert scheduled_index(date(2026, 9, 13)) == 9
    assert scheduled_index(date(2026, 9, 28)) == 13


def test_the_semana_santa_block_adds_no_scheduled_days():
    assert scheduled_index(date(2026, 9, 18)) == scheduled_index(date(2026, 9, 25))


def test_the_overlay_is_the_calendar_bench_overlay():
    assert REST_WEEKDAYS == (5, 6)
    assert date(2026, 9, 14) in HOLIDAYS and date(2026, 9, 15) in HOLIDAYS
    assert all(date(2026, 9, 21) + timedelta(days=offset) in HOLIDAYS for offset in range(5))
    assert school_day(date(2026, 9, 8))


def test_the_horizon_holds_23_school_days():
    assert scheduled_index(START + timedelta(days=DAYS - 1)) == 23
    assert CHECKPOINTS[-1] == DAYS


def test_an_undetected_student_carries_no_latency():
    assert row(None) == {
        "student": "stu11", "archetype": "struggling", "section": SECTION_A,
        "detected": False, "fired_on": None,
        "calendar_latency": None, "scheduled_latency": None,
    }


def test_a_detection_is_counted_in_both_units():
    detected = row(date(2026, 9, 8))
    assert detected["calendar_latency"] == 8
    assert detected["scheduled_latency"] == 6


def test_calendar_and_scheduled_latency_diverge_across_a_break():
    detected = row(date(2026, 9, 16))
    assert (detected["calendar_latency"], detected["scheduled_latency"]) == (16, 10)


def test_percentile_uses_nearest_rank():
    assert percentile([1, 2, 3, 4], 0.5) == 2
    assert percentile([1, 2, 3, 4], 0.9) == 4
    assert percentile([7], 0.5) == 7


def test_percentile_of_nothing_is_none():
    assert percentile([], 0.5) is None


def test_recall_at_counts_only_fires_inside_the_cutoff():
    rows = [row(date(2026, 9, 8)), row(date(2026, 10, 1)), row(None)]
    assert recall_at(rows, 14) == (1, 3)
    assert recall_at(rows, 42) == (2, 3)


def test_latencies_drop_the_students_that_were_never_found():
    rows = [row(date(2026, 9, 8)), row(None)]
    assert latencies(rows, "scheduled") == [6]
    assert latencies(rows, "calendar") == [8]


def test_spread_reports_zero_when_nothing_was_detected():
    assert spread([row(None)], "scheduled") == (0, 0, 0)


def test_spread_reports_p50_p90_and_max():
    rows = [row(date(2026, 9, offset)) for offset in (1, 2, 3, 4, 8)]
    assert spread(rows, "scheduled") == (3, 6, 6)


def test_a_seed_counts_only_when_every_low_ability_student_is_found():
    assert complete_recall_seeds([run(row(date(2026, 9, 8)), row(None))]) == 0
    assert complete_recall_seeds([run(row(date(2026, 9, 8)), row(date(2026, 9, 9)))]) == 1


def test_complete_recall_respects_the_cutoff():
    runs = [run(row(date(2026, 9, 8)), row(date(2026, 10, 1)))]
    assert complete_recall_seeds(runs, 14) == 0
    assert complete_recall_seeds(runs, DAYS) == 1


def test_the_declared_gates_are_the_reported_ones():
    assert (RECALL_GATE, LATENCY_GATE) == (0.95, 6)
    assert CHECKPOINTS == (14, 28, 42)
