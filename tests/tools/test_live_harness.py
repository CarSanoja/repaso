import ast
import json
from pathlib import Path

import repaso.agents as agents_package
from repaso.config.models import ModelRole, model_for
from repaso.core.harness.clock import SimClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.tools.instrumented_model import InstrumentedModel
from repaso.tools.llm import LocalPlaybackModel
from tests.live.calls import CallOutcome, run_probe
from tests.live.registry import build_registry
from tests.live.report import percentile
from tests.live.reporter import FILE_PREFIX, ConformanceReporter
from tests.live.usage import usage_from_event
from tests.tools.live_fixtures import (
    PAYLOADS,
    START,
    MeteredPlaybackModel,
    RampClock,
    record_registry,
)


def structured_output_names() -> set[str]:
    names: set[str] = set()
    for path in sorted(Path(agents_package.__file__).parent.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "structured" and len(node.args) >= 2:
                argument = node.args[1]
                if isinstance(argument, ast.Name):
                    names.add(argument.id)
    return names


def test_registry_covers_every_schema_the_agents_ask_for():
    covered = {probe.name for probe in build_registry()}
    assert covered == structured_output_names()


def test_registry_exercises_every_model_role():
    roles = {probe.role for probe in build_registry()}
    assert roles == set(ModelRole)


def test_every_probe_carries_a_prompt_and_a_fully_formatted_system_prompt():
    for probe in build_registry():
        assert probe.prompt.strip()
        assert probe.system.strip()
        assert "{" not in probe.system


def test_offline_payloads_cover_the_whole_registry():
    assert set(PAYLOADS) == {probe.name for probe in build_registry()}


async def test_every_registry_schema_parses_under_playback(tmp_path):
    clock = RampClock()
    reporter = ConformanceReporter(clock, 2, tmp_path / "live")
    await record_registry(reporter, clock, 2)

    report = reporter.report()
    assert report.calls == len(build_registry()) * 2
    assert report.parsed == report.calls
    assert {totals.output_schema for totals in report.schemas} == set(PAYLOADS)


async def test_usage_metadata_becomes_tokens_and_dollars_on_every_row(tmp_path):
    clock = RampClock()
    reporter = ConformanceReporter(clock, 1, tmp_path / "live")
    await record_registry(reporter, clock, 1)

    report = reporter.report()
    assert report.input_tokens == 1200 * report.calls
    assert report.output_tokens == 400 * report.calls
    assert all(row.estimated_usd > 0.0 for row in report.rows)
    assert report.total_usd == sum(row.estimated_usd for row in report.rows)


def test_usage_is_ignored_when_the_stream_carries_no_metadata():
    assert usage_from_event({"output": object()}) is None
    assert usage_from_event({"metadata": {"metrics": {"latencyMs": 12}}}) is None
    counted = usage_from_event({"metadata": {"usage": {"inputTokens": 7, "outputTokens": 3}}})
    assert (counted.input_tokens, counted.output_tokens) == (7, 3)


async def test_instrumented_model_passes_usage_through_and_traces_the_call(tmp_path):
    sink = LocalTelemetrySink(tmp_path / "telemetry.jsonl", SimClock(START))
    probe = build_registry()[0]
    inner = MeteredPlaybackModel([PAYLOADS[probe.name]], 900, 120)
    model = InstrumentedModel(inner, probe.role.value, sink)

    call = await run_probe(model, probe, model_for(probe.role), RampClock())

    assert call.outcome is CallOutcome.PARSED
    assert (call.input_tokens, call.output_tokens) == (900, 120)
    assert sink.events[-1].name == f"{probe.role.value}.structured_output"


async def test_an_exhausted_script_is_recorded_not_raised():
    probe = build_registry()[0]
    call = await run_probe(LocalPlaybackModel(), probe, model_for(probe.role), RampClock())
    assert call.outcome is CallOutcome.CALL_FAILED
    assert "PlaybackExhausted" in call.error
    assert call.estimated_usd == 0.0


async def test_a_payload_the_schema_rejects_is_recorded_as_malformed():
    probe = next(p for p in build_registry() if p.name == "OpenGrade")
    model = LocalPlaybackModel([{"correct": True, "rubric_points": 9.0, "confidence": 0.9}])
    call = await run_probe(model, probe, model_for(probe.role), RampClock())
    assert call.outcome is CallOutcome.MALFORMED
    assert "field(s) rejected" in call.error


async def test_reporter_writes_a_timestamped_json_with_rows_and_percentiles(tmp_path):
    clock = RampClock()
    directory = tmp_path / "live"
    reporter = ConformanceReporter(clock, 3, directory)
    await record_registry(reporter, clock, 3)

    path = reporter.write()
    assert path.parent == directory
    assert path.name.startswith(FILE_PREFIX) and path.name.endswith(".json")

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["samples_per_schema"] == 3
    assert len(written["rows"]) == len(build_registry()) * 3
    assert {entry["role"] for entry in written["latency"]} == {role.value for role in ModelRole}
    for entry in written["latency"]:
        assert entry["p95_ms"] >= entry["p50_ms"] > 0.0


async def test_table_names_every_schema_and_closes_with_the_spend(tmp_path):
    clock = RampClock()
    reporter = ConformanceReporter(clock, 1, tmp_path / "live")
    await record_registry(reporter, clock, 1)

    table = reporter.table()
    for name in PAYLOADS:
        assert name in table
    assert "p95 ms" in table
    calls = len(build_registry())
    assert table.splitlines()[-1].startswith(f"parsed {calls}/{calls}")


def test_an_empty_run_still_reports_without_dividing_by_zero(tmp_path):
    report = ConformanceReporter(RampClock(), 5, tmp_path / "live").report()
    assert (report.calls, report.parsed, report.total_usd) == (0, 0, 0.0)
    assert report.latency == []


def test_percentile_uses_nearest_rank():
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.5) == 20.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.95) == 40.0
    assert percentile([7.0], 0.95) == 7.0
