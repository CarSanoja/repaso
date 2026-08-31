import httpx

from repaso.core.telemetry.sink import NullTelemetrySink, TelemetrySink
from repaso.schemas.channel import MediaKind
from repaso.tools.media_fetcher import (
    ALLOWED_CONTENT_TYPES,
    OCTET_STREAM,
    FetchedMedia,
    sniff_content_type,
)
from repaso.tools.telegram import TELEGRAM_API_BASE

MAX_MEDIA_BYTES = 10 * 1024 * 1024
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 20.0
MAX_ATTEMPTS = 2
SERVER_ERROR_FLOOR = 500
TRACE_KIND = "media_fetch"


def _declared_content_type(response: httpx.Response) -> str:
    header = response.headers.get("content-type", "")
    declared = header.split(";")[0].strip().lower()
    return "" if declared == OCTET_STREAM else declared


class TelegramMediaFetcher:
    def __init__(
        self,
        token: str,
        client: httpx.Client | None = None,
        telemetry: TelemetrySink | None = None,
    ) -> None:
        if not token:
            raise ValueError("token must not be empty")
        self._token = token
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
        )
        self._telemetry = telemetry or NullTelemetrySink()

    @property
    def api_url(self) -> str:
        return f"{TELEGRAM_API_BASE}/bot{self._token}"

    @property
    def file_url(self) -> str:
        return f"{TELEGRAM_API_BASE}/file/bot{self._token}"

    def fetch(self, ref: str, kind: MediaKind) -> FetchedMedia | None:
        allowed = ALLOWED_CONTENT_TYPES.get(kind)
        if allowed is None:
            return self._declined("unsupported_kind", media_kind=kind.value)
        file_path = self._file_path(ref)
        if file_path is None:
            return None
        return self._download(file_path, allowed)

    def _file_path(self, ref: str) -> str | None:
        response = self._get(f"{self.api_url}/getFile", params={"file_id": ref})
        if response is None:
            return None
        if response.status_code != httpx.codes.OK:
            return self._declined("get_file_rejected", http_status=str(response.status_code))
        try:
            body = response.json()
        except ValueError:
            return self._declined("get_file_unreadable")
        result = body.get("result") if body.get("ok") else None
        if not isinstance(result, dict):
            return self._declined("get_file_not_ok", description=str(body.get("description", "")))
        declared = result.get("file_size")
        if isinstance(declared, int) and declared > MAX_MEDIA_BYTES:
            return self._declined("declared_size_over_cap", size=str(declared))
        file_path = str(result.get("file_path") or "")
        return file_path or self._declined("missing_file_path")

    def _download(self, file_path: str, allowed: frozenset[str]) -> FetchedMedia | None:
        response = self._get(f"{self.file_url}/{file_path}")
        if response is None:
            return None
        if response.status_code != httpx.codes.OK:
            return self._declined("download_rejected", http_status=str(response.status_code))
        data = response.content
        if len(data) > MAX_MEDIA_BYTES:
            return self._declined("size_over_cap", size=str(len(data)))
        content_type = _declared_content_type(response) or sniff_content_type(data)
        if content_type not in allowed:
            return self._declined("content_type_not_allowed", content_type=content_type)
        return FetchedMedia(data=data, content_type=content_type, size=len(data))

    def _get(self, url: str, params: dict[str, str] | None = None) -> httpx.Response | None:
        reason = ""
        for _ in range(MAX_ATTEMPTS):
            try:
                response = self._client.get(url, params=params)
            except httpx.HTTPError as error:
                reason = type(error).__name__
                continue
            if response.status_code < SERVER_ERROR_FLOOR:
                return response
            reason = f"status_{response.status_code}"
        return self._declined("telegram_unreachable", detail=reason)

    def _declined(self, reason: str, **extra: str) -> None:
        self._telemetry.trace(TRACE_KIND, reason, status="failed", **extra)
        return None
