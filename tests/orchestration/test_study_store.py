from repaso.core.harness.practice_budget import IDLE_MINUTES
from repaso.core.orchestration.privacy import forget_family
from repaso.core.orchestration.study_flow import start_sitting
from repaso.core.orchestration.study_store import (
    RETENTION_DAYS,
    items_served_today,
    list_study_sessions,
    open_sitting,
    put_study_session,
)
from repaso.schemas.session import Capsule, PracticeSession, SessionStatus
from repaso.schemas.study_session import StudySessionStatus
from tests.orchestration.fixtures import make_services, seed_family
from tests.orchestration.test_study_flow import EQUIVALENCE_TOPIC, seed_bank


def test_a_sitting_survives_the_turn_that_opened_it(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)

    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    found = open_sitting(services, family, student)

    assert found is not None
    assert found.id == opened.session.id
    assert found.progress.served == opened.session.progress.served


def test_a_sitting_nobody_came_back_to_is_abandoned_rather_than_left_open(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    services.clock.advance(minutes=IDLE_MINUTES)
    assert open_sitting(services, family, student) is None

    stored = list_study_sessions(services, family.id, student.id, services.clock.today())
    assert [session.status for session in stored] == [StudySessionStatus.ABANDONED]


def test_a_sitting_from_yesterday_never_spends_today(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    start_sitting(services, family, student, EQUIVALENCE_TOPIC)

    services.clock.advance(days=1)

    assert open_sitting(services, family, student) is None
    assert items_served_today(services, family, student) == 0


def test_the_day_counts_the_capsule_the_child_already_worked_through(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    ids = seed_bank(services, family, 4)
    services.store.put_session(
        PracticeSession(
            id="capsule-1",
            student_id=student.id,
            session_date=services.clock.today(),
            capsule=Capsule(concept_snippet="hoy", item_ids=ids[:3]),
            status=SessionStatus.COMPLETED,
            current_item_index=3,
        )
    )

    assert items_served_today(services, family, student) == 3


def test_a_sitting_carries_the_retention_the_consent_promises(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    opened = start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    put_study_session(services, opened.session)

    records = services.store.list_records(family.id, "study#")
    horizon = int(
        services.clock.now().timestamp() + RETENTION_DAYS * 24 * 3600
    )
    assert records
    assert all(record.payload["expires_at"] == horizon for record in records)


def test_forget_erases_every_sitting_the_family_ever_had(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_bank(services, family, 4)
    start_sitting(services, family, student, EQUIVALENCE_TOPIC)
    assert services.store.list_records(family.id, "study#")

    forget_family(services, family)

    assert services.store.list_records(family.id, "study#") == []
