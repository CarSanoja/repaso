from repaso.core.orchestration.context import Route
from repaso.core.orchestration.distress import RECORD_PREFIX
from repaso.core.orchestration.study_channel import handle_study_text
from repaso.core.orchestration.study_store import list_study_sessions
from repaso.core.orchestration.turn_memory import read_window
from repaso.i18n import msg
from repaso.schemas.common import Lang
from repaso.schemas.study_session import CloseReason, StudySessionStatus
from repaso.schemas.turn import TurnIntent
from tests.orchestration.fixtures import FRACTIONS, seed_family
from tests.orchestration.test_study_help import open_with, reads
from tests.orchestration.test_turn_router import reads as reads_chat
from tests.orchestration.test_turn_router import (
    said,
    says,
    seed_item,
    seed_session,
    services_with_recorder,
)

WROTE = "a veces pienso en hacerme dano cuando saco malas notas"


def records(services, family):
    return services.store.list_records(family.id, RECORD_PREFIX)


async def test_the_child_is_answered_and_the_adult_beside_them_is_called(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads_chat(services, TurnIntent.DISTRESS)

    run = await says(services, family, WROTE)

    assert run.route is Route.CONVERSATION
    assert said(run) == [msg("distress_child", Lang.ES), msg("distress_parent", Lang.ES)]


async def test_what_the_child_wrote_is_never_quoted_back(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads_chat(services, TurnIntent.DISTRESS)

    run = await says(services, family, WROTE)

    assert WROTE not in "\n".join(said(run))


async def test_distress_is_never_graded_even_when_it_carries_an_answer(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    session = seed_session(services, student.id, ["i1"])
    reads_chat(services, TurnIntent.DISTRESS, "1/2")

    await says(services, family, f"1/2 pero {WROTE}")

    assert services.grade_log.by_student(student.id) == []
    assert services.store.get_mastery(student.id, FRACTIONS) is None
    assert services.store.list_spaced(student.id) == []
    assert services.store.get_session(session.id).current_item_index == 0


async def test_the_words_are_not_kept_as_a_turn_the_practice_remembers(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    session = seed_session(services, student.id, ["i1"])
    reads_chat(services, TurnIntent.DISTRESS)

    await says(services, family, WROTE)

    assert read_window(services, family.id, session.id).notes == []


async def test_only_the_fact_and_the_hour_are_written_down(settings):
    services = services_with_recorder(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads_chat(services, TurnIntent.DISTRESS)

    await says(services, family, WROTE)

    kept = records(services, family)
    assert len(kept) == 1
    assert kept[0].payload == {
        "at": services.clock.now().isoformat(),
        "student_id": student.id,
    }
    assert WROTE not in str(kept[0].payload)


async def test_a_sitting_ends_where_the_distress_was_read(settings):
    services, family, student, session = open_with(settings)
    reads(services, TurnIntent.DISTRESS)

    reply = await handle_study_text(services, family, WROTE, 5.0, "m1")

    assert reply.session.status is StudySessionStatus.CLOSED
    assert reply.session.closed_reason is CloseReason.STOPPED_FOR_CARE
    stored = list_study_sessions(services, family.id, student.id, services.clock.today())
    assert stored[0].status is StudySessionStatus.CLOSED


async def test_a_sitting_answers_the_child_instead_of_the_next_question(settings):
    services, family, student, session = open_with(settings)
    reads(services, TurnIntent.DISTRESS)

    reply = await handle_study_text(services, family, WROTE, 5.0, "m1")

    assert [message.text for message in reply.messages] == [
        msg("distress_child", family.lang),
        msg("distress_parent", family.lang),
    ]
    assert reply.session.progress.answered_keys == []
    assert services.grade_log.by_student(student.id) == []


async def test_a_sitting_keeps_no_trace_of_the_words(settings):
    services, family, student, session = open_with(settings)
    reads(services, TurnIntent.DISTRESS)

    await handle_study_text(services, family, WROTE, 5.0, "m1")

    window = read_window(services, family.id, session.id)
    assert [note.said for note in window.notes] == []
    assert len(records(services, family)) == 1


async def test_the_sitting_does_not_reopen_on_the_next_message(settings):
    services, family, student, session = open_with(settings)
    reads(services, TurnIntent.DISTRESS)

    await handle_study_text(services, family, WROTE, 5.0, "m1")

    assert await handle_study_text(services, family, "otra", 5.0, "m2") is None
