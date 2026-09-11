import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repaso.config.settings import Settings
from repaso.core.harness.clock import SystemClock
from tests.live.agreement import run_decision_probes
from tests.live.decisions import build_decision_probes
from tests.live.sweep import build_sweep_models

FILE_PREFIX = "decisions-"
FILE_SUFFIX = ".json"
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"
HEADER = f"{'decision':<46}{'model':<44}{'met':>7}{'wilson 95%':>18}{'p50 ms':>9}{'usd':>9}"


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_decision_probe")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--out-dir", default=".local_data/live")
    parser.add_argument("--models", nargs="+", required=True)
    args = parser.parse_args()

    clock = SystemClock()
    settings = Settings(aws_region=args.region, local_mode=False, live_tests=True)
    decisions = build_decision_probes()
    models = build_sweep_models(args.models, settings)
    report = asyncio.run(
        run_decision_probes(decisions, models, args.samples, clock, args.region)
    )

    directory = Path(args.out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = report.measured_at.strftime(TIMESTAMP_FORMAT)
    path = directory / f"{FILE_PREFIX}{stamp}{FILE_SUFFIX}"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print()
    print(HEADER)
    for cell in report.cells:
        print(
            f"{cell.decision:<46}{cell.model_id:<44}"
            f"{cell.met:>4}/{cell.calls:<2}"
            f"{f'[{cell.agreement.low:.3f}, {cell.agreement.high:.3f}]':>18}"
            f"{cell.p50_ms:>9.0f}{cell.estimated_usd:>9.4f}  {cell.answers}"
        )
    print(f"\n{report.calls} calls, ${report.total_usd:.4f}, written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
