from repaso.config.models import ModelRole
from repaso.core.orchestration.study_answer import current_item
from repaso.core.orchestration.study_channel import handle_study_text
from repaso.core.orchestration.study_flow import start_sitting
from repaso.core.orchestration.study_store import open_sitting
from repaso.core.orchestration.turn_memory import read_window, tried_approaches
from repaso.core.orchestration.turn_replies import EXPLAIN_ROLE
from repaso.i18n import msg
from repaso.schemas.study_session import StudySessionStatus
from repaso.schemas.turn import TurnIntent
from repaso.tools.llm import LocalPlaybackModel
from tests.agents.stress_models import stressed
from tests.orchestration.fixtures import make_services, seed_family
from tests.orchestration.test_study_flow import EQUIVALENCE_TOPIC, seed_bank

EXPLANATION = {"text": "Parte la barra en cuatro y pinta dos.", "approach": "bar split"}


class Recorder(LocalPlaybackModel):
    def __init__(self, script=None):
        super().__init__(script)
        self.prompts: list[str] = []

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        self.prompts.append(prompt[0]["content"][0]["text"])
        async for event in super().structured_output(
            output_model, prompt, system_prompt=system_prompt, **kwargs
        ):
            yield event


def texts(reply) -> str:
    return "\n".join(message.text for message in reply.messages)


def reads(services, intent: TurnIntent, answer_text: str = "") -> None:
    services.models[ModelRole.STRUCTURED].enqueue(
        {
            "intent": intent.value,
            "speaker": "child",
            "asked_for": "lo que pidió la familia",
            "answer_text": answer_text,
        }
    )


def explains(services, payload=None) -> None:
    services.models[EXPLAIN_ROLE].enqueue(payload or EXPLANATION)


def open_with(settings, count: int = 4):
    services = make_services(settings)
    services.models[EXPLAIN_ROLE] = Recorder()
    family, student = seed_family(services.store)
    seed_bank(services, family, count)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    return services, family, student, opened.session


async def test_a_child_who_does_not_understand_gets_an_explanation_not_a_repeat(settings):
    services, family, student, session = open_with(settings)
    item = current_item(services, session)
    reads(services, TurnIntent.EXPLANATION)
    explains(services)

    reply = await handle_study_text(services, family, "no entiendo", 8.0, "m1")

    assert EXPLANATION["text"] in texts(reply)
    assert item.stem in texts(reply)
    assert services.store.get_mastery(student.id, item.competency_id) is None


async def test_the_explanation_is_asked_for_without_the_answer_key(settings):
    services, family, _, session = open_with(settings)
    item = current_item(services, session)
    reads(services, TurnIntent.EXPLANATION)
    explains(services)

    await handle_study_text(services, family, "¿por qué?", 8.0, "m1")

    prompt = services.models[EXPLAIN_ROLE].prompts[0]
    assert item.stem in prompt
    assert item.rationale not in prompt


async def test_a_second_request_is_told_which_way_in_was_already_tried(settings):
    services, family, student, session = open_with(settings)
    reads(services, TurnIntent.EXPLANATION)
    explains(services)
    await handle_study_text(services, family, "no entiendo", 8.0, "m1")
    reads(services, TurnIntent.EXPLANATION)
    explains(services, {"text": "Piensa en media pizza.", "approach": "pizza halves"})

    await handle_study_text(services, family, "sigo sin entender", 8.0, "m2")

    window = read_window(services, family.id, session.id)
    assert tried_approaches(window) == ["bar split", "pizza halves"]
    assert "bar split" in services.models[EXPLAIN_ROLE].prompts[1]


async def test_an_answer_the_reader_finds_inside_a_sentence_is_graded(settings):
    services, family, student, session = open_with(settings)
    item = current_item(services, session)
    reads(services, TurnIntent.ANSWER, answer_text=item.answer_key)

    reply = await handle_study_text(
        services, family, f"la {item.answer_key} porque las dos son la mitad", 8.0, "m1"
    )

    assert reply.session.progress.correct == 1
    assert services.store.get_mastery(student.id, item.competency_id).attempts == 1


async def test_an_extraction_that_names_no_option_is_never_graded(settings):
    services, family, student, session = open_with(settings)
    item = current_item(services, session)
    reads(services, TurnIntent.ANSWER, answer_text="siete octavos")

    reply = await handle_study_text(services, family, "creo que siete octavos", 8.0, "m1")

    assert reply.session.progress.answered_keys == []
    assert services.store.get_mastery(student.id, item.competency_id) is None
    assert msg("study_not_an_answer", family.lang) in texts(reply)


async def test_a_child_who_wants_to_stop_closes_the_sitting(settings):
    services, family, student, _ = open_with(settings)
    reads(services, TurnIntent.STOP)

    reply = await handle_study_text(services, family, "ya no quiero mas", 8.0, "m1")

    assert reply.session.status is StudySessionStatus.CLOSED
    assert open_sitting(services, family, student) is None


async def test_a_turn_the_reader_cannot_read_says_so_and_asks_again(settings):
    services, family, student, session = open_with(settings)
    item = current_item(services, session)
    services.models[ModelRole.STRUCTURED] = stressed("throttled", {})

    reply = await handle_study_text(services, family, "mmmm", 8.0, "m1")

    assert msg("study_not_an_answer", family.lang) in texts(reply)
    assert item.stem in texts(reply)
    assert services.store.get_mastery(student.id, item.competency_id) is None


async def test_asking_for_help_never_spends_one_of_the_questions(settings):
    services, family, _, session = open_with(settings)
    served = len(session.progress.served)
    for turn in range(3):
        reads(services, TurnIntent.EXPLANATION)
        explains(services)
        reply = await handle_study_text(services, family, "no entiendo", 8.0, f"m{turn}")

    assert len(reply.session.progress.served) == served
    assert reply.session.budget.questions == session.budget.questions


async def test_the_reader_is_never_called_for_a_message_that_names_an_option(settings):
    services, family, _, session = open_with(settings)
    item = current_item(services, session)

    await handle_study_text(services, family, item.answer_key, 8.0, "m1")

    assert services.models[ModelRole.STRUCTURED].calls == []
    assert services.models[EXPLAIN_ROLE].prompts == []


async def test_what_the_child_wrote_does_not_outlive_the_sitting(settings):
    services, family, student, session = open_with(settings, count=1)
    reads(services, TurnIntent.EXPLANATION)
    explains(services)
    await handle_study_text(services, family, "no entiendo nada de esto", 8.0, "m1")
    item = current_item(services, session)

    await handle_study_text(services, family, item.answer_key, 8.0, "m2")

    window = read_window(services, family.id, session.id)
    assert open_sitting(services, family, student) is None
    assert [note.said for note in window.notes] == [""]
    assert tried_approaches(window) == ["bar split"]
