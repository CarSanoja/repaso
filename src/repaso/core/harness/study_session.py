from datetime import date, datetime, timedelta

from repaso.core.harness.practice_budget import (
    CONSECUTIVE_WRONG_STOP,
    DAILY_ITEM_ALLOWANCE,
    IDLE_MINUTES,
    SESSION_MINUTES,
    session_questions,
)
from repaso.schemas.study_session import (
    Actor,
    CloseReason,
    StudyBudget,
    StudyGoal,
    StudyProgress,
    StudySession,
    StudySessionStatus,
)

OPEN_STATUSES = frozenset(
    {StudySessionStatus.PROPOSED, StudySessionStatus.ACTIVE, StudySessionStatus.PAUSED}
)
BOTH = frozenset({Actor.FAMILY, Actor.SYSTEM})
FAMILY_ONLY = frozenset({Actor.FAMILY})
SYSTEM_ONLY = frozenset({Actor.SYSTEM})

TRANSITIONS: dict[StudySessionStatus, dict[StudySessionStatus, frozenset[Actor]]] = {
    StudySessionStatus.PROPOSED: {
        StudySessionStatus.ACTIVE: FAMILY_ONLY,
        StudySessionStatus.CLOSED: BOTH,
        StudySessionStatus.ABANDONED: SYSTEM_ONLY,
    },
    StudySessionStatus.ACTIVE: {
        StudySessionStatus.PAUSED: BOTH,
        StudySessionStatus.CLOSED: BOTH,
        StudySessionStatus.ABANDONED: SYSTEM_ONLY,
    },
    StudySessionStatus.PAUSED: {
        StudySessionStatus.ACTIVE: FAMILY_ONLY,
        StudySessionStatus.CLOSED: BOTH,
        StudySessionStatus.ABANDONED: SYSTEM_ONLY,
    },
    StudySessionStatus.CLOSED: {},
    StudySessionStatus.ABANDONED: {},
}


def budget_for(served_today: int, minutes: int = SESSION_MINUTES) -> StudyBudget:
    return StudyBudget(questions=session_questions(served_today), minutes=minutes)


def open_session(
    session_id: str,
    family_id: str,
    student_id: str,
    now: datetime,
    today: date,
    budget: StudyBudget,
    goal: StudyGoal | None = None,
    opened_by: Actor = Actor.FAMILY,
) -> StudySession:
    return StudySession(
        id=session_id,
        family_id=family_id,
        student_id=student_id,
        opened_by=opened_by,
        opened_at=now,
        opened_on=today,
        last_event_at=now,
        goal=goal or StudyGoal(),
        budget=budget,
        progress=StudyProgress(),
        status=StudySessionStatus.PROPOSED,
    )


def may(session: StudySession, target: StudySessionStatus, actor: Actor) -> bool:
    return actor in TRANSITIONS[session.status].get(target, frozenset())


def transition(
    session: StudySession,
    target: StudySessionStatus,
    actor: Actor,
    now: datetime,
    reason: CloseReason | None = None,
) -> StudySession | None:
    if not may(session, target, actor):
        return None
    update = {"status": target, "last_event_at": now}
    if target is StudySessionStatus.CLOSED:
        update["closed_reason"] = reason or CloseReason.FAMILY_CLOSED
    if target is StudySessionStatus.ABANDONED:
        update["closed_reason"] = CloseReason.EXPIRED
    return session.model_copy(update=update)


def questions_left(session: StudySession) -> int:
    return max(0, session.budget.questions - len(session.progress.served))


def minutes_elapsed(session: StudySession, now: datetime) -> float:
    return max(0.0, (now - session.opened_at).total_seconds() / 60.0)


def is_expired(session: StudySession, now: datetime, today: date) -> bool:
    if session.status not in OPEN_STATUSES:
        return False
    if session.opened_on != today:
        return True
    return now - session.last_event_at >= timedelta(minutes=IDLE_MINUTES)


def stop_reason(
    session: StudySession, now: datetime, served_today: int = 0
) -> CloseReason | None:
    if session.progress.consecutive_wrong >= CONSECUTIVE_WRONG_STOP:
        return CloseReason.ENOUGH_FOR_TODAY
    if questions_left(session) < 1:
        return CloseReason.QUESTIONS_SPENT
    if minutes_elapsed(session, now) >= session.budget.minutes:
        return CloseReason.MINUTES_SPENT
    if served_today >= DAILY_ITEM_ALLOWANCE:
        return CloseReason.DAY_SPENT
    return None


def record_served(session: StudySession, item_id: str, now: datetime) -> StudySession:
    if item_id in session.progress.served:
        return session
    progress = session.progress.model_copy(
        update={"served": [*session.progress.served, item_id]}
    )
    return session.model_copy(update={"progress": progress, "last_event_at": now})


def record_answer(
    session: StudySession, key: str, correct: bool, now: datetime
) -> StudySession:
    if key in session.progress.answered_keys:
        return session
    previous = session.progress
    progress = previous.model_copy(
        update={
            "answered_keys": [*previous.answered_keys, key],
            "correct": previous.correct + (1 if correct else 0),
            "wrong": previous.wrong + (0 if correct else 1),
            "consecutive_wrong": 0 if correct else previous.consecutive_wrong + 1,
        }
    )
    return session.model_copy(update={"progress": progress, "last_event_at": now})


def close_if_spent(
    session: StudySession, now: datetime, served_today: int = 0
) -> StudySession:
    if session.status not in OPEN_STATUSES:
        return session
    reason = stop_reason(session, now, served_today)
    if reason is None:
        return session
    return transition(session, StudySessionStatus.CLOSED, Actor.SYSTEM, now, reason) or session
