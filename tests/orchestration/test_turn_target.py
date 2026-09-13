import pytest

from repaso.core.orchestration.turn_target import (
    focus_item,
    focus_student,
    items_left,
    practice_state,
    today_session,
    was_answered,
)
from repaso.schemas.session import Capsule, PracticeSession, SessionStatus
from repaso.schemas.student import Student
from repaso.schemas.turn import PracticeState
from tests.orchestration.fixtures import START, make_services, seed_family, seed_open_item


def session(services, status=SessionStatus.DELIVERED, index=0, item_ids=("i1", "i2", "i3")):
    return PracticeSession(
        id="sess1",
        student_id="s-f1",
        session_date=services.clock.today(),
        capsule=Capsule(concept_snippet="snippet", item_ids=list(item_ids)),
        status=status,
        current_item_index=index,
        delivered_at=services.clock.now(),
    )


def test_nothing_planned_and_nothing_delivered_both_read_as_not_sent(settings):
    services = make_services(settings)

    assert practice_state(None) is PracticeState.NOT_SENT
    assert practice_state(session(services, SessionStatus.PLANNED)) is PracticeState.NOT_SENT


@pytest.mark.parametrize("status", [SessionStatus.DELIVERED, SessionStatus.IN_PROGRESS])
def test_a_live_capsule_is_open(settings, status):
    services = make_services(settings)

    assert practice_state(session(services, status)) is PracticeState.OPEN


@pytest.mark.parametrize("status", [SessionStatus.COMPLETED, SessionStatus.EXPIRED])
def test_a_capsule_that_is_over_is_finished(settings, status):
    services = make_services(settings)

    assert practice_state(session(services, status)) is PracticeState.FINISHED


def test_the_question_in_front_of_the_family_is_the_current_one(settings):
    services = make_services(settings)
    seed_open_item(services.store, "i2")

    item, index = focus_item(services, session(services, index=1))

    assert (item.id, index) == ("i2", 1)


def test_a_finished_capsule_still_points_at_the_question_they_were_on(settings):
    services = make_services(settings)
    seed_open_item(services.store, "i3")
    over = session(services, SessionStatus.COMPLETED, index=3)

    item, index = focus_item(services, over)

    assert (item.id, index) == ("i3", 2)
    assert was_answered(over, index) is True


def test_the_question_on_screen_has_not_been_answered_yet(settings):
    services = make_services(settings)

    assert was_answered(session(services, index=1), 1) is False
    assert was_answered(session(services, index=1), 0) is True
    assert was_answered(None, 0) is False


def test_how_many_questions_are_still_to_come(settings):
    services = make_services(settings)

    assert items_left(session(services, index=0)) == 2
    assert items_left(session(services, index=2)) == 0
    assert items_left(None) == 0


def test_the_only_child_in_the_chat_is_the_one_the_turn_is_about(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)

    assert focus_student(services, family).id == student.id


def test_two_children_and_no_live_session_is_not_guessed(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    services.store.put_student(
        Student(
            id="s-second",
            family_id=family.id,
            alias="Estrella",
            grade=4,
            section_key="san-jose-4-b",
            created_at=START,
        )
    )

    assert focus_student(services, family) is None


def test_no_student_means_no_session_to_look_at(settings):
    services = make_services(settings)

    assert today_session(services, None) is None
