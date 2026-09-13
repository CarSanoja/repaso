from dataclasses import dataclass, field
from uuid import uuid4

from repaso.core.harness.study_session import (
    budget_for,
    close_if_spent,
    open_session,
    questions_left,
    record_served,
    transition,
)
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.study_bank import available_items
from repaso.core.orchestration.study_messages import closing, plain, question, say
from repaso.core.orchestration.study_store import (
    items_served_today,
    put_study_session,
    stopped_for_today,
)
from repaso.core.orchestration.study_topics import resolve_topic
from repaso.i18n import counted
from repaso.i18n.competencies import competency_label
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.family import Family
from repaso.schemas.student import Student
from repaso.schemas.study_session import (
    Actor,
    CloseReason,
    StudyGoal,
    StudySession,
    StudySessionStatus,
)


@dataclass
class StudyReply:
    messages: list[OutboundMessage] = field(default_factory=list)
    session: StudySession | None = None


def _about(
    family: Family, goal: StudyGoal, key: str, count: int | None = None
) -> OutboundMessage:
    name = key if goal.label else f"{key}_any"
    if count is None:
        return say(family, name, topic=goal.label)
    return plain(family, counted(name, family.lang, count, topic=goal.label))


def goal_for(services: Services, family: Family, student: Student, topic: str) -> StudyGoal | None:
    if not topic.strip():
        return StudyGoal()
    competency = resolve_topic(services, student.grade, topic, family.lang)
    if competency is None:
        return None
    return StudyGoal(competency_id=competency.id, label=competency_label(competency, family.lang))


def start_sitting(
    services: Services,
    family: Family,
    student: Student,
    topic: str = "",
    goal: StudyGoal | None = None,
) -> StudyReply:
    goal = goal if goal is not None else goal_for(services, family, student, topic)
    if goal is None:
        return StudyReply([say(family, "study_topic_unknown", grade=student.grade)])
    if stopped_for_today(services, family, student):
        return StudyReply([say(family, "study_enough_today")])
    budget = budget_for(items_served_today(services, family, student))
    if budget.questions < 1:
        return StudyReply([say(family, "study_day_done")])
    found = available_items(services, family, student, goal, budget.questions)
    if not found:
        return StudyReply([_about(family, goal, "study_empty")])
    now = services.clock.now()
    session = open_session(
        uuid4().hex,
        family.id,
        student.id,
        now,
        services.clock.today(),
        budget.model_copy(update={"questions": len(found)}),
        goal,
    )
    session = transition(session, StudySessionStatus.ACTIVE, Actor.FAMILY, now)
    reply = StudyReply([_about(family, goal, "study_open", count=len(found))])
    if len(found) < budget.questions:
        reply.messages.append(_about(family, goal, "study_thin", count=len(found)))
    return serve_next(services, family, student, session, reply)


def resume_sitting(
    services: Services, family: Family, student: Student, session: StudySession
) -> StudyReply:
    if session.status is StudySessionStatus.ACTIVE:
        return serve_next(services, family, student, session, StudyReply())
    resumed = transition(session, StudySessionStatus.ACTIVE, Actor.FAMILY, services.clock.now())
    if resumed is None:
        return StudyReply([], session)
    said = StudyReply([say(family, "study_resumed")])
    return serve_next(services, family, student, resumed, said)


def pause_sitting(
    services: Services, family: Family, session: StudySession, actor: Actor
) -> StudyReply:
    paused = transition(session, StudySessionStatus.PAUSED, actor, services.clock.now())
    if paused is None:
        return StudyReply([], session)
    put_study_session(services, paused)
    return StudyReply([say(family, "study_paused")], paused)


def close_sitting(
    services: Services,
    family: Family,
    session: StudySession,
    actor: Actor,
    reason: CloseReason = CloseReason.FAMILY_CLOSED,
) -> StudyReply:
    closed = transition(session, StudySessionStatus.CLOSED, actor, services.clock.now(), reason)
    if closed is None:
        return StudyReply([], session)
    put_study_session(services, closed)
    return StudyReply([closing(family, closed, reason)], closed)


def _closed(
    services: Services,
    family: Family,
    session: StudySession,
    reason: CloseReason,
    reply: StudyReply,
) -> StudyReply:
    put_study_session(services, session)
    reply.messages.append(closing(family, session, reason))
    reply.session = session
    return reply


def serve_next(
    services: Services,
    family: Family,
    student: Student,
    session: StudySession,
    reply: StudyReply,
) -> StudyReply:
    now = services.clock.now()
    spent = close_if_spent(session, now, items_served_today(services, family, student))
    if spent.status is StudySessionStatus.CLOSED:
        return _closed(services, family, spent, spent.closed_reason, reply)
    found = available_items(
        services, family, student, session.goal, questions_left(session), session
    )
    if not found:
        closed = transition(
            session, StudySessionStatus.CLOSED, Actor.SYSTEM, now, CloseReason.BANK_EMPTY
        )
        reply = _closed(services, family, closed, CloseReason.BANK_EMPTY, reply)
        reply.messages.append(_about(family, closed.goal, "study_empty"))
        return reply
    served = record_served(session, found[0].id, now)
    put_study_session(services, served)
    reply.messages.append(question(family, served, found[0], len(served.progress.served)))
    reply.session = served
    return reply
