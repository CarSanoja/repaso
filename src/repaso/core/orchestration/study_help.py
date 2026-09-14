from repaso.agents.explainer import explain
from repaso.agents.turn_reader import read_turn
from repaso.core.orchestration import turn_memory
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.distress import raise_alarm, stop_sitting
from repaso.core.orchestration.study_answer import answer_sitting, current_item, picked_option
from repaso.core.orchestration.study_context import explain_context, read_context
from repaso.core.orchestration.study_flow import StudyReply, close_sitting
from repaso.core.orchestration.study_messages import plain, question, say
from repaso.core.orchestration.turn_replies import EXPLAIN_ROLE
from repaso.core.orchestration.turn_router import READ_ROLE, copied_verbatim
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.family import Family
from repaso.schemas.item import Item
from repaso.schemas.student import Student
from repaso.schemas.study_session import Actor, StudySession
from repaso.schemas.turn import TurnDecision, TurnIntent, TurnWindow

REPLY_KEYS = {
    TurnIntent.ABOUT_THE_PRACTICE: "turn_about_practice",
    TurnIntent.SOMETHING_ELSE: "turn_off_task",
}


def _asked(session: StudySession) -> int:
    return len(session.progress.served)


def _with_question(
    services: Services,
    family: Family,
    session: StudySession,
    first: OutboundMessage | None = None,
) -> StudyReply:
    item = current_item(services, session)
    messages = [first] if first is not None else []
    messages.append(question(family, session, item, _asked(session)))
    return StudyReply(messages, session)


def _unread(services: Services, family: Family, session: StudySession) -> StudyReply:
    return _with_question(services, family, session, say(family, "study_not_an_answer"))


def _stopped(
    services: Services,
    family: Family,
    student: Student,
    session: StudySession,
    turn_id: str,
) -> StudyReply:
    messages = raise_alarm(services, family, student, turn_id)
    return StudyReply(messages, stop_sitting(services, session))


def _graded(
    services: Services,
    family: Family,
    student: Student,
    session: StudySession,
    chosen: str,
    latency_seconds: float,
) -> StudyReply:
    if latency_seconds < 0:
        return _with_question(services, family, session, say(family, "study_out_of_step"))
    return answer_sitting(services, family, student, session, chosen, latency_seconds)


def _extracted(item: Item, decision: TurnDecision, said: str) -> str | None:
    candidate = decision.answer_text.strip()
    if not candidate or not copied_verbatim(said, candidate):
        return None
    return picked_option(item, candidate)


async def answer_or_help(
    services: Services,
    family: Family,
    student: Student,
    session: StudySession,
    text: str,
    latency_seconds: float,
    turn_id: str,
) -> StudyReply:
    item = current_item(services, session)
    if item is None:
        return answer_sitting(services, family, student, session, text, max(0.0, latency_seconds))
    if picked_option(item, text) is not None:
        return _graded(services, family, student, session, text, latency_seconds)
    said = services.screener.redact(text)
    window = turn_memory.read_window(services, family.id, session.id)
    decision = await read_turn(
        said,
        read_context(services, family, student, session, item, window),
        services.model(READ_ROLE),
    )
    if decision is None:
        return _unread(services, family, session)
    services.telemetry.trace(
        "study_turn", decision.intent.value, family_id=family.id, student_id=student.id
    )
    return await _act(
        services, family, student, session, item, decision, said, window, latency_seconds, turn_id
    )


async def _act(
    services: Services,
    family: Family,
    student: Student,
    session: StudySession,
    item: Item,
    decision: TurnDecision,
    said: str,
    window: TurnWindow,
    latency_seconds: float,
    turn_id: str,
) -> StudyReply:
    if decision.intent is TurnIntent.DISTRESS:
        return _stopped(services, family, student, session, turn_id)
    if decision.intent is TurnIntent.ANSWER:
        chosen = _extracted(item, decision, said)
        if chosen is None:
            return _unread(services, family, session)
        return _graded(services, family, student, session, chosen, latency_seconds)
    if decision.intent is TurnIntent.STOP:
        return close_sitting(services, family, session, Actor.FAMILY)
    explained = ""
    if decision.intent is TurnIntent.EXPLANATION:
        reply, explained = await _explained(
            services, family, student, session, item, decision, said, window
        )
    else:
        key = REPLY_KEYS.get(decision.intent)
        reply = _with_question(services, family, session, say(family, key) if key else None)
    _remember(services, family, session, item, decision, said, explained, turn_id)
    return reply


async def _explained(
    services: Services,
    family: Family,
    student: Student,
    session: StudySession,
    item: Item,
    decision: TurnDecision,
    said: str,
    window: TurnWindow,
) -> tuple[StudyReply, str]:
    context = explain_context(services, family, student, item, decision, said, window)
    services.telemetry.trace(
        "memory",
        "explanation.context_loaded",
        family_id=family.id,
        notes_loaded=len(window.notes),
        approaches_loaded=len(context.already_tried),
    )
    explanation = await explain(
        context,
        services.model(EXPLAIN_ROLE),
    )
    if explanation is None:
        unavailable = say(family, "turn_explain_unavailable")
        return _with_question(services, family, session, unavailable), ""
    reply = _with_question(services, family, session, plain(family, explanation.text))
    return reply, explanation.approach


def _remember(
    services: Services,
    family: Family,
    session: StudySession,
    item: Item,
    decision: TurnDecision,
    said: str,
    explained: str,
    turn_id: str,
) -> None:
    turn_memory.remember(
        services,
        family.id,
        session.id,
        turn_memory.note(
            turn_id=turn_id,
            intent=decision.intent,
            at=services.clock.now(),
            item=item,
            item_index=max(0, _asked(session) - 1),
            said=said,
            explained=explained,
        ),
    )
