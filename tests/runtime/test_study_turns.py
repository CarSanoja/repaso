import asyncio

from repaso.agents.capsule_composer import answer_ref
from repaso.config.models import ModelRole
from repaso.core.harness.bloom import BloomLevel
from repaso.core.orchestration.study_answer import current_item
from repaso.core.orchestration.study_store import list_study_sessions, open_sitting
from repaso.i18n import msg
from repaso.runtime.entrypoint import invoke_async
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.study_session import StudySessionStatus
from repaso.tools.episode_log import list_attempts
from tests.orchestration.fixtures import FRACTIONS, START, seed_family
from tests.runtime.fixtures import FAMILY_CHAT, channel_request, inbound, pilot

CHILD_WORDS = "no entiendo nada de esto"
ONCE = {"attempts": 1, "grades": 1, "episodes": 1}
NEVER = {"attempts": 0, "grades": 0, "episodes": 0}
BANK = (
    ("¿Cuál fracción equivale a 1/2?", ["2/4", "1/3", "3/5"], "2/4"),
    ("¿Cuál fracción equivale a 1/3?", ["2/6", "1/4", "5/7"], "2/6"),
    ("¿Cuál fracción equivale a 3/4?", ["6/8", "2/5", "4/9"], "6/8"),
    ("¿Cuál fracción equivale a 2/5?", ["4/10", "1/6", "3/8"], "4/10"),
)


def seed_bank(services, family_id: str) -> None:
    for index, (stem, options, key) in enumerate(BANK):
        services.store.put_item(
            Item(
                id=f"{FRACTIONS}-{index}",
                family_id=family_id,
                competency_id=FRACTIONS,
                kind=ItemKind.MCQ,
                difficulty=2,
                stem=stem,
                options=options,
                answer_key=key,
                rationale="Multiplicas arriba y abajo por el mismo número.",
                status=ItemStatus.ACTIVE,
                bloom=BloomLevel.REMEMBER,
                provenance=Provenance(source=Source.GENERATED, created_at=START),
            )
        )


async def sent(services, message) -> dict:
    return await invoke_async(channel_request(message), services)


async def opened(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family.id)
    await sent(services, inbound(text="/sesion", chat_ref=FAMILY_CHAT))
    return services, family, student


def reads_an_answer(services, answer_text: str) -> None:
    services.models[ModelRole.STRUCTURED].enqueue(
        {
            "intent": "answer",
            "speaker": "child",
            "asked_for": "responder la pregunta",
            "answer_text": answer_text,
        }
    )


def prefixed(services, family, prefix: str) -> int:
    return len(services.store.list_records(family.id, prefix))


def stored_text(services, family) -> str:
    scopes = (family.id, f"chat:{family.chat_ref}")
    rows = [
        record.payload
        for scope in scopes
        for record in services.store.list_records(scope, "")
    ]
    return "\n".join(str(row) for row in rows)


def learning_state(services, family, student) -> dict:
    mastery = services.store.get_mastery(student.id, FRACTIONS)
    return {
        "attempts": mastery.attempts if mastery else 0,
        "grades": len(services.grade_log.by_student(student.id)),
        "episodes": len(list_attempts(services.store, family.id, student.id)),
    }


async def test_two_messages_arriving_at_once_leave_one_attempt(settings):
    services, family, student = await opened(settings)
    item = current_item(services, open_sitting(services, family, student))
    first = inbound(text=item.answer_key, chat_ref=FAMILY_CHAT, message_ref="one")
    second = inbound(text=item.options[1], chat_ref=FAMILY_CHAT, message_ref="two")
    reads_an_answer(services, item.options[1])

    await asyncio.gather(
        invoke_async(channel_request(first), services),
        invoke_async(channel_request(second), services),
        return_exceptions=True,
    )

    assert learning_state(services, family, student) == ONCE
    assert len(open_sitting(services, family, student).progress.answered_keys) == 1


