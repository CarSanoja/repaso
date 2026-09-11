import asyncio
import random
from collections.abc import Callable, Sequence

from pydantic import Field
from strands.models.model import Model

from repaso.config.settings import Settings
from repaso.core.harness.clock import Clock
from repaso.schemas.common import FrozenStrictModel
from repaso.tools.llm import build_bedrock_model
from tests.live.calls import DEFAULT_TIMEOUT_SECONDS, CallOutcome, ProbeCall, run_probe
from tests.live.registry import SchemaProbe

THROTTLE_MARK = "ThrottlingException"
MAX_THROTTLE_ATTEMPTS = 6
BACKOFF_SECONDS = 3.0
BACKOFF_JITTER = 2.0
DEFAULT_CONCURRENCY = 4


class SweepRow(FrozenStrictModel):
    sample: int = Field(ge=1)
    role: str
    output_schema: str
    model_id: str
    outcome: CallOutcome
    latency_ms: float = Field(ge=0.0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_usd: float = Field(ge=0.0)
    rejected_fields: list[str] = []
    throttled_attempts: int = Field(default=0, ge=0)
    error: str = ""


class SweepCase(FrozenStrictModel):
    probe: SchemaProbe
    model_id: str
    sample: int = Field(ge=1)


def build_cases(
    probes: Sequence[SchemaProbe], model_ids: Sequence[str], samples: int
) -> tuple[SweepCase, ...]:
    return tuple(
        SweepCase(probe=probe, model_id=model_id, sample=sample)
        for sample in range(1, samples + 1)
        for model_id in model_ids
        for probe in probes
    )


def throttled(call: ProbeCall) -> bool:
    return call.outcome is CallOutcome.CALL_FAILED and THROTTLE_MARK in call.error


def build_sweep_models(model_ids: Sequence[str], settings: Settings) -> dict[str, Model]:
    return {model_id: build_bedrock_model(model_id, settings) for model_id in model_ids}


async def run_case(
    case: SweepCase,
    model: Model,
    clock: Clock,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    sleep: Callable[[float], object] = asyncio.sleep,
) -> SweepRow:
    attempts = 0
    while True:
        call = await run_probe(model, case.probe, case.model_id, clock, timeout_seconds)
        if not throttled(call) or attempts >= MAX_THROTTLE_ATTEMPTS:
            return SweepRow(
                sample=case.sample, throttled_attempts=attempts, **call.model_dump()
            )
        attempts += 1
        await sleep(BACKOFF_SECONDS * attempts + random.uniform(0.0, BACKOFF_JITTER))


async def run_sweep(
    cases: Sequence[SweepCase],
    models: dict[str, Model],
    clock: Clock,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    announce: Callable[[str], None] = print,
) -> list[SweepRow]:
    gate = asyncio.Semaphore(concurrency)
    done = 0

    async def guarded(case: SweepCase) -> SweepRow:
        nonlocal done
        async with gate:
            row = await run_case(case, models[case.model_id], clock, timeout_seconds)
        done += 1
        announce(
            f"[{done}/{len(cases)}] {row.output_schema} {row.model_id} "
            f"sample {row.sample}: {row.outcome.value} {row.latency_ms:.0f}ms"
        )
        return row

    return list(await asyncio.gather(*(guarded(case) for case in cases)))
