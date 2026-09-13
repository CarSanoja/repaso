from repaso.core.orchestration.study_flow import answer_sitting, current_item, start_sitting
from repaso.core.orchestration.study_store import open_sitting, put_study_session
from repaso.schemas.study_session import StudySessionStatus
from tests.orchestration.fixtures import make_services, seed_family
from tests.orchestration.test_study_flow import EQUIVALENCE_TOPIC, seed_bank


def grades_for(services, student_id: str) -> list[str]:
    return [grade.id for grade in services.grade_log.by_student(student_id)]


def test_two_turns_answering_the_same_question_leave_one_attempt(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    stale = opened.session
    item = current_item(services, stale)

    answer_sitting(services, family, student, stale, item.answer_key, 10.0)
    answer_sitting(services, family, student, stale, item.answer_key, 10.0)

    assert services.store.get_mastery(student.id, item.competency_id).attempts == 1
    assert len(grades_for(services, student.id)) == 1


def test_a_stale_write_can_lose_a_served_question_but_never_an_attempt(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    stale = opened.session
    first = current_item(services, stale)

    advanced = answer_sitting(services, family, student, stale, first.answer_key, 10.0)
    put_study_session(services, stale)
    stored = open_sitting(services, family, student)

    assert stored.progress.served == stale.progress.served
    assert len(advanced.session.progress.served) == 2
    assert services.store.get_mastery(student.id, first.competency_id).attempts == 1


def test_an_answer_recorded_twice_never_moves_the_mastery_number_twice(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 6)
    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    for _ in range(2):
        item = current_item(services, reply.session)
        if item is None:
            break
        before = services.store.get_mastery(student.id, item.competency_id)
        answered = answer_sitting(services, family, student, reply.session, "1/3", 10.0)
        replayed = answer_sitting(services, family, student, reply.session, "1/3", 10.0)
        after = services.store.get_mastery(student.id, item.competency_id)
        assert replayed.session.progress.wrong == answered.session.progress.wrong
        assert after.attempts == (before.attempts if before else 0) + 1
        reply = answered

    assert len(grades_for(services, student.id)) == 2


def test_the_sitting_that_survives_a_crashed_turn_is_the_one_that_was_written(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    recovered = open_sitting(services, family, student)

    assert recovered.status is StudySessionStatus.ACTIVE
    assert recovered.id == opened.session.id
    assert recovered.progress.served == opened.session.progress.served
    assert recovered.budget == opened.session.budget
