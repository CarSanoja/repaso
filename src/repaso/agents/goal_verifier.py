from datetime import date

from repaso.core.harness.budgets import BoundedAttempts
from repaso.schemas.escalation import Escalation, EscalationStatus
from repaso.schemas.grading import GradeResult, StudentResponse
from repaso.schemas.review import QuarantineItem, QuarantineStatus
from repaso.schemas.session import PracticeSession, SessionStatus
from repaso.schemas.verification import DailyCloseReport

RESPONSE_REF_SEPARATOR = "#"
DELIVERED_STATUSES = (
    SessionStatus.DELIVERED,
    SessionStatus.IN_PROGRESS,
    SessionStatus.COMPLETED,
)
UNRESOLVED_STATUSES = (SessionStatus.PLANNED, SessionStatus.FAILED)


def response_ref(response: StudentResponse) -> str:
    return f"{response.student_id}{RESPONSE_REF_SEPARATOR}{response.item_id}"


def graded_keys(grades: list[GradeResult]) -> set[tuple[str, str]]:
    return {(grade.student_id, grade.item_id) for grade in grades}


def unresolved_candidates(
    planned: list[PracticeSession],
    responses: list[StudentResponse],
    graded: set[tuple[str, str]],
) -> list[str]:
    stalled = [session.id for session in planned if session.status in UNRESOLVED_STATUSES]
    ungraded = [
        response_ref(response)
        for response in responses
        if (response.student_id, response.item_id) not in graded
    ]
    return stalled + ungraded


def verify_daily(
    close_date: date,
    sessions: list[PracticeSession],
    grades: list[GradeResult],
    responses: list[StudentResponse],
    quarantines: list[QuarantineItem],
    escalations: list[Escalation],
    rework: BoundedAttempts,
) -> DailyCloseReport:
    planned = [session for session in sessions if session.session_date == close_date]
    delivered = [session for session in planned if session.status in DELIVERED_STATUSES]
    graded = graded_keys(grades)
    graded_responses = [
        response for response in responses if (response.student_id, response.item_id) in graded
    ]
    fired = [
        escalation for escalation in escalations if escalation.created_at.date() == close_date
    ]
    open_quarantines = [
        quarantine for quarantine in quarantines if quarantine.status is QuarantineStatus.PENDING
    ]
    pending_escalations = [
        escalation for escalation in escalations if escalation.status is EscalationStatus.PENDING
    ]
    pending_human = [quarantine.id for quarantine in open_quarantines]
    pending_human += [escalation.id for escalation in pending_escalations]
    unresolved: list[str] = []
    for candidate in unresolved_candidates(planned, responses, graded):
        rework.try_attempt()
        unresolved.append(candidate)
    return DailyCloseReport(
        close_date=close_date,
        sessions_planned=len(planned),
        sessions_delivered=len(delivered),
        responses_graded=len(graded_responses),
        quarantines_open=len(open_quarantines),
        escalations_fired=len(fired),
        rework_attempts=rework.attempts_used(),
        pending_human=pending_human,
        unresolved=unresolved,
    )
