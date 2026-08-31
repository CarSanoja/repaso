import pytest

from repaso.config.settings import Settings
from repaso.schemas.channel import MediaKind
from repaso.tools.media_fetcher import (
    INBOX_DIRNAME,
    OCTET_STREAM,
    FetchedMedia,
    LocalMediaFetcher,
    MediaFetcher,
    build_media_fetcher,
    sniff_content_type,
)
from repaso.tools.telegram_media import TelegramMediaFetcher

FILE_ID = "AgACAgEAAxkBAAIB"
JPEG_BYTES = b"\xff\xd8\xff\xe0 the notebook page"
PNG_BYTES = b"\x89PNG\r\n\x1a\n the worksheet"
WEBP_BYTES = b"RIFF\x20\x00\x00\x00WEBPVP8 payload"
PDF_BYTES = b"%PDF-1.7 weekly plan"
TOKEN = "12345:secret-token"
TRAVERSAL_REFS = ["../escape.jpg", "a/../../b.jpg", "", "   "]


def make_fetcher(settings: Settings, ref: str = FILE_ID, data: bytes = JPEG_BYTES):
    fetcher = LocalMediaFetcher(settings.local_data_dir)
    path = fetcher.inbox / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return fetcher


def test_a_file_dropped_in_the_inbox_comes_back_byte_for_byte(settings):
    fetched = make_fetcher(settings).fetch(FILE_ID, MediaKind.PHOTO)
    assert fetched == FetchedMedia(data=JPEG_BYTES, content_type="image/jpeg", size=len(JPEG_BYTES))


def test_the_inbox_sits_under_the_configured_data_dir(settings):
    fetcher = LocalMediaFetcher(settings.local_data_dir)
    assert fetcher.inbox == settings.local_data_dir / INBOX_DIRNAME


def test_a_reference_nobody_dropped_reads_as_none(settings):
    fetcher = LocalMediaFetcher(settings.local_data_dir)
    assert fetcher.fetch(FILE_ID, MediaKind.PHOTO) is None


def test_a_ref_that_would_escape_the_inbox_reads_as_none_instead_of_raising(settings, tmp_path):
    fetcher = make_fetcher(settings)
    (tmp_path / "escape.jpg").write_bytes(JPEG_BYTES)
    for ref in TRAVERSAL_REFS:
        assert fetcher.fetch(ref, MediaKind.PHOTO) is None


def test_leading_and_trailing_slashes_address_the_same_file(settings):
    fetcher = make_fetcher(settings)
    assert fetcher.fetch(f"/{FILE_ID}/", MediaKind.PHOTO) is not None


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (JPEG_BYTES, "image/jpeg"),
        (PNG_BYTES, "image/png"),
        (WEBP_BYTES, "image/webp"),
        (PDF_BYTES, "application/pdf"),
        (b"plain text from a school", OCTET_STREAM),
        (b"", OCTET_STREAM),
        (b"RIFF\x20\x00\x00\x00WAVEfmt ", OCTET_STREAM),
    ],
)
def test_the_content_type_comes_from_the_file_signature(data, expected):
    assert sniff_content_type(data) == expected


def test_a_pdf_in_the_inbox_is_typed_as_a_pdf(settings):
    fetched = make_fetcher(settings, data=PDF_BYTES).fetch(FILE_ID, MediaKind.PDF)
    assert fetched is not None
    assert fetched.content_type == "application/pdf"
    assert fetched.size == len(PDF_BYTES)


def test_fetched_media_is_frozen_and_forbids_unknown_fields():
    fetched = FetchedMedia(data=JPEG_BYTES, content_type="image/jpeg", size=len(JPEG_BYTES))
    with pytest.raises(ValueError):
        fetched.size = 0
    with pytest.raises(ValueError):
        FetchedMedia(data=b"x", content_type="image/jpeg", size=1, url="http://x")


def test_fetched_media_rejects_an_empty_content_type_and_a_negative_size():
    with pytest.raises(ValueError):
        FetchedMedia(data=b"x", content_type="", size=1)
    with pytest.raises(ValueError):
        FetchedMedia(data=b"x", content_type="image/jpeg", size=-1)


def test_factory_returns_the_local_fetcher_in_local_mode(settings):
    fetcher = build_media_fetcher(settings)
    assert isinstance(fetcher, LocalMediaFetcher)
    assert isinstance(fetcher, MediaFetcher)
    assert MediaFetcher not in LocalMediaFetcher.__mro__


def test_factory_ignores_a_token_in_local_mode(settings):
    assert isinstance(build_media_fetcher(settings, token=TOKEN), LocalMediaFetcher)


def test_factory_requires_a_token_outside_local_mode(tmp_path):
    cloud = Settings(aws_region="us-east-1", local_data_dir=tmp_path)
    with pytest.raises(ValueError):
        build_media_fetcher(cloud)


def test_factory_builds_the_telegram_fetcher_outside_local_mode(tmp_path):
    cloud = Settings(aws_region="us-east-1", local_data_dir=tmp_path)
    fetcher = build_media_fetcher(cloud, token=TOKEN)
    assert isinstance(fetcher, TelegramMediaFetcher)
    assert isinstance(fetcher, MediaFetcher)
