from httpx import ASGITransport, AsyncClient

from repaso.api.dependencies import build_container
from repaso.api.main import create_app
from repaso.channel.telegram.enrollment import CONSENT_YES
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.i18n import msg
from repaso.runtime import invoke_async
from repaso.schemas.common import Lang
from repaso.schemas.family import FamilyStatus
from repaso.tools.invite_codes import INVITE_CODES_FILENAME
from tests.orchestration.fixtures import make_services
from tests.runtime.fixtures import (
    INVITE_CODE,
    NEW_CHAT,
    inbound,
    pilot,
    pilot_settings,
    route_of,
    send,
    texts,
)

CHANNEL = "telegram"
WEBHOOK = "/telegram/webhook"
SECRET = "testsecret"


class BrokenInviteCodes:
    def codes(self) -> frozenset[str]:
        raise RuntimeError("secrets manager is unreachable")


def traced(services, tmp_path):
    services.telemetry = LocalTelemetrySink(tmp_path / "telemetry.jsonl", services.clock)
    return services


def trace_names(services) -> list[str]:
    return [f"{event.kind}.{event.name}" for event in services.telemetry.events]


def test_a_chat_nobody_invited_is_told_how_to_get_in(settings):
    services = pilot(settings)

    response = send(services, inbound(text="hola, me hablaron de esto"))

    assert route_of(response) == "unknown_chat"
    assert texts(response) == [msg("unknown_chat", Lang.ES)]
    assert services.store.get_enrollment(CHANNEL, NEW_CHAT) is None


def test_nobody_can_enroll_while_the_pilot_holds_no_invite_codes(settings, tmp_path):
    services = traced(make_services(pilot_settings(settings, codes="")), tmp_path)

    response = send(services, inbound(text="PILOTO-1"))

    assert route_of(response) == "enrollment_closed"
    assert texts(response) == [msg("enrollment_closed", Lang.ES)]
    assert services.store.get_enrollment(CHANNEL, NEW_CHAT) is None
    assert "enrollment.closed" in trace_names(services)


def test_an_unreachable_code_source_closes_enrollment_instead_of_failing(settings, tmp_path):
    services = traced(make_services(pilot_settings(settings, codes="")), tmp_path)
    services.invites = BrokenInviteCodes()

    response = send(services, inbound(text="PILOTO-1"))

    assert route_of(response) == "enrollment_closed"
    assert texts(response) == [msg("enrollment_closed", Lang.ES)]
    assert "enrollment.codes_unavailable" in trace_names(services)


def test_codes_kept_in_a_file_open_enrollment_when_no_setting_names_them(settings):
    configured = pilot_settings(settings, codes="")
    path = configured.local_data_dir / INVITE_CODES_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("PILOTO-9\nPILOTO-8\n", encoding="utf-8")
    services = make_services(configured)

    response = send(services, inbound(text="PILOTO-9"))

    assert route_of(response) == "enrollment"
    assert services.store.get_enrollment(CHANNEL, NEW_CHAT).invite_code == "PILOTO-9"


def test_an_invite_code_opens_enrollment(settings):
    services = pilot(settings)

    response = send(services, inbound(text=INVITE_CODE))

    assert route_of(response) == "enrollment"
    assert texts(response) == [msg("welcome", Lang.ES), msg("consent", Lang.ES)]
    progress = services.store.get_enrollment(CHANNEL, NEW_CHAT)
    assert progress is not None and progress.invite_code == INVITE_CODE


def test_the_whole_enrollment_walk_runs_over_channel_messages(settings):
    services = pilot(settings)

    assert route_of(send(services, inbound(text=INVITE_CODE))) == "enrollment"
    assert route_of(send(services, inbound(callback=CONSENT_YES))) == "enrollment"
    for answer in ("Leo", "4", "San José 4to B"):
        assert route_of(send(services, inbound(text=answer))) == "enrollment"
    final = send(services, inbound(text="7:30pm"))

    assert route_of(final) == "enrolled"
    family = services.store.find_family_by_chat(CHANNEL, NEW_CHAT)
    student = services.store.list_students(family.id)[0]
    assert family.status is FamilyStatus.ACTIVE
    assert family.practice_time.strftime("%H:%M") == "19:30"
    assert student.alias == "Leo" and student.grade == 4
    assert final["result"]["family_id"] == family.id
    assert final["result"]["student_id"] == student.id
    assert texts(final)[1] == msg("ask_first_material", Lang.ES, alias="Leo")
    assert services.store.get_enrollment(CHANNEL, NEW_CHAT) is None


def test_a_declined_consent_never_creates_a_family(settings):
    services = pilot(settings)

    send(services, inbound(text=INVITE_CODE))
    response = send(services, inbound(callback="consent:no"))

    assert texts(response) == [msg("consent_declined", Lang.ES)]
    assert services.store.find_family_by_chat(CHANNEL, NEW_CHAT) is None
    assert services.store.get_enrollment(CHANNEL, NEW_CHAT) is None


async def test_a_real_telegram_update_travels_from_the_webhook_into_the_runtime(settings):
    configured = pilot_settings(settings)
    services = make_services(configured)
    container = build_container(configured, telegram_secret=SECRET)
    update = {
        "update_id": 7,
        "message": {
            "message_id": 10,
            "chat": {"id": int(NEW_CHAT), "type": "private"},
            "date": 1756750000,
            "text": INVITE_CODE,
        },
    }

    transport = ASGITransport(app=create_app(container))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        posted = await client.post(
            WEBHOOK, json=update, headers={"X-Telegram-Bot-Api-Secret-Token": SECRET}
        )

    assert posted.json() == {"ok": True}
    event = container.publisher.published[0]
    response = await invoke_async(event.model_dump(mode="json"), services)

    assert route_of(response) == "enrollment"
    assert texts(response) == [msg("welcome", Lang.ES), msg("consent", Lang.ES)]
    assert services.store.get_enrollment(CHANNEL, NEW_CHAT) is not None
