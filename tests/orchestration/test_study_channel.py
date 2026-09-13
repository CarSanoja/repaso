from datetime import UTC, datetime

from repaso.agents.capsule_composer import answer_ref
from repaso.config.models import ModelRole
from repaso.core.orchestration.channel_runner import handle_channel_message
from repaso.core.orchestration.context import Route
from repaso.core.orchestration.study_answer import answer_sitting, current_item
from repaso.core.orchestration.study_flow import start_sitting
from repaso.core.orchestration.study_store import open_sitting
from repaso.schemas.channel import ChannelKind, InboundMessage
from repaso.schemas.common import Lang
from repaso.schemas.family import FamilyStatus
from repaso.schemas.session import Capsule, PracticeSession, SessionStatus
from repaso.schemas.study_session import StudySessionStatus
from repaso.schemas.turn import TurnIntent
from tests.orchestration.fixtures import make_services, seed_family
from tests.orchestration.test_study_flow import AREA, AREA_TOPIC, EQUIVALENCE_TOPIC, seed_bank
from tests.orchestration.test_turn_router import reads

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


def inbound(chat_ref: str, text: str = "", ref: str = "m1", callback: str | None = None):
    return InboundMessage(
        channel=ChannelKind.TELEGRAM,
        chat_ref=chat_ref,
        message_ref=ref,
        text=text or None,
        callback_data=callback,
        received_at=START,
    )


def texts(run) -> str:
    return "\n".join(message.text for message in run.outbound)


async def test_sesion_opens_a_sitting_from_the_chat(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)

    run = await handle_channel_message(services, inbound(family.chat_ref, "/sesion"))

    assert run.route is Route.STUDY
    assert run.study.status is StudySessionStatus.ACTIVE
    assert run.outbound
    assert open_sitting(services, family, student) is not None


async def test_the_english_command_works_for_an_english_family(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    family.lang = Lang.EN
    services.store.put_family(family)
    seed_bank(services, family, 4, lang=Lang.EN)

    run = await handle_channel_message(services, inbound(family.chat_ref, "/session"))

    assert run.route is Route.STUDY
    assert "Question 1 of" in texts(run)


async def test_tema_opens_the_sitting_on_the_topic_the_family_named(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    seed_bank(services, family, 4)

    run = await handle_channel_message(
        services, inbound(family.chat_ref, f"/tema {EQUIVALENCE_TOPIC}")
    )

    assert run.study.goal.label == "fracciones equivalentes"


async def test_tema_without_a_topic_asks_which_one(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    seed_bank(services, family, 4)

    run = await handle_channel_message(services, inbound(family.chat_ref, "/tema"))

    assert run.study is None
    assert "/tema" in texts(run)


async def test_a_plain_reply_answers_the_open_sitting(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)

    run = await handle_channel_message(
        services, inbound(family.chat_ref, item.answer_key, ref="m2")
    )

    assert run.route is Route.STUDY
    assert run.study.progress.correct == 1


async def test_a_button_from_the_open_sitting_is_graded(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)
    position = item.options.index(item.answer_key) + 1

    run = await handle_channel_message(
        services,
        inbound(
            family.chat_ref,
            ref="m2",
            callback=f"sit:{answer_ref(opened.session.id, item.id)}:{position}",
        ),
    )

    assert run.route is Route.STUDY
    assert run.study.progress.correct == 1


async def test_a_button_from_a_sitting_that_is_over_is_answered_not_ignored(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)

    run = await handle_channel_message(
        services,
        inbound(family.chat_ref, ref="m9", callback=f"sit:{answer_ref('gone', item.id)}:1"),
    )

    assert run.route is Route.STUDY
    assert run.outbound
    assert "/sesion" in texts(run)


async def test_the_daily_capsule_still_gets_the_answer_when_no_sitting_is_open(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    ids = seed_bank(services, family, 3)
    services.store.put_session(
        PracticeSession(
            id="capsule-1",
            student_id=student.id,
            session_date=services.clock.today(),
            capsule=Capsule(concept_snippet="hoy", item_ids=ids),
            status=SessionStatus.DELIVERED,
            delivered_at=services.clock.now(),
        )
    )

    reads(services, TurnIntent.ANSWER)
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "fixture"})
    run = await handle_channel_message(services, inbound(family.chat_ref, "2/4", ref="m3"))

    assert run.route is Route.ANSWER


async def test_a_redelivered_message_replays_without_counting_a_second_attempt(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)
    message = inbound(family.chat_ref, item.answer_key, ref="m5")

    first = await handle_channel_message(services, message)
    again = await handle_channel_message(services, message)

    assert [m.text for m in first.outbound] == [m.text for m in again.outbound]
    assert services.store.get_mastery(student.id, item.competency_id).attempts == 1


async def test_a_second_message_for_a_question_already_answered_does_not_count_twice(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)

    await handle_channel_message(services, inbound(family.chat_ref, item.answer_key, ref="m6"))
    sitting = open_sitting(services, family, student)
    stale = current_item(services, sitting)
    await handle_channel_message(
        services,
        inbound(family.chat_ref, ref="m7", callback=f"sit:{answer_ref(sitting.id, item.id)}:1"),
    )

    assert services.store.get_mastery(student.id, item.competency_id).attempts == 1
    assert stale.id != item.id


async def test_listo_closes_the_sitting_and_says_so(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    run = await handle_channel_message(services, inbound(family.chat_ref, "/listo", ref="m8"))

    assert run.study.status is StudySessionStatus.CLOSED
    assert open_sitting(services, family, student) is None


async def test_listo_with_nothing_open_still_answers(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)

    run = await handle_channel_message(services, inbound(family.chat_ref, "/listo"))

    assert run.outbound
    assert run.study is None


async def test_a_paused_family_is_not_handed_practice_it_asked_to_stop(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    family.status = FamilyStatus.PAUSED
    services.store.put_family(family)

    run = await handle_channel_message(services, inbound(family.chat_ref, "/sesion"))

    assert run.study is None
    assert "/resume" in texts(run)
    assert open_sitting(services, family, student) is None


async def test_a_topic_the_syllabus_lacks_does_not_take_the_open_sitting_with_it(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    run = await handle_channel_message(services, inbound(family.chat_ref, "/tema cocina", "m10"))

    still_open = open_sitting(services, family, student)
    assert still_open is not None
    assert still_open.id == opened.session.id
    assert "temario" in texts(run)


async def test_tema_without_a_topic_does_not_take_the_open_sitting_with_it(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    await handle_channel_message(services, inbound(family.chat_ref, "/tema", "m11"))

    assert open_sitting(services, family, student) is not None


async def test_switching_topic_says_how_the_practice_they_were_in_ended(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    seed_bank(services, family, 4, competency_id=AREA)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)
    answer_sitting(services, family, student, opened.session, item.answer_key, 9.0)

    run = await handle_channel_message(
        services, inbound(family.chat_ref, f"/tema {AREA_TOPIC}", "m12")
    )

    assert "Terminamos esta práctica" in texts(run)
    assert run.study.goal.label == "área de rectángulos"
