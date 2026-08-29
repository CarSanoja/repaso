import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterator
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_seed_sweep import wilson

from repaso.simulator.archetypes import PROFILES, Archetype
from repaso.simulator.student_sim import ability_on_day

COHORT_START = date(2026, 9, 1)
LOW_ABILITY = {Archetype.STRUGGLING.value, Archetype.COHORT_CLUSTER.value}
CRITERION = 0.5
CRITERIA = (0.45, 0.50, 0.55)
CLUSTER_SECTION = "colegio-demo-4-b"
WINDOW_DAYS = 7
MIN_FAMILIES = 3
TRUE_POSITIVE = "true_positive"
MEASUREMENT_CORRECT = "measurement_correct"
DETECTOR_NOISE = "detector_noise"
STRUGGLE_KIND = "struggle_triage"

Fire = tuple[int, str, str, str, date]


def day_index(fired_on: date) -> int:
    return (fired_on - COHORT_START).days


def ability_at(archetype: str, fired_on: date) -> float:
    return ability_on_day(PROFILES[Archetype(archetype)], day_index(fired_on))


def classify_fire(archetype: str, fired_on: date, criterion: float = CRITERION) -> str:
    if archetype in LOW_ABILITY:
        return TRUE_POSITIVE
    if ability_at(archetype, fired_on) < criterion:
        return MEASUREMENT_CORRECT
    return DETECTOR_NOISE


def iter_fires(results: list[dict]) -> Iterator[Fire]:
    for row in results:
        for student, dates in row["struggle_fires"].items():
            for raw in dates:
                yield (
                    row["seed"], student, row["archetypes"][student],
                    row["sections"][student], date.fromisoformat(raw),
                )


def tally(results: list[dict], criterion: float) -> tuple[Counter, dict[str, Counter]]:
    totals: Counter = Counter()
    per_archetype: dict[str, Counter] = {}
    for _, _, archetype, _, fired_on in iter_fires(results):
        label = classify_fire(archetype, fired_on, criterion)
        totals[label] += 1
        per_archetype.setdefault(archetype, Counter())[label] += 1
    return totals, per_archetype


def adjusted_precision(totals: Counter) -> tuple[float, float, float]:
    credited = totals[TRUE_POSITIVE] + totals[MEASUREMENT_CORRECT]
    return wilson(credited, sum(totals.values()))


def credited_fires(row: dict, criterion: float) -> list[tuple[str, str, date]]:
    return [(section, student, fired_on)
            for _, student, archetype, section, fired_on in iter_fires([row])
            if classify_fire(archetype, fired_on, criterion) != DETECTOR_NOISE]


def justified_cohort_fires(
    results: list[dict], criterion: float = CRITERION
) -> list[tuple[int, str, int, bool]]:
    rows = []
    for row in results:
        credited = credited_fires(row, criterion)
        for signal in row["cohort_signals"]:
            section, _, raw = signal.split("#")
            if section == CLUSTER_SECTION:
                continue
            fired_on = date.fromisoformat(raw)
            families = {student for held_section, student, fire in credited
                        if held_section == section and 0 <= (fired_on - fire).days <= WINDOW_DAYS}
            rows.append((row["seed"], signal, len(families), len(families) >= MIN_FAMILIES))
    return rows


def residue_rows(results: list[dict], base_dir: str, criterion: float) -> list[dict]:
    rows, cache = [], {}
    for seed, student, archetype, section, fired_on in iter_fires(results):
        if classify_fire(archetype, fired_on, criterion) != DETECTOR_NOISE:
            continue
        if seed not in cache:
            root = Path(base_dir) / f"seed-{seed}" / "state"
            lines = (root / "grades.jsonl").read_text(encoding="utf-8").splitlines()
            cache[seed] = (
                json.loads((root / "escalations.json").read_text(encoding="utf-8")),
                [json.loads(line) for line in lines],
            )
        escalations, grades = cache[seed]
        stamp = fired_on.isoformat()
        competency = next(
            record["competency_id"] for record in escalations.values()
            if record["kind"] == STRUGGLE_KIND and record["student_id"] == student
            and record["created_at"].startswith(stamp)
        )
        seen = [g for g in grades if g["student_id"] == student and g["graded_at"][:10] <= stamp
                and g["item_id"].removeprefix("sim-").rsplit("-", 1)[0] == competency]
        rows.append({
            "seed": seed, "student": student, "archetype": archetype, "section": section,
            "competency": competency, "day_index": day_index(fired_on), "attempts": len(seen),
            "ability": ability_at(archetype, fired_on),
            "accuracy": sum(1 for g in seen if g["correct"]) / len(seen),
        })
    return rows


