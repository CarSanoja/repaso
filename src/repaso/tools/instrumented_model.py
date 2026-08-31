import time
from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages

from repaso.config.models import ModelRole
from repaso.tools.llm import STREAM_KIND, STRUCTURED_KIND

T = TypeVar("T", bound=BaseModel)


class InstrumentedModel(Model):
    def __init__(self, inner: Model, role: str, telemetry: Any) -> None:
        self.inner = inner
        self._role = role
        self._telemetry = telemetry

    def update_config(self, **model_config: Any) -> None:
        self.inner.update_config(**model_config)

    def get_config(self) -> Any:
        return self.inner.get_config()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def _trace(self, call: str, status: str, started: float, **extra: str) -> None:
        duration = (time.perf_counter() - started) * 1000
        self._telemetry.trace(
            "llm", f"{self._role}.{call}", status=status, duration_ms=duration, **extra
        )

    async def stream(self, messages: Messages, *args: Any, **kwargs: Any):
        started = time.perf_counter()
        try:
            async for event in self.inner.stream(messages, *args, **kwargs):
                yield event
        except Exception as error:
            self._trace(STREAM_KIND, "failed", started, error=type(error).__name__)
            raise
        self._trace(STREAM_KIND, "ok", started)

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        started = time.perf_counter()
        try:
            async for event in self.inner.structured_output(
                output_model, prompt, system_prompt=system_prompt, **kwargs
            ):
                yield event
        except Exception as error:
            self._trace(
                STRUCTURED_KIND,
                "failed",
                started,
                error=type(error).__name__,
                output=output_model.__name__,
            )
            raise
        self._trace(STRUCTURED_KIND, "ok", started, output=output_model.__name__)


def instrument_models(models: dict[ModelRole, Model], telemetry: Any) -> dict[ModelRole, Model]:
    return {
        role: InstrumentedModel(model, role.value, telemetry) for role, model in models.items()
    }
