import asyncio
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime

from pydantic import Field
from strands.models.model import Model

from repaso.agents.base import user_message
from repaso.core.harness.clock import Clock
from repaso.schemas.common import FrozenStrictModel
from repaso.tools.call_cost import cost_or_none
from repaso.tools.model_usage import CallUsage, usage_from_event
from repaso.tools.proportion import ProportionInterval, wilson_interval
from tests.live.decisions import DecisionProbe

REFUSED = "call refused"
DEFAULT_TIMEOUT_SECONDS = 120.0


class DecisionRow(FrozenStrictModel):
    decision: str
    role: str
    model_id: str
    sample: int = Field(ge=1)
    answered: bool
    answer: str
    expected: str
    latency_ms: float = Field(ge=0.0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_usd: float = Field(ge=0.0)
    error: str = ""

    @property
    def met(self) -> bool:
        return self.answered and self.answer == self.expected


class DecisionCell(FrozenStrictModel):
    decision: str
    role: str
    model_id: str
    expected: str
    ground_truth: bool
    calls: int = Field(ge=1)
    answered: int = Field(ge=0)
    met: int = Field(ge=0)
    agreement: ProportionInterval
    p50_ms: float = Field(ge=0.0)
    estimated_usd: float = Field(ge=0.0)
    answers: dict[str, int]


class DecisionReport(FrozenStrictModel):
    measured_at: datetime
    region: str
    samples_per_cell: int = Field(ge=1)
    calls: int = Field(ge=0)
    total_usd: float = Field(ge=0.0)
    cells: list[DecisionCell]
    rows: list[DecisionRow]


async def run_decision(
    model: Model,
    decision: DecisionProbe,
    model_id: str,
    sample: int,
    clock: Clock,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> DecisionRow:
    probe = decision.probe
    usage = CallUsage()
    answer = REFUSED
    answered = False
    error = ""
    started = clock.now()
    try:
        async with asyncio.timeout(timeout_seconds):
            events = model.structured_output(
                probe.output_schema, [user_message(probe.prompt)], system_prompt=probe.system
            )
            async for event in events:
                usage = usage_from_event(event) or usage
                if isinstance(event, dict) and "output" in event:
                    answer = decision.reading(event["output"])
                    answered = True
    except Exception as failure:
        error = type(failure).__name__
    cost = cost_or_none(model_id, usage)
    return DecisionRow(
        decision=decision.name,
        role=probe.role.value,
        model_id=model_id,
        sample=sample,
        answered=answered,
        answer=answer,
        expected=decision.expected,
        latency_ms=max((clock.now() - started).total_seconds() * 1000, 0.0),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        estimated_usd=0.0 if cost is None else cost.total_usd,
        error=error,
    )


def _cell(decision: DecisionProbe, rows: Sequence[DecisionRow]) -> DecisionCell:
    latencies = sorted(row.latency_ms for row in rows)
    met = sum(1 for row in rows if row.met)
    return DecisionCell(
        decision=rows[0].decision,
        role=rows[0].role,
        model_id=rows[0].model_id,
        expected=rows[0].expected,
        ground_truth=decision.ground_truth,
        calls=len(rows),
        answered=sum(1 for row in rows if row.answered),
        met=met,
        agreement=wilson_interval(met, len(rows)),
        p50_ms=latencies[len(latencies) // 2],
        estimated_usd=sum(row.estimated_usd for row in rows),
        answers=dict(sorted(Counter(row.answer for row in rows).items())),
    )


async def run_decision_probes(
    decisions: Sequence[DecisionProbe],
    models: dict[str, Model],
    samples: int,
    clock: Clock,
    region: str,
    announce: Callable[[str], None] = print,
) -> DecisionReport:
    rows: list[DecisionRow] = []
    cells: list[DecisionCell] = []
    for decision in decisions:
        for model_id, model in models.items():
            batch = [
                await run_decision(model, decision, model_id, sample, clock)
                for sample in range(1, samples + 1)
            ]
            rows.extend(batch)
            cells.append(_cell(decision, batch))
            announce(f"{decision.name} on {model_id}: {cells[-1].met}/{samples}")
    return DecisionReport(
        measured_at=clock.now(),
        region=region,
        samples_per_cell=samples,
        calls=len(rows),
        total_usd=sum(row.estimated_usd for row in rows),
        cells=cells,
        rows=rows,
    )
