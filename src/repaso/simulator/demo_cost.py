from repaso.tools.cassette_cost import CassetteSpend

NO_USAGE = "no usage"
NO_RATE = "no rate"


def _tail(spend: CassetteSpend) -> str:
    missing = []
    if spend.unreported:
        missing.append(f"{spend.unreported} with {NO_USAGE} reported")
    if spend.unpriced:
        missing.append(f"{spend.unpriced} with {NO_RATE} in the price table")
    return f" ({', '.join(missing)})" if missing else ""


def cost_line(spend: CassetteSpend) -> str:
    if not spend.reported:
        return f"cost: {NO_USAGE} reported by any of the {spend.calls} recorded model calls"
    return (
        f"cost: {spend.usage.input_tokens:,} input + {spend.usage.output_tokens:,} output "
        f"tokens and ${spend.usd:.4f} over {spend.calls} recorded model calls{_tail(spend)}"
    )
