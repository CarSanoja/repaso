import json
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from repaso.config.models import ModelRole
from repaso.core.harness.clock import SimClock
from repaso.core.orchestration.nodes import StepNode
from repaso.core.telemetry.sink import LocalTelemetrySink, build_telemetry_sink
from repaso.tools.instrumented_model import instrument_models
from repaso.tools.llm import LocalPlaybackModel, PlaybackExhausted

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


class Verdict(BaseModel):
    ok: bool


def make_sink(tmp_path) -> LocalTelemetrySink:
    return LocalTelemetrySink(tmp_path / "telemetry.jsonl", SimClock(START))


def test_sink_appends_replayable_jsonl(tmp_path):
    sink = make_sink(tmp_path)
    sink.trace("node", "ingest.parse", status="completed", duration_ms=12.5, family_id="f1")
    line = (tmp_path / "telemetry.jsonl").read_text().splitlines()[0]
    parsed = json.loads(line)
    assert parsed["name"] == "ingest.parse"
    assert parsed["status"] == "completed"
    assert parsed["family_id"] == "f1"


async def test_step_node_emits_start_and_completion(tmp_path):
    sink = make_sink(tmp_path)

    async def work() -> None:
        return None

    await StepNode("parse", work, sink, "ingest").invoke_async("task")
    statuses = [(e.name, e.status) for e in sink.events]
    assert statuses == [("ingest.parse", "started"), ("ingest.parse", "completed")]
    assert sink.events[1].duration_ms is not None


async def test_step_node_records_failures_and_reraises(tmp_path):
    sink = make_sink(tmp_path)

    async def broken() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await StepNode("grade", broken, sink, "response").invoke_async("task")
    failed = sink.events[-1]
    assert failed.status == "failed"
    assert "ValueError" in failed.error


async def test_instrumented_model_traces_llm_calls(tmp_path):
    sink = make_sink(tmp_path)
    models = instrument_models({ModelRole.JUDGE: LocalPlaybackModel([{"ok": True}])}, sink)
    judge = models[ModelRole.JUDGE]

    output = None
    async for event in judge.structured_output(Verdict, [{"role": "user", "content": []}]):
        output = event.get("output")

    assert output == Verdict(ok=True)
    trace = sink.events[-1]
    assert trace.kind == "llm"
    assert trace.name == "judge.structured_output"
    assert trace.extra["output"] == "Verdict"


async def test_instrumented_model_records_failures(tmp_path):
    sink = make_sink(tmp_path)
    models = instrument_models({ModelRole.PROBE: LocalPlaybackModel([])}, sink)
    with pytest.raises(PlaybackExhausted):
        async for _ in models[ModelRole.PROBE].structured_output(Verdict, []):
            pass
    assert sink.events[-1].status == "failed"


def test_factory_returns_local_sink_in_local_mode(settings):
    sink = build_telemetry_sink(settings)
    assert isinstance(sink, LocalTelemetrySink)
