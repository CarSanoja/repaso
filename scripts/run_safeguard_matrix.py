import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repaso.config.settings import Settings
from repaso.core.harness.clock import SystemClock
from repaso.tools.guardrails import SCREENER_ERROR_REASON, BedrockGuardrailsScreener
from repaso.tools.llm import build_bedrock_model
from scripts.distress_probe_arms import quiet_rows, reaching_rows, walk
from scripts.distress_probe_report import summarize


def reader_settings(args) -> Settings:
    if not args.guard_reader:
        return Settings(aws_region=args.region, local_mode=False)
    return Settings(
        aws_region=args.region,
        local_mode=False,
        guardrail_id=args.guardrail_id,
        guardrail_version=args.guardrail_version,
    )


def reached_the_guardrail(rows: list[dict]) -> None:
    broken = [row["text"] for row in rows if SCREENER_ERROR_REASON in row["guardrail_reasons"]]
    if broken:
        raise SystemExit(
            f"the screener never reached Bedrock on {len(broken)} lines, so nothing here "
            f"measures the guardrail; first was: {broken[0]}"
        )


async def collect(args) -> dict:
    os.environ["REPASO_AWS_REGION"] = args.region
    os.environ["REPASO_LOCAL_MODE"] = "false"
    settings = reader_settings(args)
    screener = BedrockGuardrailsScreener(args.guardrail_id, args.guardrail_version)
    arms = []
    for model_id in args.models:
        model = build_bedrock_model(model_id, settings)
        reaching = await walk(screener, model, reaching_rows(), args.samples)
        quiet = await walk(screener, model, quiet_rows(), args.samples)
        reached_the_guardrail(reaching + quiet)
        arms.append(
            {
                "model_id": model_id,
                "reader_call_carries_the_guardrail": args.guard_reader,
                "reaching": reaching,
                "quiet": quiet,
            }
        )
    return {
        "measured_at": SystemClock().now().isoformat(),
        "region": args.region,
        "guardrail_version": args.guardrail_version,
        "reader_call_carries_the_guardrail": args.guard_reader,
        "samples_per_line": args.samples,
        "arms": arms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_safeguard_matrix")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--guardrail-id", required=True)
    parser.add_argument("--guardrail-version", default="DRAFT")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--guard-reader", action="store_true")
    parser.add_argument("--out", type=Path, default=Path(".local_data/live/matrix.json"))
    args = parser.parse_args()

    report = asyncio.run(collect(args))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n".join(summarize(report)))
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
