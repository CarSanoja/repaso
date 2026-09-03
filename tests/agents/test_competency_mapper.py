import pytest

from repaso.agents.competency_mapper import (
    MIN_RETRIEVAL_SCORE,
    MappingDecision,
    map_material,
)
from repaso.schemas.common import CompetencyId
from repaso.schemas.competency import CompetencyMatch
from repaso.tools.knowledge import LocalTaxonomyRetriever
from repaso.tools.llm import LocalPlaybackModel

EQUIVALENCE = "math.g4.fractions.equivalence"
COMPARISON = "math.g4.fractions.comparison"
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
