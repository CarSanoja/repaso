import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repaso.config.pricing import configured_models
from repaso.config.settings import Settings
from repaso.core.harness.clock import SystemClock
from tests.live.calls import DEFAULT_TIMEOUT_SECONDS
from tests.live.matrix import build_matrix
from tests.live.registry import build_registry
from tests.live.sweep import build_cases, build_sweep_models, run_sweep
from tests.live.table import render_matrix

FILE_PREFIX = "matrix-"
FILE_SUFFIX = ".json"
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_model_matrix")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out-dir", default=".local_data/live")
    parser.add_argument("--models", nargs="*", default=sorted(configured_models()))
    parser.add_argument("--schemas", nargs="*", help="Limit the sweep to these schema names")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    clock = SystemClock()
    settings = Settings(aws_region=args.region, local_mode=False, live_tests=True)
    probes = build_registry()
    if args.schemas:
        probes = tuple(probe for probe in probes if probe.name in set(args.schemas))
    cases = build_cases(probes, args.models, args.samples)
    print(f"{len(cases)} calls: {len(probes)} schemas x {len(args.models)} models x {args.samples}")

    models = build_sweep_models(args.models, settings)
    rows = asyncio.run(run_sweep(cases, models, clock, args.concurrency, args.timeout))
    report = build_matrix(rows, args.samples, args.region, clock.now())

    directory = Path(args.out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = report.measured_at.strftime(TIMESTAMP_FORMAT)
    path = directory / f"{FILE_PREFIX}{stamp}{FILE_SUFFIX}"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print()
    print(render_matrix(report))
    print(f"written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
