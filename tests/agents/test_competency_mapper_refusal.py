import pytest

from repaso.agents.competency_mapper import MappingDecision, map_material
from repaso.agents.prompts.competency_mapper import SYSTEM
from repaso.schemas.competency import MappingOutcome
from repaso.tools.knowledge import LocalTaxonomyRetriever
from repaso.tools.llm import LocalPlaybackModel
from tests.material_corpus_gate import GATE_CORPUS, NOT_SCHOOLWORK

EVERYDAY_PAPER = ("receipt", "price list", "bill", "timetable", "label", "leaflet", "form")


class RecordingModel:
    def __init__(self):
        self.system_prompts: list[str] = []

    def structured_output(self, output_model, prompt, system_prompt=None):
        self.system_prompts.append(system_prompt or "")

        async def events():
            yield {"output": MappingDecision(competency_ids=[])}

        return events()


@pytest.fixture
def retriever() -> LocalTaxonomyRetriever:
    return LocalTaxonomyRetriever()


def rendered() -> str:
    return SYSTEM.format(grade=4, subject="math", limit=3)


@pytest.mark.parametrize("paper", EVERYDAY_PAPER)
def test_the_prompt_names_the_everyday_paper_that_is_not_school_material(paper):
    text = rendered()

    assert paper in text
    assert "is not school material" in text


def test_the_prompt_refuses_a_page_a_competency_could_merely_be_practised_with():
    text = rendered()

    assert "only for what it already works" in text
    assert "is not a match" in text


async def test_the_refusal_rules_reach_the_model(retriever):
    model = RecordingModel()

    await map_material(NOT_SCHOOLWORK["receipt_es"], 4, "math", retriever, model)

    assert "is not school material" in model.system_prompts[0]


@pytest.mark.parametrize("name", sorted(GATE_CORPUS))
async def test_a_refused_gate_page_leaves_no_competency_behind(retriever, name):
    model = LocalPlaybackModel([MappingDecision(competency_ids=[])])

    mapping = await map_material(GATE_CORPUS[name], 4, "math", retriever, model)

    assert mapping.outcome is MappingOutcome.UNMATCHED
    assert mapping.competency_ids == []
