from repaso.agents.item_generator import (
    GeneratedBatch,
    draft_report,
    generate_items,
    is_valid_draft,
)
from repaso.schemas.common import Lang
from repaso.schemas.item import BloomLevel, GenerationOutcome
from repaso.tools.llm import LocalPlaybackModel
from tests.agents.item_drafts import LATER, MATERIAL, NOW, mcq_draft, open_draft
from tests.agents.item_drafts import competency as competency

__all__ = ["competency"]


async def test_every_generated_item_is_born_with_the_tags_a_later_session_queries_on(competency):
    model = LocalPlaybackModel([GeneratedBatch(items=[mcq_draft(), open_draft()])])
    drafted = await generate_items(
        MATERIAL, competency, 2, 4, model, NOW, model_id="us.amazon.nova-lite-v1:0", lang=Lang.ES
    )
    assert drafted.outcome is GenerationOutcome.DRAFTED
    for item in drafted.items:
        assert item.bloom is not None
        assert item.lang is Lang.ES
        assert item.grade == 4
        assert item.competency_id
        assert item.kind
        assert item.provenance.prompt_version == "v2"
        assert item.provenance.model_id == "us.amazon.nova-lite-v1:0"
    assert drafted.items[0].bloom is BloomLevel.UNDERSTAND
    assert drafted.items[1].bloom is BloomLevel.ANALYZE


async def test_the_tag_follows_the_language_the_family_reads(competency):
    model = LocalPlaybackModel([GeneratedBatch(items=[mcq_draft()])])
    drafted = await generate_items(MATERIAL, competency, 1, 4, model, LATER, lang=Lang.EN)
    assert drafted.items[0].lang is Lang.EN


async def test_a_level_the_harness_cannot_read_is_left_untagged_never_guessed(competency):
    model = LocalPlaybackModel(
        [GeneratedBatch(items=[mcq_draft(bloom="difícil"), mcq_draft(bloom="", stem="¿Y 2/4?")])]
    )
    drafted = await generate_items(MATERIAL, competency, 2, 4, model, NOW)
    assert [item.bloom for item in drafted.items] == [None, None]
    assert all(is_valid_draft(draft) for draft in [mcq_draft(bloom="difícil"), mcq_draft()])


async def test_the_report_counts_the_items_that_were_born_without_a_level(competency):
    model = LocalPlaybackModel([GeneratedBatch(items=[mcq_draft(bloom="nivel 3"), open_draft()])])
    drafted = await generate_items(MATERIAL, competency, 2, 4, model, NOW)
    assert draft_report([], drafted.items)["untagged"] == 1


async def test_a_tag_is_a_property_of_the_question_and_never_of_the_child(competency):
    model = LocalPlaybackModel([GeneratedBatch(items=[mcq_draft(bloom="analyze")])])
    drafted = await generate_items(MATERIAL, competency, 1, 4, model, NOW)
    item = drafted.items[0]
    fields = item.model_dump()
    assert item.bloom is BloomLevel.ANALYZE
    assert "student_id" not in fields
    assert "mastery" not in fields


async def test_a_level_that_arrives_as_a_number_is_read_as_text_not_a_crash(competency):
    batch = GeneratedBatch.model_validate(
        {"items": [{**mcq_draft().model_dump(), "bloom": 3}]}
    )
    model = LocalPlaybackModel([batch])
    drafted = await generate_items(MATERIAL, competency, 1, 4, model, NOW)

    assert batch.items[0].bloom == "3"
    assert drafted.items[0].bloom is None


async def test_a_level_that_arrives_as_null_is_read_as_untagged(competency):
    batch = GeneratedBatch.model_validate(
        {"items": [{**mcq_draft().model_dump(), "bloom": None}]}
    )
    model = LocalPlaybackModel([batch])
    drafted = await generate_items(MATERIAL, competency, 1, 4, model, NOW)

    assert drafted.items[0].bloom is None
