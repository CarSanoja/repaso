from collections import deque
from collections.abc import AsyncGenerator, AsyncIterable
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages, SystemContentBlock
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolChoice, ToolSpec

from repaso.config.models import ModelRole, model_for
from repaso.config.settings import Settings
from repaso.tools.cassette import (
    STREAM_KIND,
    STRUCTURED_KIND,
    CassetteEntry,
    CassetteWriter,
    load_cassette,
)
from repaso.tools.cassette_model import CassetteModel
from repaso.tools.guardrails import DEFAULT_GUARDRAIL_VERSION
from repaso.tools.recording_model import RecordingModel

T = TypeVar("T", bound=BaseModel)

ScriptEntry = str | BaseModel | dict[str, Any]


class PlaybackExhausted(RuntimeError):
    pass


class LocalPlaybackModel(Model):
    def __init__(self, script: list[ScriptEntry] | None = None) -> None:
        self._script: deque[ScriptEntry] = deque(script or [])
        self._config: dict[str, Any] = {}
        self.calls: list[dict[str, Any]] = []

    def enqueue(self, entry: ScriptEntry) -> None:
        self._script.append(entry)

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self._config

    def _next(self, kind: str, messages: Any, system_prompt: str | None) -> ScriptEntry:
        self.calls.append(
            {
                "kind": kind,
                "system_prompt": system_prompt,
                "message_count": len(messages) if isinstance(messages, list) else 1,
            }
        )
        if not self._script:
            raise PlaybackExhausted(
                f"playback script is empty: unplanned {kind} call number {len(self.calls)}"
            )
        return self._script.popleft()

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
        entry = self._next(STREAM_KIND, messages, system_prompt)
        if not isinstance(entry, str):
            raise PlaybackExhausted(
                f"playback entry for stream must be str, got {type(entry).__name__}"
            )
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": entry}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        entry = self._next(STRUCTURED_KIND, prompt, system_prompt)
        if isinstance(entry, output_model):
            yield {"output": entry}
            return
        if not isinstance(entry, dict):
            raise PlaybackExhausted(
                f"playback entry for structured_output must be {output_model.__name__} "
                f"or dict, got {type(entry).__name__}"
            )
        yield {"output": output_model(**entry)}


@lru_cache(maxsize=4)
def _cassette_entries(path: Path) -> tuple[CassetteEntry, ...]:
    return tuple(load_cassette(path))


@lru_cache(maxsize=4)
def _cassette_writer(path: Path) -> CassetteWriter:
    return CassetteWriter(path)


def clear_cassette_cache() -> None:
    _cassette_entries.cache_clear()
    _cassette_writer.cache_clear()


def guardrail_config(settings: Settings) -> dict[str, str]:
    if not settings.guardrail_id:
        return {}
    return {
        "guardrail_id": settings.guardrail_id,
        "guardrail_version": settings.guardrail_version or DEFAULT_GUARDRAIL_VERSION,
    }


def build_model(
    role: ModelRole, settings: Settings, playback: LocalPlaybackModel | None = None
) -> Model:
    if settings.local_mode:
        if playback is not None:
            return playback
        if settings.cassette_path is not None:
            return CassetteModel(_cassette_entries(settings.cassette_path), role.value)
        return LocalPlaybackModel()
    from strands.models.bedrock import BedrockModel

    model = BedrockModel(
        model_id=model_for(role),
        region_name=settings.aws_region,
        **guardrail_config(settings),
    )
    if settings.record_cassette_path is None:
        return model
    return RecordingModel(model, _cassette_writer(settings.record_cassette_path), role.value)
