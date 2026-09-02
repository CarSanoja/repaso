import time

import pytest

from repaso.agents.adaptation_policy import PolicyDecision
from repaso.agents.answerability_probe import ProbeAnswer
from repaso.agents.capsule_composer import Snippet
from repaso.agents.competency_mapper import MappingDecision
from repaso.agents.grader import OpenGrade
from repaso.agents.intake_screener import IntakeDecision
from repaso.agents.item_critic import CriticFinding
from repaso.agents.item_generator import GeneratedBatch, is_valid_draft
from repaso.config.models import ModelRole
from repaso.simulator.demo_scenario import (
    CASSETTE_PATH,
    HEDGED_ANSWER,
    INVITE_CODE,
    WRONG_ANSWER,
    build_scenario_services,
    run_demo_scenario,
    scenario_settings,
)
from repaso.simulator.demo_transcript import BOT, CHILD, PARENT, Reading, Speech
from repaso.tools.cassette import load_cassette

TIME_BUDGET_SECONDS = 10.0
SCHEMAS = {
    "IntakeDecision": IntakeDecision,
    "MappingDecision": MappingDecision,
    "GeneratedBatch": GeneratedBatch,
    "CriticFinding": CriticFinding,
    "ProbeAnswer": ProbeAnswer,
    "Snippet": Snippet,
    "OpenGrade": OpenGrade,
    "PolicyDecision": PolicyDecision,
}
EXPECTED_BEATS = [
    "enrolment ends with the family enrolled",
    "a name that looks real is refused as an alias",
    "the notebook photo becomes practice",
    "questions written from the page",
    "questions that survived review",
    "the capsule carries the day's three questions",
    "the answer the grader would not sign reaches the parent",
    "the parent's tap releases it as correct",
    "the guide's worked example is caught",
    "nothing from the guide reaches the child",
    "what the child was asked",
    "questions the review dropped",
    "answers graded",
    "the day ends two right, one wrong",
    "nobody was paged",
    "every runtime invocation was accepted",
    "roles played from the cassette",
    "cassette entries left unplayed",
]
CRITIC_FINDINGS = 12
CRITIC_REJECTIONS = 5
GENERATED_BATCHES = 2


@pytest.fixture
def demo_settings(tmp_path):
    return scenario_settings(tmp_path / "demo")


def speeches(result) -> list[Speech]:
    return [entry for entry in result.transcript if isinstance(entry, Speech)]


def readings(result) -> list[Reading]:
    return [entry for entry in result.transcript if isinstance(entry, Reading)]


async def test_the_family_journey_replays_offline_inside_the_time_budget(demo_settings):
    started = time.perf_counter()
    result = await run_demo_scenario(demo_settings)
    elapsed = time.perf_counter() - started

    assert elapsed < TIME_BUDGET_SECONDS
    assert [beat.name for beat in result.beats] == EXPECTED_BEATS
    assert result.failures == []


async def test_the_transcript_is_the_chat_the_family_would_have_had(demo_settings):
    result = await run_demo_scenario(demo_settings)
    spoken = speeches(result)

    assert spoken[0] == Speech(speaker=PARENT, text=INVITE_CODE)
    assert any(entry.speaker is BOT and "Acepto" in entry.buttons for entry in spoken)
    assert [entry.text for entry in spoken if entry.speaker == CHILD] == [
        "3/4",
        WRONG_ANSWER,
        HEDGED_ANSWER,
    ]
    assert spoken[-1].speaker == BOT
    assert "no los puedo dar por buenos" in spoken[-1].text


async def test_the_parent_is_asked_to_settle_the_answer_the_grader_would_not(demo_settings):
    result = await run_demo_scenario(demo_settings)
    prompts = [
        entry
        for entry in speeches(result)
        if entry.speaker == BOT and "¿La das por buena?" in entry.text
    ]

    assert len(prompts) == 1
    assert prompts[0].buttons == ("Está bien", "Está mal")
    assert HEDGED_ANSWER in prompts[0].text


async def test_a_harness_reading_follows_every_answer_and_the_review(demo_settings):
    result = await run_demo_scenario(demo_settings)
    taken = readings(result)

    assert [entry.label for entry in taken] == [
        "after answer 1",
        "after answer 2",
        "after answer 3",
        "after the parent's review",
    ]
    assert [name for name, _ in taken[0].values] == [
        "mastery EMA",
        "attempts",
        "level",
        "next review",
        "decision",
        "escalations open",
    ]
    assert dict(taken[2].values)["next review"] == "held"
    assert dict(taken[3].values)["attempts"] == "3"


async def test_the_cassette_is_played_to_its_last_entry(demo_settings):
    services = build_scenario_services(demo_settings)

    await run_demo_scenario(demo_settings, services)

    entries = load_cassette(CASSETTE_PATH)
    for role in ModelRole:
        played = [entry for entry in entries if entry.role == role.value]
        assert played, role
        assert services.models[role].remaining_total() == 0, role


async def test_a_short_cassette_stops_the_run_instead_of_inventing_an_answer(
    tmp_path, demo_settings
):
    truncated = tmp_path / "short.jsonl"
    lines = CASSETTE_PATH.read_text(encoding="utf-8").splitlines()
    truncated.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    settings = demo_settings.model_copy(update={"cassette_path": truncated})

    result = await run_demo_scenario(settings)

    failed = [beat.name for beat in result.failures]
    assert "every runtime invocation was accepted" in failed
    assert "the guide's worked example is caught" in failed


def test_every_cassette_entry_validates_against_the_schema_it_names():
    for number, entry in enumerate(load_cassette(CASSETTE_PATH), start=1):
        assert entry.role in {role.value for role in ModelRole}, number
        assert entry.output_model in SCHEMAS, number
        assert SCHEMAS[entry.output_model].model_validate(entry.payload), number
        assert entry.usage is not None, number


def test_every_authored_draft_is_one_the_generator_would_keep():
    batches = [
        GeneratedBatch.model_validate(entry.payload)
        for entry in load_cassette(CASSETTE_PATH)
        if entry.output_model == "GeneratedBatch"
    ]

    assert len(batches) == GENERATED_BATCHES
    assert [len(batch.items) for batch in batches] == [8, 4]
    assert all(is_valid_draft(draft) for batch in batches for draft in batch.items)


def test_the_review_rejects_the_flawed_item_and_the_whole_wrong_guide():
    findings = [
        CriticFinding.model_validate(entry.payload)
        for entry in load_cassette(CASSETTE_PATH)
        if entry.output_model == "CriticFinding"
    ]
    rejected = [finding for finding in findings if not finding.accepted]

    assert len(findings) == CRITIC_FINDINGS
    assert len(rejected) == CRITIC_REJECTIONS
    assert [finding.flaws for finding in rejected] == [
        ["ambiguous"],
        *[["ungradable"]] * 4,
    ]
    assert all(finding.notes for finding in rejected)
