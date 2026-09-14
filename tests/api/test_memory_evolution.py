from datetime import UTC, date, datetime
from types import SimpleNamespace as Row
from unittest.mock import Mock

from repaso.api.memory_evolution import learning_evolution
from repaso.api.memory_learning import ref
from repaso.schemas.escalation import EscalationKind, EscalationStatus
from repaso.schemas.item import ItemKind
from repaso.tools.grade_log import effective_grades


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def grade(key, item, when, student="a", correct=True, held=False, supersedes=None):
    return Row(
        id=key,
        item_id=item,
        student_id=student,
        correct=correct,
        quarantined=held,
        supersedes=supersedes,
        responded_at=at(when),
        graded_at=at("2026-09-14T12:00:00"),
    )


def setup():
    family = Row(id="f", timezone="America/Caracas")
    students = [Row(id=s, family_id="f", alias=s.upper()) for s in ("a", "b")]
    items = {
        key: Row(
            id=key,
            family_id="other" if key == "private" else "f",
            competency_id="fractions",
            kind=ItemKind.MCQ,
            difficulty=2,
            stem="Which is half?" if key in {"q1", "copy"} else key,
            options=["2/4", "1/4"],
        )
        for key in ["q1", "copy", "q2", "q3", "private"]
    }
    store = Mock()
    store.get_item.side_effect = items.get
    store.list_spaced.return_value = []
    return store, family, students


def aggregate(result, student=None, competency=None):
    return next(
        s
        for s in result["series"]
        if s["student_ref"] == (ref(student) if student else None)
        and s["competency_id"] == competency
    )


def test_daily_evidence_uses_response_date_local_timezone_effective_grades_and_full_history():
    store, family, students = setup()
    grades = effective_grades(
        [
            grade("baseline", "q1", "2026-08-01T12:00:00"),
            grade("old-verdict", "q1", "2026-09-13T23:30:00", correct=False),
            grade("replacement", "q1", "2026-09-13T23:30:00", supersedes="old-verdict"),
            grade("copy", "copy", "2026-09-14T01:30:00"),
            grade("different", "q2", "2026-09-14T12:00:00", correct=False),
            grade("held", "q3", "2026-09-14T12:00:00", held=True),
            grade("sibling", "q3", "2026-09-14T12:00:00", student="b"),
            grade("private-item", "private", "2026-09-14T12:00:00"),
            grade("private-student", "q1", "2026-09-14T12:00:00", student="foreign"),
        ]
    )
    # More than the episode preview's 32 notes must still count in the dashboard.
    notes = [
        {
            "id": str(i),
            "student_ref": ref("a"),
            "competency_id": "fractions",
            "intent": "explanation",
            "at": "2026-09-14T01:40:00+00:00",
            "explained": "paper" if i % 2 else "",
        }
        for i in range(40)
    ]
    result = learning_evolution(
        store, family, students, grades, notes, [], [], at("2026-09-14T14:00:00")
    )
    learner = aggregate(result, "a")
    yesterday, today = learner["days"][-2:]
    assert len(learner["days"]) == 30
    assert yesterday["date"] == "2026-09-13"
    assert (yesterday["assessed"], yesterday["correct"], yesterday["distinct_contents"]) == (
        2,
        2,
        1,
    )
    assert (yesterday["help_requests"], yesterday["explanations"]) == (40, 20)
    assert (today["assessed"], today["correct"], today["held"]) == (1, 0, 1)
    assert (
        today["cumulative_assessed"],
        today["cumulative_correct"],
        today["cumulative_distinct_contents"],
    ) == (4, 3, 2)
    assert learner["baseline"]["assessed"] == learner["baseline"]["distinct_contents"] == 1
    assert learner["summary"]["active_days"] == 3
    assert aggregate(result, "b")["summary"]["assessed"] == 1
    assert aggregate(result)["summary"]["assessed"] == 5
    assert aggregate(result, "a", "fractions")["summary"] == learner["summary"]
    assert result["mastery_history_available"] is False
    assert result["help_history_complete"] is False
    assert "private" not in str(result)


def test_stored_review_dates_and_adult_choices_require_family_and_student_ownership():
    store, family, students = setup()
    owned = Row(
        student_id="a", item_id="q1", due_date=date(2026, 9, 13), interval_days=1, repetitions=2
    )
    wrong_student = Row(
        student_id="b", item_id="q2", due_date=date(2026, 9, 15), interval_days=1, repetitions=2
    )
    foreign_item = Row(
        student_id="a",
        item_id="private",
        due_date=date(2026, 9, 15),
        interval_days=1,
        repetitions=2,
    )
    store.list_spaced.side_effect = lambda sid: (
        [owned, wrong_student, foreign_item] if sid == "a" else []
    )

    def decision(key, owner, student):
        return Row(
            id=key,
            family_id=owner,
            student_id=student,
            competency_id="fractions",
            kind=EscalationKind.STRUGGLE_TRIAGE,
            status=EscalationStatus.RESOLVED,
            chosen_option="reduce_load",
            created_at=at("2026-09-13T12:00:00"),
            resolved_at=at("2026-09-13T13:00:00"),
        )

    result = learning_evolution(
        store,
        family,
        students,
        [],
        [],
        [],
        [
            decision("own", "f", "a"),
            decision("foreign", "other", "a"),
            decision("wrong-student", "f", "foreign"),
            decision("family", "f", None),
        ],
        at("2026-09-14T14:00:00"),
    )
    learner = aggregate(result, "a")
    assert len(learner["next_reviews"]) == 1
    review = learner["next_reviews"][0]
    assert review["due_date"] == "2026-09-13"
    assert review["overdue"] is True
    assert review["source"] == "stored_spaced_review"
    assert len(learner["adult_decisions"]) == 1
    assert len(aggregate(result)["adult_decisions"]) == 2
    assert aggregate(result, "b")["adult_decisions"] == []
    assert aggregate(result, "b")["next_reviews"] == []
    assert "private" not in str(result)


def test_one_observed_day_is_not_presented_as_thirty_days_of_progress():
    store, family, students = setup()
    result = learning_evolution(
        store,
        family,
        students,
        [grade("one", "q1", "2026-09-14T12:00:00")],
        [],
        [],
        [],
        at("2026-09-14T14:00:00"),
    )
    learner = aggregate(result, "a")
    assert learner["history_status"] == "single_day"
    assert learner["summary"]["first_activity"] == "2026-09-14"
    assert learner["summary"]["last_activity"] == "2026-09-14"
    assert sum(d["active"] for d in learner["days"]) == 1
    assert all(d["cumulative_assessed"] == 0 for d in learner["days"][:-1])
    assert aggregate(result, "b")["history_status"] == "no_activity"
