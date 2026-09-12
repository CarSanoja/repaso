import pytest

from repaso.agents.item_generator import (
    MAX_OVERPRODUCTION,
    GeneratedBatch,
    draft_report,
    generate_items,
)
from repaso.schemas.common import Lang
from repaso.schemas.item import GenerationOutcome, ItemKind, ItemStatus
from repaso.schemas.provenance import Source
from repaso.tools.llm import LocalPlaybackModel
from tests.agents.item_drafts import EQUIVALENCE, LATER, MATERIAL, NOW, mcq_draft, open_draft
from tests.agents.item_drafts import competency as competency
from tests.agents.recorded_payloads import GENERATED_BATCH


class RecordingModel:
    def __init__(self, output):
        self.output = output
        self.system_prompts: list[str] = []
        self.texts: list[str] = []

    def structured_output(self, output_model, prompt, system_prompt=None):
        self.system_prompts.append(system_prompt or "")
        self.texts.append(prompt[0]["content"][0]["text"])
        output = self.output

        async def events():
            yield {"output": output}

        return events()


class BrokenModel:
    def structured_output(self, output_model, prompt, system_prompt=None):
        async def failing():
            raise RuntimeError("bedrock throttled")
            yield {}

        return failing()


async def test_valid_batch_becomes_candidate_items(competency):
    model = LocalPlaybackModel([GeneratedBatch(items=[mcq_draft(), open_draft()])])
    drafted = await generate_items(
        MATERIAL, competency, 2, 4, model, NOW, model_id="us.anthropic.claude-haiku-4-5"
    )
    items = drafted.items
    assert drafted.outcome is GenerationOutcome.DRAFTED
    assert [item.kind for item in items] == [ItemKind.MCQ, ItemKind.OPEN]
    assert all(item.competency_id == EQUIVALENCE for item in items)
    assert all(item.status is ItemStatus.CANDIDATE for item in items)
    assert len({item.id for item in items}) == 2
    assert items[0].provenance.source is Source.GENERATED
    assert items[0].provenance.created_at == NOW
    assert items[0].provenance.model_id == "us.anthropic.claude-haiku-4-5"
    assert items[0].provenance.prompt_version == "v2"
    assert items[1].rubric


async def test_regenerating_the_same_material_reuses_the_same_item_ids(competency):
    batch = GeneratedBatch(items=[mcq_draft(), open_draft()])
    first = await generate_items(
        MATERIAL, competency, 2, 4, LocalPlaybackModel([batch]), NOW
    )
    second = await generate_items(
        MATERIAL, competency, 2, 4, LocalPlaybackModel([batch]), LATER
    )

    assert [item.id for item in first.items] == [item.id for item in second.items]


async def test_a_reworded_stem_is_a_different_item(competency):
    drafts = [mcq_draft(), mcq_draft(stem="¿Cuál equivale a 3/4?")]
    drafted = await generate_items(
        MATERIAL, competency, 2, 4, LocalPlaybackModel([GeneratedBatch(items=drafts)]), NOW
    )

    assert len({item.id for item in drafted.items}) == 2


async def test_invalid_drafts_are_dropped_and_counted(competency):
    drafts = [
        mcq_draft(),
        mcq_draft(answer_key="4/8"),
        mcq_draft(options=["2/4", "2/4", "1/3"]),
        mcq_draft(options=["2/4", "1/3"]),
        open_draft(rubric=None),
        open_draft(options=["a", "b", "c"]),
        open_draft(difficulty=9),
    ]
    model = LocalPlaybackModel([GeneratedBatch(items=drafts)])
    drafted = await generate_items(MATERIAL, competency, 7, 4, model, NOW)
    assert [item.kind for item in drafted.items] == [ItemKind.MCQ]
    assert draft_report(drafts, drafted.items) == {
        "generated": 7,
        "kept": 1,
        "dropped": 6,
        "untagged": 0,
    }


async def test_an_open_item_whose_options_arrive_null_reaches_the_child(competency):
    model = LocalPlaybackModel([GENERATED_BATCH])
    drafted = await generate_items(MATERIAL, competency, 2, 4, model, NOW)

    assert [item.kind for item in drafted.items] == [ItemKind.MCQ, ItemKind.OPEN]
    assert drafted.items[1].options == []
    assert drafted.items[1].rubric


async def test_a_failed_call_is_unavailable_not_an_empty_batch(competency):
    drafted = await generate_items(MATERIAL, competency, 3, 4, BrokenModel(), NOW)

    assert drafted.outcome is GenerationOutcome.UNAVAILABLE
    assert drafted.items == []


async def test_a_batch_with_nothing_usable_in_it_is_empty_not_unavailable(competency):
    batch = GeneratedBatch(items=[mcq_draft(answer_key="4/8")])

    drafted = await generate_items(
        MATERIAL, competency, 1, 4, LocalPlaybackModel([batch]), NOW
    )

    assert drafted.outcome is GenerationOutcome.EMPTY
    assert drafted.items == []


async def test_generator_asks_for_the_family_language(competency):
    model = RecordingModel(GeneratedBatch(items=[mcq_draft()]))
    await generate_items(MATERIAL, competency, 1, 4, model, NOW, lang=Lang.ES)
    assert "in Spanish" in model.texts[0]
    assert "exactly 1 items" in model.texts[0]
    assert "grade 4" in model.system_prompts[0]
    assert competency.description in model.texts[0]


async def test_a_model_that_floods_the_batch_is_cut_to_twice_what_was_asked(competency):
    drafts = [mcq_draft(stem=f"¿Cuál equivale a {n}/8?") for n in range(60)]
    model = LocalPlaybackModel([GeneratedBatch(items=drafts)])

    drafted = await generate_items(MATERIAL, competency, 6, 4, model, NOW)

    assert len(drafted.items) == 6 * MAX_OVERPRODUCTION


async def test_a_model_that_writes_a_few_extra_items_keeps_them(competency):
    drafts = [mcq_draft(stem=f"¿Cuál equivale a {n}/8?") for n in range(8)]
    model = LocalPlaybackModel([GeneratedBatch(items=drafts)])

    assert len((await generate_items(MATERIAL, competency, 6, 4, model, NOW)).items) == 8


async def test_generator_rejects_a_non_positive_count(competency):
    with pytest.raises(ValueError):
        await generate_items(MATERIAL, competency, 0, 4, LocalPlaybackModel(), NOW)
