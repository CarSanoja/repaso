from repaso.i18n import msg
from repaso.schemas.channel import InboundMedia, MediaKind
from repaso.schemas.common import Lang
from repaso.tools.media_fetcher import INBOX_DIRNAME
from tests.orchestration.fixtures import seed_family
from tests.runtime.fixtures import (
    FAMILY_CHAT,
    FRACTION_TEXT,
    inbound,
    pilot,
    route_of,
    script_ingest,
    send,
    texts,
)

MEDIA_REF = "inbox/tg-file-1"
FILE_ID = "AgACAgEAAxkBAAIB"


def test_a_document_from_an_enrolled_family_becomes_material(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    services.media.put(MEDIA_REF, FRACTION_TEXT, "application/octet-stream")
    script_ingest(services)

    media = InboundMedia(kind=MediaKind.PDF, media_ref=MEDIA_REF)
    response = send(services, inbound(media=media, chat_ref=FAMILY_CHAT))

    assert route_of(response) == "material"
    assert response["result"]["student_id"] == student.id
    ingest = response["result"]["ingest"]
    assert len(ingest["kept_item_ids"]) == 2
    assert ingest["outbound"][0]["chat_ref"] == family.chat_ref


def test_an_unreadable_photo_still_reaches_ingest_and_answers_the_parent(settings):
    services = pilot(settings)
    seed_family(services.store)
    services.media.put(MEDIA_REF, FRACTION_TEXT, "application/octet-stream")

    media = InboundMedia(kind=MediaKind.PHOTO, media_ref=MEDIA_REF)
    response = send(services, inbound(media=media, chat_ref=FAMILY_CHAT))

    assert route_of(response) == "material"
    ingest = response["result"]["ingest"]
    assert ingest["terminal"] == "unreadable_image"
    assert ingest["kept_item_ids"] == []
    assert ingest["outbound"]


def test_a_photo_whose_bytes_never_landed_is_reported_not_crashed(settings):
    services = pilot(settings)
    seed_family(services.store)

    media = InboundMedia(kind=MediaKind.PHOTO, media_ref="inbox/never-fetched")
    response = send(services, inbound(media=media, chat_ref=FAMILY_CHAT))

    assert route_of(response) == "media_unavailable"
    assert response["result"]["ingest"] is None
    assert texts(response) == [msg("media_unreadable", Lang.ES)]


def test_a_reference_the_fetcher_can_still_resolve_becomes_material(settings):
    services = pilot(settings)
    seed_family(services.store)
    inbox = settings.local_data_dir / INBOX_DIRNAME
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / FILE_ID).write_bytes(FRACTION_TEXT)
    script_ingest(services)

    media = InboundMedia(kind=MediaKind.PDF, media_ref=FILE_ID)
    response = send(services, inbound(media=media, chat_ref=FAMILY_CHAT))

    assert route_of(response) == "material"
    assert len(response["result"]["ingest"]["kept_item_ids"]) == 2
    assert services.media.get(FILE_ID) == FRACTION_TEXT
