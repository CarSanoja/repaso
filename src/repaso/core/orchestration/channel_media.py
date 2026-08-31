from repaso.core.orchestration.context import ChannelRun, Route, Services
from repaso.core.orchestration.runner import handle_material
from repaso.i18n import msg
from repaso.schemas.channel import InboundMedia, InboundMessage, OutboundMessage
from repaso.schemas.family import Family
from repaso.schemas.student import Student

MEDIA_UNREADABLE_KEY = "media_unreadable"
MEDIA_TRACE_NAME = "media_unavailable"


async def route_material(services: Services, run: ChannelRun, family: Family) -> None:
    media = run.message.media
    student = _first_student(services, family)
    if student is None or media is None:
        run.route = Route.NO_STUDENT
        return
    data = _media_bytes(services, media)
    if data is None:
        run.route = Route.MEDIA_UNAVAILABLE
        services.telemetry.trace("channel", MEDIA_TRACE_NAME, status="failed", family_id=family.id)
        run.outbound.append(_unreadable_media(run.message, family))
        return
    run.student = student
    run.route = Route.MATERIAL
    run.ingest = await handle_material(services, family, student, media.kind, data)


def _media_bytes(services: Services, media: InboundMedia) -> bytes | None:
    try:
        if services.media.exists(media.media_ref):
            return services.media.get(media.media_ref)
        fetched = services.fetcher.fetch(media.media_ref, media.kind)
        if fetched is None:
            return None
        services.media.put(media.media_ref, fetched.data, fetched.content_type)
        return fetched.data
    except ValueError:
        return None


def _unreadable_media(message: InboundMessage, family: Family) -> OutboundMessage:
    return OutboundMessage(
        channel=message.channel,
        chat_ref=message.chat_ref,
        text=msg(MEDIA_UNREADABLE_KEY, family.lang),
    )


def _first_student(services: Services, family: Family) -> Student | None:
    students = services.store.list_students(family.id)
    return students[0] if students else None
