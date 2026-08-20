import os
from enum import StrEnum


class ModelRole(StrEnum):
    GENERATE = "generate"
    JUDGE = "judge"
    STRUCTURED = "structured"
    CLASSIFY = "classify"
    PROBE = "probe"


DEFAULT_MODELS: dict[ModelRole, str] = {
    ModelRole.GENERATE: "us.anthropic.claude-sonnet-5",
    ModelRole.JUDGE: "us.anthropic.claude-sonnet-5",
    ModelRole.STRUCTURED: "us.anthropic.claude-haiku-4-5",
    ModelRole.CLASSIFY: "us.amazon.nova-lite-v1:0",
    ModelRole.PROBE: "us.amazon.nova-micro-v1:0",
}

FALLBACK_MODELS: dict[ModelRole, tuple[str, ...]] = {
    ModelRole.GENERATE: ("us.anthropic.claude-haiku-4-5",),
    ModelRole.JUDGE: ("us.anthropic.claude-haiku-4-5",),
    ModelRole.STRUCTURED: ("us.amazon.nova-lite-v1:0",),
    ModelRole.CLASSIFY: ("us.amazon.nova-micro-v1:0",),
    ModelRole.PROBE: ("us.amazon.nova-lite-v1:0",),
}


def model_for(role: ModelRole) -> str:
    return os.environ.get(f"REPASO_MODEL_{role.name}", DEFAULT_MODELS[role])


def fallback_chain(role: ModelRole) -> tuple[str, ...]:
    return (model_for(role), *FALLBACK_MODELS[role])
