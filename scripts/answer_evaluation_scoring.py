"""Score saved predictions against completed labels; never invent a comparison."""

from math import sqrt

CONFIDENCE_BANDS = ((0, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01))


def wilson(successes: int, count: int) -> list[float] | None:
    if not count:
        return None
    z = 1.96
    p = successes / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    half = z * sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return [max(0, center - half), min(1, center + half)]


def score(cases: list[dict], predictions: list[dict], labels: list[dict]) -> dict:
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
    for low, high in CONFIDENCE_BANDS:
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
