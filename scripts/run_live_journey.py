import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from repaso.config.models import ModelRole, model_for
from repaso.config.settings import Settings
from repaso.core.harness.clock import SimClock
from repaso.simulator.demo_scenario import START, run_demo_scenario, scenario_settings
from repaso.simulator.offline_services import assemble_services
from repaso.tools.call_ledger import load_ledger
from repaso.tools.cost_report import build_cost_report
from repaso.tools.cost_table import render_cost_report
from repaso.tools.llm import build_bedrock_model

LEDGER_NAME = "model_calls.jsonl"


def live_models(region: str) -> dict[ModelRole, object]:
    provider = Settings(aws_region=region, local_mode=False, live_tests=True)
    return {role: build_bedrock_model(model_for(role), provider) for role in ModelRole}


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_live_journey")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument(
        "--decision", choices=("teacher_note", "reduce_load"), default="teacher_note"
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if data_dir.exists() and any(data_dir.iterdir()):
        parser.error("data-dir must be empty; choose a new directory to preserve previous runs")

    settings = scenario_settings(data_dir).model_copy(
        update={"cassette_path": None, "call_ledger_path": data_dir / LEDGER_NAME}
    )
    services = assemble_services(settings, SimClock(START), live_models(args.region))
    result = asyncio.run(run_demo_scenario(settings, services, decision=args.decision))

    for beat in result.beats:
        print(f"{beat.name:60} {beat.expected:>24} {beat.actual:>24}  {beat.verdict}")
    print(f"\n{len(result.failures)} failed beat(s) of {len(result.beats)}")

    records = load_ledger(settings.call_ledger_path)
    print()
    print(render_cost_report(build_cost_report(records)))
    print(f"\nledger at {settings.call_ledger_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
