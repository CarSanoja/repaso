import json
from uuid import uuid4

from repaso.config.models import ModelRole
from repaso.core.orchestration.channel_runner import handle_channel_message
from repaso.core.orchestration.context import Route
from repaso.core.orchestration.turn_memory import read_window
from repaso.core.orchestration.turn_replies import EXPLAIN_ROLE
from repaso.core.orchestration.turn_router import READ_ROLE
from repaso.i18n import msg
from repaso.schemas.channel import ChannelKind, InboundMessage
from repaso.schemas.common import Lang
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.session import Capsule, PracticeSession, SessionStatus
from repaso.schemas.turn import TurnIntent
from repaso.tools.llm import LocalPlaybackModel
from tests.agents.stress_models import stressed
from tests.orchestration.fixtures import FRACTIONS, START, make_services, seed_family

EXPLANATION = {"text": "Parte la barra en cuatro y pinta dos.", "approach": "bar split"}


class Recorder(LocalPlaybackModel):
    def __init__(self, script=None):
        super().__init__(script)
        self.prompts: list[str] = []
        self.systems: list[str] = []

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        self.prompts.append(prompt[0]["content"][0]["text"])
        self.systems.append(system_prompt or "")
        async for event in super().structured_output(
            output_model, prompt, system_prompt=system_prompt, **kwargs
        ):
            yield event


def services_with_recorder(settings):
    services = make_services(settings)
    services.models[READ_ROLE] = Recorder()
    services.models[EXPLAIN_ROLE] = Recorder()
    return services


def seed_item(store, item_id: str, kind: ItemKind = ItemKind.MCQ) -> Item:
    item = Item(
        id=item_id,
        competency_id=FRACTIONS,
        kind=kind,
        difficulty=2,
        stem="¿Qué fracción equivale a 2/4?",
        options=["1/2", "2/8", "3/4"] if kind is ItemKind.MCQ else [],
        answer_key="1/2",
        rationale="Las dos nombran la mitad.",
        rubric="2 puntos por la equivalencia" if kind is ItemKind.OPEN else None,
        status=ItemStatus.ACTIVE,
        provenance=Provenance(source=Source.GENERATED, created_at=START),
    )
    store.put_item(item)
    return item


def seed_session(services, student_id: str, item_ids: list[str], status=SessionStatus.DELIVERED):
    session = PracticeSession(
        id="sess1",
        student_id=student_id,
        session_date=services.clock.today(),
        capsule=Capsule(concept_snippet="snippet", item_ids=item_ids),
        status=status,
        delivered_at=services.clock.now(),
    )
    services.store.put_session(session)
    return session


def reads(services, intent: TurnIntent, answer_text: str = "") -> None:
    services.models[READ_ROLE].enqueue(
        {
            "intent": intent.value,
            "speaker": "child",
            "asked_for": "lo que pidió la familia",
            "answer_text": answer_text,
        }
    )


def explains(services, payload=None) -> None:
    services.models[EXPLAIN_ROLE].enqueue(payload or EXPLANATION)


def keeps_going(services) -> None:
    services.models[READ_ROLE].enqueue({"action": "continue", "reason": "fixture"})


async def says(services, family, text: str, message_ref: str | None = None):
    services.clock.advance(minutes=1)
    message = InboundMessage(
        channel=ChannelKind.TELEGRAM,
        chat_ref=family.chat_ref,
        message_ref=message_ref or uuid4().hex,
        text=text,
        received_at=services.clock.now(),
    )
    return await handle_channel_message(services, message)


def said(run) -> list[str]:
    return [message.text for message in run.outbound]


