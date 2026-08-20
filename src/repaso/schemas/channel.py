from datetime import datetime
from enum import StrEnum

from repaso.schemas.common import FrozenStrictModel, StrictBaseModel


class ChannelKind(StrEnum):
    TELEGRAM = "telegram"
    WEB = "web"


class MediaKind(StrEnum):
    PHOTO = "photo"
    PDF = "pdf"
    VOICE = "voice"


class InboundMedia(FrozenStrictModel):
    kind: MediaKind
    media_ref: str


class InboundMessage(FrozenStrictModel):
    channel: ChannelKind
    chat_ref: str
    message_ref: str
    text: str | None = None
    callback_data: str | None = None
    media: InboundMedia | None = None
    received_at: datetime


class Button(FrozenStrictModel):
    label: str
    callback_data: str


class OutboundMessage(StrictBaseModel):
    channel: ChannelKind
    chat_ref: str
    text: str
    buttons: list[Button] = []
    audio_ref: str | None = None
