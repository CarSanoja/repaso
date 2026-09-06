from repaso.channel.telegram.allowlist import valid_invite
from repaso.channel.telegram.enrollment import advance, start_enrollment
from repaso.core.orchestration.context import ChannelRun, Route, Services
from repaso.core.orchestration.enrollment_journal import EnrollmentWrites, apply_step
from repaso.i18n import msg
from repaso.schemas.channel import InboundMessage, OutboundMessage
from repaso.schemas.common import Lang
from repaso.schemas.operation import OperationRecord

DEFAULT_LANG = Lang.ES
TRACE_KIND = "enrollment"
CLOSED_TRACE = "closed"
UNAVAILABLE_TRACE = "codes_unavailable"


def route_enrollment(services: Services, run: ChannelRun) -> None:
    message = run.message
    channel = message.channel.value
    store = services.store
    scope, key = f"chat:{message.chat_ref}", f"enrollment#{message.message_ref}"
    saved = store.get_record(scope, key)
    if saved:
        _resume(services, run, saved)
        return
    codes = invite_codes(services, message)
    progress = store.get_enrollment(channel, message.chat_ref)
    if progress is None:
        if not codes:
            services.telemetry.trace(
                TRACE_KIND, CLOSED_TRACE, status="skipped", chat_ref=message.chat_ref
            )
            run.route = Route.ENROLLMENT_CLOSED
            run.outbound.append(greeting(message, "enrollment_closed"))
            return
        text = (message.text or "").strip()
        if not valid_invite(text, codes):
            run.route = Route.UNKNOWN_CHAT
            run.outbound.append(greeting(message, "unknown_chat"))
            return
        progress = start_enrollment(message.channel, message.chat_ref, text, DEFAULT_LANG)
    writes = EnrollmentWrites()
    reply = advance(progress, message, writes, services.clock.now(), codes)
    saved = OperationRecord(
        scope=scope,
        key=key,
        payload={
            "actions": writes.actions,
            "done": reply.done,
            "messages": [m.model_dump(mode="json") for m in reply.messages],
        },
    )
    store.put_record(saved)
    _resume(services, run, saved)


def _resume(services, run, saved):
    apply_step(services.store, saved)
    run.outbound.extend(OutboundMessage.model_validate(m) for m in saved.payload["messages"])
    run.route = Route.ENROLLED if saved.payload["done"] else Route.ENROLLMENT
    run.family = services.store.find_family_by_chat(run.message.channel.value, run.message.chat_ref)
    if run.family is not None:
        students = services.store.list_students(run.family.id)
        run.student = students[0] if students else None


def invite_codes(services: Services, message: InboundMessage) -> frozenset[str]:
    try:
        return services.invites.codes()
    except Exception as error:
        services.telemetry.trace(
            TRACE_KIND,
            UNAVAILABLE_TRACE,
            status="failed",
            error=f"{type(error).__name__}: {error}"[:300],
            chat_ref=message.chat_ref,
        )
        return frozenset()


def greeting(message: InboundMessage, key: str) -> OutboundMessage:
    return OutboundMessage(
        channel=message.channel, chat_ref=message.chat_ref, text=msg(key, DEFAULT_LANG)
    )
