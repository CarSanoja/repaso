from datetime import UTC, datetime, timedelta

from repaso.schemas.episode import AttemptEpisode
from repaso.schemas.grading import GradedBy
from repaso.tools.episode_log import episode_key, list_attempts, record_attempt
from repaso.tools.state_store import build_state_store

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


def episode(
    item_id: str = "i1",
    student_id: str = "s1",
    correct: bool | None = True,
    minutes: int = 0,
    held: bool = False,
) -> AttemptEpisode:
    return AttemptEpisode(
        student_id=student_id,
        session_id="sess1",
        competency_id="math.g4.fractions.equivalence",
        item_id=item_id,
        correct=correct,
        held=held,
        graded_by=GradedBy.DETERMINISTIC,
        latency_seconds=20.0,
        occurred_at=START + timedelta(minutes=minutes),
    )


def test_an_episode_carries_no_word_the_child_wrote():
    assert set(AttemptEpisode.model_fields) == {
        "student_id",
        "session_id",
        "competency_id",
        "item_id",
        "correct",
        "held",
        "graded_by",
        "latency_seconds",
        "occurred_at",
    }


def test_attempts_come_back_in_the_order_they_happened(settings):
    store = build_state_store(settings)
    record_attempt(store, "f1", episode("i3", minutes=20))
    record_attempt(store, "f1", episode("i1", minutes=0))
    record_attempt(store, "f1", episode("i2", minutes=10))

    assert [e.item_id for e in list_attempts(store, "f1", "s1")] == ["i1", "i2", "i3"]


def test_writing_the_same_attempt_twice_leaves_one_row(settings):
    store = build_state_store(settings)
    record_attempt(store, "f1", episode("i1"))
    record_attempt(store, "f1", episode("i1"))

    assert len(list_attempts(store, "f1", "s1")) == 1
    assert len(store.list_records("f1", "episode#")) == 1


def test_one_student_never_reads_another_students_attempts(settings):
    store = build_state_store(settings)
    record_attempt(store, "f1", episode("i1", student_id="s1"))
    record_attempt(store, "f1", episode("i1", student_id="s2"))

    assert [e.student_id for e in list_attempts(store, "f1", "s1")] == ["s1"]
    assert [e.student_id for e in list_attempts(store, "f1", "s2")] == ["s2"]


def test_the_key_sorts_by_student_then_by_when_it_happened():
    assert episode_key(episode("i1")).startswith("episode#s1#2026-09-01T19:00:00+00:00#")
    assert episode_key(episode("i1", minutes=0)) < episode_key(episode("i1", minutes=1))


def test_a_held_answer_is_recorded_as_neither_right_nor_wrong(settings):
    store = build_state_store(settings)
    record_attempt(store, "f1", episode("i1", correct=None, held=True))

    held = list_attempts(store, "f1", "s1")[0]
    assert held.correct is None
    assert held.held is True
