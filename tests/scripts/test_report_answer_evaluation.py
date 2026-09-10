from scripts.report_answer_evaluation import collection_shape, dataset_shape, disagreements

CASES = [
    {
        "id": "a",
        "category": "clear_correct",
        "question": "¿Por qué?",
        "answer": "Multipliqué por 2.",
        "reference_correct": True,
        "reference_needs_review": False,
    },
    {
        "id": "b",
        "category": "ambiguous",
        "question": "¿Por qué?",
        "answer": "Se parecen.",
        "reference_correct": None,
        "reference_needs_review": True,
    },
    {
        "id": "c",
        "category": "clear_correct",
        "question": "¿Y esta?",
        "answer": "Multipliqué por 2.",
        "reference_correct": True,
        "reference_needs_review": False,
    },
]


def test_a_wrong_grade_and_a_wrong_hold_are_both_published():
    predictions = [
        {"id": "a", "route": "graded", "correct": False, "confidence": 0.99},
        {"id": "b", "route": "graded", "correct": False, "confidence": 0.99},
        {"id": "c", "route": "graded", "correct": True, "confidence": 0.99},
    ]
    found = {row["id"]: row for row in disagreements(CASES, predictions, 0.85)}
    assert set(found) == {"a", "b"}
    assert found["a"]["grade_disagreement"] and not found["a"]["review_disagreement"]
    assert found["b"]["review_disagreement"] and not found["b"]["grade_disagreement"]
    assert found["a"]["answer"] == "Multipliqué por 2." and found["a"]["model_correct"] is False


def test_repeated_answers_are_counted_as_repeated():
    shape = dataset_shape(CASES)
    assert shape["cases"] == 3 and shape["distinct_answers"] == 2
    assert shape["by_category"]["clear_correct"] == {"cases": 2, "distinct_answers": 1}


def test_the_collection_shape_separates_screened_rows_from_graded_ones():
    rows = [
        {"id": "a", "route": "graded", "confidence": 0.85},
        {"id": "b", "route": "screened", "confidence": None},
        {"id": "c", "route": "graded", "confidence": 0.85},
    ]
    shape = collection_shape(rows)
    assert shape["routes"] == {"graded": 2, "screened": 1} and shape["errors"] == 0
    assert shape["confidence_counts"] == {0.85: 2}
