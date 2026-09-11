import pytest

from repaso.agents.item_generator import GeneratedBatch, items_for_material
from repaso.tools.llm import LocalPlaybackModel
from tests.agents.item_drafts import MATERIAL, NOW, mcq_draft, open_draft
from tests.agents.item_drafts import competency as competency


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
