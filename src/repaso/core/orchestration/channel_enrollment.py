from repaso.channel.telegram.allowlist import pilot_codes, valid_invite
from repaso.channel.telegram.enrollment import advance, start_enrollment
from repaso.core.orchestration.context import ChannelRun, Route, Services
from repaso.i18n import msg
from repaso.schemas.channel import InboundMessage, OutboundMessage
from repaso.schemas.common import Lang

DEFAULT_LANG = Lang.ES


def route_enrollment(services: Services, run: ChannelRun) -> None:
    message = run.message
    channel = message.channel.value
    store = services.store
    codes = pilot_codes(services.settings.pilot_invite_codes)
    progress = store.get_enrollment(channel, message.chat_ref)
    if progress is None:
        text = (message.text or "").strip()
        if not valid_invite(text, codes):
            run.route = Route.UNKNOWN_CHAT
            run.outbound.append(greeting(message, "unknown_chat"))
            return
        progress = start_enrollment(message.channel, message.chat_ref, text, DEFAULT_LANG)
        store.put_enrollment(progress)
    reply = advance(progress, message, store, services.clock.now(), codes)
    run.outbound.extend(reply.messages)
    if not reply.done:
        run.route = Route.ENROLLMENT
        return
    run.route = Route.ENROLLED
    run.family = store.find_family_by_chat(channel, message.chat_ref)
    if run.family is not None:
        students = store.list_students(run.family.id)
        run.student = students[0] if students else None


def greeting(message: InboundMessage, key: str) -> OutboundMessage:
    return OutboundMessage(
        channel=message.channel, chat_ref=message.chat_ref, text=msg(key, DEFAULT_LANG)
    )
