from datetime import UTC, datetime

import pytest

from repaso.config.settings import Settings
from repaso.tools.call_cost import CallCost, cost_for
from repaso.tools.call_ledger import (
    LEDGER_FILENAME,
    CallLedger,
    CallOrigin,
    CallOutcome,
    CallRecord,
    LedgerFormatError,
    LocalCallLedger,
    NullCallLedger,
    build_call_ledger,
    declared_prompt_version,
    declaring_prompt_version,
    load_ledger,
    new_call_id,
)
from repaso.tools.model_usage import CallUsage

SONNET = "us.anthropic.claude-sonnet-4-6"
AT = datetime(2026, 9, 12, 9, 30, tzinfo=UTC)


def record(**overrides) -> CallRecord:
    usage = overrides.pop("usage", CallUsage(input_tokens=671, output_tokens=37))
    fields = {
        "call_id": "c1",
        "at": AT,
        "role": "judge",
        "model_id": SONNET,
        "kind": "structured_output",
        "output_model": "OpenGrade",
        "origin": CallOrigin.LIVE,
        "outcome": CallOutcome.OK,
        "latency_ms": 590.0,
        "usage": usage,
        "cost": cost_for(SONNET, usage) if usage is not None else None,
        "stop_reason": "tool_use",
    }
    return CallRecord(**{**fields, **overrides})


def test_a_written_record_reads_back_whole(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    written = record(prompt_version="v1", retries=2)

    ledger.append(written)

    assert ledger.records() == [written]
    assert load_ledger(tmp_path / "calls.jsonl") == [written]


def test_the_ledger_only_ever_grows(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    ledger.append(record(call_id="c1"))
    ledger.append(record(call_id="c2", outcome=CallOutcome.FAILED, error="ThrottlingException"))
    LocalCallLedger(tmp_path / "calls.jsonl").append(record(call_id="c3"))

    assert [row.call_id for row in ledger.records()] == ["c1", "c2", "c3"]


def test_one_line_says_what_was_asked_of_which_model_and_how_it_ended(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    ledger.append(record(prompt_version="v1"))

    row = ledger.records()[0]
    assert (row.role, row.model_id, row.kind, row.output_model) == (
        "judge",
        SONNET,
        "structured_output",
        "OpenGrade",
    )
    assert (row.outcome, row.stop_reason, row.latency_ms) == (CallOutcome.OK, "tool_use", 590.0)
    assert row.cost.total_usd == pytest.approx(671 * 0.003 / 1000 + 37 * 0.015 / 1000)
    assert row.prompt_version == "v1"


def test_a_call_whose_usage_was_never_reported_records_no_usage_rather_than_zero(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    ledger.append(record(usage=None))

    row = ledger.records()[0]
    assert row.usage is None
    assert row.cost is None


def test_a_reported_zero_is_not_the_same_as_nothing_reported(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    ledger.append(record(call_id="c1", usage=CallUsage(), cost=CallCost()))
    ledger.append(record(call_id="c2", usage=None))

    zeroed, absent = ledger.records()
    assert zeroed.usage == CallUsage()
    assert absent.usage is None


def test_a_replayed_call_is_never_mistaken_for_a_measured_one(tmp_path):
    ledger = LocalCallLedger(tmp_path / "calls.jsonl")
    ledger.append(record(call_id="c1", origin=CallOrigin.LIVE))
    ledger.append(record(call_id="c2", origin=CallOrigin.REPLAYED))
    ledger.append(record(call_id="c3", origin=CallOrigin.SIMULATED))

    assert [row.measured for row in ledger.records()] == [True, False, False]


def test_a_record_rejects_a_field_it_does_not_know():
    with pytest.raises(ValueError):
        record(provider="bedrock")


def test_a_corrupt_line_names_the_file_and_the_line(tmp_path):
    path = tmp_path / "calls.jsonl"
    path.write_text('{"call_id": "c1"}\n', encoding="utf-8")

    with pytest.raises(LedgerFormatError, match="calls.jsonl:1"):
        load_ledger(path)


def test_a_missing_ledger_is_an_error_to_load_and_empty_to_read(tmp_path):
    with pytest.raises(LedgerFormatError, match="not found"):
        load_ledger(tmp_path / "absent.jsonl")
    assert LocalCallLedger(tmp_path / "absent.jsonl").records() == []


def test_the_builder_returns_a_ledger_under_the_local_data_directory(tmp_path):
    settings = Settings(local_mode=True, local_data_dir=tmp_path)
    ledger = build_call_ledger(settings)

    assert isinstance(ledger, CallLedger)
    assert ledger.path.name == LEDGER_FILENAME
    assert tmp_path in ledger.path.parents


def test_a_named_ledger_path_wins_over_the_default(tmp_path):
    named = tmp_path / "run" / "calls.jsonl"
    settings = Settings(local_mode=True, local_data_dir=tmp_path, call_ledger_path=named)

    assert build_call_ledger(settings).path == named


def test_a_blank_ledger_path_reads_as_no_path(tmp_path):
    settings = Settings(local_mode=True, local_data_dir=tmp_path, call_ledger_path="  ")
    assert settings.call_ledger_path is None


def test_the_null_ledger_keeps_nothing():
    ledger = NullCallLedger()
    ledger.append(record())
    assert isinstance(ledger, CallLedger)
    assert ledger.records() == []


def test_call_ids_do_not_repeat():
    assert len({new_call_id() for _ in range(100)}) == 100


def test_a_prompt_version_is_declared_for_the_length_of_the_call():
    assert declared_prompt_version() is None
    with declaring_prompt_version("v2-advisory"):
        assert declared_prompt_version() == "v2-advisory"
        with declaring_prompt_version(None):
            assert declared_prompt_version() is None
        assert declared_prompt_version() == "v2-advisory"
    assert declared_prompt_version() is None
