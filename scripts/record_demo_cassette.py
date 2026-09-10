import argparse
import asyncio
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from repaso.simulator.demo_recording import (
    WHAT_THIS_IS,
    WHAT_THIS_IS_NOT,
    build_recording_services,
)
from repaso.simulator.demo_scenario import run_demo_scenario, scenario_settings
from repaso.simulator.demo_stage import Stage
from repaso.tools.call_ledger import ledger_path, load_ledger
from repaso.tools.cassette import load_cassette
from repaso.tools.cassette_provenance import (
    build_provenance,
    provenance_path,
    write_provenance,
)
from repaso.tools.cost_report import build_cost_report
from repaso.tools.cost_table import render_cost_report


def head_commit(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(prog="record_demo_cassette")
    parser.add_argument("--out", required=True, help="Where to write the recorded cassette")
    parser.add_argument("--data-dir", required=True, help="Empty directory for the run's state")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument(
        "--decision", choices=("teacher_note", "reduce_load"), default="teacher_note"
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    destination = Path(args.out)
    data_dir = Path(args.data_dir)
    if destination.exists():
        parser.error(f"{destination} exists; recording never overwrites a cassette")
    if data_dir.exists() and any(data_dir.iterdir()):
        parser.error("data-dir must be empty; choose a new directory to preserve previous runs")

    settings = scenario_settings(data_dir, destination)
    services = build_recording_services(settings, args.region, destination)
    stages: list[Stage] = []
    started = datetime.now(UTC)
    result = asyncio.run(
        run_demo_scenario(
            settings, services, decision=args.decision, stage_factory=_kept(stages)
        )
    )

    records = load_ledger(ledger_path(settings))
    entries = load_cassette(destination)
    provenance = build_provenance(
        cassette=destination,
        entries=entries,
        records=records,
        recorded_at=started,
        commit=head_commit(root),
        region=args.region,
        what_this_is=WHAT_THIS_IS,
        what_this_is_not=WHAT_THIS_IS_NOT,
    )
    write_provenance(provenance_path(destination), provenance)

    print(render_cost_report(build_cost_report(records)))
    print(f"recorded {provenance.entries} entries into {destination}")
    print(f"provenance written to {provenance_path(destination)}")
    print()
    print(f"{'beat':56} {'expected':>24} {'actual':>24}  verdict")
    for beat in result.beats:
        print(f"{beat.name:56} {beat.expected:>24} {beat.actual:>24}  {beat.verdict}")
    for rejection in stages[0].rejected:
        print(f"runtime rejection: {rejection}")
    return 0


def _kept(stages: list[Stage]):
    def factory(services) -> Stage:
        stage = Stage(services)
        stages.append(stage)
        return stage

    return factory


if __name__ == "__main__":
    raise SystemExit(main())
