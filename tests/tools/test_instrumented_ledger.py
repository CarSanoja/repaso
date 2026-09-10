from typing import Any

import pytest
from pydantic import BaseModel

from repaso.core.harness.clock import SimClock
from repaso.core.telemetry.sink import NullTelemetrySink
from repaso.tools.call_ledger import CallOrigin, CallOutcome, LocalCallLedger
from repaso.tools.cassette import CassetteEntry
from repaso.tools.cassette_model import CassetteModel
from repaso.tools.instrumented_model import InstrumentedModel
from repaso.tools.llm import LocalPlaybackModel, PlaybackExhausted
from repaso.tools.model_usage import CallUsage
from tests.tools.live_fixtures import START, MeteredPlaybackModel, NestedMetadataModel

HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


class Verdict(BaseModel):
    ok: bool


def wrapped(inner: Any, ledger, role: str = "judge", model_id: str = HAIKU) -> InstrumentedModel:
    inner.update_config(model_id=model_id)
    return InstrumentedModel(inner, role, NullTelemetrySink(), None, ledger, SimClock(START))


async def drain(model: Any) -> None:
    async for _ in model.structured_output(Verdict, []):
        pass


async def test_every_call_leaves_a_line(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    model = wrapped(NestedMetadataModel([{"ok": True}, {"ok": True}], 410, 14), ledger)

    await drain(model)
    await drain(model)

    rows = ledger.records()
    assert len(rows) == 2
    assert len({row.call_id for row in rows}) == 2
    assert all(row.outcome is CallOutcome.OK for row in rows)


async def test_a_structured_call_records_the_tokens_and_dollars_it_spent(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    await drain(wrapped(NestedMetadataModel([{"ok": True}], 410, 14), ledger))

    row = ledger.records()[0]
    assert row.usage == CallUsage(input_tokens=410, output_tokens=14)
    assert row.cost.input_usd == pytest.approx(410 * 0.001 / 1000)
    assert row.cost.output_usd == pytest.approx(14 * 0.005 / 1000)
    assert row.model_id == HAIKU
    assert (row.role, row.kind, row.output_model) == ("judge", "structured_output", "Verdict")
    assert row.at == START


async def test_the_flat_shape_records_the_same_way(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    await drain(wrapped(MeteredPlaybackModel([{"ok": True}], 410, 14), ledger))

    assert ledger.records()[0].usage == CallUsage(input_tokens=410, output_tokens=14)


async def test_a_failed_call_is_recorded_with_what_went_wrong(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    with pytest.raises(PlaybackExhausted):
        await drain(wrapped(LocalPlaybackModel(), ledger))

    row = ledger.records()[0]
    assert row.outcome is CallOutcome.FAILED
    assert row.error == "PlaybackExhausted"
    assert row.usage is None and row.cost is None


async def test_a_replayed_call_carries_the_recorded_cost_and_says_it_was_replayed(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    entry = CassetteEntry(
        role="judge",
        kind="structured_output",
        output_model="Verdict",
        payload={"ok": True},
        model_id=HAIKU,
        stop_reason="tool_use",
        usage=CallUsage(input_tokens=410, output_tokens=14),
    )
    model = InstrumentedModel(
        CassetteModel([entry], "judge"), "judge", NullTelemetrySink(), None, ledger, SimClock(START)
    )

    await drain(model)

    row = ledger.records()[0]
    assert row.origin is CallOrigin.REPLAYED
    assert row.measured is False
    assert row.usage == CallUsage(input_tokens=410, output_tokens=14)
    assert row.cost.total_usd > 0.0
    assert (row.model_id, row.stop_reason) == (HAIKU, "tool_use")


async def test_a_model_that_only_plays_back_is_neither_live_nor_replayed(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    await drain(wrapped(LocalPlaybackModel([{"ok": True}]), ledger))

    assert ledger.records()[0].origin is CallOrigin.SIMULATED


async def test_an_unpriced_model_records_usage_without_inventing_a_cost(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    await drain(
        wrapped(NestedMetadataModel([{"ok": True}], 10, 2), ledger, model_id="us.mistral.large")
    )

    row = ledger.records()[0]
    assert row.usage == CallUsage(input_tokens=10, output_tokens=2)
    assert row.cost is None


async def test_the_prompt_version_an_agent_declares_reaches_the_line(tmp_path):
    from repaso.agents.base import structured

    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    model = wrapped(NestedMetadataModel([{"ok": True}], 10, 2), ledger)

    await structured(model, Verdict, "sistema", "texto", "v2-advisory")

    assert ledger.records()[0].prompt_version == "v2-advisory"


async def test_an_uninstrumented_run_writes_no_ledger(tmp_path):
    path = tmp_path / "calls.jsonl"
    model = InstrumentedModel(
        MeteredPlaybackModel([{"ok": True}], 1, 1), "judge", NullTelemetrySink()
    )

    await drain(model)

    assert path.exists() is False
