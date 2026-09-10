"""Score saved predictions against completed labels; never invent a comparison."""

from math import sqrt

CONFIDENCE_BANDS = ((0, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01))
DEFAULT_THRESHOLD = 0.85
GRADED = "graded"


def wilson(successes: int, count: int) -> list[float] | None:
    if not count:
        return None
    z = 1.96
    p = successes / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    half = z * sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return [max(0, center - half), min(1, center + half)]


def is_automatic(prediction: dict, threshold: float) -> bool:
    if prediction.get("error") or prediction.get("route") != GRADED:
        return False
    confidence = prediction.get("confidence")
    return confidence is not None and confidence >= threshold


def eligible_labels(cases: list[dict], labels: list[dict]) -> dict[str, dict]:
    case_ids = {case["id"] for case in cases}
    return {
        row["id"]: row
        for row in labels
        if row["id"] in case_ids
        and row.get("reviewer")
        and row.get("independent") is True
        and isinstance(row.get("correct"), bool)
        and isinstance(row.get("needs_review"), bool)
    }


def unique_predictions(cases: list[dict], predictions: list[dict]) -> tuple[dict, list[str]]:
    case_ids = {case["id"] for case in cases}
    unique: dict[str, dict] = {}
    duplicates: list[str] = []
    for row in predictions:
        if row["id"] not in case_ids:
            continue
        if row["id"] in unique:
            duplicates.append(row["id"])
            continue
        unique[row["id"]] = row
    return unique, duplicates


def agreement(pairs: list[tuple]) -> float | None:
    return sum(left == right for left, right in pairs) / len(pairs) if pairs else None


def grade_agreement(pairs: list[tuple[dict, dict]]) -> float | None:
    return agreement([(p["correct"], label["correct"]) for p, label in pairs])


def decisions(pairs: list[tuple[dict, dict]]) -> dict:
    called_correct = [(p, label) for p, label in pairs if p["correct"] is True]
    false_correct = sum(label["correct"] is False for _, label in called_correct)
    return {
        "automatic_reviewed": len(pairs),
        "automatic_correct_reviewed": len(called_correct),
        "false_automatic_correct": false_correct,
        "false_automatic_correct_rate": (
            false_correct / len(called_correct) if called_correct else None
        ),
        "false_automatic_correct_wilson_95": wilson(false_correct, len(called_correct)),
        "grade_agreement": grade_agreement(pairs),
    }


def score(
    cases: list[dict],
    predictions: list[dict],
    labels: list[dict],
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    eligible = eligible_labels(cases, labels)
    unique, duplicates = unique_predictions(cases, predictions)
    usable = [p for p in unique.values() if not p.get("error")]
    comparisons = [(p, eligible[p["id"]]) for p in usable if p["id"] in eligible]
    automatic = [(p, label) for p, label in comparisons if is_automatic(p, threshold)]
    report = {
        "cases": len(cases),
        "predictions": len(unique),
        "duplicate_prediction_ids": duplicates,
        "independently_reviewed": len(eligible),
        "scored": len(comparisons),
        "threshold": threshold,
        "quality_claim_allowed": bool(cases) and len(comparisons) == len(cases) and not duplicates,
        "review_agreement": agreement(
            [(not is_automatic(p, threshold), label["needs_review"]) for p, label in comparisons]
        ),
        "coverage": (
            sum(is_automatic(p, threshold) for p in usable) / len(cases) if cases else 0
        ),
        "errors": sum(bool(p.get("error")) for p in unique.values()),
    } | decisions(automatic)
    report["by_category"] = {
        category: category_report(cases, automatic, category)
        for category in sorted({case["category"] for case in cases})
    }
    report["confidence_bands"] = [
        band_report(comparisons, low, high) for low, high in CONFIDENCE_BANDS
    ]
    return report


def category_report(cases: list[dict], automatic: list[tuple[dict, dict]], category: str) -> dict:
    ids = {case["id"] for case in cases if case["category"] == category}
    pairs = [(p, label) for p, label in automatic if p["id"] in ids]
    return {
        "cases": len(ids),
        "automatic_reviewed": len(pairs),
        "grade_agreement": grade_agreement(pairs),
    }


def band_report(comparisons: list[tuple[dict, dict]], low: float, high: float) -> dict:
    pairs = [
        (p, label)
        for p, label in comparisons
        if p.get("confidence") is not None and low <= p["confidence"] < high
    ]
    return {
        "low": low,
        "high": min(high, 1),
        "reviewed": len(pairs),
        "grade_agreement": grade_agreement(pairs),
    }
