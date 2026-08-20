import json

import httpx
import pytest

from repaso.config.settings import Settings
from repaso.schemas.channel import Button, ChannelKind, OutboundMessage
from repaso.tools.telegram import (
    ChannelSender,
    LocalOutbox,
    TelegramSender,
    build_channel_sender,
)

TOKEN = "12345:secret-token"


def make_message(**overrides) -> OutboundMessage:
    defaults = dict(channel=ChannelKind.TELEGRAM, chat_ref="chat-1", text="Hola <b>Ana</b>")
    defaults.update(overrides)
    return OutboundMessage(**defaults)


def make_sender(handler) -> TelegramSender:
    transport = httpx.MockTransport(handler)
    return TelegramSender(TOKEN, client=httpx.Client(transport=transport))


def test_outbox_appends_parseable_lines_with_increasing_refs(settings):
    outbox = LocalOutbox(settings.local_data_dir)
    first = outbox.send(make_message(text="uno"))
    second = outbox.send(
        make_message(text="dos", buttons=[Button(label="Sí", callback_data="yes")])
    )
    lines = outbox.path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert (first, second) == ("local:1", "local:2")
    assert [record["text"] for record in records] == ["uno", "dos"]
    assert records[0]["chat_ref"] == "chat-1"
    assert records[1]["buttons"] == [{"label": "Sí", "callback_data": "yes"}]
    assert outbox.sent == records


def test_outbox_creates_missing_directories(settings):
    outbox = LocalOutbox(settings.local_data_dir / "nested" / "deeper")
    outbox.send(make_message())
    assert outbox.path.exists()


def test_telegram_send_posts_expected_payload():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 77}})

    ref = make_sender(handler).send(make_message())
    assert TOKEN in captured["url"]
    assert captured["url"].endswith(f"/bot{TOKEN}/sendMessage")
    assert captured["payload"] == {
        "chat_id": "chat-1",
        "text": "Hola <b>Ana</b>",
        "parse_mode": "HTML",
    }
    assert ref == "77"


def test_telegram_send_serializes_one_button_per_row():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    buttons = [Button(label="A", callback_data="a"), Button(label="B", callback_data="b")]
    make_sender(handler).send(make_message(buttons=buttons))
    markup = json.loads(captured["payload"]["reply_markup"])
    assert markup == {
        "inline_keyboard": [
            [{"text": "A", "callback_data": "a"}],
            [{"text": "B", "callback_data": "b"}],
        ]
    }


def test_telegram_send_raises_on_bad_request():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "chat not found"})

    with pytest.raises(httpx.HTTPStatusError):
        make_sender(handler).send(make_message())


def test_telegram_sender_rejects_empty_token():
    with pytest.raises(ValueError):
        TelegramSender("")


def test_factory_returns_local_outbox_in_local_mode(settings):
    sender = build_channel_sender(settings)
    assert isinstance(sender, LocalOutbox)
    assert isinstance(sender, ChannelSender)
    assert sender.send(make_message()) == "local:1"
    assert (settings.local_data_dir / "outbox.jsonl").exists()


def test_factory_ignores_token_in_local_mode(settings):
    assert isinstance(build_channel_sender(settings, token=TOKEN), LocalOutbox)


def test_factory_requires_token_outside_local_mode(tmp_path):
    cloud = Settings(aws_region="us-east-1", local_data_dir=tmp_path)
    assert cloud.local_mode is False
    with pytest.raises(ValueError):
        build_channel_sender(cloud)


def test_factory_builds_telegram_sender_outside_local_mode(tmp_path):
    cloud = Settings(aws_region="us-east-1", local_data_dir=tmp_path)
    sender = build_channel_sender(cloud, token=TOKEN)
    assert isinstance(sender, TelegramSender)
    assert isinstance(sender, ChannelSender)
