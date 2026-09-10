import math
from collections.abc import Callable, Sequence

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel
from repaso.tools.call_cost import CallCost, cache_saving_usd
from repaso.tools.call_ledger import CallOrigin, CallOutcome, CallRecord
from repaso.tools.model_usage import CallUsage

P50 = 0.50
P95 = 0.95
NOT_REPORTED = "not reported"


class GroupTotals(FrozenStrictModel):
    name: str
    calls: int = Field(ge=0)
    reported: int = Field(ge=0)
    priced: int = Field(ge=0)
    usage: CallUsage
    cost: CallCost
    cache_saving_usd: float = Field(ge=0.0)

    @property
    def total_usd(self) -> float:
        return self.cost.total_usd


class RoleLatency(FrozenStrictModel):
    name: str
    calls: int = Field(ge=1)
    p50_ms: float = Field(ge=0.0)
    p95_ms: float = Field(ge=0.0)


class CostReport(FrozenStrictModel):
    calls: int = Field(ge=0)
    reported: int = Field(ge=0)
    priced: int = Field(ge=0)
    origins: dict[str, int]
    outcomes: dict[str, int]
    usage: CallUsage
    cost: CallCost
    cache_saving_usd: float = Field(ge=0.0)
    by_role: list[GroupTotals]
    by_model: list[GroupTotals]
    by_kind: list[GroupTotals]
    latency: list[RoleLatency]

    @property
    def total_usd(self) -> float:
        return self.cost.total_usd

    @property
    def reasoning_share(self) -> float | None:
        generated = self.usage.output_tokens + self.usage.reasoning_tokens
        if not self.usage.reasoning_tokens or not generated:
            return None
        return self.usage.reasoning_tokens / generated

    @property
    def measured(self) -> bool:
        return self.origins.get(CallOrigin.LIVE.value, 0) == self.calls > 0


def percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def _saving(record: CallRecord) -> float:
    if record.usage is None or record.cost is None:
        return 0.0
    return cache_saving_usd(record.model_id, record.usage)


def _totals(name: str, group: Sequence[CallRecord]) -> GroupTotals:
    usage = CallUsage()
    cost = CallCost()
    for record in group:
        usage = usage + (record.usage or CallUsage())
        cost = cost + (record.cost or CallCost())
    return GroupTotals(
        name=name,
        calls=len(group),
        reported=sum(1 for record in group if record.usage is not None),
        priced=sum(1 for record in group if record.cost is not None),
        usage=usage,
        cost=cost,
        cache_saving_usd=sum(_saving(record) for record in group),
    )


def _grouped(
    records: Sequence[CallRecord], key: Callable[[CallRecord], str]
) -> list[GroupTotals]:
    groups: dict[str, list[CallRecord]] = {}
    for record in records:
        groups.setdefault(key(record), []).append(record)
    return [_totals(name, group) for name, group in sorted(groups.items())]


def _counted(records: Sequence[CallRecord], key: Callable[[CallRecord], str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[key(record)] = counts.get(key(record), 0) + 1
    return dict(sorted(counts.items()))


def _latency(records: Sequence[CallRecord]) -> list[RoleLatency]:
    roles: dict[str, list[float]] = {}
    for record in records:
        roles.setdefault(record.role, []).append(record.latency_ms)
    return [
        RoleLatency(
            name=role,
            calls=len(latencies),
            p50_ms=percentile(latencies, P50),
            p95_ms=percentile(latencies, P95),
        )
        for role, latencies in sorted(roles.items())
    ]


def build_cost_report(records: Sequence[CallRecord]) -> CostReport:
    whole = _totals("total", records)
    return CostReport(
        calls=whole.calls,
        reported=whole.reported,
        priced=whole.priced,
        origins=_counted(records, lambda record: CallOrigin(record.origin).value),
        outcomes=_counted(records, lambda record: CallOutcome(record.outcome).value),
        usage=whole.usage,
        cost=whole.cost,
        cache_saving_usd=whole.cache_saving_usd,
        by_role=_grouped(records, lambda record: record.role),
        by_model=_grouped(records, lambda record: record.model_id),
        by_kind=_grouped(records, lambda record: record.kind),
        latency=_latency(records),
    )
