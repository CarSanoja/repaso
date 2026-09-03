import httpx

from repaso.schemas.channel import MediaKind
from repaso.tools.telegram_media import MAX_MEDIA_BYTES
from tests.tools.telegram_transport import (
    FILE_ID,
    PDF_BYTES,
    Telegram,
    downloaded,
    failures,
    make_fetcher,
    make_telemetry,
    ok_file,
)


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