def _print_per_archetype(per_archetype: dict[str, Counter]) -> None:
    print(f"\n{'archetype':16} {'fires':>6} {'TP':>6} {'meas-ok':>8} "
          f"{'noise':>6} {'meas-ok rate':>13}")
    for archetype in sorted(per_archetype, key=lambda a: -sum(per_archetype[a].values())):
        counts = per_archetype[archetype]
        outside = counts[MEASUREMENT_CORRECT] + counts[DETECTOR_NOISE]
        rate = f"{counts[MEASUREMENT_CORRECT] / outside:.3f}" if outside else "-"
        print(f"{archetype:16} {sum(counts.values()):>6} {counts[TRUE_POSITIVE]:>6} "
              f"{counts[MEASUREMENT_CORRECT]:>8} {counts[DETECTOR_NOISE]:>6} {rate:>13}")


def _print_sensitivity(results: list[dict]) -> None:
    print(f"\n{'criterion':>9} {'meas-ok':>8} {'noise':>6} {'adjusted precision':>28}")
    for criterion in CRITERIA:
        totals, _ = tally(results, criterion)
        point, low, high = adjusted_precision(totals)
        band = f"{point:.3f} [{low:.3f}-{high:.3f}]"
        print(f"{criterion:>9.2f} {totals[MEASUREMENT_CORRECT]:>8} "
              f"{totals[DETECTOR_NOISE]:>6} {band:>28}")


def _print_cohort(results: list[dict], criterion: float) -> None:
    rows = justified_cohort_fires(results, criterion)
    justified = sum(1 for *_, ok in rows if ok)
    total_signals = sum(len(row["cohort_signals"]) for row in results)
    print(f"\ncohort signals: {total_signals} total, {total_signals - len(rows)} in "
          f"{CLUSTER_SECTION}, {len(rows)} outside")
    print(f"outside signals justified by ground truth: {justified}/{len(rows)}")
    spread = Counter(count for *_, count, _ in rows)
    for count in sorted(spread):
        print(f"  {count} credited families in the prior {WINDOW_DAYS}d: {spread[count]} signals")


def _print_residue(rows: list[dict]) -> None:
    print(f"\nresidue: {len(rows)} detector-noise fires from "
          f"{len({(row['seed'], row['student']) for row in rows})} distinct students; "
          f"competencies {sorted({row['competency'] for row in rows})}")
    print(f"{'seed':>9} {'student':>8} {'archetype':15} {'sec':>4} {'day':>4} "
          f"{'attempts':>9} {'accuracy':>9} {'ability':>8}")
    for row in sorted(rows, key=lambda r: (r["day_index"], r["attempts"], r["seed"])):
        print(f"{row['seed']:>9} {row['student']:>8} {row['archetype']:15} "
              f"{row['section'][-3:]:>4} {row['day_index']:>4} {row['attempts']:>9} "
              f"{row['accuracy']:>9.3f} {row['ability']:>8.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="score_fp_ground_truth")
    parser.add_argument("--results", default=".local_data/sweep/results.json")
    parser.add_argument("--criterion", type=float, default=CRITERION)
    parser.add_argument("--residue-dir")
    args = parser.parse_args()

    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    totals, per_archetype = tally(results, args.criterion)
    fires = sum(totals.values())
    outside = totals[MEASUREMENT_CORRECT] + totals[DETECTOR_NOISE]
    point, low, high = adjusted_precision(totals)
    raw = wilson(totals[TRUE_POSITIVE], fires)

    print(f"scored {fires} struggle fires across {len(results)} seeds "
          f"(criterion ability < {args.criterion:.2f})")
    print(f"  low-ability fires (TP): {totals[TRUE_POSITIVE]}   outside archetypes: {outside}")
    print(f"    measurement-correct: {totals[MEASUREMENT_CORRECT]}   "
          f"detector noise: {totals[DETECTOR_NOISE]}")
    print(f"\nper-fire precision (archetype ledger): {raw[0]:.3f} [{raw[1]:.3f}-{raw[2]:.3f}]")
    print(f"ground-truth-adjusted precision:       {point:.3f} [{low:.3f}-{high:.3f}]")
    _print_per_archetype(per_archetype)
    _print_sensitivity(results)
    _print_cohort(results, args.criterion)
    if args.residue_dir:
        _print_residue(residue_rows(results, args.residue_dir, args.criterion))
    return 0


if __name__ == "__main__":
    sys.exit(main())
