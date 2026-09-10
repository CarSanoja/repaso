"""Freeze the item set, run the three arms against it, and score what each arm kept."""

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from ablation_generate import GRADE, collect_items, frozen_set
from ablation_items import FrozenSet, read_frozen, write_frozen
from ablation_report import build_report
from ablation_rows import Observation, observations, write_rows
from ablation_run import CapturingLedger, Review, review_item

from repaso.config.models import ModelRole, model_for
from repaso.config.settings import Settings
from repaso.core.harness.clock import SystemClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.simulator.demo_material import NOTEBOOK_TEXT
from repaso.tools.call_ledger import LocalCallLedger, load_ledger
from repaso.tools.cost_report import build_cost_report
from repaso.tools.instrumented_model import InstrumentedModel
from repaso.tools.llm import build_model

PROFILE = "quanta"
REGION = "us-east-1"
DEFAULT_ITEMS = 30
DEFAULT_SEEDS = (1, 2, 3)


def live_settings(data_dir: Path) -> Settings:
    if os.environ.setdefault("AWS_PROFILE", PROFILE) != PROFILE:
        raise ValueError(f"this run must use the {PROFILE} profile")
    return Settings(local_mode=False, aws_region=REGION, local_data_dir=data_dir)


def instrumented(role: ModelRole, settings: Settings, ledger, telemetry) -> InstrumentedModel:
    return InstrumentedModel(build_model(role, settings), role.value, telemetry, ledger=ledger)


def open_run(data_dir: Path, stamp: str) -> tuple[Settings, CapturingLedger, LocalTelemetrySink]:
    settings = live_settings(data_dir)
    ledger = CapturingLedger(LocalCallLedger(data_dir / f"model-calls-{stamp}.jsonl"))
    telemetry = LocalTelemetrySink(data_dir / f"telemetry-{stamp}.jsonl", SystemClock())
    return settings, ledger, telemetry


def spent(ledger: CapturingLedger) -> float:
    return build_cost_report(ledger.records()).total_usd


async def freeze(count: int, out: Path, data_dir: Path) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    settings, ledger, telemetry = open_run(data_dir, stamp)
    model = instrumented(ModelRole.GENERATE, settings, ledger, telemetry)
    now = datetime.now(UTC)
    items = await collect_items(model, model_for(ModelRole.GENERATE), count, now)
    write_frozen(out, frozen_set(items, model_for(ModelRole.GENERATE), now))
    print(f"froze {len(items)} items to {out}; generation spend ${spent(ledger):.4f}")


async def run(frozen: FrozenSet, seeds: list[int], transcript: Path, data_dir: Path, cap: float):
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    settings, ledger, telemetry = open_run(data_dir, stamp)
    judge = instrumented(ModelRole.JUDGE, settings, ledger, telemetry)
    probe = instrumented(ModelRole.PROBE, settings, ledger, telemetry)
    now = datetime.now(UTC)
    transcript.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    with transcript.open("w", encoding="utf-8") as handle:
        for seed in seeds:
            for number, item in enumerate(frozen.items, start=1):
                review = await review_item(
                    item,
                    seed,
                    NOTEBOOK_TEXT,
                    GRADE,
                    judge,
                    probe,
                    ledger,
                    now,
                    frozen.model_id,
                    repeat_critic=seed == seeds[0],
                )
                handle.write(review.model_dump_json() + "\n")
                handle.flush()
                usd = spent(ledger)
                print(f"seed {seed} item {number}/{len(frozen.items)} spend ${usd:.4f}", flush=True)
                if usd > cap:
                    raise RuntimeError(f"spend ${usd:.4f} passed the ${cap:.2f} cap")
    elapsed = (datetime.now(UTC) - started).total_seconds()
    print(f"wall clock {elapsed:.1f}s, ledger spend ${spent(ledger):.4f}")


def read_transcript(path: Path) -> list[Review]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Review.model_validate_json(line) for line in lines if line.strip()]


def analyze(frozen: FrozenSet, transcript: Path, rows_path: Path, report_path: Path) -> dict:
    reviews = read_transcript(transcript)
    items = {item.item_id: item for item in frozen.items}
    rows: list[Observation] = []
    for review in reviews:
        rows.extend(observations(review, items[review.item_id], frozen.label_source))
    write_rows(rows_path, rows)
    report = build_report(rows, reviews, frozen.items)
    report["model_ids"] = {
        "critic": model_for(ModelRole.JUDGE),
        "probe": model_for(ModelRole.PROBE),
        "item_generation": frozen.model_id,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def ledger_total(path: Path) -> float:
    return build_cost_report(load_ledger(path)).total_usd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--items", type=Path, default=Path("evaluation/ablation_items.json"))
    parser.add_argument("--count", type=int, default=DEFAULT_ITEMS)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument(
        "--transcript", type=Path, default=Path("evaluation/ablation_transcript.jsonl")
    )
    parser.add_argument(
        "--rows", type=Path, default=Path("evaluation/ablation_observations.csv")
    )
    parser.add_argument("--report", type=Path, default=Path("docs/evidence/probe-ablation.json"))
    parser.add_argument("--data-dir", type=Path, default=Path(".local_data/ablation"))
    parser.add_argument("--max-usd", type=float, default=4.0)
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()

    if args.freeze:
        asyncio.run(freeze(args.count, args.items, args.data_dir))
    if args.run:
        asyncio.run(
            run(read_frozen(args.items), args.seeds, args.transcript, args.data_dir, args.max_usd)
        )
    if args.analyze:
        report = analyze(read_frozen(args.items), args.transcript, args.rows, args.report)
        if args.ledger:
            report["ledger_usd"] = round(ledger_total(args.ledger), 6)
            args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(report["arms"], indent=2))


if __name__ == "__main__":
    main()
