from collections import defaultdict, deque
from collections.abc import AsyncGenerator, AsyncIterable, Iterable
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages, SystemContentBlock
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec

from repaso.tools.cassette import STREAM_KIND, STRUCTURED_KIND, CassetteEntry
from repaso.tools.model_usage import usage_metadata

T = TypeVar("T", bound=BaseModel)

CassetteKey = tuple[str, str | None]


class CassetteExhausted(RuntimeError):
    pass


class CassetteModel(Model):
    def __init__(self, entries: Iterable[CassetteEntry], role: str) -> None:
        self.role = role
        self._queues: dict[CassetteKey, deque[CassetteEntry]] = {}
        for entry in entries:
            if entry.role == role:
                self._queues.setdefault((entry.kind, entry.output_model), deque()).append(entry)
        self._calls: dict[CassetteKey, int] = defaultdict(int)
        self._config: dict[str, Any] = {}

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self._config

    def remaining(self, kind: str, output_model: str | None = None) -> int:
        return len(self._queues.get((kind, output_model), ()))

    def remaining_total(self) -> int:
        return sum(len(queue) for queue in self._queues.values())

    def _take(self, kind: str, output_model: str | None) -> CassetteEntry:
        key = (kind, output_model)
        self._calls[key] += 1
        queue = self._queues.get(key)
        if not queue:
            raise CassetteExhausted(
                f"cassette for role {self.role} has no {kind} entry left for "
                f"{output_model or 'text'}: call number {self._calls[key]}"
            )
        return queue.popleft()

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        *,
        tool_choice: ToolChoice | None = None,
        system_prompt_content: list[SystemContentBlock] | None = None,
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        entry = self._take(STREAM_KIND, None)
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": entry.text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        if entry.usage is not None:
            yield usage_metadata(entry.usage)

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        entry = self._take(STRUCTURED_KIND, output_model.__name__)
        if entry.usage is not None:
            yield {"event": usage_metadata(entry.usage)}
        yield {"output": output_model.model_validate(entry.payload)}
