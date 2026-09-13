from datetime import datetime

from repaso.core.harness.study_session import transition
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.study_store import put_study_session
from repaso.i18n import msg
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.family import Family
from repaso.schemas.operation import OperationRecord
from repaso.schemas.student import Student
from repaso.schemas.study_session import Actor, CloseReason, StudySession, StudySessionStatus

CHILD_KEY = "distress_child"
PARENT_KEY = "distress_parent"
RECORD_PREFIX = "distress#"
TRACE_KIND = "distress"
TRACE_NAME = "read"


def _say(family: Family, key: str) -> OutboundMessage:
    return OutboundMessage(
        channel=family.channel,
        chat_ref=family.chat_ref,
        text=msg(key, family.lang),
    )


def replies(family: Family) -> list[OutboundMessage]:
    return [_say(family, CHILD_KEY), _say(family, PARENT_KEY)]


def remember(
    services: Services, family: Family, student: Student | None, turn_id: str, at: datetime
) -> None:
    services.store.put_record(
        OperationRecord(
            scope=family.id,
            key=f"{RECORD_PREFIX}{turn_id}",
            payload={"at": at.isoformat(), "student_id": student.id if student else ""},
        )
    )


def raise_alarm(
    services: Services, family: Family, student: Student | None, turn_id: str
) -> list[OutboundMessage]:
    now = services.clock.now()
    remember(services, family, student, turn_id, now)
    services.telemetry.trace(
        TRACE_KIND,
        TRACE_NAME,
        family_id=family.id,
        student_id=student.id if student else None,
    )
    return replies(family)


def stop_sitting(services: Services, session: StudySession) -> StudySession:
    closed = transition(
        session,
        StudySessionStatus.CLOSED,
        Actor.SYSTEM,
        services.clock.now(),
        CloseReason.STOPPED_FOR_CARE,
    )
    if closed is None:
        return session
    put_study_session(services, closed)
    return closed
