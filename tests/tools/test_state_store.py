from datetime import UTC, date, datetime

import pytest

from repaso.schemas.channel import ChannelKind, MediaKind
from repaso.schemas.escalation import Escalation, EscalationKind, EscalationStatus
from repaso.schemas.family import Family
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.mastery import MasteryState
from repaso.schemas.material import Material
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.review import QuarantineItem, QuarantineKind, QuarantineStatus
from repaso.schemas.schedule import SpacedItemState
from repaso.schemas.session import PracticeSession
from repaso.schemas.student import Student
from repaso.tools.state_store import LocalStateStore, StateStore, build_state_store

NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
TODAY = date(2026, 9, 1)
PROVENANCE = Provenance(source=Source.SYSTEM, created_at=NOW)


@pytest.fixture
def store(settings) -> StateStore:
    return build_state_store(settings)


def make_family(family_id: str = "f1", chat_ref: str = "chat-1") -> Family:
    return Family(
        id=family_id,
        channel=ChannelKind.TELEGRAM,
        chat_ref=chat_ref,
        invite_code="INV-1",
        created_at=NOW,
    )


def make_student(student_id: str = "s1", family_id: str = "f1") -> Student:
    return Student(
        id=student_id,
        family_id=family_id,
        alias="Ana",
        grade=5,
        section_key="5A",
        created_at=NOW,
    )


def make_item(item_id: str = "i1", competency_id: str = "c1", status=ItemStatus.ACTIVE) -> Item:
    return Item(
        id=item_id,
        competency_id=competency_id,
        kind=ItemKind.MCQ,
        difficulty=3,
        stem="2 + 2",
        options=["3", "4"],
        answer_key="4",
        rationale="suma",
        status=status,
        provenance=PROVENANCE,
    )


def make_escalation(escalation_id: str, family_id: str = "f1", status=None) -> Escalation:
    return Escalation(
        id=escalation_id,
        kind=EscalationKind.STRUGGLE_TRIAGE,
        family_id=family_id,
        summary="Ana falla fracciones",
        status=status or EscalationStatus.PENDING,
        created_at=NOW,
    )


def make_quarantine(item_id: str, family_id: str = "f1", status=None) -> QuarantineItem:
    return QuarantineItem(
        id=item_id,
        kind=QuarantineKind.LOW_CONFIDENCE_GRADE,
        family_id=family_id,
        evidence=EvidenceSpan(quote="respuesta", source_ref="m1"),
        payload={"score": 0.4},
        status=status or QuarantineStatus.PENDING,
        created_at=NOW,
    )


def test_factory_returns_local_store_in_local_mode(settings, store):
    assert isinstance(store, LocalStateStore)
    assert isinstance(store, StateStore)


def test_family_round_trip_and_chat_lookup(store):
    family = make_family()
    store.put_family(family)
    assert store.get_family("f1") == family
    assert store.find_family_by_chat("telegram", "chat-1") == family
    assert store.find_family_by_chat("telegram", "otro") is None
    assert store.get_family("missing") is None


def test_students_are_listed_per_family(store):
    store.put_student(make_student("s1", "f1"))
    store.put_student(make_student("s2", "f1"))
    store.put_student(make_student("s3", "f2"))
    assert store.get_student("s2") == make_student("s2", "f1")
    assert {student.id for student in store.list_students("f1")} == {"s1", "s2"}


def test_mastery_round_trip_and_listing(store):
    state = MasteryState(
        student_id="s1", competency_id="c1", ema_accuracy=0.5, attempts=4, correct=2
    )
    store.put_mastery(state)
    store.put_mastery(state.model_copy(update={"competency_id": "c2"}))
    store.put_mastery(state.model_copy(update={"student_id": "s2"}))
    assert store.get_mastery("s1", "c1") == state
    assert store.get_mastery("s1", "c9") is None
    assert len(store.list_mastery("s1")) == 2


def test_spaced_states_are_listed_per_student(store):
    state = SpacedItemState(student_id="s1", item_id="i1", due_date=TODAY)
    store.put_spaced(state)
    store.put_spaced(state.model_copy(update={"item_id": "i2"}))
    store.put_spaced(state.model_copy(update={"student_id": "s2"}))
    assert store.list_spaced("s1") == [state, state.model_copy(update={"item_id": "i2"})]


def test_items_filter_by_competency_and_status(store):
    store.put_item(make_item("i1", "c1", ItemStatus.ACTIVE))
    store.put_item(make_item("i2", "c1", ItemStatus.CANDIDATE))
    store.put_item(make_item("i3", "c2", ItemStatus.ACTIVE))
    assert store.get_item("i1") == make_item("i1", "c1", ItemStatus.ACTIVE)
    assert {item.id for item in store.list_items_by_competency("c1")} == {"i1", "i2"}
    active = store.list_items_by_competency("c1", ItemStatus.ACTIVE)
    assert [item.id for item in active] == ["i1"]


def test_material_round_trip(store):
    material = Material(
        id="m1", family_id="f1", kind=MediaKind.PHOTO, media_ref="s3://x", provenance=PROVENANCE
    )
    store.put_material(material)
    assert store.get_material("m1") == material
    assert store.get_material("m2") is None


def test_sessions_are_reachable_by_id_and_by_date(store):
    session = PracticeSession(id="sess1", student_id="s1", session_date=TODAY)
    store.put_session(session)
    assert store.get_session("sess1") == session
    assert store.get_session_by_date("s1", TODAY) == session
    assert store.get_session_by_date("s1", date(2026, 9, 2)) is None
    assert store.get_session_by_date("s2", TODAY) is None


def test_only_pending_escalations_are_listed(store):
    store.put_escalation(make_escalation("e1"))
    store.put_escalation(make_escalation("e2", status=EscalationStatus.RESOLVED))
    store.put_escalation(make_escalation("e3", family_id="f2"))
    assert store.get_escalation("e1") == make_escalation("e1")
    assert [item.id for item in store.list_pending_escalations("f1")] == ["e1"]


def test_only_pending_quarantine_is_listed(store):
    store.put_quarantine(make_quarantine("q1"))
    store.put_quarantine(make_quarantine("q2", status=QuarantineStatus.APPROVED))
    store.put_quarantine(make_quarantine("q3", family_id="f2"))
    assert [item.id for item in store.list_pending_quarantine("f1")] == ["q1"]


def test_claim_is_won_once(store):
    assert store.claim("job#1", "worker-a") is True
    assert store.claim("job#1", "worker-b") is False
    assert store.claim("job#2", "worker-b") is True


def test_state_survives_a_fresh_store_on_the_same_directory(settings):
    first = build_state_store(settings)
    first.put_family(make_family())
    first.put_item(make_item())
    assert first.claim("job#1", "worker-a") is True

    second = build_state_store(settings)
    assert second.get_family("f1") == make_family()
    assert [item.id for item in second.list_items_by_competency("c1")] == ["i1"]
    assert second.claim("job#1", "worker-b") is False


def test_put_overwrites_the_previous_revision(store):
    store.put_item(make_item("i1", "c1", ItemStatus.CANDIDATE))
    store.put_item(make_item("i1", "c1", ItemStatus.ACTIVE))
    assert store.get_item("i1").status is ItemStatus.ACTIVE
    assert len(store.list_items_by_competency("c1")) == 1
