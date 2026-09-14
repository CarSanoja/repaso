from types import SimpleNamespace as Row
from unittest.mock import Mock

from repaso.api.memory_learning import learning_topics, ref
from repaso.schemas.item import ItemKind


def test_topics_keep_learners_separate_and_disclose_repeated_content():
    item = Row(
        family_id="f1",
        competency_id="fractions",
        kind=ItemKind.MCQ,
        stem="Which is half?",
        options=["2/4", "1/4"],
    )
    foreign = Row(family_id="f2", competency_id="private", stem="PRIVATE")
    store = Mock()
    store.get_item.side_effect = lambda key: foreign if key == "foreign" else item
    students = [Row(id="a", alias="A"), Row(id="b", alias="B")]
    grades = [
        Row(student_id=s, item_id=i, quarantined=q, correct=c)
        for s, i, q, c in [
            ("a", "one", False, True),
            ("a", "copy", False, True),
            ("a", "held", True, False),
            ("a", "foreign", False, True),
            ("b", "one", False, False),
        ]
    ]
    notes = [
        {"student_ref": ref("a"), "competency_id": "fractions", "explained": v}
        for v in ["", "fold paper"]
    ]
    result = learning_topics(store, "f1", students, grades, notes, [], [])
    assert len(result) == 2
    a, b = result
    assert (a["assessed"], a["correct"], a["held"], a["distinct_contents"]) == (2, 2, 1, 1)
    assert a["repeated_attempts"] == 1
    assert a["explanations"] == 1
    assert a["mastery"] is None
    assert (b["assessed"], b["correct"], b["explanations"]) == (1, 0, 0)
    assert "PRIVATE" not in str(result)


def test_difficulty_coverage_and_current_mastery_are_not_a_learning_gain():
    store = Mock()
    store.get_item.side_effect = lambda key: Row(
        family_id="f1",
        competency_id="math.fractions",
        kind=ItemKind.MCQ,
        stem="Which is half?",
        options=["2/4", "1/4"],
        difficulty=2,
    )
    students = [Row(id="a", alias="A")]
    grades = [
        Row(student_id="a", item_id=i, quarantined=False, correct=True)
        for i in ["one", "copy", "third-copy"]
    ]
    mastery = [
        {
            "student_id": "a",
            "competency_id": "math.fractions",
            "ema_accuracy": 1.0,
            "attempts": 3,
            "level": "developing",
            "last_practiced_at": "2026-09-14T10:00:00+00:00",
        }
    ]
    row = learning_topics(store, "f1", students, grades, [], mastery, [])[0]
    assert row["difficulties"] == [
        {"level": 2, "assessed": 3, "correct": 3, "distinct_contents": 1}
    ]
    assert row["distinct_contents"] == 1
    assert row["repeated_attempts"] == 2
    assert len(row["contents"][0]["content_refs"]) == 3
    assert row["mastery"]["ema_accuracy"] == 1.0
    assert row["mastery_basis"] == "current_stored_estimate"
    assert row["improvement_demonstrated"] is None
    assert row["evidence"] == "limited"
    assert "not a measured learning gain" in row["summary"]
