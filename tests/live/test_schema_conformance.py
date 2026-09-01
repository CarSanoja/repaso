import pytest

from repaso.config.models import model_for
from repaso.core.harness.clock import SystemClock
from tests.live.calls import CallOutcome, run_probe
from tests.live.conftest import ENVIRONMENT
from tests.live.registry import build_registry

CASES = tuple(
    (probe, sample)
    for probe in build_registry()
    for sample in range(1, ENVIRONMENT.samples + 1)
)
CASE_IDS = tuple(f"{probe.name}-{sample:02d}" for probe, sample in CASES)


@pytest.mark.parametrize(("probe", "sample"), CASES, ids=CASE_IDS)
async def test_the_model_fills_the_schema_on_every_sample(
    probe, sample, live_models, live_reporter
):
    call = await run_probe(live_models[probe.role], probe, model_for(probe.role), SystemClock())
    live_reporter.record(call, sample)
    assert call.outcome is CallOutcome.PARSED, f"{probe.name} sample {sample}: {call.error}"


def test_the_run_measured_every_call_it_made(live_reporter):
    report = live_reporter.report()
    assert report.calls == len(CASES)
    assert report.parsed == report.calls
    assert report.input_tokens > 0
    assert report.output_tokens > 0
    assert report.total_usd > 0.0
    assert all(row.latency_ms > 0.0 for row in report.rows)
