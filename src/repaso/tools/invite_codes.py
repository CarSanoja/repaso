from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from repaso.config.settings import Settings
from repaso.core.harness.clock import Clock, SystemClock

INVITE_CODES_FILENAME = "invite_codes.txt"
CACHE_TTL_SECONDS = 300.0


@runtime_checkable
class InviteCodeSource(Protocol):
    def codes(self) -> frozenset[str]: ...


def parse_codes(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.replace(",", "\n").splitlines() if part.strip())


class LocalInviteCodes:
    def __init__(self, configured: str, path: Path) -> None:
        self._configured = parse_codes(configured)
        self._path = Path(path)

    def codes(self) -> frozenset[str]:
        if self._configured:
            return self._configured
        if not self._path.is_file():
            return frozenset()
        return parse_codes(self._path.read_text(encoding="utf-8"))


class SecretsManagerInviteCodes:
    def __init__(
        self,
        secret_name: str,
        configured: str = "",
        clock: Clock | None = None,
        ttl_seconds: float = CACHE_TTL_SECONDS,
    ) -> None:
        if not secret_name:
            raise ValueError("secret name must not be empty")
        self._secret_name = secret_name
        self._configured = parse_codes(configured)
        self._clock = clock or SystemClock()
        self._ttl_seconds = ttl_seconds
        self._cached: frozenset[str] | None = None
        self._fetched_at: datetime | None = None

    def codes(self) -> frozenset[str]:
        if self._configured:
            return self._configured
        now = self._clock.now()
        if self._cached is not None and self._fetched_at is not None:
            if (now - self._fetched_at).total_seconds() < self._ttl_seconds:
                return self._cached
        self._cached = parse_codes(self._secret_string())
        self._fetched_at = now
        return self._cached

    def _secret_string(self) -> str:
        response = self._client().get_secret_value(SecretId=self._secret_name)
        return str(response.get("SecretString") or "")

    def _client(self) -> Any:
        from repaso.config.clients import secrets_client

        client = secrets_client()
        if client is None:
            raise RuntimeError("secrets manager client is unavailable in local mode")
        return client


def build_invite_codes(settings: Settings, clock: Clock | None = None) -> InviteCodeSource:
    if settings.local_mode:
        return LocalInviteCodes(
            settings.pilot_invite_codes, settings.local_data_dir / INVITE_CODES_FILENAME
        )
    return SecretsManagerInviteCodes(
        settings.invite_codes_secret_name, settings.pilot_invite_codes, clock
    )
