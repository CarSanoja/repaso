"""Validate a proposed set, or collect real predictions without exposing labels to the model."""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from scripts.answer_evaluation_collect import collect
from scripts.answer_evaluation_scoring import score


def read_cases(path):
    cases = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not cases or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("case IDs must be nonempty and unique")
    required = {"question", "answer", "answer_key", "rubric", "category", "label_origin"}
    if any(not required <= c.keys() for c in cases):
        raise ValueError("incomplete evaluation case")
    return cases


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/answer_review_set.jsonl")
    parser.add_argument("--labels", default="evaluation/teacher_labels.jsonl")
    parser.add_argument("--output", default="private/reports/answer-evaluation.jsonl")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--predictions", help="Score a saved JSONL batch without model calls")
    parser.add_argument("--split", choices=("all", "development", "held_out"), default="all")
    parser.add_argument("--max-calls", type=int, default=15)
    args = parser.parse_args()
    if not 1 <= args.max_calls <= 60:
        parser.error("max-calls must be between 1 and 60")
    cases = read_cases(args.dataset)
    if args.split != "all":
        cases = [c for c in cases if c.get("split") == args.split]
    if args.live and args.predictions:
        parser.error("live collection and saved scoring are separate")
    labels = read_rows(args.labels)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.live and output.exists():
        parser.error("choose a new output to preserve previous evidence")
    predictions = (
        asyncio.run(collect(cases, output, args.max_calls, args.dataset, args.split))
        if args.live
        else (read_rows(args.predictions) if args.predictions else [])
    )
    report = score(cases, predictions, labels) | {
        "mode": "live"
        if args.live
        else ("saved scoring" if args.predictions else "schema validation"),
        "split": args.split,
        "at": datetime.now(UTC).isoformat(),
    }
    output.with_suffix(".summary.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 1 if any(p.get("error") for p in predictions) else 0


if __name__ == "__main__":
    raise SystemExit(main())
