"""Aggregate observed pilot activity; never manufacture missing observations."""

import argparse
import csv
import json
from pathlib import Path
from statistics import median

COUNTS = [
    "scheduled",
    "received",
    "completed",
    "questions_answered",
    "quarantines",
    "decisions_completed",
    "material_rejections",
    "help_requests",
    "abandoned",
]
TIMES = ["preparation_minutes", "accompaniment_minutes", "review_minutes", "correction_minutes"]


def analyze(rows):
    seen = set()
    for row in rows:
        key = row["family_code"], row["day"], row["mode"]
        if not all(key) or key in seen or row["mode"] not in {"repaso", "manual"}:
            raise ValueError("unique observed family/day/mode required; simulations are excluded")
        seen.add(key)
        for name in COUNTS + TIMES + ["operator_minutes"]:
            if row[name] and float(row[name]) < 0:
                raise ValueError("negative observation")
    report = {
        "observations": len(rows),
        "families": len({r["family_code"] for r in rows}),
        "use_claim_allowed": bool(rows),
        "learning_effect_claim_allowed": False,
        "modes": {},
    }
    for mode in ["repaso", "manual"]:
        selected = [r for r in rows if r["mode"] == mode]
        data = {"observations": len(selected)}
        for key in COUNTS + ["operator_minutes"]:
            values = [float(r[key]) for r in selected if r[key] != ""]
            data[key] = {"sum": sum(values) if values else None, "observed": len(values)}
        minutes = [
            sum(float(r[k]) for k in TIMES) for r in selected if all(r[k] != "" for k in TIMES)
        ]
        data["adult_active_minutes"] = {
            "observed": len(minutes),
            "median": median(minutes) if minutes else None,
            "range": [min(minutes), max(minutes)] if minutes else None,
        }
        report["modes"][mode] = data
    # Paired family means keep families with more observation rows from dominating.
    paired = []
    for family in {r["family_code"] for r in rows}:
        means = {}
        for mode in ["manual", "repaso"]:
            values = [
                sum(float(r[k]) for k in TIMES)
                for r in rows
                if r["family_code"] == family
                and r["mode"] == mode
                and all(r[k] != "" for k in TIMES)
            ]
            if values:
                means[mode] = sum(values) / len(values)
        if len(means) == 2:
            paired.append(means["manual"] - means["repaso"])
    report["paired_families"] = len(paired)
    report["median_minutes_difference_manual_minus_repaso"] = median(paired) if paired else None
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("observations", type=Path)
    args = parser.parse_args()
    with args.observations.open() as handle:
        rows = list(csv.DictReader(handle))
    print(json.dumps(analyze(rows), indent=2))


if __name__ == "__main__":
    main()
