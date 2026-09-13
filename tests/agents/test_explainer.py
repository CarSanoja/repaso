import pytest

from repaso.agents.explainer import explain, explain_prompt
from repaso.agents.intake_screener import UNTRUSTED_CLOSE, UNTRUSTED_OPEN
from repaso.schemas.common import Lang
from repaso.schemas.turn import ExplainContext
from tests.agents.stress_models import STRESSES, stressed
from tests.live.samples import COMPETENCY, MCQ_ITEM

SAID = "no entiendo por que"
GAVE = "3/8"
REPLY = {"text": "Pinta 3 de 4 partes y luego 6 de 8.", "approach": "bar split into parts"}


def context(**overrides) -> ExplainContext:
    base = {
        "lang": Lang.ES,
        "grade": 4,
        "competency": COMPETENCY.name,
        "description": COMPETENCY.description,
        "question": MCQ_ITEM.stem,
        "options": list(MCQ_ITEM.options),
        "asked_for": "Pide que le expliquen otra vez.",
        "child_said": SAID,
    }
    return ExplainContext(**(base | overrides))


def answered(**overrides) -> ExplainContext:
    graded = {
        "answered": True,
        "was_correct": False,
        "answer_given": GAVE,
        "answer_key": MCQ_ITEM.answer_key,
        "rationale": MCQ_ITEM.rationale,
    }
    return context(**(graded | overrides))


def test_the_prompt_is_pitched_at_this_child_and_this_question():
    prompt = explain_prompt(answered())

    assert "School grade: 4" in prompt
    assert COMPETENCY.name in prompt
    assert COMPETENCY.description in prompt
    assert MCQ_ITEM.stem in prompt
    assert "1. 6/8" in prompt
    assert "Pide que le expliquen otra vez." in prompt


def test_an_unanswered_question_is_never_given_the_answer_to_leak():
    prompt = explain_prompt(context())

    assert "The expected answer" not in prompt
    assert MCQ_ITEM.rationale not in prompt
    assert "has NOT answered this question yet" in prompt
    assert "do not reveal it" in prompt.casefold()


def test_an_answered_question_carries_the_written_reason_as_the_ground_truth():
    prompt = explain_prompt(answered())

    assert MCQ_ITEM.rationale in prompt
    assert f"The expected answer: {MCQ_ITEM.answer_key}" in prompt
    assert "was not the expected one" in prompt


def test_a_child_who_got_it_right_and_asks_why_is_not_told_they_were_wrong():
    prompt = explain_prompt(answered(was_correct=True))

    assert "got it right" in prompt
    assert "was not the expected one" not in prompt


def test_both_pieces_of_the_child_text_sit_inside_one_untrusted_frame():
    prompt = explain_prompt(answered())
    framed = prompt[prompt.index(UNTRUSTED_OPEN) : prompt.index(UNTRUSTED_CLOSE)]

    assert GAVE in framed
    assert SAID in framed


def test_an_approach_that_did_not_land_is_named_so_it_is_not_repeated():
    prompt = explain_prompt(answered(already_tried=["bar split into parts", "number line"]))

    assert "already tried tonight" in prompt
    assert "- bar split into parts" in prompt
    assert "- number line" in prompt


async def test_the_explanation_and_its_label_come_back_from_the_model():
    explanation = await explain(answered(), stressed("malformed", REPLY))

    assert explanation.text == REPLY["text"]
    assert explanation.approach == REPLY["approach"]


@pytest.mark.parametrize("kind", STRESSES)
async def test_a_failed_call_explains_nothing_rather_than_something_wrong(kind):
    model = stressed(kind, {})

    assert await explain(answered(), model) is None
    assert model.calls == 1


async def test_an_empty_explanation_is_not_an_explanation():
    assert await explain(answered(), stressed("malformed", {"text": "   "})) is None
