from datetime import datetime
from typing import Any

from repaso.core.orchestration.context import Services
from repaso.runtime.entrypoint import invoke_async
from repaso.schemas.channel import ChannelKind, InboundMedia, InboundMessage, MediaKind
from repaso.schemas.events import EventKind
from repaso.simulator.demo_transcript import BOT, Beat, Reading, ScenarioResult, Speech

CHAT_REF = "6120074513"
LABEL_KEY = "label"
CALLBACK_KEY = "callback_data"


def channel_event(message: InboundMessage) -> dict[str, Any]:
    return {
        "kind": EventKind.CHANNEL_MESSAGE.value,
        "family_id": None,
        "idempotency_key": f"channel#{message.chat_ref}#{message.message_ref}",
        "occurred_at": message.received_at.isoformat(),
        "payload": message.model_dump(mode="json"),
    }


def session_event(family_id: str, student_id: str, now: datetime) -> dict[str, Any]:
    return {
        "kind": EventKind.DAILY_SESSION_DUE.value,
        "family_id": family_id,
        "idempotency_key": f"session#{student_id}#{now.date().isoformat()}",
        "occurred_at": now.isoformat(),
        "payload": {"student_id": student_id},
    }


class Stage:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.result = ScenarioResult()
        self.rejected: list[str] = []
        self._delivered = 0
        self._dispatched = 0
        self._inbound = 0

    @property
    def clock(self) -> Any:
        return self.services.clock

    @property
    def outbox(self) -> list[dict[str, Any]]:
        return self.services.sender.sent

    def note(self, label: str, values: tuple[tuple[str, str], ...]) -> None:
        self.result.transcript.append(Reading(label=label, values=values))

    def beat(self, name: str, expected: Any, actual: Any) -> None:
        self.result.beats.append(Beat(name=name, expected=str(expected), actual=str(actual)))

    def inbound(
        self, text: str | None = None, callback: str | None = None, media_ref: str | None = None
    ) -> InboundMessage:
        self._inbound += 1
        media = None
        if media_ref is not None:
            media = InboundMedia(kind=MediaKind.PHOTO, media_ref=media_ref)
        return InboundMessage(
            channel=ChannelKind.TELEGRAM,
            chat_ref=CHAT_REF,
            message_ref=f"demo-{self._inbound:02d}",
            text=text,
            callback_data=callback,
            media=media,
            received_at=self.clock.now(),
        )

    async def says(self, speaker: str, shown: str, **fields: Any) -> dict[str, Any]:
        self.result.transcript.append(Speech(speaker=speaker, text=shown))
        return await self.dispatch(channel_event(self.inbound(**fields)))

    async def dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await invoke_async(payload, self.services)
        self._record_rejection(payload, result)
        await self._drain()
        self._replay_outbox()
        return result.get("result", {}) if result.get("ok") else {}

    async def _drain(self) -> None:
        published = getattr(self.services.publisher, "published", [])
        while self._dispatched < len(published):
            event = published[self._dispatched].model_dump(mode="json")
            self._dispatched += 1
            self._record_rejection(event, await invoke_async(event, self.services))

    def _record_rejection(self, payload: dict[str, Any], result: dict[str, Any]) -> None:
        if not result.get("ok"):
            self.rejected.append(f"{payload.get('kind')}: {result.get('error')}")

    def _replay_outbox(self) -> None:
        for record in self.outbox[self._delivered :]:
            buttons = tuple(button[LABEL_KEY] for button in record.get("buttons", []))
            self.result.transcript.append(
                Speech(speaker=BOT, text=record["text"], buttons=buttons)
            )
        self._delivered = len(self.outbox)

    def offered_button(self, prefix: str, suffix: str = "") -> tuple[str, str] | None:
        for record in reversed(self.outbox):
            for button in record.get("buttons", []):
                callback = button[CALLBACK_KEY]
                if callback.startswith(prefix) and callback.endswith(suffix):
                    return button[LABEL_KEY], callback
        return None
