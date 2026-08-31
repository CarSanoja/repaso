from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import Field

from repaso.config.settings import Settings
from repaso.schemas.channel import MediaKind
from repaso.schemas.common import FrozenStrictModel
from repaso.tools.media_store import normalize_ref

INBOX_DIRNAME = "inbox"
OCTET_STREAM = "application/octet-stream"
JPEG = "image/jpeg"
PNG = "image/png"
WEBP = "image/webp"
PDF = "application/pdf"

SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", JPEG),
    (b"\x89PNG\r\n\x1a\n", PNG),
    (b"%PDF-", PDF),
)
RIFF_PREFIX = b"RIFF"
WEBP_TAG = b"WEBP"
WEBP_TAG_OFFSET = 8

ALLOWED_CONTENT_TYPES: dict[MediaKind, frozenset[str]] = {
    MediaKind.PHOTO: frozenset({JPEG, PNG, WEBP}),
    MediaKind.PDF: frozenset({PDF}),
}


class FetchedMedia(FrozenStrictModel):
    data: bytes
    content_type: str = Field(min_length=1)
    size: int = Field(ge=0)


@runtime_checkable
class MediaFetcher(Protocol):
    def fetch(self, ref: str, kind: MediaKind) -> FetchedMedia | None: ...


def sniff_content_type(data: bytes) -> str:
    for signature, content_type in SIGNATURES:
        if data.startswith(signature):
            return content_type
    if data.startswith(RIFF_PREFIX) and data[WEBP_TAG_OFFSET : WEBP_TAG_OFFSET + 4] == WEBP_TAG:
        return WEBP
    return OCTET_STREAM


class LocalMediaFetcher:
    def __init__(self, root: Path) -> None:
        self._inbox = Path(root) / INBOX_DIRNAME

    @property
    def inbox(self) -> Path:
        return self._inbox

    def fetch(self, ref: str, kind: MediaKind) -> FetchedMedia | None:
        try:
            key = normalize_ref(ref)
        except ValueError:
            return None
        path = self._inbox / key
        if not path.is_file():
            return None
        data = path.read_bytes()
        return FetchedMedia(data=data, content_type=sniff_content_type(data), size=len(data))


def build_media_fetcher(settings: Settings, token: str | None = None) -> MediaFetcher:
    if settings.local_mode:
        return LocalMediaFetcher(settings.local_data_dir)
    if not token:
        raise ValueError("token is required when local_mode is off")
    from repaso.tools.telegram_media import TelegramMediaFetcher

    return TelegramMediaFetcher(token)
