from repaso.channel.telegram.commands import handle_command
from repaso.config.models import ModelRole
from repaso.core.orchestration.privacy import forget_family
from repaso.core.orchestration.runner import handle_answer
from repaso.core.orchestration.study_answer import answer_sitting
from repaso.core.orchestration.study_answer import current_item as served_item
from repaso.core.orchestration.study_flow import start_sitting
from repaso.schemas.grading import GradedBy
from repaso.schemas.item import ItemKind
from repaso.tools.episode_log import list_attempts
from tests.orchestration.fixtures import FRACTIONS, make_services, seed_family
from tests.orchestration.test_study_flow import EQUIVALENCE_TOPIC, seed_bank
from tests.orchestration.test_tutor_graphs import seed_item, seed_session


def with_policy(settings, decisions: int = 4):
    services = make_services(settings)
    for _ in range(decisions):
        services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "fixture"})
    return services


async def test_every_answer_leaves_an_episode_of_what_was_answered_and_when(settings):
    services = with_policy(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_item(services.store, "i2")
    seed_session(services, student.id, ["i1", "i2"])

    await handle_answer(services, family, student, "1/2", 20.0)
    await handle_answer(services, family, student, "3/4", 25.0)

    episodes = list_attempts(services.store, family.id, student.id)
    assert [(e.item_id, e.correct) for e in episodes] == [("i1", True), ("i2", False)]
    assert {e.competency_id for e in episodes} == {FRACTIONS}
    assert {e.session_id for e in episodes} == {"sess1"}
    assert [e.graded_by for e in episodes] == [GradedBy.DETERMINISTIC] * 2
    assert [e.occurred_at for e in episodes] == [services.clock.now()] * 2
    assert [e.latency_seconds for e in episodes] == [20.0, 25.0]


async def test_an_answer_the_judge_could_not_settle_is_logged_as_neither(settings):
    services = with_policy(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1", kind=ItemKind.OPEN)
    seed_session(services, student.id, ["i1"])
    services.models[ModelRole.JUDGE].enqueue(
        {"correct": True, "rubric_points": 1.5, "confidence": 0.3, "feedback": "casi"}
    )

    await handle_answer(services, family, student, "porque los dos son la mitad", 30.0)

    episode = list_attempts(services.store, family.id, student.id)[0]
    assert episode.correct is None
    assert episode.held is True
    assert services.store.get_mastery(student.id, FRACTIONS) is None


async def test_replaying_the_same_answer_does_not_log_a_second_attempt(settings):
    services = with_policy(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])

    await handle_answer(services, family, student, "1/2", 20.0, response_id="chat:42")
    await handle_answer(services, family, student, "1/2", 20.0, response_id="chat:42")

    episodes = list_attempts(services.store, family.id, student.id)
    assert len(episodes) == 1
    assert services.store.get_mastery(student.id, FRACTIONS).attempts == 1


async def test_the_episode_log_counts_what_the_status_readout_reports(settings):
    services = with_policy(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_item(services.store, "i2")
    seed_session(services, student.id, ["i1", "i2"])

    await handle_answer(services, family, student, "1/2", 20.0)
    await handle_answer(services, family, student, "3/4", 25.0)

    episodes = list_attempts(services.store, family.id, student.id)
    mastery = services.store.get_mastery(student.id, FRACTIONS)
    assert len(episodes) == mastery.attempts
    assert sum(1 for e in episodes if e.correct) == mastery.correct


async def test_forget_erases_the_episodes_with_everything_else(settings):
    services = with_policy(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    await handle_answer(services, family, student, "1/2", 20.0)
    assert list_attempts(services.store, family.id, student.id)

    forget_family(services, family)

    assert list_attempts(services.store, family.id, student.id) == []
    assert services.store.list_records(family.id, "episode#") == []


async def test_a_study_sitting_lands_in_the_same_ledger_the_capsule_does(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = served_item(services, opened.session)

    answer_sitting(services, family, student, opened.session, item.answer_key, 12.0)

    episode = list_attempts(services.store, family.id, student.id)[0]
    mastery = services.store.get_mastery(student.id, item.competency_id)
    assert episode.item_id == item.id
    assert episode.correct is True
    assert episode.session_id == opened.session.id
    assert episode.graded_by is GradedBy.DETERMINISTIC
    assert mastery.attempts == 1


async def test_a_redelivered_sitting_answer_leaves_one_episode(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    item = served_item(services, opened.session)

    answer_sitting(services, family, student, opened.session, item.answer_key, 12.0)
    answer_sitting(services, family, student, opened.session, item.answer_key, 12.0)

    episodes = list_attempts(services.store, family.id, student.id)
    assert len(episodes) == 1
    assert services.store.get_mastery(student.id, item.competency_id).attempts == 1


async def test_status_reports_the_days_the_episode_log_can_show(settings):
    services = with_policy(settings, decisions=6)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    await handle_answer(services, family, student, "1/2", 20.0)
    services.clock.advance(days=1)
    seed_session(services, student.id, ["i1"], "sess2")
    await handle_answer(services, family, student, "1/2", 20.0)

    line = handle_command(family, [student], "/status", services.store, services.clock.now())

    assert "en 2 días de práctica registrados" in line.messages[0].text
    assert len(list_attempts(services.store, family.id, student.id)) == 2
