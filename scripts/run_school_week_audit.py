import argparse
import asyncio
import json
import math
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from calendar_scoring import HOLIDAYS, REST_WEEKDAYS, START, school_day
from run_seed_sweep import wilson

DAYS = 42
LOW_ABILITY = ("struggling", "cohort_cluster")
CLUSTER_SECTION = "colegio-demo-4-b"
RECALL_GATE = 0.95
LATENCY_GATE = 6
CHECKPOINTS = (14, 28, 42)
COHORT_LABEL = "cohort-4-b"


def scheduled_index(day: date) -> int:
    span = (day - START).days + 1
    return sum(1 for offset in range(span) if school_day(START + timedelta(days=offset)))


def detection_row(student: str, archetype: str, section: str, fired_on: date | None) -> dict:
    return {
        "student": student, "archetype": archetype, "section": section,
        "detected": fired_on is not None, "fired_on": fired_on.isoformat() if fired_on else None,
        "calendar_latency": (fired_on - START).days + 1 if fired_on else None,
        "scheduled_latency": scheduled_index(fired_on) if fired_on else None,
    }


def percentile(values: list[int], quantile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(1, math.ceil(quantile * len(ordered))) - 1]


def recall_at(rows: list[dict], cutoff: int) -> tuple[int, int]:
    found = sum(1 for row in rows if row["detected"] and row["calendar_latency"] <= cutoff)
    return found, len(rows)


def latencies(rows: list[dict], unit: str) -> list[int]:
    return [row[f"{unit}_latency"] for row in rows if row["detected"]]


def spread(rows: list[dict], unit: str) -> tuple[int, int, int]:
    found = latencies(rows, unit)
    return (percentile(found, 0.5) or 0, percentile(found, 0.9) or 0, max(found, default=0))


def complete_recall_seeds(runs: list[dict], cutoff: int = DAYS) -> int:
    return sum(1 for run in runs
               if all(row["detected"] and row["calendar_latency"] <= cutoff
                      for row in run["students"]))


def student_rows(result) -> list[dict]:
    rows = []
    for member in result.ledger.members:
        if member.archetype.value not in LOW_ABILITY:
            continue
        fires = sorted(result.struggle_fires.get(member.student.id, []))
        rows.append(detection_row(
            member.student.id, member.archetype.value,
            member.student.section_key, fires[0] if fires else None,
        ))
    return rows


def cohort_row(store, result) -> dict:
    from repaso.schemas.escalation import EscalationKind

    section_by_family = {m.family.id: m.student.section_key for m in result.ledger.members}
    inside, outside = [], set()
    for member in result.ledger.members:
        for escalation in store.list_escalations(member.family.id):
            if escalation.kind is not EscalationKind.COHORT_SIGNAL:
                continue
            fired_on = escalation.created_at.date()
            section = section_by_family[escalation.family_id]
            if section == CLUSTER_SECTION:
                inside.append(fired_on)
            else:
                outside.add(f"{section}#{escalation.competency_id}#{fired_on.isoformat()}")
    row = detection_row(COHORT_LABEL, "cohort_cluster", CLUSTER_SECTION, min(inside, default=None))
    row["outside_signals"] = sorted(outside)
    return row


def run_one(args: tuple[int, str]) -> dict:
    seed, base_dir = args
    from repaso.config.settings import Settings
    from repaso.simulator.demo_clock import run_demo_clock
    from repaso.tools.state_store import build_state_store

    data_dir = Path(base_dir) / f"seed-{seed}"
    shutil.rmtree(data_dir, ignore_errors=True)
    settings = Settings(local_mode=True, local_data_dir=data_dir)
    started = time.perf_counter()
    result = asyncio.run(run_demo_clock(
        settings, days=DAYS, seed=seed, rest_weekdays=list(REST_WEEKDAYS),
        holiday_dates=list(HOLIDAYS), mask_scheduled=True,
    ))
    return {
        "seed": seed, "elapsed_seconds": round(time.perf_counter() - started, 1),
        "scheduled_days": result.scheduled_days, "responses": result.responses,
        "sessions_delivered": result.sessions_delivered, "students": student_rows(result),
        "cohort": cohort_row(build_state_store(settings), result),
    }


