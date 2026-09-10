from datetime import UTC, datetime, timedelta
from pathlib import Path

from repaso.tools.call_cost import cost_or_none
from repaso.tools.call_ledger import CallOrigin, CallOutcome, CallRecord
from repaso.tools.cassette import CassetteEntry
from repaso.tools.cassette_provenance import (
    NO_VERSION,
    build_provenance,
    load_provenance,
    prompt_versions_in,
    provenance_path,
    roles_in,
    write_provenance,
)
from repaso.tools.model_usage import CallUsage

SONNET = "us.anthropic.claude-sonnet-4-6"
NOVA = "us.amazon.nova-micro-v1:0"
AT = datetime(2026, 9, 12, 9, 30, tzinfo=UTC)
USAGE = CallUsage(input_tokens=1000, output_tokens=100)
IS = "one recording of the journey"
IS_NOT = "not a live run"


def entry(role: str = "judge", model_id: str = SONNET) -> CassetteEntry:
    return CassetteEntry(
        role=role,
        kind="structured_output",
        output_model="OpenGrade",
        payload={"correct": True, "rubric_points": 2.0, "confidence": 0.9, "feedback": "bien"},
        model_id=model_id,
        usage=USAGE,
    )


def record(
    number: int,
    role: str = "judge",
    schema: str | None = "OpenGrade",
    version: str | None = "v1",
    outcome: CallOutcome = CallOutcome.OK,
    origin: CallOrigin = CallOrigin.LIVE,
) -> CallRecord:
    return CallRecord(
        call_id=f"c{number}",
        at=AT + timedelta(seconds=number),
        role=role,
        model_id=SONNET,
        kind="structured_output",
        output_model=schema,
        origin=origin,
        outcome=outcome,
        latency_ms=120.0,
        usage=USAGE,
        cost=cost_or_none(SONNET, USAGE),
        prompt_version=version,
    )


def provenance(entries=None, records=None):
    return build_provenance(
        cassette=Path("demo_fracciones.jsonl"),
        entries=entries if entries is not None else [entry(), entry("probe", NOVA)],
        records=records if records is not None else [record(1), record(2, "probe")],
        recorded_at=AT,
        commit="89338b1",
        region="us-east-1",
        what_this_is=IS,
        what_this_is_not=IS_NOT,
    )


def test_the_provenance_sits_beside_the_cassette_it_describes():
    beside = provenance_path(Path("a/demo_fracciones.jsonl"))

    assert beside == Path("a/demo_fracciones.provenance.json")


def test_each_role_records_the_models_it_played_and_how_often():
    roles = roles_in([entry(), entry(), entry("probe", NOVA)])

    assert roles["judge"].calls == 2
    assert roles["judge"].model_ids == [SONNET]
    assert roles["probe"].model_ids == [NOVA]


def test_a_schema_asked_for_without_a_declared_version_says_so():
    versions = prompt_versions_in([record(1), record(2, schema="Snippet", version=None)])

    assert versions == {"OpenGrade": "v1", "Snippet": NO_VERSION}


def test_what_the_replay_costs_is_the_cassette_and_what_the_recording_cost_is_the_ledger():
    built = provenance(records=[record(1), record(2), record(3, outcome=CallOutcome.FAILED)])

    assert built.replayed.calls == 2
    assert built.recorded.calls == 3
    assert built.recorded.usd > built.replayed.usd
    assert built.failed_calls == 1
    assert built.live_calls == 3


def test_the_provenance_survives_the_trip_through_the_file(tmp_path):
    written = provenance()
    path = tmp_path / "demo.provenance.json"

    write_provenance(path, written)

    assert load_provenance(path) == written
    assert load_provenance(path.with_name("absent.json")) is None


def test_the_provenance_names_every_model_the_cassette_replays():
    built = provenance()

    assert built.model_ids == [NOVA, SONNET]
    assert built.entries == 2
    assert built.commit == "89338b1"
    assert built.what_this_is_not == IS_NOT
