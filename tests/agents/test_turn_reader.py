import pytest

from repaso.agents.intake_screener import UNTRUSTED_CLOSE, UNTRUSTED_OPEN
from repaso.agents.turn_reader import read_prompt, read_turn
from repaso.schemas.common import Lang
from repaso.schemas.turn import PracticeState, Speaker, TurnContext, TurnIntent
from repaso.tools.llm import LocalPlaybackModel
from tests.agents.stress_models import STRESSES, stressed

CHILD_TEXT = "no entiendo nada de esto 😭"


def context(**overrides) -> TurnContext:
    base = {
        "lang": Lang.ES,
        "grade": 4,
        "competency": "Fracciones equivalentes",
        "practice": PracticeState.OPEN,
        "question": "¿Qué fracción equivale a 2/4?",
        "options": ["1/2", "2/8", "3/4"],
        "items_left": 2,
    }
    return TurnContext(**(base | overrides))


def test_prompt_carries_the_grade_the_topic_and_the_question_on_screen():
    prompt = read_prompt(context(), CHILD_TEXT)

    assert "School grade: 4" in prompt
    assert "Fracciones equivalentes" in prompt
    assert "¿Qué fracción equivale a 2/4?" in prompt
    assert "1. 1/2\n2. 2/8\n3. 3/4" in prompt
    assert "Questions still to come after this one: 2" in prompt


def test_the_family_text_is_framed_as_untrusted_data():
    prompt = read_prompt(context(), CHILD_TEXT)

    assert f"{UNTRUSTED_OPEN}\n{CHILD_TEXT}\n{UNTRUSTED_CLOSE}" in prompt


def test_the_prompt_says_whether_the_question_was_already_answered():
    assert "not answered this question yet" in read_prompt(context(), CHILD_TEXT)
    assert "already answered" in read_prompt(context(answered=True), CHILD_TEXT)


def test_a_finished_practice_still_names_the_question_they_are_talking_about():
    prompt = read_prompt(context(practice=PracticeState.FINISHED), CHILD_TEXT)

    assert "already finished" in prompt
    assert "¿Qué fracción equivale a 2/4?" in prompt


def test_nothing_on_screen_is_said_plainly():
    prompt = read_prompt(
        context(practice=PracticeState.NOT_SENT, question="", options=[]), CHILD_TEXT
    )

    assert "has not been sent yet" in prompt


def test_what_happened_earlier_tonight_enters_the_prompt_in_order():
    lines = ["turn 1 asked for help", "turn 2 explained with: number line"]
    prompt = read_prompt(context(history=lines), CHILD_TEXT)

    assert "Earlier in tonight's practice" in prompt
    assert prompt.index(lines[0]) < prompt.index(lines[1])


async def test_the_decision_is_whatever_the_model_returned():
    model = LocalPlaybackModel(
        [{"intent": "answer", "speaker": "child", "asked_for": "responde", "answer_text": "1/2"}]
    )

    decision = await read_turn("creo que es 1/2", context(), model)

    assert decision.intent is TurnIntent.ANSWER
    assert decision.speaker is Speaker.CHILD
    assert decision.answer_text == "1/2"


@pytest.mark.parametrize("kind", STRESSES)
async def test_a_failed_call_reads_nothing_rather_than_guessing(kind):
    model = stressed(kind, {})

    decision = await read_turn(CHILD_TEXT, context(), model)

    assert model.calls == 1
    assert decision is None


@pytest.mark.parametrize("intent", list(TurnIntent))
async def test_every_intent_in_the_contract_round_trips(intent):
    model = LocalPlaybackModel([{"intent": intent.value, "speaker": "unclear"}])

    decision = await read_turn(CHILD_TEXT, context(), model)

    assert decision.intent is intent
    assert decision.answer_text == ""
