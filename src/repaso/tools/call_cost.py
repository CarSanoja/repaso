from pydantic import Field

from repaso.config.pricing import TOKENS_PER_UNIT, TokenPrice, UnpricedModel, price_for
from repaso.schemas.common import FrozenStrictModel
from repaso.tools.model_usage import CallUsage


class CallCost(FrozenStrictModel):
    input_usd: float = Field(default=0.0, ge=0.0)
    output_usd: float = Field(default=0.0, ge=0.0)
    cache_read_usd: float = Field(default=0.0, ge=0.0)
    cache_write_usd: float = Field(default=0.0, ge=0.0)
    reasoning_usd: float = Field(default=0.0, ge=0.0)

    def __add__(self, other: "CallCost") -> "CallCost":
        return CallCost(
            input_usd=self.input_usd + other.input_usd,
            output_usd=self.output_usd + other.output_usd,
            cache_read_usd=self.cache_read_usd + other.cache_read_usd,
            cache_write_usd=self.cache_write_usd + other.cache_write_usd,
            reasoning_usd=self.reasoning_usd + other.reasoning_usd,
        )

    @property
    def total_usd(self) -> float:
        return (
            self.input_usd
            + self.output_usd
            + self.cache_read_usd
            + self.cache_write_usd
            + self.reasoning_usd
        )


def _charged(tokens: int, usd_per_1k: float) -> float:
    return tokens * usd_per_1k / TOKENS_PER_UNIT


def cost_for(model_id: str, usage: CallUsage) -> CallCost:
    return _cost_at(price_for(model_id), usage)


def cost_or_none(model_id: str, usage: CallUsage) -> CallCost | None:
    try:
        return cost_for(model_id, usage)
    except UnpricedModel:
        return None


def cache_saving_usd(model_id: str, usage: CallUsage) -> float:
    price = price_for(model_id)
    uncached = _charged(usage.cache_read_tokens, price.input_usd_per_1k)
    return uncached - _charged(usage.cache_read_tokens, price.cache_read_usd_per_1k)


def _cost_at(price: TokenPrice, usage: CallUsage) -> CallCost:
    return CallCost(
        input_usd=_charged(usage.input_tokens, price.input_usd_per_1k),
        output_usd=_charged(usage.output_tokens, price.output_usd_per_1k),
        cache_read_usd=_charged(usage.cache_read_tokens, price.cache_read_usd_per_1k),
        cache_write_usd=_charged(usage.cache_write_tokens, price.cache_write_usd_per_1k),
        reasoning_usd=_charged(usage.reasoning_tokens, price.reasoning_usd_per_1k),
    )
