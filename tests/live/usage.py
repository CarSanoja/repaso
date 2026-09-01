from collections.abc import Mapping
from typing import Any

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel

INPUT_KEY = "inputTokens"
OUTPUT_KEY = "outputTokens"


class CallUsage(FrozenStrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    def plus(self, other: "CallUsage") -> "CallUsage":
        return CallUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


def _counted(usage: Mapping[str, Any], key: str) -> int:
    value = usage.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0


def usage_from_event(event: Any) -> CallUsage | None:
    if not isinstance(event, Mapping):
        return None
    metadata = event.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    usage = metadata.get("usage")
    if not isinstance(usage, Mapping):
        return None
    return CallUsage(
        input_tokens=_counted(usage, INPUT_KEY),
        output_tokens=_counted(usage, OUTPUT_KEY),
    )
