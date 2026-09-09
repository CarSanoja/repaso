from pydantic import Field

from repaso.config.models import DEFAULT_MODELS, FALLBACK_MODELS
from repaso.schemas.common import FrozenStrictModel

TOKENS_PER_UNIT = 1000


class UnpricedModel(LookupError):
    pass


class TokenPrice(FrozenStrictModel):
    input_usd_per_1k: float = Field(ge=0.0)
    output_usd_per_1k: float = Field(ge=0.0)
    cache_read_usd_per_1k: float = Field(ge=0.0)
    cache_write_usd_per_1k: float = Field(ge=0.0)

    @property
    def reasoning_usd_per_1k(self) -> float:
        return self.output_usd_per_1k


PRICES: dict[str, TokenPrice] = {
    "us.anthropic.claude-sonnet-4-6": TokenPrice(
        input_usd_per_1k=0.003,
        output_usd_per_1k=0.015,
        cache_read_usd_per_1k=0.0003,
        cache_write_usd_per_1k=0.00375,
    ),
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": TokenPrice(
        input_usd_per_1k=0.001,
        output_usd_per_1k=0.005,
        cache_read_usd_per_1k=0.0001,
        cache_write_usd_per_1k=0.00125,
    ),
    "us.amazon.nova-lite-v1:0": TokenPrice(
        input_usd_per_1k=0.00006,
        output_usd_per_1k=0.00024,
        cache_read_usd_per_1k=0.000015,
        cache_write_usd_per_1k=0.0,
    ),
    "us.amazon.nova-micro-v1:0": TokenPrice(
        input_usd_per_1k=0.000035,
        output_usd_per_1k=0.00014,
        cache_read_usd_per_1k=0.00000875,
        cache_write_usd_per_1k=0.0,
    ),
}


def configured_models() -> frozenset[str]:
    chains = {model for chain in FALLBACK_MODELS.values() for model in chain}
    return frozenset(DEFAULT_MODELS.values()) | chains


def price_for(model_id: str) -> TokenPrice:
    price = PRICES.get(model_id)
    if price is None:
        raise UnpricedModel(f"no on-demand price is recorded for {model_id}")
    return price


def estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts cannot be negative")
    price = price_for(model_id)
    charged = input_tokens * price.input_usd_per_1k + output_tokens * price.output_usd_per_1k
    return charged / TOKENS_PER_UNIT
