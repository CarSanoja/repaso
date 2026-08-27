import argparse
import asyncio
import json
import math
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _cohort_signals(store, members) -> list[str]:
    from repaso.schemas.escalation import EscalationKind

    section_by_family = {m.family.id: m.student.section_key for m in members}
    signals = set()
    for member in members:
        for escalation in store.list_escalations(member.family.id):
            if escalation.kind is not EscalationKind.COHORT_SIGNAL:
                continue
            section = section_by_family[escalation.family_id]
            fired_on = escalation.created_at.date().isoformat()
            signals.add(f"{section}#{escalation.competency_id}#{fired_on}")
    return sorted(signals)


def run_one(args: tuple[int, str]) -> dict:
    seed, base_dir = args
    from repaso.config.settings import Settings
    from repaso.simulator.demo_clock import run_demo_clock
    from repaso.simulator.verdicts import verdict_rows
    from repaso.tools.state_store import build_state_store

    data_dir = Path(base_dir) / f"seed-{seed}"
    shutil.rmtree(data_dir, ignore_errors=True)
    settings = Settings(local_mode=True, local_data_dir=data_dir)
    result = asyncio.run(run_demo_clock(settings, days=14, seed=seed))
    rows = verdict_rows(result)
    low = {
        m.student.id
        for m in result.ledger.members
        if m.archetype.value in {"struggling", "cohort_cluster"}
    }
    struggle = result.escalated_students.get("struggle_triage", set())
    interrupts = (
        sum(result.escalations_by_kind.values())
        + sum(result.quarantines_by_kind.values())
    )
    members = result.ledger.members
    return {
        "seed": seed,
        "verdicts": {case: verdict == "as expected" for case, _, _, verdict in rows},
        "tp": len(struggle & low),
        "fp": len(struggle - low),
        "low": len(low),
        "interrupts": interrupts,
        "archetypes": {m.student.id: m.archetype.value for m in members},
        "sections": {m.student.id: m.student.section_key for m in members},
        "struggle_fires": {
            student: [fired_on.isoformat() for fired_on in sorted(dates)]
            for student, dates in sorted(result.struggle_fires.items())
        },
        "cohort_signals": _cohort_signals(build_state_store(settings), members),
    }


def wilson(successes: int, total: int) -> tuple[float, float, float]:
    if total == 0:
        return (0.0, 0.0, 0.0)
    z = 1.96
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (p, max(0.0, centre - margin), min(1.0, centre + margin))


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_seed_sweep")
    parser.add_argument("--seeds", type=int, default=40)
    parser.add_argument("--first-seed", type=int, default=20260902)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--base-dir", default=".local_data/sweep")
    parser.add_argument("--out", default=".local_data/sweep/results.json")
    args = parser.parse_args()

    seeds = [args.first_seed + offset for offset in range(args.seeds)]
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run_one, [(seed, args.base_dir) for seed in seeds]))
    elapsed = time.perf_counter() - started

    cases = list(results[0]["verdicts"])
    print(f"sweep: {len(results)} held-out seeds in {elapsed:.0f}s\n")
    print(f"{'gate':64} pass-rate")
    for case in cases:
        passed = sum(1 for r in results if r["verdicts"][case])
        print(f"{case:64} {passed}/{len(results)}")

    tp = sum(r["tp"] for r in results)
    fp = sum(r["fp"] for r in results)
    expected = sum(r["low"] for r in results)
    precision = wilson(tp, tp + fp)
    recall = wilson(tp, expected)
    interrupts = sorted(r["interrupts"] for r in results)
    p50 = interrupts[len(interrupts) // 2]
    p95 = interrupts[max(0, math.ceil(len(interrupts) * 0.95) - 1)]
    random_precision = results[0]["low"] / 30

    print(f"\nstruggle precision: {precision[0]:.3f} [{precision[1]:.3f}-{precision[2]:.3f}]"
          f"  (tp={tp}, fp={fp})")
    print(f"struggle recall:    {recall[0]:.3f} [{recall[1]:.3f}-{recall[2]:.3f}]"
          f"  (expected={expected})")
    print(f"interrupts per 420 student-days: p50={p50} p95={p95}")
    print(f"baselines: never-interrupt recall=0.000 | "
          f"rate-matched random precision={random_precision:.3f}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"\nraw results: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
