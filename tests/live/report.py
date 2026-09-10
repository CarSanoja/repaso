from collections.abc import Sequence
from datetime import datetime

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel
from repaso.tools.cost_report import P50, P95, percentile
from tests.live.calls import CallOutcome, ProbeCall

__all__ = ["percentile"]


class SampleRow(FrozenStrictModel):
    sample: int = Field(ge=1)
    role: str
    output_schema: str
    model_id: str
    outcome: CallOutcome
    latency_ms: float = Field(ge=0.0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_usd: float = Field(ge=0.0)
    error: str = ""


class RoleLatency(FrozenStrictModel):
    role: str
    calls: int = Field(ge=1)
    p50_ms: float = Field(ge=0.0)
    p95_ms: float = Field(ge=0.0)


class SchemaTotals(FrozenStrictModel):
    role: str
    output_schema: str
    calls: int = Field(ge=1)
    parsed: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_usd: float = Field(ge=0.0)


class ConformanceReport(FrozenStrictModel):
    written_at: datetime
    samples_per_schema: int = Field(ge=1)
    calls: int = Field(ge=0)
    parsed: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_usd: float = Field(ge=0.0)
    latency: list[RoleLatency]
    schemas: list[SchemaTotals]
    rows: list[SampleRow]


def row_for(call: ProbeCall, sample: int) -> SampleRow:
    return SampleRow(sample=sample, **call.model_dump())


def _latency(rows: Sequence[SampleRow]) -> list[RoleLatency]:
    roles: dict[str, list[float]] = {}
    for row in rows:
        roles.setdefault(row.role, []).append(row.latency_ms)
    return [
        RoleLatency(
            role=role,
            calls=len(latencies),
            p50_ms=percentile(latencies, P50),
            p95_ms=percentile(latencies, P95),
        )
        for role, latencies in sorted(roles.items())
    ]


def _schemas(rows: Sequence[SampleRow]) -> list[SchemaTotals]:
    grouped: dict[tuple[str, str], list[SampleRow]] = {}
    for row in rows:
        grouped.setdefault((row.role, row.output_schema), []).append(row)
    return [
        SchemaTotals(
            role=role,
            output_schema=name,
            calls=len(group),
            parsed=sum(1 for row in group if row.outcome is CallOutcome.PARSED),
            input_tokens=sum(row.input_tokens for row in group),
            output_tokens=sum(row.output_tokens for row in group),
            estimated_usd=sum(row.estimated_usd for row in group),
        )
        for (role, name), group in sorted(grouped.items())
    ]


def build_report(
    rows: Sequence[SampleRow], samples_per_schema: int, written_at: datetime
) -> ConformanceReport:
    return ConformanceReport(
        written_at=written_at,
        samples_per_schema=samples_per_schema,
        calls=len(rows),
        parsed=sum(1 for row in rows if row.outcome is CallOutcome.PARSED),
        input_tokens=sum(row.input_tokens for row in rows),
        output_tokens=sum(row.output_tokens for row in rows),
        total_usd=sum(row.estimated_usd for row in rows),
        latency=_latency(rows),
        schemas=_schemas(rows),
        rows=list(rows),
    )
