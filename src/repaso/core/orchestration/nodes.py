import time
from collections.abc import Awaitable, Callable
from typing import Any

from strands.multiagent.base import MultiAgentBase, MultiAgentResult, Status

from repaso.core.telemetry.sink import NullTelemetrySink, TelemetrySink


class StepNode(MultiAgentBase):
    def __init__(
        self,
        name: str,
        fn: Callable[[], Awaitable[None]],
        telemetry: TelemetrySink | None = None,
        graph: str = "",
    ) -> None:
        super().__init__()
        self.id = name
        self.name = name
        self._fn = fn
        self._telemetry = telemetry or NullTelemetrySink()
        self._graph = graph

    async def invoke_async(
        self, task: Any, invocation_state: dict[str, Any] | None = None, **kwargs: Any
    ) -> MultiAgentResult:
        qualified = f"{self._graph}.{self.name}" if self._graph else self.name
        self._telemetry.trace("node", qualified, status="started")
        started = time.perf_counter()
        try:
            await self._fn()
        except Exception as error:
            self._telemetry.trace(
                "node",
                qualified,
                status="failed",
                duration_ms=(time.perf_counter() - started) * 1000,
                error=f"{type(error).__name__}: {error}"[:300],
            )
            raise
        self._telemetry.trace(
            "node",
            qualified,
            status="completed",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        return MultiAgentResult(status=Status.COMPLETED)
