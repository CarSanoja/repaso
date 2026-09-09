from datetime import datetime
from enum import StrEnum

from repaso.config.settings import Settings
from repaso.tools.call_quota import CallQuota
from repaso.tools.state_store import StateStore

MINUTE_FORMAT = "%Y-%m-%dT%H:%M"
DAY_FORMAT = "%Y-%m-%d"
WINDOW_TTL_SECONDS = 3600
DAY_TTL_SECONDS = 172800
TRACE_KIND = "throttle"
REFUSED = "refused"


class Admission(StrEnum):
    ADMITTED = "admitted"
    RATE_LIMITED = "rate_limited"
    UNKNOWN_CHAT_EXHAUSTED = "unknown_chat_exhausted"


def _reserve(quota: CallQuota, key: str, limit: int, now: datetime, ttl: int) -> bool:
    return quota.reserve(key, limit, int(now.timestamp()) + ttl)


def _enrolled(store: StateStore, channel: str, chat_ref: str) -> bool:
    if store.find_family_by_chat(channel, chat_ref) is not None:
        return True
    return store.get_enrollment(channel, chat_ref) is not None


def admit(
    store: StateStore,
    quota: CallQuota,
    settings: Settings,
    now: datetime,
    channel: str,
    chat_ref: str,
) -> Admission:
    window = now.strftime(MINUTE_FORMAT)
    if not _reserve(
        quota,
        f"rate#{channel}#{chat_ref}#{window}",
        settings.chat_messages_per_minute,
        now,
        WINDOW_TTL_SECONDS,
    ):
        return Admission.RATE_LIMITED
    if _enrolled(store, channel, chat_ref):
        return Admission.ADMITTED
    day = now.strftime(DAY_FORMAT)
    if not _reserve(
        quota,
        f"stranger#{channel}#{chat_ref}#{day}",
        settings.unknown_chat_daily_messages,
        now,
        DAY_TTL_SECONDS,
    ):
        return Admission.UNKNOWN_CHAT_EXHAUSTED
    return Admission.ADMITTED


def report(
    telemetry,
    quota: CallQuota,
    now: datetime,
    channel: str,
    chat_ref: str,
    admission: Admission,
) -> None:
    window = now.strftime(MINUTE_FORMAT)
    key = f"refusal#{admission.value}#{channel}#{chat_ref}#{window}"
    if not _reserve(quota, key, 1, now, WINDOW_TTL_SECONDS):
        return
    telemetry.trace(TRACE_KIND, admission.value, status=REFUSED, channel=channel)
