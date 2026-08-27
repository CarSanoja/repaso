import argparse
import asyncio
import json
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from sensitivity_grid import (
    GRIDS,
    LOW_ARCHETYPES,
    SETTINGS_FIELDS,
    apply_constants,
    default_points,
    format_default_check,
    format_table,
    job_data_dir,
    summarize,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def run_one(job: tuple[str, float, int, int, str]) -> dict:
    param, value, seed, days, base_dir = job
    from repaso.config.settings import Settings

    apply_constants(param, value)
    from repaso.simulator.demo_clock import run_demo_clock

    data_dir = job_data_dir(base_dir, param, value, seed)
    shutil.rmtree(data_dir, ignore_errors=True)
    settings = Settings(
        local_mode=True,
        local_data_dir=data_dir,
        **({param: value} if param in SETTINGS_FIELDS else {}),
    )
    try:
        result = asyncio.run(run_demo_clock(settings, days=days, seed=seed))
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)
    low = {m.student.id for m in result.ledger.members if m.archetype.value in LOW_ARCHETYPES}
    struggle = result.escalated_students.get("struggle_triage", set())
    interrupts = sum(result.escalations_by_kind.values()) + sum(result.quarantines_by_kind.values())
    return {
        "param": param, "value": value, "seed": seed, "low": len(low),
        "tp": len(struggle & low), "fp": len(struggle - low), "interrupts": interrupts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="run_sensitivity")
    parser.add_argument("--seeds", type=int, default=15)
    parser.add_argument("--first-seed", type=int, default=20260950)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--params", nargs="*", default=list(GRIDS))
    parser.add_argument("--base-dir", default=".local_data/sensitivity")
    parser.add_argument("--out", default=".local_data/sensitivity/results.json")
    return parser.parse_args()


def execute(jobs: list[tuple], workers: int) -> tuple[list[dict], float]:
    started = time.perf_counter()
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, job) for job in jobs]
        for done, future in enumerate(as_completed(futures), start=1):
            rows.append(future.result())
            if done % workers == 0 or done == len(jobs):
                eta = (time.perf_counter() - started) / done * (len(jobs) - done)
                print(f"progress {done}/{len(jobs)} eta {eta:.0f}s", flush=True)
    return rows, time.perf_counter() - started


def main() -> int:
    args = parse_args()
    seeds = [args.first_seed + offset for offset in range(args.seeds)]
    jobs = [
        (param, value, seed, args.days, args.base_dir)
        for param in args.params
        for value in GRIDS[param]
        for seed in seeds
    ]
    rows, elapsed = execute(jobs, args.workers)

    report = summarize(rows, args.params)
    print(f"\nsensitivity: {len(jobs)} runs in {elapsed:.0f}s\n")
    for param in args.params:
        print(format_table(param, report[param]["points"], report[param]["span"]))
        print(report[param]["verdict"], "\n")
    print(format_default_check(default_points(report)))

    payload = {"elapsed_seconds": elapsed, "seeds": seeds, "report": report, "runs": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\nraw results: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
