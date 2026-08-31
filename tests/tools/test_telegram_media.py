from datetime import UTC, datetime

import httpx
import pytest

from repaso.core.harness.clock import SimClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.schemas.channel import MediaKind
from repaso.tools.telegram_media import (
    MAX_MEDIA_BYTES,
    TRACE_KIND,
    TelegramMediaFetcher,
)

TOKEN = "12345:secret-token"
FILE_ID = "AgACAgEAAxkBAAIB"
FILE_PATH = "photos/file_0.jpg"
JPEG_BYTES = b"\xff\xd8\xff\xe0 the notebook page"
PDF_BYTES = b"%PDF-1.7 weekly plan"
NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


class Telegram:
    def __init__(self, file_response, download_response) -> None:
        self._file_response = file_response
        self._download_response = download_response
        self.paths: list[str] = []
        self.queries: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        self.queries.append(str(request.url.query.decode()))
        if request.url.path.endswith("/getFile"):
            return self._reply(self._file_response)
        return self._reply(self._download_response)

    def _reply(self, response):
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response(len(self.paths))
        return response

    @property
    def downloads(self) -> list[str]:
        return [path for path in self.paths if not path.endswith("/getFile")]


def ok_file(file_size: int | None = len(JPEG_BYTES)) -> httpx.Response:
    result: dict = {"file_id": FILE_ID, "file_path": FILE_PATH}
    if file_size is not None:
        result["file_size"] = file_size
    return httpx.Response(200, json={"ok": True, "result": result})


def downloaded(data: bytes = JPEG_BYTES, content_type: str | None = "image/jpeg"):
    headers = {"content-type": content_type} if content_type else {}
    return httpx.Response(200, content=data, headers=headers)


def make_fetcher(telegram: Telegram, telemetry=None) -> TelegramMediaFetcher:
    client = httpx.Client(transport=httpx.MockTransport(telegram))
    return TelegramMediaFetcher(TOKEN, client=client, telemetry=telemetry)


def make_telemetry(settings) -> LocalTelemetrySink:
    return LocalTelemetrySink(settings.local_data_dir / "telemetry.jsonl", SimClock(NOW))


def failures(telemetry: LocalTelemetrySink) -> list[str]:
    return [event.name for event in telemetry.events if event.kind == TRACE_KIND]


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


def test_voice_notes_are_declined_before_any_request_is_made(settings):
    telemetry = make_telemetry(settings)
    telegram = Telegram(ok_file(), downloaded())

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.VOICE) is None
    assert telegram.paths == []
    assert failures(telemetry) == ["unsupported_kind"]


def test_a_size_the_api_declares_over_the_cap_is_never_downloaded(settings):
    telemetry = make_telemetry(settings)
    telegram = Telegram(ok_file(file_size=MAX_MEDIA_BYTES + 1), downloaded())

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert telegram.downloads == []
    assert failures(telemetry) == ["declared_size_over_cap"]


def test_a_body_that_outgrows_the_cap_is_dropped_after_the_download(settings):
    telemetry = make_telemetry(settings)
    oversized = b"\xff\xd8\xff" + b"x" * MAX_MEDIA_BYTES
    telegram = Telegram(ok_file(file_size=None), downloaded(oversized))

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert failures(telemetry) == ["size_over_cap"]


def test_a_content_type_outside_the_allowlist_is_refused(settings):
    telemetry = make_telemetry(settings)
    telegram = Telegram(ok_file(), downloaded(b"<html>login</html>", "text/html"))

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert failures(telemetry) == ["content_type_not_allowed"]


def test_a_pdf_served_where_a_photo_was_expected_is_refused(settings):
    telemetry = make_telemetry(settings)
    telegram = Telegram(ok_file(), downloaded(PDF_BYTES, "application/pdf"))

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert failures(telemetry) == ["content_type_not_allowed"]


def test_a_telegram_api_error_stops_before_the_download(settings):
    telemetry = make_telemetry(settings)
    rejected = httpx.Response(200, json={"ok": False, "description": "file is too big"})
    telegram = Telegram(rejected, downloaded())

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert telegram.downloads == []
    assert failures(telemetry) == ["get_file_not_ok"]


def test_an_unauthorized_get_file_is_reported_not_raised(settings):
    telemetry = make_telemetry(settings)
    telegram = Telegram(httpx.Response(401, json={"ok": False}), downloaded())

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert failures(telemetry) == ["get_file_rejected"]


def test_a_reference_without_a_file_path_is_reported(settings):
    telemetry = make_telemetry(settings)
    empty = httpx.Response(200, json={"ok": True, "result": {"file_id": FILE_ID}})
    telegram = Telegram(empty, downloaded())

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert failures(telemetry) == ["missing_file_path"]


def test_a_missing_file_on_the_download_host_is_reported(settings):
    telemetry = make_telemetry(settings)
    telegram = Telegram(ok_file(), httpx.Response(404, content=b"not found"))

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert failures(telemetry) == ["download_rejected"]


def test_a_read_timeout_is_retried_once_and_then_given_up_on(settings):
    telemetry = make_telemetry(settings)
    telegram = Telegram(httpx.ReadTimeout("timed out"), downloaded())

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert len(telegram.paths) == 2
    assert failures(telemetry) == ["telegram_unreachable"]


def test_a_transient_failure_is_survived_by_the_single_retry():
    telegram = Telegram(
        lambda attempt: httpx.Response(503, json={}) if attempt == 1 else ok_file(),
        downloaded(),
    )

    fetched = make_fetcher(telegram).fetch(FILE_ID, MediaKind.PHOTO)

    assert fetched is not None
    assert len(telegram.paths) == 3


def test_a_server_error_that_never_clears_is_attempted_exactly_twice(settings):
    telemetry = make_telemetry(settings)
    telegram = Telegram(httpx.Response(500, json={}), downloaded())

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert len(telegram.paths) == 2
    assert failures(telemetry) == ["telegram_unreachable"]


def test_a_body_that_is_not_json_is_reported(settings):
    telemetry = make_telemetry(settings)
    telegram = Telegram(httpx.Response(200, content=b"<html>gateway</html>"), downloaded())

    assert make_fetcher(telegram, telemetry).fetch(FILE_ID, MediaKind.PHOTO) is None
    assert failures(telemetry) == ["get_file_unreadable"]


def test_the_fetcher_rejects_an_empty_token():
    with pytest.raises(ValueError):
        TelegramMediaFetcher("")


def test_the_urls_carry_the_bot_token_on_both_hosts():
    fetcher = TelegramMediaFetcher(TOKEN)
    assert fetcher.api_url.endswith(f"/bot{TOKEN}")
    assert fetcher.file_url.endswith(f"/file/bot{TOKEN}")
