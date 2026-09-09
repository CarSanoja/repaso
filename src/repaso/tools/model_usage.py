from collections.abc import Mapping
from typing import Any

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel

INPUT_KEY = "inputTokens"
OUTPUT_KEY = "outputTokens"
TOTAL_KEY = "totalTokens"
CACHE_READ_KEY = "cacheReadInputTokens"
CACHE_WRITE_KEY = "cacheWriteInputTokens"
REASONING_KEYS = ("reasoningTokens", "reasoning_tokens")

WRAPPER_KEYS = ("event", "chunk")
METADATA_KEY = "metadata"
USAGE_KEY = "usage"
MESSAGE_STOP_KEY = "messageStop"
STOP_REASON_KEY = "stopReason"


class CallUsage(FrozenStrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)

    def __add__(self, other: "CallUsage") -> "CallUsage":
        return CallUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
        )

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
            + self.reasoning_tokens
        )


def _unwrapped(event: Any) -> Mapping[str, Any] | None:
    if not isinstance(event, Mapping):
        return None
    for key in WRAPPER_KEYS:
        inner = event.get(key)
        if isinstance(inner, Mapping):
            return inner
    return event


def _counted(usage: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float) and value >= 0:
            return int(value)
    return 0


def _reading(usage: Any) -> CallUsage | None:
    if not isinstance(usage, Mapping):
        return None
    counted = CallUsage(
        input_tokens=_counted(usage, INPUT_KEY),
        output_tokens=_counted(usage, OUTPUT_KEY),
        cache_read_tokens=_counted(usage, CACHE_READ_KEY),
        cache_write_tokens=_counted(usage, CACHE_WRITE_KEY),
        reasoning_tokens=_counted(usage, *REASONING_KEYS),
    )
    known = {INPUT_KEY, OUTPUT_KEY, CACHE_READ_KEY, CACHE_WRITE_KEY, *REASONING_KEYS}
    return counted if known & set(usage) else None


def usage_from_event(event: Any) -> CallUsage | None:
    unwrapped = _unwrapped(event)
    if unwrapped is None:
        return None
    metadata = unwrapped.get(METADATA_KEY)
    if not isinstance(metadata, Mapping):
        return None
    return _reading(metadata.get(USAGE_KEY))


def usage_from_response(response: Any) -> CallUsage | None:
    if not isinstance(response, Mapping):
        return None
    return _reading(response.get(USAGE_KEY))


def stop_reason_from_event(event: Any) -> str | None:
    unwrapped = _unwrapped(event)
    if unwrapped is None:
        return None
    stop = unwrapped.get(MESSAGE_STOP_KEY)
    if not isinstance(stop, Mapping):
        return None
    reason = stop.get(STOP_REASON_KEY)
    return reason if isinstance(reason, str) and reason else None


def usage_metadata(usage: CallUsage) -> dict[str, Any]:
    reported: dict[str, int] = {
        INPUT_KEY: usage.input_tokens,
        OUTPUT_KEY: usage.output_tokens,
        TOTAL_KEY: usage.total_tokens,
    }
    if usage.cache_read_tokens:
        reported[CACHE_READ_KEY] = usage.cache_read_tokens
    if usage.cache_write_tokens:
        reported[CACHE_WRITE_KEY] = usage.cache_write_tokens
    if usage.reasoning_tokens:
        reported[REASONING_KEYS[0]] = usage.reasoning_tokens
    return {METADATA_KEY: {USAGE_KEY: reported}}
