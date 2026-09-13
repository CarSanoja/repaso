import json

import pytest

from repaso.config.models import ModelRole
from repaso.core.harness.retention import ANSWER_RETENTION_DAYS, expiry_stamp
from repaso.core.orchestration.privacy import forget_family
from repaso.core.orchestration.runner import handle_answer, live_journal
from repaso.schemas.operation import OperationRecord
from repaso.tools.episode_log import list_attempts
from tests.orchestration.fixtures import make_services, seed_family
from tests.orchestration.test_tutor_graphs import seed_item, seed_session

ANSWER = "creo que la mitad exacta"
JOURNAL = "answer#chat:9"


def with_policy(settings):
    services = make_services(settings)
    for _ in range(4):
        services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "fixture"})
    return services


async def answered(settings):
    services = with_policy(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    await handle_answer(services, family, student, ANSWER, 20.0, response_id="chat:9")
    return services, family, student


async def test_the_journal_holds_the_child_words_twice_and_both_copies_expire(settings):
    services, family, _ = await answered(settings)

    record = services.store.get_record(family.id, JOURNAL)
    assert json.dumps(record.payload).count(ANSWER) == 2
    assert record.payload["expires_at"] == expiry_stamp(services.clock.now())


async def test_the_journal_is_not_read_back_once_the_horizon_passes(settings):
    services, family, _ = await answered(settings)
    assert live_journal(services, family.id, JOURNAL) is not None

    services.clock.advance(days=ANSWER_RETENTION_DAYS)

    assert live_journal(services, family.id, JOURNAL) is None


async def test_the_attempt_outlives_the_words_it_was_made_of(settings):
    services, family, student = await answered(settings)

    services.clock.advance(days=ANSWER_RETENTION_DAYS + 1)

    assert live_journal(services, family.id, JOURNAL) is None
    episodes = list_attempts(services.store, family.id, student.id)
    assert [(e.item_id, e.correct) for e in episodes] == [("i1", False)]
    assert services.store.get_mastery(student.id, episodes[0].competency_id).attempts == 1


async def test_a_turn_abandoned_before_the_horizon_still_holds_the_student(settings):
    services, family, student = await answered(settings)
    services.store.put_record(
        OperationRecord(
            scope=family.id,
            key="answer#chat:10",
            payload={"student_id": student.id, "expires_at": expiry_stamp(services.clock.now())},
        )
    )
    seed_session(services, student.id, ["i1"])

    with pytest.raises(RuntimeError, match="awaiting recovery"):
        await handle_answer(services, family, student, "1/2", 20.0, response_id="chat:11")


async def test_an_abandoned_turn_stops_blocking_the_student_after_the_horizon(settings):
    services, family, student = await answered(settings)
    services.store.put_record(
        OperationRecord(
            scope=family.id,
            key="answer#chat:10",
            payload={"student_id": student.id, "expires_at": expiry_stamp(services.clock.now())},
        )
    )
    services.clock.advance(days=ANSWER_RETENTION_DAYS + 1)
    seed_session(services, student.id, ["i1"])

    run = await handle_answer(services, family, student, "1/2", 20.0, response_id="chat:11")

    assert run is not None
    assert run.grade.correct is True


async def test_forget_takes_the_journal_without_waiting_for_the_horizon(settings):
    services, family, _ = await answered(settings)

    forget_family(services, family)

    assert services.store.get_record(family.id, JOURNAL) is None
    assert services.store.list_records(family.id, "answer#") == []
