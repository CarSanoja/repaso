from collections import Counter
from collections.abc import Sequence
from datetime import datetime

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel
from repaso.tools.cost_report import P50, P95, percentile
from repaso.tools.proportion import ProportionInterval, wilson_interval
from tests.live.calls import CallOutcome
from tests.live.sweep import SweepRow


class MatrixCell(FrozenStrictModel):
    role: str
    output_schema: str
    model_id: str
    calls: int = Field(ge=1)
    parsed: int = Field(ge=0)
    parse_rate: ProportionInterval
    p50_ms: float = Field(ge=0.0)
    p95_ms: float = Field(ge=0.0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_usd: float = Field(ge=0.0)
    throttled_attempts: int = Field(ge=0)
    malformed: int = Field(ge=0)
    timed_out: int = Field(ge=0)
    call_failed: int = Field(ge=0)
    rejected_fields: dict[str, int] = {}

    @property
    def usd_per_call(self) -> float:
        return self.estimated_usd / self.calls


class MatrixReport(FrozenStrictModel):
    measured_at: datetime
    region: str
    samples_per_cell: int = Field(ge=1)
    calls: int = Field(ge=0)
    parsed: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_usd: float = Field(ge=0.0)
    throttled_attempts: int = Field(ge=0)
    cells: list[MatrixCell]
    rows: list[SweepRow]


def _counted(rows: Sequence[SweepRow], outcome: CallOutcome) -> int:
    return sum(1 for row in rows if row.outcome is outcome)


def _cell(rows: Sequence[SweepRow]) -> MatrixCell:
    latencies = [row.latency_ms for row in rows]
    parsed = _counted(rows, CallOutcome.PARSED)
    fields = Counter(name for row in rows for name in row.rejected_fields)
    return MatrixCell(
        role=rows[0].role,
        output_schema=rows[0].output_schema,
        model_id=rows[0].model_id,
        calls=len(rows),
        parsed=parsed,
        parse_rate=wilson_interval(parsed, len(rows)),
        p50_ms=percentile(latencies, P50),
        p95_ms=percentile(latencies, P95),
        input_tokens=sum(row.input_tokens for row in rows),
        output_tokens=sum(row.output_tokens for row in rows),
        estimated_usd=sum(row.estimated_usd for row in rows),
        throttled_attempts=sum(row.throttled_attempts for row in rows),
        malformed=_counted(rows, CallOutcome.MALFORMED),
        timed_out=_counted(rows, CallOutcome.TIMED_OUT),
        call_failed=_counted(rows, CallOutcome.CALL_FAILED),
        rejected_fields=dict(sorted(fields.items())),
    )


def build_matrix(
    rows: Sequence[SweepRow], samples_per_cell: int, region: str, measured_at: datetime
) -> MatrixReport:
    grouped: dict[tuple[str, str, str], list[SweepRow]] = {}
    for row in rows:
        grouped.setdefault((row.role, row.output_schema, row.model_id), []).append(row)
    return MatrixReport(
        measured_at=measured_at,
        region=region,
        samples_per_cell=samples_per_cell,
        calls=len(rows),
        parsed=_counted(rows, CallOutcome.PARSED),
        input_tokens=sum(row.input_tokens for row in rows),
        output_tokens=sum(row.output_tokens for row in rows),
        total_usd=sum(row.estimated_usd for row in rows),
        throttled_attempts=sum(row.throttled_attempts for row in rows),
        cells=[_cell(group) for _, group in sorted(grouped.items())],
        rows=list(rows),
    )
