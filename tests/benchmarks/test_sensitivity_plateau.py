import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from sensitivity_grid import (
    GRIDS,
    default_points,
    default_points_agree,
    format_default_check,
    format_table,
    plateau_span,
    plateau_verdict,
    summarize,
)

COOLDOWN = "DEFAULT_COOLDOWN_DAYS"


def make_points(values, precisions, recalls):
    return [
        {"value": value, "precision": precision, "recall": recall,
         "p50": 50, "tp": 90, "fp": 10, "low": 90, "seeds": 10}
        for value, precision, recall in zip(values, precisions, recalls, strict=True)
    ]


def make_runs(param, tp_by_value):
    return [
        {"param": param, "value": value, "seed": 20260950 + index,
         "tp": tp, "fp": 1, "low": 9, "interrupts": 50}
        for value, tp in tp_by_value.items()
        for index in range(2)
    ]


def test_plateau_span_picks_the_widest_contiguous_run():
    grid = make_points(
        [1, 2, 3, 4, 5, 6], [0.90, 0.60, 0.89, 0.90, 0.88, 0.60], [1.0] * 6
    )
    assert plateau_span(grid) == (2, 4)


def test_plateau_span_breaks_on_the_recall_floor():
    grid = make_points([1, 2, 3], [0.90, 0.90, 0.90], [1.0, 0.90, 1.0])
    assert plateau_span(grid) == (0, 0)


def test_plateau_span_uses_the_precision_tolerance():
    grid = make_points([1, 2, 3], [0.90, 0.88, 0.80], [1.0] * 3)
    assert plateau_span(grid) == (0, 1)


def test_plateau_span_is_none_when_nothing_clears_the_floors():
    assert plateau_span(make_points([1, 2], [0.9, 0.9], [0.5, 0.4])) is None
    assert plateau_span([]) is None


def test_plateau_verdict_places_the_default():
    grid = make_points(GRIDS[COOLDOWN], [0.9] * 5, [1.0] * 5)
    assert "INSIDE (interior)" in plateau_verdict(COOLDOWN, grid, (0, 4))
    assert "INSIDE (edge)" in plateau_verdict(COOLDOWN, grid, (2, 4))
    assert "OUTSIDE" in plateau_verdict(COOLDOWN, grid, (0, 1))
    assert "NO PLATEAU" in plateau_verdict(COOLDOWN, grid, None)


def test_plateau_verdict_reports_the_span_endpoints_and_width():
    grid = make_points(GRIDS[COOLDOWN], [0.9] * 5, [1.0] * 5)
    verdict = plateau_verdict(COOLDOWN, grid, (1, 3))
    assert "plateau [5, 10]" in verdict
    assert "3/5 values" in verdict


def test_format_table_marks_plateau_rows_and_the_default():
    grid = make_points(GRIDS[COOLDOWN], [0.9] * 5, [1.0] * 5)
    lines = format_table(COOLDOWN, grid, (1, 3)).splitlines()
    assert lines[0] == "DEFAULT_COOLDOWN_DAYS  (5 values x 10 seeds)"
    assert lines[1].split() == ["value", "precision", "recall", "p50", "tp", "fp", "flag"]
    assert "plateau" not in lines[2]
    assert lines[4].split()[-2:] == ["plateau", "DEFAULT"]
    assert "0.900" in lines[4]
    assert "plateau" not in lines[6]


def test_summarize_pools_each_grid_point_in_grid_order():
    report = summarize(make_runs(COOLDOWN, dict.fromkeys(GRIDS[COOLDOWN], 9)), [COOLDOWN])
    points = report[COOLDOWN]["points"]
    assert [point["value"] for point in points] == GRIDS[COOLDOWN]
    assert points[0]["seeds"] == 2
    assert points[0]["tp"] == 18
    assert points[0]["recall"] == 1.0
    assert report[COOLDOWN]["span"] == [0, 4]


def test_summarize_leaves_a_grid_point_with_no_runs_empty():
    runs = [row for row in make_runs(COOLDOWN, dict.fromkeys(GRIDS[COOLDOWN], 9))
            if row["value"] != 14]
    points = summarize(runs, [COOLDOWN])[COOLDOWN]["points"]
    assert points[-1] == {"value": 14, "seeds": 0, "tp": 0, "fp": 0, "low": 0,
                          "precision": 0.0, "recall": 0.0, "p50": 0}


def test_default_points_picks_the_shipped_value_from_every_parameter():
    report = summarize(
        make_runs(COOLDOWN, dict.fromkeys(GRIDS[COOLDOWN], 9))
        + make_runs("escalation_min_samples", dict.fromkeys(GRIDS["escalation_min_samples"], 9)),
        [COOLDOWN, "escalation_min_samples"],
    )
    rows = default_points(report)
    assert [(row["param"], row["value"]) for row in rows] == [
        (COOLDOWN, 7), ("escalation_min_samples", 9)
    ]


def test_default_points_agree_detects_a_leaked_parameter():
    identical = [{"tp": 90, "fp": 10, "low": 90, "p50": 50} for _ in range(4)]
    assert default_points_agree(identical)
    assert default_points_agree([])
    leaked = [*identical[:3], {"tp": 88, "fp": 10, "low": 90, "p50": 50}]
    assert not default_points_agree(leaked)


def test_format_default_check_names_the_outcome_and_lists_every_row():
    rows = [
        {"param": COOLDOWN, "value": 7, "tp": 90, "fp": 10, "low": 90,
         "recall": 1.0, "p50": 50},
        {"param": "escalation_min_samples", "value": 8, "tp": 90, "fp": 10, "low": 90,
         "recall": 1.0, "p50": 50},
    ]
    text = format_default_check(rows)
    assert "(2 parameters): identical" in text
    assert len(text.splitlines()) == 3
    rows[1]["fp"] = 11
    assert "MISMATCH" in format_default_check(rows)
