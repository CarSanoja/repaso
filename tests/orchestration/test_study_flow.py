from repaso.core.harness.practice_budget import (
    CONSECUTIVE_WRONG_STOP,
    DAILY_ITEM_ALLOWANCE,
    DAILY_ITEM_LIMIT,
)
from repaso.core.orchestration.study_flow import (
    answer_sitting,
    close_sitting,
    current_item,
    pause_sitting,
    resume_sitting,
    start_sitting,
)
from repaso.core.orchestration.study_store import items_served_today, open_sitting
from repaso.schemas.item import BloomLevel, ItemStatus
from repaso.schemas.study_session import Actor, CloseReason, StudySessionStatus
from tests.bank.items import FRACTIONS, make_item
from tests.orchestration.fixtures import make_services, seed_family

EQUIVALENCE_TOPIC = "fracciones equivalentes"


def seed_bank(services, family, count: int, competency_id: str = FRACTIONS) -> list[str]:
    ids = []
    for index in range(count):
        item = make_item(
            f"{competency_id}-{index}",
            family_id=family.id,
            competency_id=competency_id,
            stem=f"¿Cuál fracción equivale a 1/2? ({index})",
            rationale="Multiplicas arriba y abajo por dos.",
            bloom=BloomLevel.APPLY if index % 2 else BloomLevel.REMEMBER,
        )
        services.store.put_item(item)
        ids.append(item.id)
    return ids


def texts(reply) -> str:
    return "\n".join(message.text for message in reply.messages)


def answer(services, family, student, reply, text):
    return answer_sitting(services, family, student, reply.session, text, 12.0)


def test_a_sitting_opens_on_a_topic_and_serves_the_first_question(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 5)

    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    assert reply.session.status is StudySessionStatus.ACTIVE
    assert reply.session.goal.competency_id == FRACTIONS
    assert reply.session.budget.questions == DAILY_ITEM_LIMIT
    assert len(reply.session.progress.served) == 1
    assert "fracciones equivalentes" in texts(reply)
    assert reply.messages[-1].buttons


def test_a_topic_the_syllabus_does_not_have_is_refused_without_opening_a_sitting(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 3)

    reply = start_sitting(services, family, student, "cocina")

    assert reply.session is None
    assert "temario" in texts(reply)
    assert open_sitting(services, family, student) is None


def test_an_empty_bank_asks_for_a_photograph_of_that_topic_by_name(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)

    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    assert reply.session is None
    assert "fracciones equivalentes" in texts(reply)
    assert "foto" in texts(reply)


def test_one_question_in_the_bank_is_served_and_the_shortfall_is_said_plainly(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 1)

    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    assert reply.session.budget.questions == 1
    assert "1" in texts(reply)
    assert "foto" in texts(reply)


def test_two_questions_are_served_as_two_and_the_family_is_asked_for_more(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 2)

    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    assert reply.session.budget.questions == 2

    first = current_item(services, reply.session)
    after = answer(services, family, student, reply, first.answer_key)
    assert after.session.status is StudySessionStatus.ACTIVE
    second = current_item(services, after.session)
    assert second.id != first.id
    done = answer(services, family, student, after, second.answer_key)
    assert done.session.status is StudySessionStatus.CLOSED
    assert done.session.closed_reason is CloseReason.QUESTIONS_SPENT


def test_a_wrong_answer_hands_the_family_the_explanation_that_was_already_written(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 3)

    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    reply = answer(services, family, student, opened, "1/3")

    assert "Multiplicas arriba y abajo por dos." in texts(reply)
    assert "2/4" in texts(reply)


def test_a_right_answer_is_graded_deterministically_and_no_model_is_called(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 3)

    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)
    reply = answer(services, family, student, opened, item.answer_key)

    assert reply.session.progress.correct == 1
    assert all(model.calls == [] for model in services.models.values())
    mastery = services.store.get_mastery(student.id, FRACTIONS)
    assert mastery.attempts == 1
    assert mastery.correct == 1


