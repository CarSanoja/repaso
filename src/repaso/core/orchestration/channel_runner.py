from datetime import datetime

from repaso.channel.telegram.commands import (
    FORGET_NO,
    FORGET_YES,
    handle_command,
    handle_forget_callback,
)
from repaso.core.orchestration.channel_enrollment import route_enrollment
from repaso.core.orchestration.channel_media import route_material
from repaso.core.orchestration.context import ChannelRun, Route, Services
from repaso.core.orchestration.runner import active_session, deliver_outbound, handle_answer
from repaso.schemas.channel import InboundMessage
from repaso.schemas.events import DomainEvent, EventKind
from repaso.schemas.family import Family
from repaso.schemas.student import Student

ESCALATION_PREFIX = "esc:"
QUARANTINE_PREFIX = "quar:"
ANSWER_PREFIX = "ans:"
COMMAND_PREFIX = "/"
ANSWER_CALLBACK_PARTS = 4
QUARANTINE_DECISIONS = {"yes": True, "no": False}


async def handle_channel_message(services: Services, message: InboundMessage) -> ChannelRun:
    run = ChannelRun(message=message, route=Route.IGNORED)
    family = services.store.find_family_by_chat(message.channel.value, message.chat_ref)
    if family is None:
        route_enrollment(services, run)
    else:
        run.family = family
        await _route_family(services, run, family)
    deliver_outbound(services, run.outbound)
    for event in run.events:
        services.publisher.publish(event)
    return run


async def _route_family(services: Services, run: ChannelRun, family: Family) -> None:
    message = run.message
    if message.callback_data:
        await _route_callback(services, run, family, message.callback_data)
        return
    text = (message.text or "").strip()
    if text.startswith(COMMAND_PREFIX):
        _route_command(services, run, family, text)
        return
    if message.media is not None:
        await route_material(services, run, family)
        return
    if text:
        await _route_answer(services, run, family, text)


def _route_command(services: Services, run: ChannelRun, family: Family, text: str) -> None:
    students = services.store.list_students(family.id)
    reply = handle_command(family, students, text, services.store, services.clock.now())
    if reply is None:
        return
    run.route = Route.COMMAND
    run.outbound.extend(reply.messages)
    run.events.extend(reply.events)


async def _route_callback(services: Services, run: ChannelRun, family: Family, data: str) -> None:
    if data in (FORGET_YES, FORGET_NO):
        reply = handle_forget_callback(family, services.store, family.lang, data == FORGET_YES)
        run.route = Route.FORGET
        run.outbound.extend(reply.messages)
        return
    if data.startswith(ESCALATION_PREFIX):
        escalation_id, _, option_key = data[len(ESCALATION_PREFIX) :].partition(":")
        if escalation_id and option_key:
            run.route = Route.ESCALATION
            run.events.append(
                _escalation_event(family, escalation_id, option_key, services.clock.now())
            )
            return
    if data.startswith(QUARANTINE_PREFIX):
        quarantine_id, _, decision = data[len(QUARANTINE_PREFIX) :].partition(":")
        accepted = QUARANTINE_DECISIONS.get(decision)
        if quarantine_id and accepted is not None:
            run.route = Route.QUARANTINE
            run.events.append(
                _quarantine_event(
                    family, quarantine_id, decision, accepted, services.clock.now()
                )
            )
            return
    if data.startswith(ANSWER_PREFIX):
        chosen = _button_answer(services, data)
        if chosen is not None:
            await _route_answer(services, run, family, chosen)
            return
    run.route = Route.UNROUTED_CALLBACK


async def _route_answer(services: Services, run: ChannelRun, family: Family, text: str) -> None:
    student = _answering_student(services, family)
    if student is None:
        run.route = Route.IGNORED
        return
    run.student = student
    run.route = Route.ANSWER
    latency = _latency(services, student.id, run.message.received_at)
    run.tutor = await handle_answer(services, family, student, text, latency)


def _button_answer(services: Services, data: str) -> str | None:
    parts = data.split(":")
    if len(parts) != ANSWER_CALLBACK_PARTS or not parts[3].isdigit():
        return None
    item = services.store.get_item(parts[2])
    if item is None:
        return None
    index = int(parts[3]) - 1
    if not 0 <= index < len(item.options):
        return None
    return item.options[index]


def _answering_student(services: Services, family: Family) -> Student | None:
    for student in services.store.list_students(family.id):
        if active_session(services, student.id) is not None:
            return student
    return None


def _latency(services: Services, student_id: str, received_at: datetime) -> float:
    session = active_session(services, student_id)
    if session is None or session.delivered_at is None:
        return 0.0
    return max(0.0, (received_at - session.delivered_at).total_seconds())


def _escalation_event(
    family: Family, escalation_id: str, option_key: str, now: datetime
) -> DomainEvent:
    return DomainEvent(
        kind=EventKind.ESCALATION_RESOLVED,
        family_id=family.id,
        idempotency_key=f"esc#{escalation_id}#{option_key}",
        occurred_at=now,
        payload={"escalation_id": escalation_id, "option_key": option_key},
    )


def _quarantine_event(
    family: Family, quarantine_id: str, decision: str, accepted: bool, now: datetime
) -> DomainEvent:
    return DomainEvent(
        kind=EventKind.QUARANTINE_RESOLVED,
        family_id=family.id,
        idempotency_key=f"quar#{quarantine_id}#{decision}",
        occurred_at=now,
        payload={"quarantine_id": quarantine_id, "accepted": accepted},
    )
