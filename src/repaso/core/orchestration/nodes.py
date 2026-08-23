from collections.abc import Awaitable, Callable
from typing import Any

from strands.multiagent.base import MultiAgentBase, MultiAgentResult, Status


class StepNode(MultiAgentBase):
    def __init__(self, name: str, fn: Callable[[], Awaitable[None]]) -> None:
        super().__init__()
        self.id = name
        self.name = name
        self._fn = fn

    async def invoke_async(
        self, task: Any, invocation_state: dict[str, Any] | None = None, **kwargs: Any
    ) -> MultiAgentResult:
        await self._fn()
        return MultiAgentResult(status=Status.COMPLETED)
