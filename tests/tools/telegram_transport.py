from datetime import UTC, datetime

import httpx

from repaso.core.harness.clock import SimClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.tools.telegram_media import TRACE_KIND, TelegramMediaFetcher

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
