import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from repaso.config.settings import Settings
from repaso.simulator.demo_clock import run_demo_clock, verdict_rows


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_demo_clock")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--data-dir", default=".local_data/demo_clock")
    args = parser.parse_args()

    settings = Settings(local_mode=True, local_data_dir=Path(args.data_dir))
    started = time.perf_counter()
    result = asyncio.run(run_demo_clock(settings, days=args.days, seed=args.seed))
    elapsed = time.perf_counter() - started

    student_days = result.days * result.students
    print(f"demo-clock: {result.students} students x {result.days} days "
          f"= {student_days} student-days in {elapsed:.1f}s (seed {args.seed})")
    print(f"sessions delivered: {result.sessions_delivered} | responses graded: {result.responses}")
    print(f"escalations: {dict(result.escalations_by_kind)}")
    print(f"quarantines: {dict(result.quarantines_by_kind)}")
    print(f"cohort signals: {result.cohort_signals}")
    print(f"retired items: {len(result.retired_items)}")
    print()
    print(f"{'case':64} {'expected':>9} {'actual':>7}  verdict")
    failures = 0
    for case, expected, actual, verdict in verdict_rows(result):
        print(f"{case:64} {expected:>9} {actual:>7}  {verdict}")
        if verdict != "as expected":
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
