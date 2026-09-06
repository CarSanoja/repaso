"""Validate a proposed set, or collect real predictions without exposing labels to the model."""

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from repaso.agents.grader import grade_open
from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.harness.clock import SystemClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.schemas.common import Lang
from repaso.schemas.grading import StudentResponse
from repaso.schemas.item import Item, ItemKind
from repaso.schemas.provenance import Provenance, Source
from repaso.tools.guardrails import LocalScreener
from repaso.tools.instrumented_model import InstrumentedModel
from repaso.tools.llm import build_model


def read_cases(path):
    cases = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not cases or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("case IDs must be nonempty and unique")
    required = {"question", "answer", "answer_key", "rubric", "category", "label_origin"}
    if any(not required <= c.keys() for c in cases):
        raise ValueError("incomplete evaluation case")
    return cases


def wilson(successes, count):
    if not count:
        return None
    from math import sqrt

    z = 1.96
    p = successes / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    half = z * sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return [max(0, center - half), min(1, center + half)]


def score(cases, predictions, labels):
    case_ids = {r["id"] for r in cases}
    eligible = {
        r["id"]: r
        for r in labels
        if r["id"] in case_ids
        and r.get("reviewer")
        and r.get("independent") is True
        and isinstance(r.get("correct"), bool)
        and isinstance(r.get("needs_review"), bool)
    }
    unique = {}
    duplicates = []
    for row in predictions:
        if row["id"] not in case_ids:
            continue
        if row["id"] in unique:
            duplicates.append(row["id"])
            continue
        unique[row["id"]] = row
    usable = [p for p in unique.values() if not p.get("error")]
    comparisons = [(p, eligible[p["id"]]) for p in usable if p["id"] in eligible]
    auto = [(p, r) for p, r in comparisons if not p["quarantined"]]
    auto_correct = [(p, r) for p, r in auto if p["correct"] is True]
    false_correct = sum(r["correct"] is False for _, r in auto_correct)

    def agreement(pairs, field, reference):
        return sum(p[field] == r[reference] for p, r in pairs) / len(pairs) if pairs else None

    report = {
        "cases": len(cases),
        "predictions": len(unique),
        "duplicate_prediction_ids": duplicates,
        "independently_reviewed": len(eligible),
        "scored": len(comparisons),
        "quality_claim_allowed": bool(cases) and len(comparisons) == len(cases) and not duplicates,
        "grade_agreement": agreement(auto, "correct", "correct"),
        "review_agreement": agreement(comparisons, "quarantined", "needs_review"),
        "coverage": sum(not p["quarantined"] for p in usable) / len(cases) if cases else 0,
        "automatic_reviewed": len(auto),
        "automatic_correct_reviewed": len(auto_correct),
        "false_automatic_correct": false_correct,
        "false_automatic_correct_rate": false_correct / len(auto_correct) if auto_correct else None,
        "false_automatic_correct_wilson_95": wilson(false_correct, len(auto_correct)),
        "errors": sum(bool(p.get("error")) for p in unique.values()),
    }
    report["by_category"] = {}
    for category in sorted({c["category"] for c in cases}):
        ids = {c["id"] for c in cases if c["category"] == category}
        pairs = [(p, r) for p, r in auto if p["id"] in ids]
        report["by_category"][category] = {
            "cases": len(ids),
            "automatic_reviewed": len(pairs),
            "grade_agreement": agreement(pairs, "correct", "correct"),
        }
    report["confidence_bands"] = []
    for low, high in [(0, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01)]:
        pairs = [
            (p, r)
            for p, r in comparisons
            if p.get("confidence") is not None and low <= p["confidence"] < high
        ]
        report["confidence_bands"].append(
            {
                "low": low,
                "high": min(high, 1),
                "reviewed": len(pairs),
                "grade_agreement": agreement(pairs, "correct", "correct"),
            }
        )
    return report


async def collect(cases, output, max_calls):
    import boto3

    os.environ["AWS_PROFILE"] = "quanta"
    session = boto3.Session(profile_name="quanta", region_name="us-east-1")
    if session.client("sts").get_caller_identity()["Account"] != "811479699647":
        raise ValueError("evaluation must stay in the authorized Quanta account")
    settings = Settings(local_mode=False, aws_region="us-east-1", local_data_dir=output.parent)
    model = InstrumentedModel(
        build_model(ModelRole.JUDGE, settings),
        "judge",
        LocalTelemetrySink(output.with_suffix(".telemetry.jsonl"), SystemClock()),
    )
    predictions = []
    for case in cases[:max_calls]:
        now = datetime.now(UTC)
        row = {"id": case["id"], "origin": "live", "at": now.isoformat()}
        try:
            if not LocalScreener().screen(case["answer"]).safe:
                row.update(correct=None, quarantined=True, confidence=None, route="screened")
            else:
                item = Item(
                    id=case["id"],
                    family_id="evaluation-synthetic",
                    kind=ItemKind.OPEN,
                    competency_id="math.g4.fractions.equivalence",
                    difficulty=2,
                    stem=case["question"],
                    answer_key=case["answer_key"],
                    rubric=case["rubric"],
                    rationale=case["answer_key"],
                    provenance=Provenance(source=Source.SIMULATED, created_at=now),
                )
                response = StudentResponse(
                    student_id="evaluation-synthetic",
                    item_id=item.id,
                    text=case["answer"],
                    latency_seconds=45,
                    received_at=now,
                )
                grade, _ = await grade_open(
                    item, response, Lang.ES, model, 0.85, now, "evaluation-synthetic"
                )
                row.update(
                    correct=grade.correct,
                    quarantined=grade.quarantined,
                    confidence=grade.confidence,
                    rubric_points=grade.rubric_points,
                )
        except Exception as error:
            row["error"] = type(error).__name__
        predictions.append(row)
        with output.open("a") as file:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
        if row.get("error"):
            break
    return predictions


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
    labels = [
        json.loads(line) for line in Path(args.labels).read_text().splitlines() if line.strip()
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.live and output.exists():
        parser.error("choose a new output to preserve previous evidence")
    predictions = (
        asyncio.run(collect(cases, output, args.max_calls))
        if args.live
        else (
            [
                json.loads(line)
                for line in Path(args.predictions).read_text().splitlines()
                if line.strip()
            ]
            if args.predictions
            else []
        )
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
