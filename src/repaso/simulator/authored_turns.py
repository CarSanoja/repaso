"""Authored payloads for the schemas the demonstration recording predates."""

from collections.abc import AsyncGenerator
from typing import Any

from strands.models.model import Model

TURN_DECISION = "TurnDecision"
AUTHORED_TURNS: dict[str, dict[str, Any]] = {
    TURN_DECISION: {
        "intent": "answer",
        "speaker": "child",
        "asked_for": "Responde la pregunta que está en pantalla.",
        "answer_text": "",
    }
}


class AuthoredSchemaModel(Model):
    def __init__(self, recorded: Model, authored: dict[str, dict[str, Any]]) -> None:
        self._recorded = recorded
        self._authored = authored
        self.authored_calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self._recorded, name)

    def update_config(self, **model_config: Any) -> None:
        self._recorded.update_config(**model_config)

    def get_config(self) -> Any:
        return self._recorded.get_config()

    def stream(self, *args: Any, **kwargs: Any):
        return self._recorded.stream(*args, **kwargs)

    def structured_output(
        self, output_model: type, prompt: Any, system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        payload = self._authored.get(output_model.__name__)
        if payload is None:
            return self._recorded.structured_output(
                output_model, prompt, system_prompt=system_prompt, **kwargs
            )
        self.authored_calls.append(output_model.__name__)

        async def generator() -> AsyncGenerator[dict[str, Any], None]:
            yield {"output": output_model(**payload)}

        return generator()