def test_the_same_answer_arriving_twice_is_counted_once(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 3)

    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)
    first = answer_sitting(services, family, student, opened.session, item.answer_key, 12.0)
    replayed = answer_sitting(services, family, student, opened.session, item.answer_key, 12.0)

    assert first.session.progress.answered_keys == replayed.session.progress.answered_keys
    assert replayed.session.progress.correct == 1
    assert services.store.get_mastery(student.id, FRACTIONS).attempts == 1


def test_three_wrong_in_a_row_stops_the_sitting_with_care_rather_than_a_quota(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 6)

    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    for _ in range(CONSECUTIVE_WRONG_STOP):
        reply = answer(services, family, student, reply, "1/3")

    assert reply.session.status is StudySessionStatus.CLOSED
    assert reply.session.closed_reason is CloseReason.ENOUGH_FOR_TODAY
    assert "mañana" in texts(reply)


def test_the_sitting_closes_when_the_ten_minutes_are_up(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 6)

    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    services.clock.advance(minutes=reply.session.budget.minutes)
    item = current_item(services, reply.session)
    reply = answer(services, family, student, reply, item.answer_key)

    assert reply.session.closed_reason is CloseReason.MINUTES_SPENT


def test_a_bank_that_runs_dry_mid_sitting_closes_and_asks_for_a_page(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    ids = seed_bank(services, family, 3)

    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    served = opened.session.progress.served[0]
    for item_id in ids:
        if item_id != served:
            stored = services.store.get_item(item_id)
            services.store.put_item(stored.model_copy(update={"status": ItemStatus.RETIRED}))
    item = current_item(services, opened.session)
    reply = answer(services, family, student, opened, item.answer_key)

    assert reply.session.status is StudySessionStatus.CLOSED
    assert reply.session.closed_reason is CloseReason.BANK_EMPTY
    assert "foto" in texts(reply)


def test_the_day_is_bounded_by_items_not_by_model_calls(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 12)

    served = 0
    for _ in range(4):
        reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
        while reply.session is not None and reply.session.status is StudySessionStatus.ACTIVE:
            item = current_item(services, reply.session)
            reply = answer(services, family, student, reply, item.answer_key)
        served = items_served_today(services, family, student)

    assert served == DAILY_ITEM_ALLOWANCE
    assert "descansar" in texts(start_sitting(services, family, student, EQUIVALENCE_TOPIC))
    assert all(model.calls == [] for model in services.models.values())


def test_a_paused_sitting_is_resumed_by_the_family_and_never_by_the_system(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)

    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    paused = pause_sitting(services, family, opened.session, Actor.FAMILY)
    assert paused.session.status is StudySessionStatus.PAUSED

    resumed = resume_sitting(services, family, student, paused.session)
    assert resumed.session.status is StudySessionStatus.ACTIVE
    assert current_item(services, resumed.session) is not None


def test_the_family_can_close_a_sitting_and_it_stays_closed(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)

    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    closed = close_sitting(services, family, opened.session, Actor.FAMILY)

    assert closed.session.status is StudySessionStatus.CLOSED
    assert open_sitting(services, family, student) is None
    assert resume_sitting(services, family, student, closed.session).session.status is (
        StudySessionStatus.CLOSED
    )


def test_the_capsule_questions_of_today_are_not_served_again_in_a_sitting(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    ids = seed_bank(services, family, 4)
    from repaso.schemas.session import Capsule, PracticeSession, SessionStatus

    services.store.put_session(
        PracticeSession(
            id="capsule-1",
            student_id=student.id,
            session_date=services.clock.today(),
            capsule=Capsule(concept_snippet="hoy", item_ids=ids[:2]),
            status=SessionStatus.DELIVERED,
        )
    )

    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    assert set(reply.session.progress.served).isdisjoint(set(ids[:2]))
