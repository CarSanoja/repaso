from collections.abc import Callable, Sequence

from pydantic import Field

from repaso.config.models import model_for
from repaso.config.pricing import estimate_cost_usd
from repaso.schemas.common import FrozenStrictModel
from tests.live.registry import SchemaProbe

CONSERVATIVE_INPUT_TOKENS = 2000
CONSERVATIVE_OUTPUT_TOKENS = 1000
ROUTING_INPUT_TOKENS = 64
ROUTING_OUTPUT_TOKENS = 16


class LiveBudgetExceeded(RuntimeError):
    pass


class BudgetEstimate(FrozenStrictModel):
    samples: int = Field(ge=1)
    conformance_calls: int = Field(ge=0)
    routing_calls: int = Field(ge=0)
    estimated_usd: float = Field(ge=0.0)
    limit_usd: float = Field(gt=0.0)

    @property
    def calls(self) -> int:
        return self.conformance_calls + self.routing_calls

    @property
    def within_budget(self) -> bool:
        return self.estimated_usd <= self.limit_usd

    def line(self) -> str:
        verdict = "within" if self.within_budget else "OVER"
        return (
            f"live tier estimate: {self.calls} calls "
            f"({self.conformance_calls} conformance at {self.samples} samples, "
            f"{self.routing_calls} routing) "
            f"~${self.estimated_usd:.4f} against a ${self.limit_usd:.4f} budget [{verdict}]"
        )


def estimate_budget(
    probes: Sequence[SchemaProbe],
    routing_models: Sequence[str],
    samples: int,
    limit_usd: float,
) -> BudgetEstimate:
    conformance = sum(
        estimate_cost_usd(
            model_for(probe.role), CONSERVATIVE_INPUT_TOKENS, CONSERVATIVE_OUTPUT_TOKENS
        )
        for probe in probes
    )
    routing = sum(
        estimate_cost_usd(model_id, ROUTING_INPUT_TOKENS, ROUTING_OUTPUT_TOKENS)
        for model_id in routing_models
    )
    return BudgetEstimate(
        samples=samples,
        conformance_calls=len(probes) * samples,
        routing_calls=len(routing_models),
        estimated_usd=conformance * samples + routing,
        limit_usd=limit_usd,
    )


def enforce_budget(
    estimate: BudgetEstimate, announce: Callable[[str], None] = print
) -> BudgetEstimate:
    announce(estimate.line())
    if not estimate.within_budget:
        raise LiveBudgetExceeded(estimate.line())
    return estimate