async def test_an_answer_that_predates_the_question_on_screen_is_never_graded(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family.id)
    services.clock.advance(minutes=5)
    await sent(services, inbound(text="/sesion", chat_ref=FAMILY_CHAT))
    item = current_item(services, open_sitting(services, family, student))

    response = await sent(
        services,
        inbound(
            text=item.answer_key,
            chat_ref=FAMILY_CHAT,
            message_ref="stale",
            received_at=START,
        ),
    )

    said = [message["text"] for message in response["result"]["outbound"]]
    assert msg("study_out_of_step", family.lang) in said
    assert item.stem in "\n".join(said)
    assert learning_state(services, family, student) == NEVER


async def test_a_redelivered_webhook_mid_sitting_replays_instead_of_answering_twice(settings):
    services, family, student = await opened(settings)
    item = current_item(services, open_sitting(services, family, student))
    message = inbound(text=item.answer_key, chat_ref=FAMILY_CHAT, message_ref="same")

    first = await sent(services, message)
    again = await sent(services, message)

    assert first["result"]["outbound"] == again["result"]["outbound"]
    assert learning_state(services, family, student) == ONCE


async def test_a_redelivery_arriving_at_the_same_moment_still_counts_once(settings):
    services, family, student = await opened(settings)
    item = current_item(services, open_sitting(services, family, student))
    message = inbound(text=item.answer_key, chat_ref=FAMILY_CHAT, message_ref="same")

    await asyncio.gather(
        invoke_async(channel_request(message), services),
        invoke_async(channel_request(message), services),
        return_exceptions=True,
    )

    assert learning_state(services, family, student) == ONCE


async def test_a_button_from_a_sitting_abandoned_between_question_and_answer(settings):
    services, family, student = await opened(settings)
    sitting = open_sitting(services, family, student)
    item = current_item(services, sitting)
    position = item.options.index(item.answer_key) + 1
    data = f"sit:{answer_ref(sitting.id, item.id)}:{position}"
    services.clock.advance(minutes=61)

    response = await sent(
        services, inbound(callback=data, chat_ref=FAMILY_CHAT, message_ref="late")
    )

    assert response["ok"] is True
    assert learning_state(services, family, student) == NEVER
    assert open_sitting(services, family, student) is None


async def test_the_sitting_abandoned_between_question_and_answer_is_not_reopened(settings):
    services, family, student = await opened(settings)
    sitting = open_sitting(services, family, student)
    services.clock.advance(minutes=61)

    assert open_sitting(services, family, student) is None

    stored = list_study_sessions(services, family.id, student.id, sitting.opened_on)
    assert [session.status for session in stored] == [StudySessionStatus.ABANDONED]


async def test_forget_after_a_sitting_leaves_nothing_the_sitting_wrote(settings):
    services, family, student = await opened(settings)
    item = current_item(services, open_sitting(services, family, student))
    services.models[ModelRole.STRUCTURED].enqueue(
        {
            "intent": "explanation",
            "speaker": "child",
            "asked_for": "que se lo explique",
            "answer_text": "",
        }
    )
    services.models[ModelRole.GENERATE].enqueue(
        {"text": "Parte la barra en cuatro.", "approach": "bar split"}
    )
    await sent(services, inbound(text=CHILD_WORDS, chat_ref=FAMILY_CHAT, message_ref="h1"))
    await sent(services, inbound(text=item.answer_key, chat_ref=FAMILY_CHAT, message_ref="a1"))
    assert CHILD_WORDS in stored_text(services, family)

    await sent(services, inbound(callback="forget:yes", chat_ref=FAMILY_CHAT))

    assert learning_state(services, family, student) == NEVER
    assert services.store.get_family(family.id) is None
    assert services.store.list_students(family.id) == []
    assert prefixed(services, family, "study#") == 0
    assert prefixed(services, family, "episode#") == 0
    assert prefixed(services, family, "turn#") == 0
    assert stored_text(services, family) == ""
