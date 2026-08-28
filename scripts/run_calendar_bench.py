import argparse
import asyncio
import json
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from calendar_report import print_report
from calendar_scoring import (
    ARMS,
    DAYS,
    DISENGAGED,
    DROPOUT_DAY,
    HOLIDAYS,
    OUTAGE,
    OUTAGE_DROPOUT,
    REST_WEEKDAYS,
    START,
    cause_of,
    gaps_in,
    run_days,
    school_day,
    silent_run,
)

BLACKOUT: set[int] = set()


def _no_outage(*_args, **_kwargs) -> set:
    return set()


def install_outage() -> None:
    from repaso.simulator import demo_clock
    from repaso.simulator.student_sim import SimulatedAnswer

    if getattr(demo_clock.simulate_answer, "outage_installed", False):
        return
    responding = demo_clock.simulate_answer
    silent = SimulatedAnswer(text="", correct_intent=False, latency_seconds=0.0, responded=False)

    def outaged(seed, student_id, archetype, day, item):
        if not BLACKOUT:
            return responding(seed, student_id, archetype, day, item)
        if student_id == OUTAGE_DROPOUT and day == DROPOUT_DAY:
            return responding(seed, student_id, archetype, DROPOUT_DAY - 1, item)
        if day in BLACKOUT:
            return silent
        return responding(seed, student_id, archetype, day, item)

    outaged.outage_installed = True
    demo_clock.simulate_answer = outaged


def install_health(enabled: bool) -> None:
    from repaso.core.harness.calendar import outage_days
    from repaso.core.orchestration import quality_graph

    quality_graph.outage_days = outage_days if enabled else _no_outage


def engagement_alerts(settings, result) -> list[tuple[str, object]]:
    from repaso.schemas.escalation import EscalationKind
    from repaso.tools.state_store import build_state_store

    store = build_state_store(settings)
    alerts = set()
    for member in result.ledger.members:
        for escalation in store.list_escalations(member.family.id):
            if escalation.kind is EscalationKind.ENGAGEMENT and escalation.student_id:
                alerts.add((escalation.student_id, escalation.created_at.date()))
    return sorted(alerts)


def health_days(grades, members, arm: str) -> list[str]:
    from repaso.core.harness.calendar import outage_days

    if not ARMS[arm]["health"]:
        return []
    totals = Counter(
        grade.graded_at.date()
        for member in members
        for grade in grades.by_student(member.student.id)
    )
    configured = ARMS[arm]["overlay"] and ARMS[arm]["mask"]
    days = [day for day in run_days() if school_day(day)] if configured else run_days()
    return [day.isoformat() for day in sorted(outage_days(totals, days))]


def score(result, settings, arm: str) -> tuple[list[dict], list[dict], list[str]]:
    from repaso.tools.grade_log import build_grade_log

    overlay, masked, health = (ARMS[arm][key] for key in ("overlay", "mask", "health"))
    grades = build_grade_log(settings)
    answered = {
        member.student.id: {g.graded_at.date() for g in grades.by_student(member.student.id)}
        for member in result.ledger.members
    }
    archetypes = {member.student.id: member.archetype.value for member in result.ledger.members}
    false_alerts, detections, caught = [], [], set()
    for student_id, fired_on in engagement_alerts(settings, result):
        days = answered[student_id]
        if archetypes[student_id] == DISENGAGED:
            if student_id in caught:
                continue
            caught.add(student_id)
            detections.append({
                "student": student_id,
                "fired_on": fired_on.isoformat(),
                "latency": len(silent_run(fired_on, days, overlay, overlay)),
                "school_days": len(silent_run(fired_on, days, overlay)),
                "calendar_days": len(silent_run(fired_on, days, False)),
            })
            continue
        consumed = silent_run(fired_on, days, overlay and masked, overlay and health)
        false_alerts.append({
            "student": student_id,
            "fired_on": fired_on.isoformat(),
            "cause": cause_of(consumed, overlay),
            "gaps": gaps_in(silent_run(fired_on, days, False)) if overlay else [],
            "silent_days": len(consumed),
        })
    return false_alerts, detections, health_days(grades, result.ledger.members, arm)


def run_one(args: tuple[int, str, str]) -> dict:
    seed, base_dir, arm = args
    from repaso.config.settings import Settings
    from repaso.simulator.demo_clock import run_demo_clock
    from repaso.simulator.verdicts import verdict_rows

    overlay = ARMS[arm]["overlay"]
    BLACKOUT.clear()
    BLACKOUT.update({(day - START).days for day in OUTAGE} if overlay else set())
    install_outage()
    install_health(ARMS[arm]["health"])
    data_dir = Path(base_dir) / f"{arm}-{seed}"
    shutil.rmtree(data_dir, ignore_errors=True)
    settings = Settings(local_mode=True, local_data_dir=data_dir)
    started = time.perf_counter()
    result = asyncio.run(
        run_demo_clock(
            settings, days=DAYS, seed=seed,
            rest_weekdays=list(REST_WEEKDAYS) if overlay else [],
            holiday_dates=list(HOLIDAYS) if overlay else [],
            mask_scheduled=ARMS[arm]["mask"],
        )
    )
    false_alerts, detections, masked_days = score(result, settings, arm)
    return {
        "seed": seed,
        "arm": arm,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "students": result.students,
        "scheduled_days": result.scheduled_days,
        "sessions_delivered": result.sessions_delivered,
        "responses": result.responses,
        "dropouts": sum(1 for m in result.ledger.members if m.archetype.value == DISENGAGED),
        "false_alerts": false_alerts,
        "detections": detections,
        "health_days": masked_days,
        "verdicts": {
            case: verdict == "as expected" for case, _, _, verdict in verdict_rows(result)
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_calendar_bench")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--first-seed", type=int, default=20261100)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--base-dir", default=".local_data/calendar")
    parser.add_argument("--out", default=".local_data/calendar/results.json")
    args = parser.parse_args()

    seeds = [args.first_seed + offset for offset in range(args.seeds)]
    jobs = [(seed, args.base_dir, arm) for arm in ARMS for seed in seeds]
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run_one, jobs))
    elapsed = time.perf_counter() - started

    arms = {arm: [run for run in results if run["arm"] == arm] for arm in ARMS}
    print_report(arms, len(seeds), elapsed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"\nraw results: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
