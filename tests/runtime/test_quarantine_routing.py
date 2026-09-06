from repaso.i18n import msg
from repaso.runtime import invoke
from repaso.schemas.common import Lang
from repaso.schemas.review import QuarantineStatus
from tests.orchestration.fixtures import (
    FRACTIONS,
    seed_family,
    seed_held_answer,
    seed_open_item,
)
from tests.runtime.fixtures import (
    FAMILY_CHAT,
    channel_request,
    inbound,
    pilot,
    request,
)


def test_a_button_carrying_an_unreadable_decision_is_not_routed(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    seed_held_answer(services.store, family.id, student.id)

    for callback in ("quar:q1:maybe", "quar::yes", "quar:q1"):
        tap = invoke(channel_request(inbound(callback=callback, chat_ref=FAMILY_CHAT)), services)
        assert tap["result"]["route"] == "unrouted_callback", callback
        assert tap["result"]["events"] == []
    assert services.publisher.published == []


def test_a_missing_quarantine_is_reported_not_found(settings):
    services = pilot(settings)
    family, _ = seed_family(services.store)

    response = invoke(
        request("quarantine_resolved", family.id, quarantine_id="ghost", accepted=True), services
    )

    assert response["ok"] is False
    assert response["error"] == {"code": "not_found", "message": "quarantine not found: ghost"}


def test_a_quarantine_belonging_to_another_family_is_refused(settings):
    services = pilot(settings)
    seed_family(services.store, "f1", "100")
    other, student = seed_family(services.store, "f2", "200")
    seed_held_answer(services.store, other.id, student.id)

    response = invoke(
        request("quarantine_resolved", "f1", quarantine_id="q1", accepted=True), services
    )

    assert response["error"] == {"code": "not_found", "message": "quarantine not found: q1"}


def test_the_quarantine_payload_is_strict(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    seed_held_answer(services.store, family.id, student.id)

    response = invoke(
        request(
            "quarantine_resolved", family.id, quarantine_id="q1", accepted=True, decided_by="mom"
        ),
        services,
    )

    assert response["error"]["code"] == "invalid_payload"
    assert "decided_by" in response["error"]["message"]


def test_resolving_the_same_quarantine_twice_releases_the_answer_once(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    seed_open_item(services.store)
    seed_held_answer(services.store, family.id, student.id)
    body = request("quarantine_resolved", family.id, quarantine_id="q1", accepted=True)

    first = invoke(body, services)
    again = invoke(body, services)

    assert first["result"]["handled"] is True
    assert again["ok"] is True
    assert again["result"]["handled"] is False
    assert again["result"]["terminal"] == "already_resolved"
    assert again["result"]["outbound"] == first["result"]["outbound"]
    assert services.store.get_mastery(student.id, FRACTIONS).attempts == 1


def test_the_quarantine_button_travels_from_the_chat_to_a_released_answer(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    item = seed_open_item(services.store)
    seed_held_answer(services.store, family.id, student.id)

    tap = invoke(channel_request(inbound(callback="quar:q1:yes", chat_ref=FAMILY_CHAT)), services)

    assert tap["result"]["route"] == "quarantine"
    assert tap["result"]["events"] == ["quarantine_resolved"]
    published = services.publisher.published[0]
    assert published.idempotency_key == "quar#q1#yes"
    assert published.payload == {"quarantine_id": "q1", "accepted": True}

    resolution = invoke(published.model_dump(mode="json"), services)

    assert resolution["ok"] is True
    assert resolution["result"]["released_item_id"] == item.id
    assert services.store.get_mastery(student.id, FRACTIONS).correct == 1


def test_the_rejecting_button_carries_the_decision_it_shows(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    seed_open_item(services.store)
    seed_held_answer(services.store, family.id, student.id)

    tap = invoke(channel_request(inbound(callback="quar:q1:no", chat_ref=FAMILY_CHAT)), services)

    assert tap["result"]["route"] == "quarantine"
    published = services.publisher.published[0]
    assert published.idempotency_key == "quar#q1#no"
    assert published.payload == {"quarantine_id": "q1", "accepted": False}


def test_the_parent_approving_releases_the_answer_and_is_told_so(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    item = seed_open_item(services.store)
    seed_held_answer(services.store, family.id, student.id)

    response = invoke(
        request("quarantine_resolved", family.id, quarantine_id="q1", accepted=True), services
    )

    assert response["ok"] is True
    result = response["result"]
    assert result["status"] == QuarantineStatus.APPROVED.value
    assert result["released_item_id"] == item.id
    assert result["outbound"] == [
        {
            "channel": family.channel.value,
            "chat_ref": family.chat_ref,
            "text": msg("quarantine_ack_approved", Lang.ES),
        }
    ]
    assert services.store.get_mastery(student.id, FRACTIONS).correct == 1


def test_the_parent_rejecting_discards_the_answer_and_is_told_so(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    seed_open_item(services.store)
    seed_held_answer(services.store, family.id, student.id)

    response = invoke(
        request("quarantine_resolved", family.id, quarantine_id="q1", accepted=False), services
    )

    assert response["result"]["status"] == QuarantineStatus.REJECTED.value
    assert response["result"]["released_item_id"] == "i1"
    assert response["result"]["outbound"][0]["text"] == msg("quarantine_ack_rejected", Lang.ES)
    assert services.store.get_mastery(student.id, FRACTIONS).correct == 0
    assert services.store.get_mastery(student.id, FRACTIONS).attempts == 1
