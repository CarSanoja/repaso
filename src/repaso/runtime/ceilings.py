from repaso.core.orchestration.outbox import deliver
from repaso.i18n import msg
from repaso.schemas.channel import ChannelKind, OutboundMessage
from repaso.schemas.common import Lang
from repaso.tools.model_limits import LimitReason

TRACE_KIND = "spend"
TRIPPED = "tripped"
PAUSED_KEY = "practice_paused_today"
WAITING_KEY = "model_waiting"

NOTICES = {
    LimitReason.DAILY_CEILING: (PAUSED_KEY, "daily_ceiling"),
    LimitReason.MESSAGE_CEILING: (PAUSED_KEY, "message_ceiling"),
    LimitReason.BREAKER_OPEN: (WAITING_KEY, "breaker_open"),
    LimitReason.PROVIDER_UNAVAILABLE: (WAITING_KEY, "provider_unavailable"),
}

SPENT = frozenset({LimitReason.DAILY_CEILING, LimitReason.MESSAGE_CEILING})


def is_spent(reason: LimitReason) -> bool:
    return reason in SPENT


def announce(services, request, scope: str, reason: LimitReason) -> None:
    message_key, trace_name = NOTICES[reason]
    if is_spent(reason):
        services.telemetry.trace(
            TRACE_KIND, trace_name, status=TRIPPED, family_id=scope, event_kind=request.kind.value
        )
    family = services.store.get_family(scope)
    chat = family.chat_ref if family else request.payload.get("chat_ref")
    if not chat:
        return
    notice = OutboundMessage(
        channel=family.channel if family else ChannelKind.TELEGRAM,
        chat_ref=str(chat),
        text=msg(message_key, family.lang if family else Lang.ES),
    )
    deliver(services, [notice], f"{trace_name}#{services.clock.today()}", scope)
