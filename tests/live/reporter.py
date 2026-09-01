from pathlib import Path

from repaso.core.harness.clock import Clock
from tests.live.calls import ProbeCall
from tests.live.report import ConformanceReport, SampleRow, build_report, row_for
from tests.live.table import render_table

FILE_PREFIX = "conformance-"
FILE_SUFFIX = ".json"
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


class ConformanceReporter:
    def __init__(self, clock: Clock, samples_per_schema: int, directory: Path) -> None:
        self._clock = clock
        self._samples = samples_per_schema
        self._directory = directory
        self._rows: list[SampleRow] = []

    def record(self, call: ProbeCall, sample: int) -> SampleRow:
        row = row_for(call, sample)
        self._rows.append(row)
        return row

    def report(self) -> ConformanceReport:
        return build_report(self._rows, self._samples, self._clock.now())

    def table(self) -> str:
        return render_table(self.report())

    def write(self) -> Path:
        report = self.report()
        stamp = report.written_at.strftime(TIMESTAMP_FORMAT)
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{FILE_PREFIX}{stamp}{FILE_SUFFIX}"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path
