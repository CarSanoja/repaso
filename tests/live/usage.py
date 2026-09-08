from typing import Any

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel
from repaso.tools.recording_model import reported_usage


class CallUsage(FrozenStrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    def plus(self, other: "CallUsage") -> "CallUsage":
        return CallUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


def usage_from_event(event: Any) -> CallUsage | None:
    counted = reported_usage(event)
    if counted is None:
        return None
    return CallUsage(input_tokens=counted.input_tokens, output_tokens=counted.output_tokens)
