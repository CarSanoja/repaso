import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from repaso.config.models import ModelRole
from repaso.core.harness.clock import SimClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.tools.call_ledger import CallOutcome, LocalCallLedger
from repaso.tools.cloud_trace import TraceFormatError, call_records, hops, trace_events
from repaso.tools.instrumented_model import instrument_models
from repaso.tools.llm import LocalPlaybackModel

START = datetime(2026, 9, 12, 22, 30, tzinfo=UTC)
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


class Verdict(BaseModel):
    ok: bool


class UsageReportingModel(LocalPlaybackModel):
    def get_config(self) -> dict[str, Any]:
        return {"model_id": MODEL_ID}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 1200, "outputTokens": 340, "cacheReadInputTokens": 64}
            }
        }
        async for event in super().structured_output(
            output_model, prompt, system_prompt=system_prompt, **kwargs
        ):
            yield event


def cloudwatch_lines(sink: LocalTelemetrySink) -> list[str]:
    lines = []
    for event in sink.events:
        logged = event.model_dump(mode="json")
        logged.pop("family_id", None)
        logged.pop("student_id", None)
        lines.append(json.dumps(logged))
    return lines


async def drive(tmp_path):
    sink = LocalTelemetrySink(tmp_path / "telemetry.jsonl", SimClock(START))
    ledger = LocalCallLedger(tmp_path / "model_calls.jsonl")
    models = instrument_models(
        {ModelRole.JUDGE: UsageReportingModel([{"ok": True}])},
        sink,
        None,
        ledger,
        SimClock(START),
    )
    async for _ in models[ModelRole.JUDGE].structured_output(Verdict, [{"role": "user"}]):
        pass
    sink.trace("delivery", "attempted")
    return sink, ledger


async def test_every_field_the_ledger_keeps_survives_the_log_line(tmp_path):
    sink, ledger = await drive(tmp_path)
    rebuilt = call_records(trace_events(cloudwatch_lines(sink)))
    assert rebuilt == ledger.records()


async def test_the_rebuilt_call_carries_tokens_price_and_stop_reason(tmp_path):
    sink, _ = await drive(tmp_path)
    record = call_records(trace_events(cloudwatch_lines(sink)))[0]
    assert record.role == "judge"
    assert record.model_id == MODEL_ID
    assert record.output_model == "Verdict"
    assert record.usage.input_tokens == 1200
    assert record.usage.output_tokens == 340
    assert record.usage.cache_read_tokens == 64
    assert record.stop_reason == "end_turn"
    assert record.outcome is CallOutcome.OK
    assert record.cost.total_usd == pytest.approx(0.0029064)


async def test_the_hops_between_the_calls_are_kept_apart(tmp_path):
    sink, _ = await drive(tmp_path)
    events = trace_events(cloudwatch_lines(sink))
    assert [(event.kind, event.name) for event in hops(events)] == [("delivery", "attempted")]


def test_lines_that_are_not_traces_are_passed_over():
    noise = [
        "START RequestId: 1",
        "{not json}",
        json.dumps({"timestamp": "x", "message": "Invocation completed successfully"}),
        json.dumps({"at": "2026-09-12T22:30:00Z", "kind": "node", "name": "ingest.parse"}),
    ]
    assert [event.name for event in trace_events(noise)] == ["ingest.parse"]


def test_an_llm_trace_without_a_call_id_is_refused():
    line = json.dumps(
        {
            "at": "2026-09-12T22:30:00Z",
            "kind": "llm",
            "name": "judge.structured_output",
            "extra": {"model_id": MODEL_ID, "evidence_origin": "live"},
        }
    )
    with pytest.raises(TraceFormatError):
        call_records(trace_events([line]))
