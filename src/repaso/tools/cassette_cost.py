from pydantic import Field

from repaso.schemas.common import FrozenStrictModel
from repaso.tools.call_cost import cost_or_none
from repaso.tools.cassette import CassetteEntry
from repaso.tools.model_usage import CallUsage


class CassetteSpend(FrozenStrictModel):
    calls: int = Field(ge=0)
    reported: int = Field(ge=0)
    priced: int = Field(ge=0)
    usage: CallUsage
    usd: float = Field(ge=0.0)

    @property
    def unreported(self) -> int:
        return self.calls - self.reported

    @property
    def unpriced(self) -> int:
        return self.reported - self.priced


def cassette_spend(entries: list[CassetteEntry]) -> CassetteSpend:
    usage = CallUsage()
    usd = 0.0
    reported = 0
    priced = 0
    for entry in entries:
        if entry.usage is None:
            continue
        reported += 1
        usage = usage + entry.usage
        cost = cost_or_none(entry.model_id, entry.usage) if entry.model_id else None
        if cost is None:
            continue
        priced += 1
        usd += cost.total_usd
    return CassetteSpend(
        calls=len(entries), reported=reported, priced=priced, usage=usage, usd=usd
    )


def model_ids_in(entries: list[CassetteEntry]) -> list[str]:
    seen: list[str] = []
    for entry in entries:
        if entry.model_id and entry.model_id not in seen:
            seen.append(entry.model_id)
    return sorted(seen)
