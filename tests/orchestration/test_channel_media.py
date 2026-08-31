from datetime import UTC, datetime

from repaso.core.harness.clock import SimClock
from repaso.core.orchestration.channel_runner import handle_channel_message
from repaso.core.orchestration.context import Route, Services
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.i18n import msg
from repaso.schemas.channel import ChannelKind, InboundMedia, InboundMessage, MediaKind
from repaso.schemas.common import Lang
from repaso.schemas.family import Family
from repaso.tools.media_fetcher import FetchedMedia
from tests.orchestration.fixtures import make_services, seed_family
from tests.runtime.fixtures import FAMILY_CHAT, FRACTION_TEXT, script_ingest

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
FILE_ID = "AgACAgEAAxkBAAIBY2ZmZg"


class SpyFetcher:
    def __init__(self, fetched: FetchedMedia | None) -> None:
        self._fetched = fetched
        self.calls: list[tuple[str, MediaKind]] = []

    def fetch(self, ref: str, kind: MediaKind) -> FetchedMedia | None:
        self.calls.append((ref, kind))
        return self._fetched


def fetched(data: bytes = FRACTION_TEXT, content_type: str = "image/jpeg") -> FetchedMedia:
    return FetchedMedia(data=data, content_type=content_type, size=len(data))


def upload(kind: MediaKind = MediaKind.PHOTO, ref: str = FILE_ID) -> InboundMessage:
    return InboundMessage(
        channel=ChannelKind.TELEGRAM,
        chat_ref=FAMILY_CHAT,
        message_ref="1",
        media=InboundMedia(kind=kind, media_ref=ref),
        received_at=START,
    )


def with_fetcher(settings, spy: SpyFetcher) -> Services:
    services = make_services(settings)
    services.fetcher = spy
    return services


async def test_a_photo_only_telegram_holds_now_reaches_the_ingest_graph(settings):
    spy = SpyFetcher(fetched())
    services = with_fetcher(settings, spy)
    seed_family(services.store)
    script_ingest(services)

    run = await handle_channel_message(services, upload())

    assert run.route is Route.MATERIAL
    assert run.ingest is not None
    assert spy.calls == [(FILE_ID, MediaKind.PHOTO)]


async def test_a_document_that_had_to_be_downloaded_still_produces_items(settings):
    spy = SpyFetcher(fetched(content_type="application/pdf"))
    services = with_fetcher(settings, spy)
    seed_family(services.store)
    script_ingest(services)

    run = await handle_channel_message(services, upload(MediaKind.PDF))

    assert run.route is Route.MATERIAL
    assert run.ingest is not None
    assert len(run.ingest.kept) == 2


async def test_the_downloaded_bytes_are_kept_so_a_redelivery_never_downloads_twice(settings):
    spy = SpyFetcher(fetched(content_type="application/pdf"))
    services = with_fetcher(settings, spy)
    seed_family(services.store)
    script_ingest(services)

    first = await handle_channel_message(services, upload(MediaKind.PDF))
    script_ingest(services)
    second = await handle_channel_message(services, upload(MediaKind.PDF))

    assert (first.route, second.route) == (Route.MATERIAL, Route.MATERIAL)
    assert len(spy.calls) == 1
    assert services.media.get(FILE_ID) == FRACTION_TEXT
    assert services.media.content_type(FILE_ID) == "application/pdf"


async def test_bytes_already_in_the_store_are_never_fetched_again(settings):
    spy = SpyFetcher(fetched())
    services = with_fetcher(settings, spy)
    seed_family(services.store)
    services.media.put(FILE_ID, FRACTION_TEXT, "application/pdf")
    script_ingest(services)

    run = await handle_channel_message(services, upload(MediaKind.PDF))

    assert run.route is Route.MATERIAL
    assert spy.calls == []


async def test_a_file_that_cannot_be_fetched_asks_the_parent_to_send_it_again(settings):
    spy = SpyFetcher(None)
    services = with_fetcher(settings, spy)
    services.telemetry = LocalTelemetrySink(settings.local_data_dir / "t.jsonl", SimClock(START))
    family, _ = seed_family(services.store)

    run = await handle_channel_message(services, upload())

    assert run.route is Route.MEDIA_UNAVAILABLE
    assert run.ingest is None
    assert [message.text for message in run.outbound] == [msg("media_unreadable", family.lang)]
    assert [event.name for event in services.telemetry.events] == ["media_unavailable"]
    assert services.sender.sent[0]["text"] == msg("media_unreadable", Lang.ES)


async def test_a_reference_that_would_escape_the_store_is_refused_without_raising(settings):
    spy = SpyFetcher(fetched())
    services = with_fetcher(settings, spy)
    seed_family(services.store)

    run = await handle_channel_message(services, upload(ref="../../escape"))

    assert run.route is Route.MEDIA_UNAVAILABLE
    assert spy.calls == []
    assert run.outbound


async def test_an_upload_from_a_family_with_no_student_never_fetches(settings):
    spy = SpyFetcher(fetched())
    services = with_fetcher(settings, spy)
    services.store.put_family(
        Family(
            id="f2",
            channel=ChannelKind.TELEGRAM,
            chat_ref=FAMILY_CHAT,
            lang=Lang.ES,
            invite_code="PILOT1",
            created_at=START,
        )
    )

    run = await handle_channel_message(services, upload())

    assert run.route is Route.NO_STUDENT
    assert spy.calls == []