def _print_recall(rows: list[dict], runs: list[dict]) -> None:
    print(f"\nrecall curve over calendar time\n{'horizon':>8}{'school days':>13}"
          f"{'detected':>10}{'of':>5}{'recall':>9}{'95% CI':>18}{'seeds complete':>16}")
    for cutoff in CHECKPOINTS:
        found, total = recall_at(rows, cutoff)
        point, low, high = wilson(found, total)
        school = scheduled_index(START + timedelta(days=cutoff - 1))
        seeds = f"{complete_recall_seeds(runs, cutoff)}/{len(runs)}"
        print(f"{cutoff:>8}{school:>13}{found:>10}{total:>5}{point:>9.3f}"
              f"{f'[{low:.3f}-{high:.3f}]':>18}{seeds:>16}")


def _print_latency(rows: list[dict], cohort: list[dict]) -> None:
    print(f"\ndetection latency, term start = day 1, detected only\n{'signal':>15}{'n':>5}"
          f"{'never':>7}{'p50 sc':>8}{'p90 sc':>8}{'max sc':>8}{'p50 cal':>9}"
          f"{'p90 cal':>9}{'max cal':>9}")
    groups = [("struggle", rows), (COHORT_LABEL, cohort)]
    groups += [(name, [row for row in rows if row["archetype"] == name]) for name in LOW_ABILITY]
    for label, group in groups:
        cells = "".join(f"{value:>8}" for value in spread(group, "scheduled"))
        cells += "".join(f"{value:>9}" for value in spread(group, "calendar"))
        found = sum(1 for row in group if row["detected"])
        print(f"{label:>15}{found:>5}{len(group) - found:>7}{cells}")
    counted = Counter(latencies(rows, "scheduled"))
    cells = "".join(f"{day:>5}" for day in sorted(counted))
    print(f"\nstruggle detections by scheduled day\n{'day':>5}{cells}")
    print(f"{'n':>5}" + "".join(f"{counted[day]:>5}" for day in sorted(counted)))


def print_report(runs: list[dict], elapsed: float) -> None:
    rows = [row for run in runs for row in run["students"]]
    cohort = [run["cohort"] for run in runs]
    print(f"school-week audit: {len(runs)} held-out seeds x {DAYS} calendar days x 30 students"
          f" = {len(runs) * DAYS * 30:,} student-days in {elapsed:.0f}s")
    print(f"  {runs[0]['scheduled_days']} scheduled days, {runs[0]['sessions_delivered']}"
          f" sessions, {runs[0]['responses']} responses per run;"
          f" {len(rows)} low-ability students scored\n")
    found, total = recall_at(rows, DAYS)
    point, low, high = wilson(found, total)
    passed = "passed" if total and found / total >= RECALL_GATE else "FAILED"
    print(f"{'R  struggle recall within 42 calendar days':46}{'>= 95%':>11}"
          f"{found:>5}/{total:<4} {point:.3f} [{low:.3f}-{high:.3f}]  {passed}")
    median = spread(rows, "scheduled")[0]
    passed = "passed" if median and median <= LATENCY_GATE else "FAILED"
    print(f"{'L  median detection latency, detected only':46}{'<= 6 sched':>11}"
          f"{median:>5} {'':<23}{passed}")
    _print_recall(rows, runs)
    _print_latency(rows, cohort)
    print(f"\ncohort signals outside {CLUSTER_SECTION}: "
          f"{len({s for run in cohort for s in run['outside_signals']})}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_school_week_audit")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--first-seed", type=int, default=20261200)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--base-dir", default=".local_data/school_week")
    parser.add_argument("--out", default=".local_data/school_week/results.json")
    args = parser.parse_args()

    seeds = [args.first_seed + offset for offset in range(args.seeds)]
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        runs = list(pool.map(run_one, [(seed, args.base_dir) for seed in seeds]))
    print_report(runs, time.perf_counter() - started)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(runs, indent=1), encoding="utf-8")
    print(f"\nraw results: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
