import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from repaso.simulator.demo_cost import cost_line
from repaso.simulator.demo_provenance import replay_note
from repaso.simulator.demo_scenario import (
    CASSETTE_PATH,
    run_demo_scenario,
    scenario_settings,
)
from repaso.simulator.demo_transcript import render
from repaso.simulator.run_directory import MUST_BE_EMPTY, occupied
from repaso.tools.cassette import load_cassette
from repaso.tools.cassette_cost import cassette_spend
from repaso.tools.cassette_provenance import load_provenance, provenance_path

LEGEND = (
    "Everything below happens in one Telegram chat, Carla's. Sofi has no account of "
    "her own:\nthe practice lands in her mother's chat and they do it together, which "
    "is why the child's\nanswers are typed from the same phone. Buttons are drawn in "
    "brackets, and the lines that\nstart with an arrow are the harness reading itself "
    "after each answer."
)


def record(result, decision: str) -> dict:
    return {
        **asdict(result),
        "origin": "recorded replay",
        "live_inference": False,
        "decision": decision,
        "passed": not result.failures,
        "checks": len(result.beats),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_demo_scenario")
    parser.add_argument("--data-dir", default=".local_data/demo_scenario")
    parser.add_argument("--cassette", default=str(CASSETTE_PATH))
    parser.add_argument(
        "--decision", choices=("teacher_note", "reduce_load"), default="teacher_note"
    )
    parser.add_argument("--report", help="Write the complete synthetic journey as JSON")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    cassette = Path(args.cassette)
    if occupied(data_dir):
        parser.error(MUST_BE_EMPTY)
    settings = scenario_settings(data_dir, cassette)

    started = time.perf_counter()
    result = asyncio.run(run_demo_scenario(settings, decision=args.decision))
    elapsed = time.perf_counter() - started

    print(LEGEND)
    print()
    for entry in result.transcript:
        for line in render(entry):
            print(line)
    print()
    print(cost_line(cassette_spend(load_cassette(cassette))))
    print(replay_note(load_provenance(provenance_path(cassette))))
    print(f"one family, four labeled school days, simulated in {elapsed:.1f}s into {data_dir}")
    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        payload = record(result, args.decision)
        report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print()
    print(f"{'beat':56} {'expected':>24} {'actual':>24}  verdict")
    for beat in result.beats:
        print(f"{beat.name:56} {beat.expected:>24} {beat.actual:>24}  {beat.verdict}")
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
