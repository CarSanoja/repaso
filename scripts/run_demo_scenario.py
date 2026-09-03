import argparse
import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from repaso.simulator.demo_cost import cost_line, token_totals
from repaso.simulator.demo_scenario import (
    CASSETTE_PATH,
    run_demo_scenario,
    scenario_settings,
)
from repaso.simulator.demo_transcript import render
from repaso.tools.cassette import load_cassette

LEGEND = (
    "Everything below happens in one Telegram chat, Carla's. Sofi has no account of "
    "her own:\nthe practice lands in her mother's chat and they do it together, which "
    "is why the child's\nanswers are typed from the same phone. Buttons are drawn in "
    "brackets, and the lines that\nstart with an arrow are the harness reading itself "
    "after each answer."
)
PROVENANCE = (
    "The model outputs come from an authored cassette, not from a live recording: the "
    "token\ncounts are the ones the cassette declares, and nothing left this machine."
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_demo_scenario")
    parser.add_argument("--data-dir", default=".local_data/demo_scenario")
    parser.add_argument("--cassette", default=str(CASSETTE_PATH))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    cassette = Path(args.cassette)
    shutil.rmtree(data_dir, ignore_errors=True)
    settings = scenario_settings(data_dir, cassette)

    started = time.perf_counter()
    result = asyncio.run(run_demo_scenario(settings))
    elapsed = time.perf_counter() - started

    print(LEGEND)
    print()
    for entry in result.transcript:
        for line in render(entry):
            print(line)
    print()
    print(cost_line(token_totals(load_cassette(cassette))))
    print(PROVENANCE)
    print(f"one family, one school day, replayed in {elapsed:.1f}s into {data_dir}")
    print()
    print(f"{'beat':56} {'expected':>24} {'actual':>24}  verdict")
    for beat in result.beats:
        print(f"{beat.name:56} {beat.expected:>24} {beat.actual:>24}  {beat.verdict}")
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main())
