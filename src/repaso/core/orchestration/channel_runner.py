from datetime import datetime, timedelta
from hashlib import sha256

from repaso.agents.capsule_composer import answer_ref
from repaso.channel.telegram.commands import (
    FORGET_NO,
    FORGET_YES,
    handle_command,
    handle_forget_callback,
)
from repaso.core.orchestration.channel_enrollment import route_enrollment
from repaso.core.orchestration.channel_media import route_material
from repaso.core.orchestration.context import ChannelRun, Route, Services
from repaso.core.orchestration.privacy import forget_family
from repaso.core.orchestration.runner import (
    active_session,
    current_item,
    deliver_outbound,
    handle_answer,
)
from repaso.core.orchestration.scheduling import sync_schedule
from repaso.core.orchestration.study_channel import (
    apply_study,
    handle_study_callback,
    handle_study_command,
    handle_study_text,
    study_latency,
)
from repaso.core.orchestration.turn_router import answering_student, route_answer, route_turn
from repaso.schemas.channel import InboundMessage, OutboundMessage
from repaso.schemas.events import DomainEvent, EventKind
from repaso.schemas.family import Family
from repaso.schemas.operation import OperationRecord

ESCALATION_PREFIX = "esc:"
QUARANTINE_PREFIX = "quar:"
ANSWER_PREFIX = "ans:"
STUDY_PREFIX = "sit:"
COMMAND_PREFIX = "/"
ANSWER_CALLBACK_PARTS = 4
QUARANTINE_DECISIONS = {"yes": True, "no": False}


async def handle_channel_message(services: Services, message: InboundMessage) -> ChannelRun:
    run = ChannelRun(message=message, route=Route.IGNORED)
    if message.callback_data == FORGET_YES:
        return _erase_and_ack(services, run)
    scope, key = f"chat:{message.chat_ref}", f"channel#{message.message_ref}"
    prepared = services.store.get_record(scope, key)
    if prepared:
        return _finish_channel(services, run, prepared)
    family = services.store.find_family_by_chat(message.channel.value, message.chat_ref)
    enrolling = services.store.get_record(scope, f"enrollment#{message.message_ref}")
    if family is None or enrolling is not None:
        route_enrollment(services, run)
    else:
        run.family = family
        sync_schedule(services, family)
        saved = services.store.get_record(family.id, f"answer#chat:{message.message_ref}")
        if saved:
            run.route = Route.ANSWER
            run.student = services.store.get_student(saved.payload["student_id"])
            response = saved.payload["response"]
            run.tutor = await handle_answer(
                services,
                family,
                run.student,
                response["text"],
                response["latency_seconds"],
                response_id=f"chat:{message.message_ref}",
            )
        else:
            await _route_family(services, run, family)
    if message.callback_data == FORGET_YES:
        # Do not recreate private outbox/cache rows after erasure.
        for outbound in run.outbound:
            services.sender.send(outbound)
        return run
    from repaso.runtime.summaries import channel_summary

    prepared = OperationRecord(
        scope=scope,
        key=key,
        payload={
            "summary": channel_summary(run),
            "messages": [m.model_dump(mode="json") for m in run.outbound],
            "events": [e.model_dump(mode="json") for e in run.events],
            "published": 0,
        },
    )
    services.store.put_record(prepared)
    _finish_channel(services, run, prepared)
    return run


def _finish_channel(services, run, prepared):
    data = prepared.payload
    summary = data["summary"]
    run.route = Route(summary["route"])
    run.family = services.store.get_family(summary["family_id"]) if summary["family_id"] else None
    run.student = (
        services.store.get_student(summary["student_id"]) if summary["student_id"] else None
    )
    run.outbound = [OutboundMessage.model_validate(m) for m in data["messages"]]
    run.events = [DomainEvent.model_validate(e) for e in data["events"]]
    if run.family:
        sync_schedule(services, run.family)
    deliver_outbound(services, run.outbound, prepared.key, prepared.scope)
    for event in run.events[data["published"] :]:
        services.publisher.publish(event)
        data["published"] += 1
        services.store.put_record(prepared)
    run.replayed_summary = summary
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
        study = handle_study_text(services, family, text, study_latency(services, family, run))
        if study is not None:
            apply_study(run, study)
            return
        await route_turn(services, run, family, text)


