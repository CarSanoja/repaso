from datetime import UTC, datetime

from repaso.core.harness.idempotency import job_key
from repaso.lambdas import bootstrap, scheduler
from repaso.schemas.events import EventKind

TICK = {"family_id": "f1"}


def published_events():
    return bootstrap.publisher().published


def test_scheduler_publishes_one_daily_session_due_event(lambda_env):
    response = scheduler.handler(TICK, None)
    assert response["ok"] is True
    assert response["duplicate"] is False
    assert len(published_events()) == 1
    event = published_events()[0]
    assert event.kind is EventKind.DAILY_SESSION_DUE
    assert event.family_id == "f1"
    assert event.payload == {"family_id": "f1"}
    assert event.occurred_at.tzinfo is not None


def test_scheduler_keys_the_event_on_the_family_and_the_day(lambda_env):
    response = scheduler.handler(TICK, None)
    event = published_events()[0]
    expected = job_key("daily_session", "f1", event.occurred_at.date().isoformat())
    assert response["idempotency_key"] == expected
    assert event.idempotency_key == expected
    assert expected.startswith("job#daily_session#f1#")


def test_scheduler_carries_the_student_reference_when_the_tick_names_one(lambda_env):
    scheduler.handler({"family_id": "f1", "student_id": "s1"}, None)
    assert published_events()[0].payload == {"family_id": "f1", "student_id": "s1"}


def test_scheduler_fires_a_family_once_per_day(lambda_env):
    first = scheduler.handler(TICK, None)
    second = scheduler.handler(TICK, None)
    assert first["duplicate"] is False
    assert second == {"ok": True, "duplicate": True, "idempotency_key": first["idempotency_key"]}
    assert len(published_events()) == 1


def test_scheduler_fires_each_family_independently(lambda_env):
    scheduler.handler(TICK, None)
    scheduler.handler({"family_id": "f2"}, None)
    assert [event.family_id for event in published_events()] == ["f1", "f2"]


def test_scheduler_claims_the_day_before_publishing(lambda_env):
    response = scheduler.handler(TICK, None)
    assert bootstrap.store().claim(response["idempotency_key"], "other-owner") is False


def test_scheduler_rejects_a_tick_without_a_family(lambda_env):
    assert scheduler.handler({}, None) == {"ok": False, "error": "missing_family_id"}
    assert scheduler.handler({"family_id": "   "}, None)["error"] == "missing_family_id"
    assert scheduler.handler({"family_id": 7}, None)["error"] == "missing_family_id"
    assert published_events() == []


def test_scheduler_rejects_a_tick_that_is_not_an_object(lambda_env):
    assert scheduler.handler("family", None) == {"ok": False, "error": "missing_family_id"}
    assert published_events() == []


def test_scheduler_rejects_a_family_reference_holding_a_key_separator(lambda_env):
    response = scheduler.handler({"family_id": "f1#f2"}, None)
    assert response == {"ok": False, "error": "invalid_family_id"}
    assert published_events() == []


def test_scheduler_does_not_deliver_messages_inline(lambda_env):
    scheduler.handler(TICK, None)
    assert bootstrap.container().sender.sent == []


def test_scheduler_publishes_within_the_current_utc_day(lambda_env):
    before = datetime.now(UTC)
    scheduler.handler(TICK, None)
    event = published_events()[0]
    assert before <= event.occurred_at <= datetime.now(UTC)
