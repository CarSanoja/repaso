from datetime import UTC, datetime
from typing import Any

from repaso.schemas.channel import ChannelKind, InboundMedia, InboundMessage, MediaKind

PDF_MIME = "application/pdf"


def _received_at(payload: dict[str, Any]) -> datetime:
    return datetime.fromtimestamp(payload.get("date", 0), tz=UTC)


def _media(message: dict[str, Any]) -> InboundMedia | None:
    photos = message.get("photo")
    if photos:
        largest = max(photos, key=lambda p: p.get("width", 0))
        return InboundMedia(kind=MediaKind.PHOTO, media_ref=largest["file_id"])
    document = message.get("document")
    if document and document.get("mime_type") == PDF_MIME:
        return InboundMedia(kind=MediaKind.PDF, media_ref=document["file_id"])
    voice = message.get("voice")
    if voice:
        return InboundMedia(kind=MediaKind.VOICE, media_ref=voice["file_id"])
    return None


def parse_update(update: dict[str, Any]) -> InboundMessage | None:
    callback = update.get("callback_query")
    if callback:
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        if "id" not in chat:
            return None
        return InboundMessage(
            channel=ChannelKind.TELEGRAM,
            chat_ref=str(chat["id"]),
            message_ref=str(callback["id"]),
            callback_data=callback.get("data"),
            received_at=_received_at(message),
        )
    message = update.get("message")
    if not message:
        return None
    chat = message.get("chat") or {}
    if "id" not in chat:
        return None
    text = message.get("text") or message.get("caption")
    media = _media(message)
    if text is None and media is None:
        return None
    return InboundMessage(
        channel=ChannelKind.TELEGRAM,
        chat_ref=str(chat["id"]),
        message_ref=str(message["message_id"]),
        text=text,
        media=media,
        received_at=_received_at(message),
    )


def update_id_of(update: dict[str, Any]) -> int | None:
    value = update.get("update_id")
    return value if isinstance(value, int) else None