def _route_command(services: Services, run: ChannelRun, family: Family, text: str) -> None:
    study = handle_study_command(services, family, text)
    if study is not None:
        apply_study(run, study)
        return
    students = services.store.list_students(family.id)
    reply = handle_command(family, students, text, services.store, services.clock.now())
    if reply is None:
        return
    run.route = Route.COMMAND
    run.outbound.extend(reply.messages)
    run.events.extend(reply.events)


async def _route_callback(services: Services, run: ChannelRun, family: Family, data: str) -> None:
    if data in (FORGET_YES, FORGET_NO):
        if data == FORGET_YES:
            forget_family(services, family)
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
        if decision == "later" and services.store.get_quarantine(family.id, quarantine_id):
            from repaso.i18n import msg
            from repaso.schemas.channel import OutboundMessage

            run.route = Route.QUARANTINE
            run.outbound.append(
                OutboundMessage(
                    channel=family.channel,
                    chat_ref=family.chat_ref,
                    text=msg("quarantine_deferred", family.lang),
                )
            )
            return
        accepted = QUARANTINE_DECISIONS.get(decision)
        if quarantine_id and accepted is not None:
            run.route = Route.QUARANTINE
            run.events.append(
                _quarantine_event(family, quarantine_id, decision, accepted, services.clock.now())
            )
            return
    if data.startswith(STUDY_PREFIX):
        study = handle_study_callback(services, family, data, study_latency(services, family, run))
        if study is not None:
            apply_study(run, study)
            return
    if data.startswith(ANSWER_PREFIX):
        chosen = _button_answer(services, family, data)
        if chosen is not None:
            await route_answer(services, run, family, chosen)
            return
    run.route = Route.UNROUTED_CALLBACK


def _button_answer(services: Services, family: Family, data: str) -> str | None:
    parts = data.split(":")
    if len(parts) not in (3, ANSWER_CALLBACK_PARTS) or not parts[-1].isdigit():
        return None
    student = answering_student(services, family)
    if student is None:
        return None
    session = active_session(services, student.id)
    item = current_item(services, session)
    if item is None or item.family_id not in (None, family.id):
        return None
    if len(parts) == 3 and parts[1] != answer_ref(session.id, item.id):
        return None
    if len(parts) == 4 and (parts[1] != session.id or parts[2] != item.id):
        return None
    index = int(parts[-1]) - 1
    if not 0 <= index < len(item.options):
        return None
    return item.options[index]


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


def _erase_and_ack(services, run):
    from repaso.i18n import msg
    from repaso.schemas.common import Lang

    message = run.message
    key = sha256(f"{message.chat_ref}:{message.message_ref}".encode()).hexdigest()
    record = services.store.get_record("erasure-receipts", key)
    family = services.store.find_family_by_chat(message.channel.value, message.chat_ref)
    if record is None:
        if family is None:
            run.route = Route.IGNORED
            return run
        record = OperationRecord(
            scope="erasure-receipts",
            key=key,
            payload={
                "family_id": family.id,
                "lang": family.lang.value,
                "erased": False,
                "ack": False,
                "expires_at": int((services.clock.now() + timedelta(days=7)).timestamp()),
            },
        )
        services.store.put_record(record)
    if not record.payload["erased"]:
        family = family or services.store.get_family(record.payload["family_id"])
        if family is not None:
            forget_family(services, family)
        else:
            services.store.forget_family(record.payload["family_id"])
            services.store.delete_records(f"chat:{message.chat_ref}")
        record.payload.pop("family_id", None)
        record.payload["erased"] = True
        services.store.put_record(record)
    run.route = Route.FORGET
    if not record.payload["ack"]:
        lang = Lang(record.payload["lang"])
        reply = OutboundMessage(
            channel=message.channel, chat_ref=message.chat_ref, text=msg("forget_done", lang)
        )
        # Only the opaque receipt survives; no chat identifier is stored here.
        services.sender.send(reply)
        record.payload["ack"] = True
        services.store.put_record(record)
        run.outbound.append(reply)
    return run
