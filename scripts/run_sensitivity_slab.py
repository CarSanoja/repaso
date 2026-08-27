import argparse
import asyncio
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sensitivity_grid import CONSTANT_MODULES, LOW_ARCHETYPES, rebind_constant

MIN_SAMPLES = (8, 9, 10)
CEILINGS = (0.35, 0.40, 0.45)


def run_cell(job: tuple[int, float, int, int, str]) -> dict:
    min_samples, ceiling, seed, days, base_dir = job
    from repaso.config.settings import Settings

    rebind_constant("STRUGGLING_CEILING", ceiling, CONSTANT_MODULES["STRUGGLING_CEILING"])
    from repaso.simulator.demo_clock import run_demo_clock

    data_dir = Path(base_dir) / f"m{min_samples}-c{ceiling}-s{seed}"
    shutil.rmtree(data_dir, ignore_errors=True)
    settings = Settings(
        local_mode=True, local_data_dir=data_dir, escalation_min_samples=min_samples
    )
    try:
        result = asyncio.run(run_demo_clock(settings, days=days, seed=seed))
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)
    low = {m.student.id for m in result.ledger.members if m.archetype.value in LOW_ARCHETYPES}
    struggle = result.escalated_students.get("struggle_triage", set())
    return {
        "min_samples": min_samples, "ceiling": ceiling, "seed": seed,
        "low": len(low), "tp": len(struggle & low), "fp": len(struggle - low),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_sensitivity_slab")
    parser.add_argument("--seeds", type=int, default=15)
    parser.add_argument("--first-seed", type=int, default=20260950)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--base-dir", default=".local_data/slab")
    args = parser.parse_args()

    jobs = [
        (m, c, args.first_seed + s, 14, args.base_dir)
        for m in MIN_SAMPLES
        for c in CEILINGS
        for s in range(args.seeds)
    ]
    started = time.perf_counter()
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_cell, job) for job in jobs]
        for done, future in enumerate(as_completed(futures), start=1):
            rows.append(future.result())
            if done % 15 == 0 or done == len(jobs):
                eta = (time.perf_counter() - started) / done * (len(jobs) - done)
                print(f"progress {done}/{len(jobs)} eta {eta:.0f}s", flush=True)

    print(f"\nslab: {len(jobs)} runs in {time.perf_counter() - started:.0f}s")
    print(f"{'min_samples':>11} {'ceiling':>8} {'precision':>10} {'recall':>7} {'tp':>5} {'fp':>4}")
    for m in MIN_SAMPLES:
        for c in CEILINGS:
            cell = [r for r in rows if r["min_samples"] == m and r["ceiling"] == c]
            tp = sum(r["tp"] for r in cell)
            fp = sum(r["fp"] for r in cell)
            expected = sum(r["low"] for r in cell)
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / expected if expected else 0.0
            print(f"{m:>11} {c:>8.2f} {precision:>10.3f} {recall:>7.3f} {tp:>5} {fp:>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
