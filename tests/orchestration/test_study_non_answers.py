from repaso.core.orchestration.study_answer import answer_sitting, current_item, picked_option
from repaso.core.orchestration.study_flow import start_sitting
from tests.orchestration.fixtures import make_services, seed_family
from tests.orchestration.test_study_flow import EQUIVALENCE_TOPIC, seed_bank

CONFUSED = ("no entiendo", "¿por qué?", "explícame", "no sé", "otra", "gracias", "👍")


def texts(reply) -> str:
    return "\n".join(message.text for message in reply.messages)


def test_a_choice_is_read_from_the_option_or_from_its_number(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 2)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)

    assert picked_option(item, item.options[1]) == item.options[1]
    assert picked_option(item, "2") == item.options[1]
    assert picked_option(item, f"  {item.options[0].upper()} ") == item.options[0]
    assert picked_option(item, "9") is None


def test_a_child_who_says_they_do_not_understand_is_not_recorded_as_wrong(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, reply.session)

    for text in CONFUSED:
        reply = answer_sitting(services, family, student, reply.session, text, 8.0)

    assert reply.session.progress.answered_keys == []
    assert reply.session.progress.wrong == 0
    assert services.store.get_mastery(student.id, item.competency_id) is None
    assert services.grade_log.by_student(student.id) == []


def test_the_question_is_asked_again_instead_of_moving_on(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = current_item(services, opened.session)

    reply = answer_sitting(services, family, student, opened.session, "no entiendo", 8.0)

    assert current_item(services, reply.session).id == item.id
    assert item.stem in texts(reply)
    assert len(reply.session.progress.served) == 1


def test_the_budget_is_not_spent_by_a_message_that_was_not_an_answer(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    reply = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    before = reply.session.budget.questions

    for _ in range(5):
        reply = answer_sitting(services, family, student, reply.session, "no entiendo", 8.0)

    assert reply.session.budget.questions == before
    assert len(reply.session.progress.served) == 1
