from tests.live.matrix import MatrixReport
from tests.live.report import ConformanceReport

SCHEMA_HEADER = f"{'role':<11}{'schema':<18}{'calls':>6}{'ok':>5}{'in':>9}{'out':>8}{'usd':>10}"
LATENCY_HEADER = f"{'role':<11}{'calls':>6}{'p50 ms':>10}{'p95 ms':>10}"
MATRIX_HEADER = (
    f"{'schema':<17}{'model':<44}{'ok':>6}{'wilson 95%':>18}"
    f"{'p50 ms':>9}{'p95 ms':>9}{'in':>8}{'out':>7}{'usd':>9}"
)


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


def _matrix_lines(report: MatrixReport) -> list[str]:
    return [
        f"{cell.output_schema:<17}{cell.model_id:<44}"
        f"{cell.parsed:>3}/{cell.calls:<2}"
        f"{f'[{cell.parse_rate.low:.3f}, {cell.parse_rate.high:.3f}]':>18}"
        f"{cell.p50_ms:>9.0f}{cell.p95_ms:>9.0f}"
        f"{cell.input_tokens:>8}{cell.output_tokens:>7}{cell.estimated_usd:>9.4f}"
        for cell in report.cells
    ]


def render_matrix(report: MatrixReport) -> str:
    lines = [
        f"every schema against every configured model, {report.samples_per_cell} samples per cell",
        MATRIX_HEADER,
        *_matrix_lines(report),
        "",
        f"parsed {report.parsed}/{report.calls}, "
        f"{report.input_tokens} in, {report.output_tokens} out, "
        f"${report.total_usd:.4f}, {report.throttled_attempts} throttled attempts",
    ]
    return "\n".join(lines)
