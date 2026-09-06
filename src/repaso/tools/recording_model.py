import time
from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages

from repaso.tools.cassette import (
    STREAM_KIND,
    STRUCTURED_KIND,
    CassetteEntry,
    CassetteWriter,
    Usage,
)

T = TypeVar("T", bound=BaseModel)


def _mapping(value: Any, key: str) -> dict[str, Any]:
    inner = value.get(key) if isinstance(value, dict) else None
    return inner if isinstance(inner, dict) else {}


def _streamed_text(event: Any) -> str | None:
    text = _mapping(_mapping(event, "contentBlockDelta"), "delta").get("text")
    return text if isinstance(text, str) else None


def _reported_usage(event: Any) -> Usage | None:
    usage = _mapping(_mapping(event, "metadata"), "usage")
    if not usage:
        usage = _mapping(_mapping(_mapping(event, "chunk"), "metadata"), "usage")
    if "inputTokens" not in usage or "outputTokens" not in usage:
        return None
    return Usage(input_tokens=usage["inputTokens"], output_tokens=usage["outputTokens"])


class RecordingModel(Model):
    def __init__(self, inner: Model, writer: CassetteWriter, role: str) -> None:
        self.inner = inner
        self._writer = writer
        self._role = role
        self.evidence_origin = getattr(inner, "evidence_origin", None) or (
            "live" if type(inner).__name__ == "BedrockModel" else "simulation"
        )

    def update_config(self, **model_config: Any) -> None:
        self.inner.update_config(**model_config)

    def get_config(self) -> Any:
        return self.inner.get_config()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def _elapsed_ms(self, started: float) -> float:
        return (time.perf_counter() - started) * 1000

    async def stream(self, messages: Messages, *args: Any, **kwargs: Any):
        started = time.perf_counter()
        chunks: list[str] = []
        usage: Usage | None = None
        async for event in self.inner.stream(messages, *args, **kwargs):
            text = _streamed_text(event)
            if text is not None:
                chunks.append(text)
            usage = _reported_usage(event) or usage
            yield event
        self._writer.append(
            CassetteEntry(
                role=self._role,
                kind=STREAM_KIND,
                text="".join(chunks),
                usage=usage,
                latency_ms=self._elapsed_ms(started),
            )
        )

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        started = time.perf_counter()
        payload: dict[str, Any] | None = None
        usage: Usage | None = None
        async for event in self.inner.structured_output(
            output_model, prompt, system_prompt=system_prompt, **kwargs
        ):
            output = event.get("output") if isinstance(event, dict) else None
            if isinstance(output, BaseModel):
                payload = output.model_dump(mode="json")
            usage = _reported_usage(event) or usage
            yield event
        if payload is None:
            return
        self._writer.append(
            CassetteEntry(
                role=self._role,
                kind=STRUCTURED_KIND,
                output_model=output_model.__name__,
                payload=payload,
                usage=usage,
                latency_ms=self._elapsed_ms(started),
            )
        )
