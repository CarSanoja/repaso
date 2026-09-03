import httpx
import pytest

from repaso.schemas.channel import MediaKind
from repaso.tools.telegram_media import TelegramMediaFetcher
from tests.tools.telegram_transport import (
    FILE_ID,
    FILE_PATH,
    JPEG_BYTES,
    PDF_BYTES,
    TOKEN,
    Telegram,
    downloaded,
    make_fetcher,
    ok_file,
)


def test_the_file_reference_is_resolved_and_then_downloaded():
    telegram = Telegram(ok_file(), downloaded())

    fetched = make_fetcher(telegram).fetch(FILE_ID, MediaKind.PHOTO)

    assert fetched is not None
    assert fetched.data == JPEG_BYTES
    assert fetched.content_type == "image/jpeg"
    assert fetched.size == len(JPEG_BYTES)
    assert telegram.paths == [f"/bot{TOKEN}/getFile", f"/file/bot{TOKEN}/{FILE_PATH}"]
    assert telegram.queries[0] == f"file_id={FILE_ID}"


def test_a_pdf_document_is_downloaded_under_its_own_allowlist():
    telegram = Telegram(ok_file(), downloaded(PDF_BYTES, "application/pdf"))

    fetched = make_fetcher(telegram).fetch(FILE_ID, MediaKind.PDF)

    assert fetched is not None
    assert fetched.content_type == "application/pdf"


def test_a_download_without_a_content_type_header_falls_back_to_the_signature():
    telegram = Telegram(ok_file(), downloaded(content_type=None))

    fetched = make_fetcher(telegram).fetch(FILE_ID, MediaKind.PHOTO)

    assert fetched is not None
    assert fetched.content_type == "image/jpeg"


def test_a_transient_failure_is_survived_by_the_single_retry():
    telegram = Telegram(
        lambda attempt: httpx.Response(503, json={}) if attempt == 1 else ok_file(),
        downloaded(),
    )

    fetched = make_fetcher(telegram).fetch(FILE_ID, MediaKind.PHOTO)

    assert fetched is not None
    assert len(telegram.paths) == 3


def test_the_fetcher_rejects_an_empty_token():
    with pytest.raises(ValueError):
        TelegramMediaFetcher("")


def test_the_urls_carry_the_bot_token_on_both_hosts():
    fetcher = TelegramMediaFetcher(TOKEN)
    assert fetcher.api_url.endswith(f"/bot{TOKEN}")
    assert fetcher.file_url.endswith(f"/file/bot{TOKEN}")
