import pytest

from repaso.agents.competency_mapper import (
    CANDIDATE_LIMIT,
    MappingDecision,
    map_material,
    ordered_candidates,
)
from repaso.schemas.common import CompetencyId
from repaso.schemas.competency import CompetencyMatch, MappingOutcome
from repaso.tools.knowledge import LocalTaxonomyRetriever
from repaso.tools.llm import LocalPlaybackModel
from tests.material_corpus import HISTORY_EN, INVITATION_ES, PRINTED_PAGE_ES

EQUIVALENCE = "math.g4.fractions.equivalence"
COMPARISON = "math.g4.fractions.comparison"
DECIMALS = "math.g4.decimals.tenths_hundredths"
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


class EmptyTaxonomy:
    def retrieve(self, query, grade, subject, limit=5):
        return []

    def get_competency(self, competency_id):
        return None

    def list_competencies(self, grade, subject):
        return []


@pytest.fixture
def retriever() -> LocalTaxonomyRetriever:
    return LocalTaxonomyRetriever()


async def test_a_page_the_hint_scores_at_zero_still_reaches_the_model(retriever):
    model = RecordingModel(MappingDecision(competency_ids=[]))

    await map_material(PRINTED_PAGE_ES, 4, "math", retriever, model)

    offered = model.texts[0]
    for competency in retriever.list_competencies(4, "math"):
        assert str(competency.id) in offered


async def test_the_printed_page_maps_to_fractions_and_decimals(retriever):
    model = RecordingModel(MappingDecision(competency_ids=[COMPARISON, DECIMALS]))

    mapping = await map_material(PRINTED_PAGE_ES, 4, "math", retriever, model)

    assert mapping.outcome is MappingOutcome.MAPPED
    assert [str(key) for key in mapping.competency_ids] == [COMPARISON, DECIMALS]


async def test_off_subject_material_in_either_language_is_unmatched(retriever):
    for page in (INVITATION_ES, HISTORY_EN):
        model = LocalPlaybackModel([MappingDecision(competency_ids=[])])
        mapping = await map_material(page, 4, "math", retriever, model)
        assert mapping.outcome is MappingOutcome.UNMATCHED
        assert mapping.competency_ids == []


async def test_a_failed_call_is_undetermined_and_never_a_guess(retriever):
    mapping = await map_material(MATERIAL, 4, "math", retriever, BrokenModel(), limit=2)

    assert mapping.outcome is MappingOutcome.UNDETERMINED
    assert mapping.competency_ids == []


async def test_hallucinated_ids_are_dropped(retriever):
    model = LocalPlaybackModel(
        [MappingDecision(competency_ids=[EQUIVALENCE, "math.g4.invented.by_the_model"])]
    )

    mapping = await map_material(MATERIAL, 4, "math", retriever, model)

    assert [str(key) for key in mapping.competency_ids] == [EQUIVALENCE]


async def test_a_repeated_id_is_kept_once(retriever):
    model = LocalPlaybackModel([MappingDecision(competency_ids=[EQUIVALENCE, EQUIVALENCE])])

    mapping = await map_material(MATERIAL, 4, "math", retriever, model)

    assert [str(key) for key in mapping.competency_ids] == [EQUIVALENCE]


async def test_the_model_answer_is_cut_to_the_limit(retriever):
    model = LocalPlaybackModel(
        [MappingDecision(competency_ids=[EQUIVALENCE, COMPARISON, DECIMALS])]
    )

    mapping = await map_material(MATERIAL, 4, "math", retriever, model, limit=2)

    assert [str(key) for key in mapping.competency_ids] == [EQUIVALENCE, COMPARISON]


async def test_candidate_list_and_limit_reach_the_prompt(retriever):
    model = RecordingModel(MappingDecision(competency_ids=[COMPARISON]))

    await map_material(MATERIAL, 4, "math", retriever, model, limit=2)

    assert "Equivalent fractions" in model.texts[0]
    assert EQUIVALENCE in model.texts[0]
    assert "at most 2" in model.texts[0]
    assert "grade 4 math" in model.system_prompts[0]


async def test_the_prompt_tells_the_model_the_languages_may_differ(retriever):
    model = RecordingModel(MappingDecision(competency_ids=[]))

    await map_material(MATERIAL, 4, "math", retriever, model)

    assert "different languages" in model.system_prompts[0]


async def test_an_empty_taxonomy_is_unmatched_without_calling_the_model():
    model = LocalPlaybackModel()

    mapping = await map_material(MATERIAL, 4, "math", EmptyTaxonomy(), model)

    assert mapping.outcome is MappingOutcome.UNMATCHED
    assert model.calls == []


def test_the_hint_orders_the_slate_without_dropping_anything(retriever):
    slate = retriever.list_competencies(4, "math")
    hints = [CompetencyMatch(competency_id=CompetencyId(DECIMALS), confidence=0.9)]

    ordered = ordered_candidates(hints, slate)

    assert str(ordered[0].id) == DECIMALS
    assert {competency.id for competency in ordered} == {competency.id for competency in slate}


def test_a_hint_outside_the_slate_is_ignored(retriever):
    slate = retriever.list_competencies(4, "math")
    hints = [CompetencyMatch(competency_id=CompetencyId("math.g5.fractions.x"), confidence=1.0)]

    ordered = ordered_candidates(hints, slate)

    assert {competency.id for competency in ordered} == {competency.id for competency in slate}


def test_the_candidate_list_is_capped():
    slate = LocalTaxonomyRetriever().list_competencies(4, "math")
    assert len(ordered_candidates([], slate * 4)) == CANDIDATE_LIMIT


async def test_mapper_rejects_a_non_positive_limit(retriever):
    with pytest.raises(ValueError):
        await map_material(MATERIAL, 4, "math", retriever, LocalPlaybackModel(), limit=0)
