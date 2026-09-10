from scripts.answer_evaluation_scoring import AUTHOR_LABELS, is_automatic, score

CASES = [
    {
        "id": "a",
        "category": "clear_correct",
        "reference_correct": True,
        "reference_needs_review": False,
    },
    {
        "id": "b",
        "category": "ambiguous",
        "reference_correct": None,
        "reference_needs_review": True,
    },
]


def teacher(case_id: str, correct: bool, needs_review: bool) -> dict:
    return {
        "id": case_id,
        "reviewer": "t1",
        "independent": True,
        "correct": correct,
        "needs_review": needs_review,
    }


def test_a_verdict_under_the_threshold_survives_and_scores_at_a_lower_one():
    prediction = {"id": "a", "route": "graded", "correct": True, "confidence": 0.8}
    labels = [teacher("a", True, False)]
    held = score(CASES, [prediction], labels, 0.85)
    assert held["automatic_reviewed"] == 0 and held["coverage"] == 0
    assert held["grade_agreement"] is None
    admitted = score(CASES, [prediction], labels, 0.7)
    assert admitted["automatic_reviewed"] == 1 and admitted["grade_agreement"] == 1.0
    assert admitted["coverage"] == 0.5 and admitted["threshold"] == 0.7


def test_a_screened_or_failed_answer_is_never_an_automatic_decision():
    screened = {"id": "b", "route": "screened", "correct": None, "confidence": None}
    failed = {"id": "a", "route": "call_failed", "correct": None, "confidence": 0.0}
    errored = {"id": "a", "route": "graded", "correct": True, "confidence": 1.0, "error": "X"}
    assert not any(is_automatic(row, 0.0) for row in (screened, failed, errored))
    report = score(CASES, [screened, failed], [teacher("b", True, True)], 0.0)
    assert report["coverage"] == 0 and report["review_agreement"] == 1.0


def test_the_band_below_the_threshold_reports_the_verdicts_it_holds():
    predictions = [
        {"id": "a", "route": "graded", "correct": True, "confidence": 0.6},
        {"id": "b", "route": "graded", "correct": False, "confidence": 0.99},
    ]
    labels = [teacher("a", False, True), teacher("b", False, False)]
    bands = score(CASES, predictions, labels, 0.85)["confidence_bands"]
    low = next(band for band in bands if band["low"] == 0)
    high = next(band for band in bands if band["low"] == 0.95)
    assert low["reviewed"] == 1 and low["grade_agreement"] == 0.0
    assert high["reviewed"] == 1 and high["grade_agreement"] == 1.0


def test_author_labels_never_authorize_a_quality_claim():
    predictions = [
        {"id": "a", "route": "graded", "correct": True, "confidence": 0.99},
        {"id": "b", "route": "graded", "correct": False, "confidence": 0.99},
    ]
    report = score(CASES, predictions, [], 0.85, AUTHOR_LABELS)
    assert report["label_source"] == AUTHOR_LABELS
    assert report["scored"] == 2 and not report["quality_claim_allowed"]
    assert report["grade_scored"] == 1 and report["grade_agreement"] == 1.0
    assert report["review_agreement"] == 0.5


def test_the_sweep_trades_coverage_against_automatic_decisions():
    predictions = [
        {"id": "a", "route": "graded", "correct": True, "confidence": 0.9},
        {"id": "b", "route": "graded", "correct": True, "confidence": 0.8},
    ]
    sweep = score(CASES, predictions, [], 0.85, AUTHOR_LABELS)["threshold_sweep"]
    coverage = {row["threshold"]: row["coverage"] for row in sweep}
    assert coverage[0.7] == 1.0 and coverage[0.85] == 0.5 and coverage[0.95] == 0.0
    assert [row["coverage"] for row in sweep] == sorted(
        (row["coverage"] for row in sweep), reverse=True
    )
