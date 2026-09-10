import asyncio
from enum import StrEnum

from pydantic import Field, ValidationError
from strands.models.model import Model

from repaso.agents.base import user_message
from repaso.core.harness.clock import Clock
from repaso.schemas.common import FrozenStrictModel
from repaso.tools.call_cost import cost_or_none
from repaso.tools.model_usage import CallUsage, usage_from_event
from tests.live.registry import SchemaProbe

DEFAULT_TIMEOUT_SECONDS = 120.0
NO_OUTPUT = "the model returned no structured output"


class CallOutcome(StrEnum):
    PARSED = "parsed"
    MALFORMED = "malformed"
    TIMED_OUT = "timed_out"
    CALL_FAILED = "call_failed"


class ProbeCall(FrozenStrictModel):
    role: str
    output_schema: str
    model_id: str
    outcome: CallOutcome
    latency_ms: float = Field(ge=0.0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_usd: float = Field(default=0.0, ge=0.0)
    error: str = ""

    @property
    def parsed(self) -> bool:
        return self.outcome is CallOutcome.PARSED


class Spend:
    def __init__(self) -> None:
        self.usage = CallUsage()


async def _drain(model: Model, probe: SchemaProbe, spend: Spend) -> None:
    output = None
    events = model.structured_output(
        probe.output_schema, [user_message(probe.prompt)], system_prompt=probe.system
    )
    async for event in events:
        spend.usage = usage_from_event(event) or spend.usage
        if isinstance(event, dict) and "output" in event:
            output = event["output"]
    if not isinstance(output, probe.output_schema):
        raise ValueError(NO_OUTPUT)


def _rejected(failure: ValidationError) -> str:
    named = ", ".join(".".join(str(part) for part in error["loc"]) for error in failure.errors())
    return f"{failure.error_count()} field(s) rejected: {named}"


def _priced(model_id: str, usage: CallUsage) -> float:
    cost = cost_or_none(model_id, usage)
    return 0.0 if cost is None else cost.total_usd


async def run_probe(
    model: Model,
    probe: SchemaProbe,
    model_id: str,
    clock: Clock,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ProbeCall:
    started = clock.now()
    outcome = CallOutcome.PARSED
    spend = Spend()
    error = ""
    try:
        async with asyncio.timeout(timeout_seconds):
            await _drain(model, probe, spend)
    except TimeoutError:
        outcome = CallOutcome.TIMED_OUT
        error = f"no structured output within {timeout_seconds:.0f}s"
    except ValidationError as failure:
        outcome = CallOutcome.MALFORMED
        error = f"{type(failure).__name__}: {_rejected(failure)}"
    except Exception as failure:
        outcome = CallOutcome.CALL_FAILED
        error = f"{type(failure).__name__}: {failure}"
    elapsed_ms = (clock.now() - started).total_seconds() * 1000
    return ProbeCall(
        role=probe.role.value,
        output_schema=probe.name,
        model_id=model_id,
        outcome=outcome,
        latency_ms=max(elapsed_ms, 0.0),
        input_tokens=spend.usage.input_tokens,
        output_tokens=spend.usage.output_tokens,
        estimated_usd=_priced(model_id, spend.usage),
        error=error,
    )
