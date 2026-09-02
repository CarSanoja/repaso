from datetime import UTC, datetime

import pytest

from repaso.agents.competency_mapper import (
    MIN_RETRIEVAL_SCORE,
    MappingDecision,
    map_material,
)
from repaso.agents.item_generator import (
    GeneratedBatch,
    ItemDraft,
    draft_report,
    generate_items,
)
from repaso.schemas.common import CompetencyId, Lang
from repaso.schemas.competency import Competency, CompetencyMatch
from repaso.schemas.item import ItemKind, ItemStatus
from repaso.schemas.provenance import Source
from repaso.tools.knowledge import LocalTaxonomyRetriever
from repaso.tools.llm import LocalPlaybackModel

EQUIVALENCE = "math.g4.fractions.equivalence"
COMPARISON = "math.g4.fractions.comparison"
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


class LowScoreRetriever:
    def retrieve(self, query, grade, subject, limit=5):
        return [
            CompetencyMatch(competency_id=CompetencyId(EQUIVALENCE), confidence=0.05),
            CompetencyMatch(competency_id=CompetencyId(COMPARISON), confidence=0.1),
        ]

    def get_competency(self, competency_id):
        return None

    def list_competencies(self, grade, subject):
        return []


@pytest.fixture
def retriever() -> LocalTaxonomyRetriever:
    return LocalTaxonomyRetriever()


@pytest.fixture
def competency(retriever) -> Competency:
    return retriever.get_competency(CompetencyId(EQUIVALENCE))


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


async def test_off_topic_material_maps_to_nothing(retriever):
    model = LocalPlaybackModel()
    result = await map_material("photosynthesis chloroplast leaves", 4, "math", retriever, model)
    assert result == []
    assert model.calls == []


async def test_weak_candidates_are_a_wrong_subject_signal():
    model = LocalPlaybackModel()
    retriever = LowScoreRetriever()
    weak = retriever.retrieve(MATERIAL, 4, "math")
    assert weak and all(match.confidence < MIN_RETRIEVAL_SCORE for match in weak)
    assert await map_material(MATERIAL, 4, "math", retriever, model) == []
    assert model.calls == []


async def test_hallucinated_ids_are_dropped(retriever):
    model = LocalPlaybackModel(
        [MappingDecision(competency_ids=[EQUIVALENCE, "math.g4.invented.by_the_model"])]
    )
    result = await map_material(MATERIAL, 4, "math", retriever, model)
    assert [str(match.competency_id) for match in result] == [EQUIVALENCE]
    assert result[0] == retriever.retrieve(MATERIAL, 4, "math", limit=8)[0]


async def test_candidate_list_and_limit_reach_the_prompt(retriever):
    model = RecordingModel(MappingDecision(competency_ids=[COMPARISON]))
    await map_material(MATERIAL, 4, "math", retriever, model, limit=2)
    assert "Equivalent fractions" in model.texts[0]
    assert EQUIVALENCE in model.texts[0]
    assert "at most 2" in model.texts[0]
    assert "grade 4 math" in model.system_prompts[0]


async def test_mapper_falls_back_to_top_candidates_when_the_model_fails(retriever):
    result = await map_material(MATERIAL, 4, "math", retriever, BrokenModel(), limit=2)
    assert [str(match.competency_id) for match in result] == [EQUIVALENCE, COMPARISON]


async def test_mapper_rejects_a_non_positive_limit(retriever):
    with pytest.raises(ValueError):
        await map_material(MATERIAL, 4, "math", retriever, LocalPlaybackModel(), limit=0)


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


async def test_generator_returns_nothing_when_the_model_fails(competency):
    assert await generate_items(MATERIAL, competency, 3, 4, BrokenModel(), NOW) == []


async def test_generator_asks_for_the_family_language(competency):
    model = RecordingModel(GeneratedBatch(items=[mcq_draft()]))
    await generate_items(MATERIAL, competency, 1, 4, model, NOW, lang=Lang.ES)
    assert "in Spanish" in model.texts[0]
    assert "exactly 1 items" in model.texts[0]
    assert "grade 4" in model.system_prompts[0]
    assert competency.description in model.texts[0]


async def test_generator_rejects_a_non_positive_count(competency):
    with pytest.raises(ValueError):
        await generate_items(MATERIAL, competency, 0, 4, LocalPlaybackModel(), NOW)
