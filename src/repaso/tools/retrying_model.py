import asyncio
import random
from collections.abc import AsyncGenerator, AsyncIterable, Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent

from repaso.tools.model_limits import transient

T = TypeVar("T", bound=BaseModel)

DEFAULT_ATTEMPTS = 5
DEFAULT_BACKOFF_SECONDS = 2.0
JITTER_FLOOR = 0.5


class RetryingModel(Model):
    def __init__(
        self,
        inner: Model,
        attempts: int = DEFAULT_ATTEMPTS,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least one")
        self.inner = inner
        self.attempts = attempts
        self.backoff_seconds = backoff_seconds
        self.waits: list[float] = []
        self._sleep = sleep
        self._jitter = jitter

    def update_config(self, **model_config: Any) -> None:
        self.inner.update_config(**model_config)

    def get_config(self) -> Any:
        return self.inner.get_config()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def delay_before(self, attempt: int) -> float:
        return self.backoff_seconds * 2 ** (attempt - 1) * (JITTER_FLOOR + self._jitter())

    async def _collected(self, call: Callable[[], AsyncIterable[Any]]) -> list[Any]:
        for attempt in range(1, self.attempts + 1):
            try:
                return [event async for event in call()]
            except Exception as error:
                if attempt == self.attempts or not transient(error):
                    raise
                waited = self.delay_before(attempt)
                self.waits.append(waited)
                await self._sleep(waited)
        raise AssertionError("unreachable")

    async def stream(
        self, messages: Messages, *args: Any, **kwargs: Any
    ) -> AsyncIterable[StreamEvent]:
        for event in await self._collected(lambda: self.inner.stream(messages, *args, **kwargs)):
            yield event

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        def call() -> AsyncIterable[Any]:
            return self.inner.structured_output(
                output_model, prompt, system_prompt=system_prompt, **kwargs
            )

        for event in await self._collected(call):
            yield event
