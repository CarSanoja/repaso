from datetime import UTC, datetime

from repaso.schemas.channel import ChannelKind
from repaso.schemas.enrollment import EnrollmentProgress, EnrollmentStep
from repaso.schemas.family import Family
from repaso.schemas.mastery import MasteryState
from repaso.schemas.student import Student
from repaso.tools.state_store import build_state_store

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def make_family(family_id: str, chat_ref: str) -> Family:
    return Family(
        id=family_id,
        channel=ChannelKind.TELEGRAM,
        chat_ref=chat_ref,
        invite_code="PILOT1",
        created_at=NOW,
    )


def make_student(student_id: str, family_id: str) -> Student:
    return Student(
        id=student_id,
        family_id=family_id,
        alias="leo",
        grade=4,
        section_key="school-4-b",
        created_at=NOW,
    )


def test_list_families_returns_all(settings):
    store = build_state_store(settings)
    store.put_family(make_family("f1", "100"))
    store.put_family(make_family("f2", "200"))
    assert {family.id for family in store.list_families()} == {"f1", "f2"}


def test_enrollment_progress_round_trip_and_delete(settings):
    store = build_state_store(settings)
    progress = EnrollmentProgress(
        channel=ChannelKind.TELEGRAM, chat_ref="300", step=EnrollmentStep.ALIAS
    )
    store.put_enrollment(progress)
    loaded = store.get_enrollment(ChannelKind.TELEGRAM, "300")
    assert loaded.step is EnrollmentStep.ALIAS
    store.delete_enrollment(ChannelKind.TELEGRAM, "300")
    assert store.get_enrollment(ChannelKind.TELEGRAM, "300") is None


def test_forget_family_erases_every_trace(settings):
    store = build_state_store(settings)
    family = make_family("f1", "100")
    store.put_family(family)
    store.put_family(make_family("f2", "200"))
    store.put_student(make_student("s1", "f1"))
    store.put_mastery(
        MasteryState(
            student_id="s1", competency_id="c1", ema_accuracy=0.5, attempts=4, correct=2
        )
    )
    store.put_enrollment(EnrollmentProgress(channel=ChannelKind.TELEGRAM, chat_ref="100"))
    store.forget_family("f1")
    assert store.get_family("f1") is None
    assert store.get_student("s1") is None
    assert store.list_mastery("s1") == []
    assert store.get_enrollment(ChannelKind.TELEGRAM, "100") is None
    assert store.find_family_by_chat(ChannelKind.TELEGRAM, "100") is None
    assert store.get_family("f2") is not None
