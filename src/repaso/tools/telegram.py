import json
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx

from repaso.config.settings import Settings
from repaso.schemas.channel import Button, OutboundMessage

TELEGRAM_API_BASE = "https://api.telegram.org"
OUTBOX_FILENAME = "outbox.jsonl"
DEFAULT_TIMEOUT_SECONDS = 15.0


@runtime_checkable
class ChannelSender(Protocol):
    def send(self, message: OutboundMessage) -> str: ...


def _inline_keyboard(buttons: list[Button]) -> str:
    if any(not 1 <= len(b.callback_data.encode("utf-8")) <= 64 for b in buttons):
        raise ValueError("Telegram callback_data must be between 1 and 64 bytes")
    rows = [[{"text": button.label, "callback_data": button.callback_data}] for button in buttons]
    return json.dumps({"inline_keyboard": rows}, ensure_ascii=False)


class LocalOutbox:
    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / OUTBOX_FILENAME
        self.sent: list[dict] = []

    def send(self, message: OutboundMessage) -> str:
        _inline_keyboard(message.buttons)
        record = {
            "chat_ref": message.chat_ref,
            "text": message.text,
            "buttons": [button.model_dump() for button in message.buttons],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.sent.append(record)
        return f"local:{len(self.sent)}"


class TelegramSender:
    def __init__(self, token: str, client: httpx.Client | None = None) -> None:
        if not token:
            raise ValueError("token must not be empty")
        self._token = token
        self._client = client or httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)

    @property
    def url(self) -> str:
        return f"{TELEGRAM_API_BASE}/bot{self._token}/sendMessage"

    def send(self, message: OutboundMessage) -> str:
        payload = {
            "chat_id": message.chat_ref,
            "text": message.text,
        }
        if message.buttons:
            payload["reply_markup"] = _inline_keyboard(message.buttons)
        response = self._client.post(self.url, json=payload)
        response.raise_for_status()
        body = response.json()
        if body.get("ok") is False:
            raise RuntimeError("Telegram rejected the message")
        result = body.get("result", body)
        return str(result["message_id"])


def build_channel_sender(settings: Settings, token: str | None = None) -> ChannelSender:
    if settings.local_mode:
        return LocalOutbox(settings.local_data_dir)
    if not token:
        raise ValueError("token is required when local_mode is off")
    return TelegramSender(token)
