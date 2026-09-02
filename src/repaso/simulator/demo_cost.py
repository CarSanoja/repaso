from dataclasses import dataclass

from repaso.tools.cassette import CassetteEntry

NOT_RECORDED = "not recorded"


@dataclass(frozen=True)
class TokenTotals:
    calls: int
    priced: int
    input_tokens: int
    output_tokens: int

    @property
    def unpriced(self) -> int:
        return self.calls - self.priced


def token_totals(entries: list[CassetteEntry]) -> TokenTotals:
    priced = [entry.usage for entry in entries if entry.usage is not None]
    return TokenTotals(
        calls=len(entries),
        priced=len(priced),
        input_tokens=sum(usage.input_tokens for usage in priced),
        output_tokens=sum(usage.output_tokens for usage in priced),
    )


def cost_line(totals: TokenTotals) -> str:
    if not totals.priced:
        return f"cost: {NOT_RECORDED} — none of the {totals.calls} cassette entries carry usage"
    tail = f" ({totals.unpriced} {NOT_RECORDED})" if totals.unpriced else ""
    return (
        f"cost: {totals.input_tokens:,} input + {totals.output_tokens:,} output tokens "
        f"over {totals.priced} of {totals.calls} model calls{tail}"
    )
