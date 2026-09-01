import asyncio
from typing import Any

from strands.models.model import Model

from repaso.agents.base import user_message
from repaso.config.models import FALLBACK_MODELS, ModelRole, model_for
from repaso.config.settings import Settings
from repaso.schemas.common import FrozenStrictModel

PING_PROMPT = "Responde únicamente con la palabra listo."
PING_TIMEOUT_SECONDS = 60.0


class LiveModeRequired(RuntimeError):
    pass


class ModelRoute(FrozenStrictModel):
    role: ModelRole
    model_id: str
    fallback: bool

    @property
    def name(self) -> str:
        tier = "fallback" if self.fallback else "default"
        return f"{self.role.value}-{tier}-{self.model_id}"


def build_routes() -> tuple[ModelRoute, ...]:
    defaults = [
        ModelRoute(role=role, model_id=model_for(role), fallback=False) for role in ModelRole
    ]
    fallbacks = [
        ModelRoute(role=role, model_id=model_id, fallback=True)
        for role in ModelRole
        for model_id in FALLBACK_MODELS[role]
    ]
    return (*defaults, *fallbacks)


def routing_model_ids() -> tuple[str, ...]:
    return tuple(route.model_id for route in build_routes())


def build_route_model(route: ModelRoute, settings: Settings) -> Model:
    if settings.local_mode:
        raise LiveModeRequired(f"{route.name} needs a region-backed Settings, not local mode")
    from strands.models.bedrock import BedrockModel

    return BedrockModel(model_id=route.model_id, region_name=settings.aws_region)


def _delta_text(event: Any) -> str:
    if not isinstance(event, dict):
        return ""
    delta = event.get("contentBlockDelta", {}).get("delta", {})
    text = delta.get("text") if isinstance(delta, dict) else None
    return text if isinstance(text, str) else ""


async def ping(model: Model, timeout_seconds: float = PING_TIMEOUT_SECONDS) -> str:
    chunks: list[str] = []
    async with asyncio.timeout(timeout_seconds):
        async for event in model.stream([user_message(PING_PROMPT)]):
            chunks.append(_delta_text(event))
    return "".join(chunks).strip()
