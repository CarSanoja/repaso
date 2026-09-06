from repaso.i18n import msg
from repaso.runtime import invoke
from repaso.schemas.common import Lang
from repaso.schemas.escalation import (
    Escalation,
    EscalationKind,
    EscalationOption,
    EscalationStatus,
)
from tests.orchestration.fixtures import START, seed_family
from tests.runtime.fixtures import (
    FAMILY_CHAT,
    channel_request,
    inbound,
    pilot,
    request,
)

TEACHER_NOTE = "teacher_note"
NOTE_LABEL = "Nota para la maestra"


def seed_escalation(services, family_id: str = "f1", escalation_id: str = "e1") -> Escalation:
    escalation = Escalation(
        id=escalation_id,
        kind=EscalationKind.STRUGGLE_TRIAGE,
        family_id=family_id,
        summary="Leo lleva días tropezando con fracciones",
        options=[
            EscalationOption(key=TEACHER_NOTE, label=NOTE_LABEL, tradeoff="la maestra se entera"),
            EscalationOption(key="reduce_load", label="Bajar el ritmo", tradeoff="va más lento"),
        ],
        created_at=START,
    )
    services.store.put_escalation(escalation)
    return escalation


def test_the_escalation_button_travels_from_the_chat_to_a_resolved_escalation(settings):
    services = pilot(settings)
    family, _ = seed_family(services.store)
    seed_escalation(services, family.id)

    tap = invoke(
        channel_request(inbound(callback="esc:e1:teacher_note", chat_ref=FAMILY_CHAT)), services
    )

    assert tap["result"]["route"] == "escalation"
    assert tap["result"]["events"] == ["escalation_resolved"]
    published = services.publisher.published[0]
    assert published.payload == {"escalation_id": "e1", "option_key": TEACHER_NOTE}

    resolution = invoke(published.model_dump(mode="json"), services)

    assert resolution["ok"] is True
    result = resolution["result"]
    assert result["status"] == EscalationStatus.RESOLVED.value
    assert result["chosen_option"] == TEACHER_NOTE
    assert result["outbound"][0]["text"] == services.store.get_escalation("e1").summary
    assert result["outbound"][1:] == [
        {
            "channel": family.channel.value,
            "chat_ref": family.chat_ref,
            "text": msg("escalation_ack", Lang.ES, option=NOTE_LABEL),
        }
    ]
    stored = services.store.get_escalation("e1")
    assert stored.status is EscalationStatus.RESOLVED
    assert stored.resolved_at == services.clock.now()
    assert services.store.list_pending_escalations(family.id) == []


def test_resolving_the_same_escalation_twice_changes_nothing(settings):
    services = pilot(settings)
    family, _ = seed_family(services.store)
    seed_escalation(services, family.id)
    body = request("escalation_resolved", family.id, escalation_id="e1", option_key=TEACHER_NOTE)

    invoke(body, services)
    again = invoke(body, services)

    assert again["ok"] is True
    assert again["result"]["handled"] is False
    assert again["result"]["terminal"] == "already_resolved"
    assert again["result"]["outbound"] == []


def test_an_unknown_option_is_rejected_without_side_effects(settings):
    services = pilot(settings)
    family, _ = seed_family(services.store)
    seed_escalation(services, family.id)

    response = invoke(
        request("escalation_resolved", family.id, escalation_id="e1", option_key="whatever"),
        services,
    )

    assert response["ok"] is False
    assert services.store.get_escalation("e1").status is EscalationStatus.PENDING
    assert services.sender.sent == []


def test_an_escalation_belonging_to_another_family_is_refused(settings):
    services = pilot(settings)
    seed_family(services.store, "f1", "100")
    other, _ = seed_family(services.store, "f2", "200")
    seed_escalation(services, other.id)

    response = invoke(
        request("escalation_resolved", "f1", escalation_id="e1", option_key=TEACHER_NOTE), services
    )

    assert response["error"]["code"] == "not_found"
    assert "does not belong" in response["error"]["message"]


def test_a_missing_escalation_is_reported_not_found(settings):
    services = pilot(settings)
    family, _ = seed_family(services.store)

    response = invoke(
        request("escalation_resolved", family.id, escalation_id="ghost", option_key="x"), services
    )

    assert response["error"] == {"code": "not_found", "message": "escalation not found: ghost"}


def test_the_escalation_payload_is_strict(settings):
    services = pilot(settings)
    family, _ = seed_family(services.store)
    seed_escalation(services, family.id)

    response = invoke(
        request(
            "escalation_resolved",
            family.id,
            escalation_id="e1",
            option_key=TEACHER_NOTE,
            chosen_by="dad",
        ),
        services,
    )

    assert response["error"]["code"] == "invalid_payload"
    assert "chosen_by" in response["error"]["message"]
