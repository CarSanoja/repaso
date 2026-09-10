from repaso.tools.cost_report import NOT_REPORTED, CostReport, GroupTotals

GROUP_HEADER = f"{'':<44}{'calls':>6}{'in':>9}{'out':>8}{'cache r':>9}{'cache w':>9}{'usd':>10}"
LATENCY_HEADER = f"{'role':<44}{'calls':>6}{'p50 ms':>10}{'p95 ms':>10}"


def _group_line(totals: GroupTotals) -> str:
    if not totals.reported:
        return f"{totals.name[:43]:<44}{totals.calls:>6}{NOT_REPORTED:>45}"
    usage = totals.usage
    return (
        f"{totals.name[:43]:<44}{totals.calls:>6}{usage.input_tokens:>9}"
        f"{usage.output_tokens:>8}{usage.cache_read_tokens:>9}"
        f"{usage.cache_write_tokens:>9}{totals.total_usd:>10.4f}"
    )


def _block(title: str, groups: list[GroupTotals]) -> list[str]:
    return [title, GROUP_HEADER, *(_group_line(totals) for totals in groups), ""]


def _reasoning_line(report: CostReport) -> str:
    share = report.reasoning_share
    if share is None:
        return f"reasoning tokens: {NOT_REPORTED}"
    return (
        f"reasoning tokens: {report.usage.reasoning_tokens} of "
        f"{report.usage.output_tokens + report.usage.reasoning_tokens} generated "
        f"({share:.1%})"
    )


def _spend_line(report: CostReport) -> str:
    if not report.reported:
        return f"spend: {NOT_REPORTED} — none of the {report.calls} calls reported usage"
    unreported = report.calls - report.reported
    tail = f", {unreported} of {report.calls} without reported usage" if unreported else ""
    unpriced = report.reported - report.priced
    tail += f", {unpriced} with no rate in the price table" if unpriced else ""
    return f"spend: ${report.total_usd:.4f} over {report.calls} calls{tail}"


def _origin_line(report: CostReport) -> str:
    if not report.calls:
        return "origin: no calls"
    named = ", ".join(f"{count} {origin}" for origin, count in report.origins.items())
    verdict = "measured" if report.measured else "not a live measurement"
    return f"origin: {named} — {verdict}"


def render_cost_report(report: CostReport) -> str:
    if not report.calls:
        return "no model calls in this ledger"
    outcomes = ", ".join(f"{count} {outcome}" for outcome, count in report.outcomes.items())
    lines = [
        *_block("by role", report.by_role),
        *_block("by model", report.by_model),
        *_block("by call kind", report.by_kind),
        LATENCY_HEADER,
        *(
            f"{row.name[:43]:<44}{row.calls:>6}{row.p50_ms:>10.1f}{row.p95_ms:>10.1f}"
            for row in report.latency
        ),
        "",
        _spend_line(report),
        f"cache hit savings: ${report.cache_saving_usd:.4f}",
        _reasoning_line(report),
        f"outcomes: {outcomes}",
        _origin_line(report),
    ]
    return "\n".join(lines)
