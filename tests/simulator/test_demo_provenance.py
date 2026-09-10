from datetime import UTC, datetime
from pathlib import Path

from repaso.simulator.demo_provenance import (
    CLEAN_TREE,
    MODIFIED_TREE,
    NO_PROVENANCE,
    replay_note,
)
from repaso.simulator.demo_scenario import CASSETTE_PATH
from repaso.tools.cassette import load_cassette
from repaso.tools.cassette_cost import cassette_spend, model_ids_in
from repaso.tools.cassette_provenance import (
    CassetteProvenance,
    RolePlayback,
    RunSpend,
    load_provenance,
    provenance_path,
)

COMMIT = "70f1d1e959ea11171dd62664d877bd698f959e9b"


def provenance() -> CassetteProvenance:
    return CassetteProvenance(
        cassette="demo_fracciones.jsonl",
        recorded_at=datetime(2026, 9, 12, 8, 35, tzinfo=UTC),
        commit=COMMIT,
        working_tree_modified=True,
        region="us-east-1",
        what_this_is="one recording",
        what_this_is_not="not a live run",
        entries=1,
        model_ids=["us.amazon.nova-micro-v1:0", "us.anthropic.claude-sonnet-4-6"],
        roles={"judge": RolePlayback(model_ids=["us.anthropic.claude-sonnet-4-6"], calls=1)},
        prompt_versions={"OpenGrade": "v1"},
        replayed=RunSpend(calls=1, input_tokens=10, output_tokens=2, usd=0.001),
        recorded=RunSpend(calls=1, input_tokens=10, output_tokens=2, usd=0.001),
        live_calls=1,
        failed_calls=0,
    )


def test_the_note_names_the_day_the_region_and_the_commit():
    note = replay_note(provenance())

    assert "2026-09-12" in note
    assert "us-east-1" in note
    assert COMMIT[:12] in note
    assert "2 model ids" in note


def test_the_note_refuses_to_call_a_replay_a_run():
    note = replay_note(provenance())

    assert "reached no network and spent nothing" in note
    assert "not evidence" in note


def test_the_note_does_not_call_a_modified_tree_a_commit():
    modified = replay_note(provenance())
    clean = replay_note(provenance().model_copy(update={"working_tree_modified": False}))

    assert MODIFIED_TREE in modified
    assert CLEAN_TREE in clean
    assert MODIFIED_TREE not in clean


def test_a_cassette_without_a_record_beside_it_says_nothing_about_its_models():
    assert replay_note(None) == NO_PROVENANCE


def test_the_demonstration_cassette_is_described_by_the_record_beside_it():
    recorded = load_provenance(provenance_path(CASSETTE_PATH))
    entries = load_cassette(CASSETTE_PATH)

    assert recorded is not None
    assert recorded.cassette == CASSETTE_PATH.name
    assert recorded.entries == len(entries)
    assert recorded.model_ids == model_ids_in(entries)
    assert recorded.replayed.usd == cassette_spend(entries).usd
    assert recorded.failed_calls == 0
    assert Path(recorded.cassette).suffix == ".jsonl"
