import pytest

from repaso.agents.turn_reader import briefing, read_turn
from repaso.schemas.common import Lang
from repaso.schemas.turn import PracticeState, Speaker, TurnContext, TurnIntent
from repaso.tools.llm import LocalPlaybackModel
from tests.agents.stress_models import STRESSES, stressed

CHILD_TEXT = "no entiendo nada de esto 😭"


class Recorder(LocalPlaybackModel):
    def __init__(self, script=None) -> None:
        super().__init__(script)
        self.turns: list[list[dict]] = []
        self.systems: list[str] = []

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        self.turns.append([dict(block) for message in prompt for block in message["content"]])
        self.systems.append(system_prompt or "")
        async for event in super().structured_output(
            output_model, prompt, system_prompt, **kwargs
        ):
            yield event


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
    prompt = briefing(context())

    assert "School grade: 4" in prompt
    assert "Fracciones equivalentes" in prompt
    assert "¿Qué fracción equivale a 2/4?" in prompt
    assert "1. 1/2\n2. 2/8\n3. 3/4" in prompt
    assert "Questions still to come after this one: 2" in prompt


def test_the_briefing_carries_none_of_the_family_words():
    assert CHILD_TEXT not in briefing(context())


async def test_the_guarded_turn_is_the_family_message_and_nothing_of_ours():
    model = Recorder([{"intent": "explanation", "speaker": "child"}])

    await read_turn(CHILD_TEXT, context(), model)

    assert model.turns == [[{"text": CHILD_TEXT}]]
    assert "untrusted data" in model.systems[0]


def test_the_prompt_says_whether_the_question_was_already_answered():
    assert "not answered this question yet" in briefing(context())
    assert "already answered" in briefing(context(answered=True))


def test_a_finished_practice_still_names_the_question_they_are_talking_about():
    prompt = briefing(context(practice=PracticeState.FINISHED))

    assert "already finished" in prompt
    assert "¿Qué fracción equivale a 2/4?" in prompt


def test_nothing_on_screen_is_said_plainly():
    prompt = briefing(context(practice=PracticeState.NOT_SENT, question="", options=[]))

    assert "has not been sent yet" in prompt


def test_what_happened_earlier_tonight_enters_the_prompt_in_order():
    lines = ["turn 1 asked for help", "turn 2 explained with: number line"]
    prompt = briefing(context(history=lines))

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
