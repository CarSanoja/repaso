import asyncio
from enum import StrEnum

from pydantic import Field, ValidationError
from strands.models.model import Model

from repaso.agents.base import user_message
from repaso.config.pricing import estimate_cost_usd
from repaso.core.harness.clock import Clock
from repaso.schemas.common import FrozenStrictModel
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


async def _drain(model: Model, probe: SchemaProbe) -> CallUsage:
    usage = CallUsage()
    output = None
    events = model.structured_output(
        probe.output_schema, [user_message(probe.prompt)], system_prompt=probe.system
    )
    async for event in events:
        usage = usage_from_event(event) or usage
        if isinstance(event, dict) and "output" in event:
            output = event["output"]
    if not isinstance(output, probe.output_schema):
        raise ValueError(NO_OUTPUT)
    return usage


async def run_probe(
    model: Model,
    probe: SchemaProbe,
    model_id: str,
    clock: Clock,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ProbeCall:
    started = clock.now()
    outcome = CallOutcome.PARSED
    usage = CallUsage()
    error = ""
    try:
        async with asyncio.timeout(timeout_seconds):
            usage = await _drain(model, probe)
    except TimeoutError:
        outcome = CallOutcome.TIMED_OUT
        error = f"no structured output within {timeout_seconds:.0f}s"
    except ValidationError as failure:
        outcome = CallOutcome.MALFORMED
        error = f"{type(failure).__name__}: {failure.error_count()} field(s) rejected"
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
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        estimated_usd=estimate_cost_usd(model_id, usage.input_tokens, usage.output_tokens),
        error=error,
    )
