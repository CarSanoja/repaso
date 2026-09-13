from datetime import date, timedelta

from repaso.core.harness.study_session import (
    OPEN_STATUSES,
    is_expired,
    transition,
)
from repaso.core.orchestration.context import Services
from repaso.schemas.family import Family
from repaso.schemas.operation import OperationRecord
from repaso.schemas.student import Student
from repaso.schemas.study_session import Actor, StudySession, StudySessionStatus

STUDY_PREFIX = "study#"
RETENTION_DAYS = 7


def day_prefix(student_id: str, day: date) -> str:
    return f"{STUDY_PREFIX}{student_id}#{day.isoformat()}#"


def record_key(session: StudySession) -> str:
    return f"{day_prefix(session.student_id, session.opened_on)}{session.id}"


def put_study_session(services: Services, session: StudySession) -> None:
    expires = services.clock.now() + timedelta(days=RETENTION_DAYS)
    services.store.put_record(
        OperationRecord(
            scope=session.family_id,
            key=record_key(session),
            payload={
                "session": session.model_dump(mode="json"),
                "expires_at": int(expires.timestamp()),
            },
        )
    )


def list_study_sessions(
    services: Services, family_id: str, student_id: str, day: date
) -> list[StudySession]:
    records = services.store.list_records(family_id, day_prefix(student_id, day))
    sessions = [StudySession.model_validate(record.payload["session"]) for record in records]
    return sorted(sessions, key=lambda session: (session.opened_at, session.id))


def open_sitting(services: Services, family: Family, student: Student) -> StudySession | None:
    today = services.clock.today()
    now = services.clock.now()
    found = None
    for session in list_study_sessions(services, family.id, student.id, today):
        if session.status not in OPEN_STATUSES:
            continue
        if is_expired(session, now, today):
            abandoned = transition(session, StudySessionStatus.ABANDONED, Actor.SYSTEM, now)
            if abandoned is not None:
                put_study_session(services, abandoned)
            continue
        found = session
    return found


def capsule_items_served(services: Services, student: Student) -> int:
    session = services.store.get_session_by_date(student.id, services.clock.today())
    if session is None or session.capsule is None:
        return 0
    return min(session.current_item_index, len(session.capsule.item_ids))


def items_served_today(services: Services, family: Family, student: Student) -> int:
    today = services.clock.today()
    study = sum(
        len(session.progress.served)
        for session in list_study_sessions(services, family.id, student.id, today)
    )
    return capsule_items_served(services, student) + study
