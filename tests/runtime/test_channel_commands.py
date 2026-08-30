import json

from repaso.i18n import msg
from repaso.runtime import invoke
from repaso.schemas.common import Lang
from tests.orchestration.fixtures import seed_family
from tests.runtime.fixtures import (
    FAMILY_CHAT,
    channel_request,
    inbound,
    pilot,
    route_of,
    send,
    texts,
)


def test_a_command_from_an_enrolled_family_is_answered(settings):
    services = pilot(settings)
    family, _ = seed_family(services.store)

    response = send(services, inbound(text="/help", chat_ref=FAMILY_CHAT))

    assert route_of(response) == "command"
    assert texts(response) == [msg("help", family.lang)]
    assert json.loads(json.dumps(response)) == response


def test_an_unknown_command_does_not_reach_the_tutor(settings):
    services = pilot(settings)
    seed_family(services.store)

    response = send(services, inbound(text="/teleport", chat_ref=FAMILY_CHAT))

    assert route_of(response) == "command"
    assert texts(response) == [msg("unknown_command", Lang.ES)]
    assert response["result"]["tutor"] is None


def test_the_exam_command_publishes_an_event_the_runtime_can_handle(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)

    response = send(services, inbound(text="/exam Fracciones 12/09", chat_ref=FAMILY_CHAT))

    assert route_of(response) == "command"
    assert response["result"]["events"] == ["exam_announced"]
    published = services.publisher.published[0]
    assert published.family_id == family.id
    assert published.payload == {"exam_date": "2026-09-12", "topic": "Fracciones"}
    followup = invoke(published.model_dump(mode="json"), services)
    assert followup["ok"] is True
    assert followup["result"]["student_ids"] == [student.id]
    assert [exam.exam_date.isoformat() for exam in services.store.list_exam_dates(student.id)] == [
        "2026-09-12"
    ]


def test_the_forget_button_erases_the_family(settings):
    services = pilot(settings)
    family, _ = seed_family(services.store)

    response = send(services, inbound(callback="forget:yes", chat_ref=FAMILY_CHAT))

    assert route_of(response) == "forget"
    assert texts(response) == [msg("forget_done", Lang.ES)]
    assert services.store.get_family(family.id) is None


def test_a_callback_nothing_owns_is_reported_rather_than_dropped(settings):
    services = pilot(settings)
    seed_family(services.store)

    response = send(services, inbound(callback="digest:weekly:send", chat_ref=FAMILY_CHAT))

    assert route_of(response) == "unrouted_callback"
    assert response["result"]["outbound"] == []


def test_the_channel_payload_is_strict(settings):
    services = pilot(settings)
    body = channel_request(inbound(text="hola"))
    body["payload"]["nickname"] = "Leo"

    response = invoke(body, services)

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_payload"
