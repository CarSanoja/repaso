from hashlib import sha256

from repaso.core.orchestration.context import ChannelRun, Route, Services
from repaso.core.orchestration.runner import handle_material
from repaso.i18n import msg
from repaso.schemas.channel import InboundMedia, InboundMessage, MediaKind, OutboundMessage
from repaso.schemas.family import Family
from repaso.schemas.student import Student

MEDIA_UNREADABLE_KEY = "media_unreadable"
TRACE_KIND = "channel"
MEDIA_TRACE_NAME = "media_unavailable"
MEDIA_ERROR_TRACE_NAME = "media_error"
ERROR_DETAIL_LIMIT = 300


async def route_material(services: Services, run: ChannelRun, family: Family) -> None:
    media = run.message.media
    student = _first_student(services, family)
    if student is None or media is None:
        run.route = Route.NO_STUDENT
        return
    if media.kind is MediaKind.VOICE:
        run.route = Route.MEDIA_UNAVAILABLE
        run.outbound.append(
            OutboundMessage(
                channel=family.channel,
                chat_ref=family.chat_ref,
                text=msg("supported_material", family.lang),
            )
        )
        return
    material_id = sha256(f"{family.id}:{run.message.message_ref}".encode()).hexdigest()[:32]
    cache_ref = f"media/{family.id}/{material_id}"
    data = _media_bytes(services, media, cache_ref)
    if data is None:
        run.route = Route.MEDIA_UNAVAILABLE
        services.telemetry.trace(TRACE_KIND, MEDIA_TRACE_NAME, status="failed", family_id=family.id)
        run.outbound.append(_unreadable_media(run.message, family))
        return
    run.student = student
    run.route = Route.MATERIAL
    run.ingest = await handle_material(services, family, student, media.kind, data, material_id)


def _media_bytes(services: Services, media: InboundMedia, cache_ref: str) -> bytes | None:
    try:
        if services.media.exists(cache_ref):
            return services.media.get(cache_ref)
        if services.settings.local_mode and services.media.exists(media.media_ref):
            return services.media.get(media.media_ref)
        fetched = services.fetcher.fetch(media.media_ref, media.kind)
        if fetched is None:
            return None
        services.media.put(cache_ref, fetched.data, fetched.content_type)
        return fetched.data
    except Exception as error:
        services.telemetry.trace(
            TRACE_KIND,
            MEDIA_ERROR_TRACE_NAME,
            status="failed",
            error=f"{type(error).__name__}: {error}"[:ERROR_DETAIL_LIMIT],
        )
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
