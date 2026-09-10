from datetime import UTC, datetime

import pytest

from repaso.agents.item_generator import (
    MAX_OVERPRODUCTION,
    GeneratedBatch,
    ItemDraft,
    draft_report,
    generate_items,
    items_for_material,
)
from repaso.schemas.common import CompetencyId, Lang
from repaso.schemas.competency import Competency
from repaso.schemas.item import ItemKind, ItemStatus
from repaso.schemas.provenance import Source
from repaso.tools.knowledge import LocalTaxonomyRetriever
from repaso.tools.llm import LocalPlaybackModel
from tests.agents.recorded_payloads import GENERATED_BATCH

EQUIVALENCE = "math.g4.fractions.equivalence"
NOW = datetime(2026, 3, 2, 19, 0, tzinfo=UTC)
LATER = datetime(2026, 3, 9, 19, 0, tzinfo=UTC)
MATERIAL = (
    "Cuaderno de 4to grado: fracciones equivalentes. equivalent fractions such as 2/4 "
    "and 1/2, and comparing fractions with a common denominator."
)


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


@pytest.fixture
def competency() -> Competency:
    return LocalTaxonomyRetriever().get_competency(CompetencyId(EQUIVALENCE))


def mcq_draft(**overrides) -> ItemDraft:
    payload = {
        "kind": ItemKind.MCQ,
        "difficulty": 2,
        "stem": "¿Cuál fracción es equivalente a 1/2?",
        "options": ["2/4", "1/3", "3/5"],
        "answer_key": "2/4",
        "rationale": "Multiplicas arriba y abajo por 2 y llegas a 2/4.",
    }
    return ItemDraft(**{**payload, **overrides})


def open_draft(**overrides) -> ItemDraft:
    payload = {
        "kind": ItemKind.OPEN,
        "difficulty": 3,
        "stem": "Explica por qué 3/6 y 1/2 valen lo mismo.",
        "answer_key": "Porque 3/6 se simplifica dividiendo entre 3.",
        "rationale": "Dividir numerador y denominador entre 3 deja 1/2.",
        "rubric": "2 puntos si nombra la simplificación, 1 si solo dice que son iguales, 0 si no.",
    }
    return ItemDraft(**{**payload, **overrides})


async def test_valid_batch_becomes_candidate_items(competency):
    model = LocalPlaybackModel([GeneratedBatch(items=[mcq_draft(), open_draft()])])
    items = await generate_items(
        MATERIAL, competency, 2, 4, model, NOW, model_id="us.anthropic.claude-haiku-4-5"
    )
    assert [item.kind for item in items] == [ItemKind.MCQ, ItemKind.OPEN]
    assert all(item.competency_id == EQUIVALENCE for item in items)
    assert all(item.status is ItemStatus.CANDIDATE for item in items)
    assert len({item.id for item in items}) == 2
    assert items[0].provenance.source is Source.GENERATED
    assert items[0].provenance.created_at == NOW
    assert items[0].provenance.model_id == "us.anthropic.claude-haiku-4-5"
    assert items[0].provenance.prompt_version == "v1"
    assert items[1].rubric


async def test_regenerating_the_same_material_reuses_the_same_item_ids(competency):
    batch = GeneratedBatch(items=[mcq_draft(), open_draft()])
    first = await generate_items(
        MATERIAL, competency, 2, 4, LocalPlaybackModel([batch]), NOW
    )
    second = await generate_items(
        MATERIAL, competency, 2, 4, LocalPlaybackModel([batch]), LATER
    )

    assert [item.id for item in first] == [item.id for item in second]


async def test_a_reworded_stem_is_a_different_item(competency):
    drafts = [mcq_draft(), mcq_draft(stem="¿Cuál equivale a 3/4?")]
    items = await generate_items(
        MATERIAL, competency, 2, 4, LocalPlaybackModel([GeneratedBatch(items=drafts)]), NOW
    )

    assert len({item.id for item in items}) == 2


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
    items = await generate_items(MATERIAL, competency, 7, 4, model, NOW)
    assert [item.kind for item in items] == [ItemKind.MCQ]
    assert draft_report(drafts, items) == {"generated": 7, "kept": 1, "dropped": 6}


async def test_an_open_item_whose_options_arrive_null_reaches_the_child(competency):
    model = LocalPlaybackModel([GENERATED_BATCH])
    items = await generate_items(MATERIAL, competency, 2, 4, model, NOW)

    assert [item.kind for item in items] == [ItemKind.MCQ, ItemKind.OPEN]
    assert items[1].options == []
    assert items[1].rubric


async def test_generator_returns_nothing_when_the_model_fails(competency):
    assert await generate_items(MATERIAL, competency, 3, 4, BrokenModel(), NOW) == []


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

    items = await generate_items(MATERIAL, competency, 6, 4, model, NOW)

    assert len(items) == 6 * MAX_OVERPRODUCTION


async def test_a_model_that_writes_a_few_extra_items_keeps_them(competency):
    drafts = [mcq_draft(stem=f"¿Cuál equivale a {n}/8?") for n in range(8)]
    model = LocalPlaybackModel([GeneratedBatch(items=drafts)])

    assert len(await generate_items(MATERIAL, competency, 6, 4, model, NOW)) == 8


async def test_generator_rejects_a_non_positive_count(competency):
    with pytest.raises(ValueError):
        await generate_items(MATERIAL, competency, 0, 4, LocalPlaybackModel(), NOW)


class MalformedThenWhole:
    def __init__(self, rejections: int, output) -> None:
        self.rejections = rejections
        self.output = output
        self.calls = 0

    def structured_output(self, output_model, prompt, system_prompt=None):
        self.calls += 1
        rejected = self.calls <= self.rejections
        output = self.output

        async def events():
            if rejected:
                raise ValueError("items: Input should be a valid list")
            yield {"output": output}

        return events()


async def test_a_rejected_batch_is_asked_for_again_before_the_page_is_given_up(competency):
    model = MalformedThenWhole(2, GeneratedBatch(items=[mcq_draft(), open_draft()]))

    items = await items_for_material(MATERIAL, competency, 2, 4, model, NOW, 2)

    assert len(items) == 2
    assert model.calls == 3


async def test_the_page_is_given_up_once_every_attempt_is_rejected(competency):
    model = MalformedThenWhole(9, GeneratedBatch(items=[mcq_draft()]))

    assert await items_for_material(MATERIAL, competency, 2, 4, model, NOW, 2) == []
    assert model.calls == 3


async def test_a_batch_that_arrives_whole_is_asked_for_once(competency):
    model = MalformedThenWhole(0, GeneratedBatch(items=[mcq_draft()]))

    items = await items_for_material(MATERIAL, competency, 1, 4, model, NOW, 2)

    assert len(items) == 1
    assert model.calls == 1


async def test_a_run_that_allows_no_second_attempt_makes_one_call(competency):
    model = MalformedThenWhole(1, GeneratedBatch(items=[mcq_draft()]))

    assert await items_for_material(MATERIAL, competency, 1, 4, model, NOW) == []
    assert model.calls == 1


async def test_a_negative_allowance_is_not_a_number_of_attempts(competency):
    with pytest.raises(ValueError):
        await items_for_material(MATERIAL, competency, 1, 4, LocalPlaybackModel(), NOW, -1)