async def test_a_question_that_looks_like_an_answer_is_not_graded(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    session = seed_session(services, student.id, ["i1", "i2"])
    reads(services, TurnIntent.EXPLANATION)
    explains(services)

    run = await says(services, family, "1/2")

    assert run.route is Route.CONVERSATION
    assert said(run) == [EXPLANATION["text"]]
    assert services.grade_log.by_student(student.id) == []
    assert services.store.get_mastery(student.id, FRACTIONS) is None
    assert services.store.list_spaced(student.id) == []
    assert services.store.get_session(session.id).current_item_index == 0


async def test_a_confused_sounding_answer_is_graded_when_the_model_reads_it_as_one(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANSWER, "1/2")
    keeps_going(services)

    run = await says(services, family, "no entiendo pero creo que 1/2")

    assert run.route is Route.ANSWER
    assert run.tutor.grade.correct is True
    assert services.store.get_mastery(student.id, FRACTIONS).attempts == 1


async def test_the_spoken_answer_is_graded_through_the_option_the_model_copied(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANSWER, "1/2")
    keeps_going(services)

    run = await says(services, family, "la 1/2 porque las dos son la mitad")

    assert run.tutor.grade.correct is True


async def test_an_extraction_that_names_no_option_grades_what_the_family_wrote(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANSWER, "la mitad exacta")
    keeps_going(services)

    run = await says(services, family, "2/8")

    assert run.tutor.grade.correct is False
    assert run.tutor.grade.evidence.quote == "2/8"


async def test_an_explanation_is_remembered_and_never_offered_twice(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    session = seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.EXPLANATION)
    explains(services)
    reads(services, TurnIntent.EXPLANATION)
    explains(services, {"text": "Cuenta los pedacitos en la recta.", "approach": "number line"})

    await says(services, family, "no entiendo")
    await says(services, family, "sigo sin entender")

    window = read_window(services, family.id, session.id)
    assert [entry.explained for entry in window.notes] == ["bar split", "number line"]
    prompt = services.models[EXPLAIN_ROLE].prompts[-1]
    assert json.loads(prompt)["already_tried"] == ["bar split"]


async def test_what_happened_earlier_tonight_reaches_the_next_turn(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_item(services.store, "i2")
    seed_session(services, student.id, ["i1", "i2"])
    reads(services, TurnIntent.ANSWER, "2/8")
    keeps_going(services)
    reads(services, TurnIntent.EXPLANATION)
    explains(services)

    await says(services, family, "2/8")
    await says(services, family, "¿por qué?")

    briefed = services.models[READ_ROLE].systems[-1]
    assert "Earlier in tonight's practice" in briefed
    assert 'wrote: "2/8"' in briefed
    assert "harness graded: incorrect" in briefed
    assert services.models[READ_ROLE].prompts[-1] == "¿por qué?"


async def test_an_explanation_asked_before_answering_is_not_told_the_answer(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.EXPLANATION)
    explains(services)

    await says(services, family, "no entiendo")

    prompt = services.models[EXPLAIN_ROLE].prompts[-1]
    assert json.loads(prompt)["answered"] is False
    assert "answer_key" not in json.loads(prompt)
    assert "Las dos nombran la mitad." not in prompt


async def test_an_explanation_after_a_wrong_answer_carries_the_written_reason(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANSWER, "2/8")
    keeps_going(services)
    reads(services, TurnIntent.EXPLANATION)
    explains(services)

    await says(services, family, "2/8")
    await says(services, family, "¿por qué?")

    prompt = services.models[EXPLAIN_ROLE].prompts[-1]
    assert "Las dos nombran la mitad." in prompt
    assert json.loads(prompt)["was_correct"] is False
    assert not json.loads(prompt)["answer_given"]


async def test_mid_capsule_the_explanation_is_about_the_question_now_on_screen(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    second = seed_item(services.store, "i2")
    services.store.put_item(second.model_copy(update={"stem": "¿Cuánto es 1/4 + 1/4?"}))
    seed_session(services, student.id, ["i1", "i2"])
    reads(services, TurnIntent.ANSWER, "2/8")
    keeps_going(services)
    reads(services, TurnIntent.EXPLANATION)
    explains(services)

    await says(services, family, "2/8")
    await says(services, family, "no entiendo")

    prompt = services.models[EXPLAIN_ROLE].prompts[-1]
    assert "¿Cuánto es 1/4 + 1/4?" in prompt
    assert json.loads(prompt)["answered"] is False
    assert "answer_key" not in json.loads(prompt)


async def test_an_explanation_that_fails_falls_back_to_the_written_reason(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANSWER, "2/8")
    keeps_going(services)
    reads(services, TurnIntent.EXPLANATION)
    services.models[EXPLAIN_ROLE] = stressed("throttled", {})

    await says(services, family, "2/8")
    run = await says(services, family, "¿por qué?")

    assert said(run) == [item.rationale]


async def test_an_explanation_that_fails_before_an_answer_says_so_plainly(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.EXPLANATION)
    services.models[EXPLAIN_ROLE] = stressed("timed_out", {})

    run = await says(services, family, "no entiendo")

    assert said(run) == [msg("turn_explain_unavailable", Lang.ES)]
    assert services.grade_log.by_student(student.id) == []


async def test_asking_for_another_question_sends_the_one_on_screen_again(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANOTHER_QUESTION)

    run = await says(services, family, "otra")

    assert item.stem in said(run)[0]
    assert run.outbound[0].buttons
    assert services.grade_log.by_student(student.id) == []


async def test_a_finished_capsule_says_what_it_can_do_instead_of_going_quiet(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"], status=SessionStatus.COMPLETED)
    reads(services, TurnIntent.ANOTHER_QUESTION)

    run = await says(services, family, "otra más")

    assert run.route is Route.CONVERSATION
    assert said(run) == [msg("turn_more_tomorrow", Lang.ES, time="19:00")]


async def test_an_answer_after_the_capsule_closes_is_not_counted(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"], status=SessionStatus.COMPLETED)
    reads(services, TurnIntent.ANSWER, "1/2")

    run = await says(services, family, "1/2")

    assert said(run) == [msg("turn_practice_done", Lang.ES, time="19:00")]
    assert services.grade_log.by_student(student.id) == []


async def test_a_child_who_wants_to_stop_is_told_nothing_is_lost(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.STOP)

    run = await says(services, family, "ya no quiero")

    assert said(run) == [msg("turn_stop", Lang.ES)]
    assert services.grade_log.by_student(student.id) == []
    assert services.store.get_mastery(student.id, FRACTIONS) is None


async def test_a_question_about_the_practice_names_the_commands_that_answer_it(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ABOUT_THE_PRACTICE)

    run = await says(services, family, "¿cómo va?")

    assert said(run) == [msg("turn_about_practice", Lang.ES)]


async def test_a_turn_the_reader_cannot_read_is_never_graded(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    services.models[READ_ROLE] = stressed("throttled", {})

    run = await says(services, family, "1/2")

    assert run.route is Route.CONVERSATION
    assert said(run) == [msg("turn_not_understood", Lang.ES)]
    assert services.grade_log.by_student(student.id) == []
    assert services.store.get_mastery(student.id, FRACTIONS) is None


async def test_the_last_answer_closes_the_session_and_its_memory(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    session = seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANSWER, "1/2")
    keeps_going(services)

    run = await says(services, family, "1/2")

    assert run.tutor.session.status is SessionStatus.COMPLETED
    kept = read_window(services, family.id, session.id).notes
    assert [entry.said for entry in kept] == [""]
    assert kept[0].correct is True
    rows = services.store.list_records(family.id, f"turn#{session.id}#")
    assert rows and all("1/2" not in str(row.payload) for row in rows)


async def test_the_same_message_twice_is_graded_and_remembered_once(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_item(services.store, "i2")
    session = seed_session(services, student.id, ["i1", "i2"])
    reads(services, TurnIntent.ANSWER, "1/2")
    keeps_going(services)

    first = await says(services, family, "1/2", message_ref="m1")
    second = await says(services, family, "1/2", message_ref="m1")

    assert first.route is Route.ANSWER and second.route is Route.ANSWER
    assert len(services.grade_log.by_student(student.id)) == 1
    assert len(read_window(services, family.id, session.id).notes) == 1
    assert services.store.get_mastery(student.id, FRACTIONS).attempts == 1


async def test_reading_a_turn_costs_one_cheap_call_and_grading_an_option_costs_none(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANSWER, "1/2")
    keeps_going(services)

    await says(services, family, "1/2")

    assert len(services.models[READ_ROLE].calls) == 2
    assert services.models[ModelRole.JUDGE].calls == []
    assert services.models[EXPLAIN_ROLE].calls == []


async def test_an_item_with_no_written_reason_never_sends_an_empty_message(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1")
    services.store.put_item(item.model_copy(update={"rationale": ""}))
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANSWER, "2/8")
    keeps_going(services)
    reads(services, TurnIntent.EXPLANATION)
    services.models[EXPLAIN_ROLE] = stressed("throttled", {})

    await says(services, family, "2/8")
    run = await says(services, family, "\u00bfpor qu\u00e9?")

    assert said(run) == [msg("turn_explain_unavailable", Lang.ES)]


async def test_an_option_the_family_never_wrote_is_not_graded_as_their_answer(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads(services, TurnIntent.ANSWER, "1/2")
    keeps_going(services)

    run = await says(services, family, "👍")

    assert run.tutor.grade.correct is False
    assert run.tutor.grade.evidence.quote == "👍"
