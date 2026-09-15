from datetime import UTC, datetime

from repaso.core.harness.idempotency import job_key
from repaso.lambdas import bootstrap, scheduler
from repaso.schemas.channel import ChannelKind
from repaso.schemas.events import EventKind
from repaso.schemas.family import Family, FamilyStatus
from repaso.schemas.student import Student
from tests.lambdas.conftest import CHAT_REF, NOW

TICK = {"family_id": "f1"}


def published_events():
    return bootstrap.publisher().published


def seed_student(student_id: str = "s1", family_id: str = "f1") -> Student:
    store = bootstrap.store()
    if store.get_family(family_id) is None:
        store.put_family(
            Family(
                id=family_id,
                channel=ChannelKind.TELEGRAM,
                chat_ref=CHAT_REF,
                invite_code=f"INV-{family_id}",
                created_at=NOW,
            )
        )
    student = Student(
        id=student_id,
        family_id=family_id,
        alias="Ana",
        grade=5,
        section_key="5A",
        created_at=NOW,
    )
    store.put_student(student)
    return student


def test_scheduler_fires_the_enrolled_student_of_the_family(lambda_env):
    seed_student()
    response = scheduler.handler(TICK, None)
    assert response["ok"] is True
    assert response["fired"] == ["s1"]
    assert response["skipped"] == []
    assert len(published_events()) == 1
    event = published_events()[0]
    assert event.kind is EventKind.DAILY_SESSION_DUE
    assert event.family_id == "f1"
    assert event.payload == {"student_id": "s1"}
    assert event.occurred_at.tzinfo is not None


def test_scheduler_keys_the_event_on_the_student_and_the_family_day(lambda_env, monkeypatch):
    seed_student()
    # UTC has crossed midnight while the family's Caracas date is still September 14.
    now = datetime(2026, 9, 15, 0, 10, tzinfo=UTC)
    monkeypatch.setattr(scheduler.SystemClock, "now", lambda self: now)
    scheduler.handler(TICK, None)
    event = published_events()[0]
    assert event.occurred_at == now
    assert bootstrap.store().get_family("f1").timezone == "America/Caracas"
    expected = job_key("daily_session", "s1", "2026-09-14")
    assert event.idempotency_key == expected
    assert expected.startswith("job#daily_session#s1#")


def test_scheduler_fires_every_student_in_the_family(lambda_env):
    seed_student("s1")
    seed_student("s2")
    response = scheduler.handler(TICK, None)
    assert sorted(response["fired"]) == ["s1", "s2"]
    assert sorted(event.payload["student_id"] for event in published_events()) == ["s1", "s2"]


def test_scheduler_honours_a_tick_that_names_one_student(lambda_env):
    seed_student("s1")
    seed_student("s2")
    response = scheduler.handler({"family_id": "f1", "student_id": "s2"}, None)
    assert response["fired"] == ["s2"]
    assert [event.payload for event in published_events()] == [{"student_id": "s2"}]


def test_scheduler_fires_a_student_once_per_day(lambda_env):
    seed_student()
    first = scheduler.handler(TICK, None)
    second = scheduler.handler(TICK, None)
    assert first["fired"] == ["s1"]
    assert second == {"ok": True, "family_id": "f1", "fired": [], "skipped": ["s1"]}
    assert len(published_events()) == 1


def test_scheduler_records_the_day_only_after_publication(lambda_env):
    seed_student()
    scheduler.handler(TICK, None)
    key = published_events()[0].idempotency_key
    assert bootstrap.store().get_record("f1", key).payload["published"] is True


def test_scheduler_publishes_nothing_for_a_family_without_students(lambda_env):
    seed_student()
    bootstrap.store().forget_family("f1")
    response = scheduler.handler(TICK, None)
    assert response == {"ok": True, "forgotten": True, "fired": [], "skipped": []}
    assert published_events() == []


def test_scheduler_fires_nothing_for_a_paused_family(lambda_env):
    seed_student()
    store = bootstrap.store()
    family = store.get_family("f1")
    store.put_family(family.model_copy(update={"status": FamilyStatus.PAUSED}))

    response = scheduler.handler(TICK, None)

    assert response == {
        "ok": True,
        "family_id": "f1",
        "fired": [],
        "skipped": [],
        "paused": True,
    }
    assert published_events() == []


def test_scheduler_fires_again_once_the_family_resumes(lambda_env):
    seed_student()
    store = bootstrap.store()
    family = store.get_family("f1")
    store.put_family(family.model_copy(update={"status": FamilyStatus.PAUSED}))
    scheduler.handler(TICK, None)

    store.put_family(family.model_copy(update={"status": FamilyStatus.ACTIVE}))
    response = scheduler.handler(TICK, None)

    assert response["fired"] == ["s1"]
    assert len(published_events()) == 1


def test_scheduler_rejects_a_tick_without_a_family(lambda_env):
    assert scheduler.handler({}, None) == {"ok": False, "error": "missing_family_id"}
    assert scheduler.handler({"family_id": "   "}, None)["error"] == "missing_family_id"
    assert scheduler.handler({"family_id": 7}, None)["error"] == "missing_family_id"
    assert published_events() == []


def test_scheduler_rejects_a_tick_that_is_not_an_object(lambda_env):
    assert scheduler.handler("family", None) == {"ok": False, "error": "missing_family_id"}
    assert published_events() == []


def test_scheduler_skips_a_student_reference_holding_a_key_separator(lambda_env):
    seed_student()
    response = scheduler.handler({"family_id": "f1", "student_id": "s1#s2"}, None)
    assert response["fired"] == []
    assert response["skipped"] == ["s1#s2"]
    assert published_events() == []


def test_scheduler_does_not_deliver_messages_inline(lambda_env):
    seed_student()
    scheduler.handler(TICK, None)
    assert bootstrap.container().sender.sent == []


def test_scheduler_publishes_within_the_current_utc_day(lambda_env):
    seed_student()
    before = datetime.now(UTC)
    scheduler.handler(TICK, None)
    event = published_events()[0]
    assert before <= event.occurred_at <= datetime.now(UTC)


def test_scheduler_payload_matches_the_runtime_contract(lambda_env):
    from repaso.runtime.payload import StudentScoped

    seed_student()
    scheduler.handler(TICK, None)
    assert StudentScoped.model_validate(published_events()[0].payload).student_id == "s1"
