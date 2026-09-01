from tests.live.report import ConformanceReport

SCHEMA_HEADER = f"{'role':<11}{'schema':<18}{'calls':>6}{'ok':>5}{'in':>9}{'out':>8}{'usd':>10}"
LATENCY_HEADER = f"{'role':<11}{'calls':>6}{'p50 ms':>10}{'p95 ms':>10}"


def _schema_lines(report: ConformanceReport) -> list[str]:
    return [
        f"{totals.role:<11}{totals.output_schema:<18}{totals.calls:>6}{totals.parsed:>5}"
        f"{totals.input_tokens:>9}{totals.output_tokens:>8}{totals.estimated_usd:>10.4f}"
        for totals in report.schemas
    ]


def _latency_lines(report: ConformanceReport) -> list[str]:
    return [
        f"{latency.role:<11}{latency.calls:>6}{latency.p50_ms:>10.1f}{latency.p95_ms:>10.1f}"
        for latency in report.latency
    ]


def render_table(report: ConformanceReport) -> str:
    conformance = f"{report.parsed}/{report.calls}" if report.calls else "0/0"
    lines = [
        f"schema conformance at {report.samples_per_schema} samples per schema",
        SCHEMA_HEADER,
        *_schema_lines(report),
        f"{'total':<11}{'':<18}{report.calls:>6}{report.parsed:>5}"
        f"{report.input_tokens:>9}{report.output_tokens:>8}{report.total_usd:>10.4f}",
        "",
        LATENCY_HEADER,
        *_latency_lines(report),
        "",
        f"parsed {conformance}, estimated spend ${report.total_usd:.4f}",
    ]
    return "\n".join(lines)
