"""Build the publication-safe evaluation artifact from a collected batch and its ledger."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from repaso.tools.call_ledger import load_ledger
from repaso.tools.cost_report import build_cost_report
from scripts.answer_evaluation_scoring import (
    AUTHOR_LABELS,
    DEFAULT_THRESHOLD,
    eligible_labels,
    is_automatic,
    score,
)
from scripts.run_answer_evaluation import read_cases, read_rows


def dataset_shape(cases: list[dict]) -> dict:
    categories = sorted({case["category"] for case in cases})
    return {
        "cases": len(cases),
        "distinct_questions": len({case["question"] for case in cases}),
        "distinct_answers": len({case["answer"] for case in cases}),
        "by_category": {
            category: {
                "cases": sum(case["category"] == category for case in cases),
                "distinct_answers": len(
                    {case["answer"] for case in cases if case["category"] == category}
                ),
            }
            for category in categories
        },
    }


def collection_shape(predictions: list[dict]) -> dict:
    routes = Counter(row.get("route", "error") for row in predictions)
    reported = Counter(row["confidence"] for row in predictions if row.get("confidence"))
    return {
        "predictions": len(predictions),
        "routes": dict(sorted(routes.items())),
        "errors": sum(bool(row.get("error")) for row in predictions),
        "confidence_counts": dict(sorted(reported.items())),
    }


def measured_spend(ledger: Path) -> dict:
    records = load_ledger(ledger)
    priced = [record for record in records if record.cost is not None]
    return {
        "ledger_calls": len(records),
        "live_calls": sum(record.measured for record in records),
        "model_ids": sorted({record.model_id for record in records}),
        "prompt_versions": sorted({record.prompt_version or "" for record in records}),
        "input_tokens": sum(record.usage.input_tokens for record in records if record.usage),
        "output_tokens": sum(record.usage.output_tokens for record in records if record.usage),
        "usd": round(sum(record.cost.total_usd for record in priced), 4),
        "calls_without_reported_usage": sum(record.usage is None for record in records),
        "latency_ms": [
            {"role": row.name, "calls": row.calls, "p50": row.p50_ms, "p95": row.p95_ms}
            for row in build_cost_report(records).latency
        ],
        "first_call_at": min(record.at for record in records).isoformat(),
        "last_call_at": max(record.at for record in records).isoformat(),
    }


def disagreements(cases: list[dict], predictions: list[dict], threshold: float) -> list[dict]:
    labels = eligible_labels(cases, [], AUTHOR_LABELS)
    by_id = {row["id"]: row for row in predictions}
    rows = []
    for case in cases:
        prediction = by_id.get(case["id"])
        if prediction is None or case["id"] not in labels:
            continue
        label = labels[case["id"]]
        automatic = is_automatic(prediction, threshold)
        held = not automatic
        wrong_grade = (
            automatic
            and isinstance(label["correct"], bool)
            and prediction.get("correct") is not label["correct"]
        )
        wrong_hold = held != label["needs_review"]
        if not (wrong_grade or wrong_hold):
            continue
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "answer": case["answer"],
                "model_correct": prediction.get("correct"),
                "model_confidence": prediction.get("confidence"),
                "model_rubric_points": prediction.get("rubric_points"),
                "decided_automatically": automatic,
                "author_correct": label["correct"],
                "author_needs_review": label["needs_review"],
                "grade_disagreement": wrong_grade,
                "review_disagreement": wrong_hold,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/answer_review_set.jsonl")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--split", default="development")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    cases = [c for c in read_cases(args.dataset) if c.get("split") == args.split]
    predictions = read_rows(args.predictions)
    artifact = {
        "split": args.split,
        "label_source": AUTHOR_LABELS,
        "label_origin": sorted({case["label_origin"] for case in cases}),
        "threshold": args.threshold,
        "dataset": dataset_shape(cases),
        "collection": collection_shape(predictions),
        "spend": measured_spend(Path(args.ledger)),
        "scoring": score(cases, predictions, [], args.threshold, AUTHOR_LABELS),
        "disagreements": disagreements(cases, predictions, args.threshold),
    }
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
    print(f"written to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
