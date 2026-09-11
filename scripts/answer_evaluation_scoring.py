"""Score saved predictions against labels, saying whose labels they are."""

from repaso.tools.proportion import wilson_interval

CONFIDENCE_BANDS = ((0, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01))
DEFAULT_THRESHOLD = 0.85
SWEEP_THRESHOLDS = tuple(round(0.70 + 0.01 * step, 2) for step in range(31))
GRADED = "graded"
AUTHOR_LABELS = "author-proposed"
TEACHER_LABELS = "independent-teacher"


def wilson(successes: int, count: int) -> list[float] | None:
    if not count:
        return None
    interval = wilson_interval(successes, count)
    return [interval.low, interval.high]


def is_automatic(prediction: dict, threshold: float) -> bool:
    if prediction.get("error") or prediction.get("route") != GRADED:
        return False
    confidence = prediction.get("confidence")
    return confidence is not None and confidence >= threshold


def author_labels(cases: list[dict]) -> dict[str, dict]:
    return {
        case["id"]: {
            "correct": case.get("reference_correct"),
            "needs_review": case.get("reference_needs_review"),
        }
        for case in cases
        if isinstance(case.get("reference_needs_review"), bool)
    }


def teacher_labels(cases: list[dict], labels: list[dict]) -> dict[str, dict]:
    case_ids = {case["id"] for case in cases}
    return {
        row["id"]: row
        for row in labels
        if row["id"] in case_ids
        and row.get("reviewer")
        and row.get("independent") is True
        and isinstance(row.get("needs_review"), bool)
    }


def eligible_labels(cases: list[dict], labels: list[dict], source: str) -> dict[str, dict]:
    if source == AUTHOR_LABELS:
        return author_labels(cases)
    return teacher_labels(cases, labels)


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


def graded_pairs(pairs: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
    return [(p, label) for p, label in pairs if isinstance(label.get("correct"), bool)]


def grade_agreement(pairs: list[tuple[dict, dict]]) -> float | None:
    return agreement([(p["correct"], label["correct"]) for p, label in graded_pairs(pairs)])


def decisions(pairs: list[tuple[dict, dict]]) -> dict:
    graded = graded_pairs(pairs)
    called_correct = [(p, label) for p, label in graded if p["correct"] is True]
    false_correct = sum(label["correct"] is False for _, label in called_correct)
    return {
        "automatic_reviewed": len(graded),
        "automatic_correct_reviewed": len(called_correct),
        "false_automatic_correct": false_correct,
        "false_automatic_correct_rate": (
            false_correct / len(called_correct) if called_correct else None
        ),
        "false_automatic_correct_wilson_95": wilson(false_correct, len(called_correct)),
        "grade_agreement": grade_agreement(graded),
    }


def at_threshold(
    cases: list[dict], usable: list[dict], comparisons: list[tuple[dict, dict]], threshold: float
) -> dict:
    automatic = [(p, label) for p, label in comparisons if is_automatic(p, threshold)]
    decided = sum(is_automatic(p, threshold) for p in usable)
    return {
        "threshold": threshold,
        "automatic_decisions": decided,
        "coverage": decided / len(cases) if cases else 0,
        "review_agreement": agreement(
            [(not is_automatic(p, threshold), label["needs_review"]) for p, label in comparisons]
        ),
    } | decisions(automatic)


def score(
    cases: list[dict],
    predictions: list[dict],
    labels: list[dict],
    threshold: float = DEFAULT_THRESHOLD,
    source: str = TEACHER_LABELS,
) -> dict:
    eligible = eligible_labels(cases, labels, source)
    unique, duplicates = unique_predictions(cases, predictions)
    usable = [p for p in unique.values() if not p.get("error")]
    comparisons = [(p, eligible[p["id"]]) for p in usable if p["id"] in eligible]
    report = {
        "cases": len(cases),
        "predictions": len(unique),
        "duplicate_prediction_ids": duplicates,
        "label_source": source,
        "labels_eligible": len(eligible),
        "scored": len(comparisons),
        "grade_scored": len(graded_pairs(comparisons)),
        "quality_claim_allowed": (
            source == TEACHER_LABELS
            and bool(cases)
            and len(graded_pairs(comparisons)) == len(cases)
            and not duplicates
        ),
        "errors": sum(bool(p.get("error")) for p in unique.values()),
    } | at_threshold(cases, usable, comparisons, threshold)
    report["by_category"] = {
        category: category_report(cases, comparisons, threshold, category)
        for category in sorted({case["category"] for case in cases})
    }
    report["confidence_bands"] = [
        band_report(comparisons, low, high) for low, high in CONFIDENCE_BANDS
    ]
    report["threshold_sweep"] = [
        at_threshold(cases, usable, comparisons, point) for point in SWEEP_THRESHOLDS
    ]
    return report


def category_report(
    cases: list[dict], comparisons: list[tuple[dict, dict]], threshold: float, category: str
) -> dict:
    ids = {case["id"] for case in cases if case["category"] == category}
    held = [(p, label) for p, label in comparisons if p["id"] in ids]
    pairs = [(p, label) for p, label in held if is_automatic(p, threshold)]
    return {
        "cases": len(ids),
        "scored": len(held),
        "automatic": len(pairs),
        "automatic_reviewed": len(graded_pairs(pairs)),
        "grade_agreement": grade_agreement(pairs),
        "review_agreement": agreement(
            [(not is_automatic(p, threshold), label["needs_review"]) for p, label in held]
        ),
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
        "reviewed": len(graded_pairs(pairs)),
        "grade_agreement": grade_agreement(pairs),
    }
