from collections import deque
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any

from strands.models.model import Model

SNIPPET_TEXT = "Recuerda: dos fracciones son equivalentes cuando nombran la misma cantidad."
NOTE_TEXT = "Estimada maestra: varias prácticas recientes muestran dificultades con este tema."

DEFAULTS: dict[str, dict[str, Any]] = {
    "Snippet": {"text": SNIPPET_TEXT},
    "PolicyDecision": {"action": "continue", "reason": "auto"},
    "TeacherNote": {"text": NOTE_TEXT},
    "OpenGrade": {"correct": True, "rubric_points": 2.0, "confidence": 0.92, "feedback": "Bien."},
    "IntakeDecision": {"safe": True, "reasons": []},
}


class AutoStubModel(Model):
    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self.queues: dict[str, deque] = {}
        self.calls: list[str] = []

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    def prime(self, output_name: str, payload: dict[str, Any]) -> None:
        self.queues.setdefault(output_name, deque()).append(payload)

    def structured_output(
        self, output_model: type, prompt: Any, system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        name = output_model.__name__
        self.calls.append(name)
        queue = self.queues.get(name)
        payload = queue.popleft() if queue else DEFAULTS.get(name)
        if payload is None:
            raise RuntimeError(f"AutoStubModel has no default for {name}")

        async def generator() -> AsyncGenerator[dict[str, Any], None]:
            yield {"output": output_model(**payload)}

        return generator()

    def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncIterable[dict[str, Any]]:
        self.calls.append("stream")

        async def generator() -> AsyncGenerator[dict[str, Any], None]:
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": "ok"}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}

        return generator()
