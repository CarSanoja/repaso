import pytest
from httpx import ASGITransport, AsyncClient

from repaso.api.dependencies import build_container
from repaso.api.main import create_app
from repaso.core.harness.clock import SimClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from tests.orchestration.fixtures import START, seed_family
from tests.runtime.fixtures import INVITE_CODE, NEW_CHAT, pilot_settings

WEBHOOK = "/telegram/webhook"
SECRET = "testsecret"
FAMILY_CHAT = "100"
PER_MINUTE = 3
PER_DAY = 2


@pytest.fixture
def wired(settings, tmp_path):
    configured = pilot_settings(settings).model_copy(
        update={
            "chat_messages_per_minute": PER_MINUTE,
            "unknown_chat_daily_messages": PER_DAY,
        }
    )
    container = build_container(configured, telegram_secret=SECRET)
    container.clock = SimClock(START)
    container.telemetry = LocalTelemetrySink(tmp_path / "traces.jsonl", container.clock)
    return container


def update(chat_ref: str, update_id: int, text: str = "hola") -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "chat": {"id": int(chat_ref), "type": "private"},
            "date": 1756750000,
            "text": text,
        },
    }


async def post(container, body: dict) -> dict:
    transport = ASGITransport(app=create_app(container))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            WEBHOOK, json=body, headers={"X-Telegram-Bot-Api-Secret-Token": SECRET}
        )
    assert response.status_code == 200
    return response.json()


async def test_a_flood_from_one_chat_stops_at_the_webhook(wired):
    seed_family(wired.store, chat_ref=FAMILY_CHAT)

    answers = [await post(wired, update(FAMILY_CHAT, n)) for n in range(1, 7)]

    assert answers[:PER_MINUTE] == [{"ok": True}] * PER_MINUTE
    assert answers[PER_MINUTE:] == [{"ok": True, "throttled": "rate_limited"}] * 3
    assert len(wired.publisher.published) == PER_MINUTE


async def test_a_stranger_stops_costing_anything_once_the_day_is_spent(wired):
    for number in range(1, PER_DAY + 1):
        await post(wired, update(NEW_CHAT, number))
    wired.clock.advance(minutes=5)

    refused = await post(wired, update(NEW_CHAT, PER_DAY + 1))

    assert refused == {"ok": True, "throttled": "unknown_chat_exhausted"}
    assert len(wired.publisher.published) == PER_DAY


async def test_a_refused_chat_is_reported_where_an_alarm_can_see_it(wired):
    for number in range(1, PER_DAY + 2):
        await post(wired, update(NEW_CHAT, number))

    names = [f"{event.kind}.{event.name}.{event.status}" for event in wired.telemetry.events]
    assert names == ["throttle.unknown_chat_exhausted.refused"]


async def test_the_parent_who_finally_types_the_code_is_let_through(wired):
    admitted = await post(wired, update(NEW_CHAT, 1, INVITE_CODE))

    assert admitted == {"ok": True}
    assert len(wired.publisher.published) == 1
