from scripts.analyze_pilot import COUNTS, TIMES, analyze
from scripts.answer_evaluation_scoring import score
from scripts.run_answer_evaluation import read_cases


def test_proposed_or_incomplete_labels_cannot_be_reported_as_independent_quality():
    cases = read_cases("evaluation/answer_review_set.jsonl")
    prediction = {"id": cases[0]["id"], "correct": True, "route": "graded", "confidence": 0.99}
    label = {
        "id": cases[0]["id"],
        "reviewer": "teacher",
        "independent": False,
        "correct": True,
        "needs_review": False,
    }
    assert score(cases, [prediction], [label])["scored"] == 0
    label["independent"] = True
    label["correct"] = None
    assert score(cases, [prediction], [label])["scored"] == 0
    label["correct"] = False
    result = score(cases, [prediction, prediction], [label])
    assert result["scored"] == 1 and result["false_automatic_correct"] == 1
    assert not result["quality_claim_allowed"]
    assert result["false_automatic_correct_wilson_95"][0] > 0


def test_empty_pilot_does_not_imply_zero_work_or_observed_users():
    empty = analyze([])
    assert empty["families"] == 0 and not empty["use_claim_allowed"]
    assert empty["modes"]["repaso"]["adult_active_minutes"]["median"] is None
    row = {key: "" for key in COUNTS + TIMES + ["operator_minutes"]}
    row.update(family_code="F01", day="1", mode="repaso")
    missing = analyze([row])
    assert missing["modes"]["repaso"]["received"] == {"sum": None, "observed": 0}
