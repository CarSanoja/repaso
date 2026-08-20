from repaso.channel.telegram.dedupe import accept_update
from repaso.channel.telegram.parser import parse_update, update_id_of
from repaso.schemas.channel import MediaKind
from repaso.tools.state_store import build_state_store

CHAT = {"id": 12345, "type": "private"}


def text_update(update_id: int = 1, text: str = "hola") -> dict:
    return {
        "update_id": update_id,
        "message": {"message_id": 10, "chat": CHAT, "date": 1756750000, "text": text},
    }


def test_text_message_parses():
    message = parse_update(text_update())
    assert message.chat_ref == "12345"
    assert message.text == "hola"
    assert message.media is None
    assert message.received_at.year == 2025 or message.received_at.year == 2026


def test_photo_picks_largest_size():
    update = {
        "update_id": 2,
        "message": {
            "message_id": 11,
            "chat": CHAT,
            "date": 1756750000,
            "caption": "cuaderno",
            "photo": [
                {"file_id": "small", "width": 90},
                {"file_id": "big", "width": 1280},
            ],
        },
    }
    message = parse_update(update)
    assert message.media.kind is MediaKind.PHOTO
    assert message.media.media_ref == "big"
    assert message.text == "cuaderno"


def test_pdf_and_voice_documents():
    pdf = {
        "update_id": 3,
        "message": {
            "message_id": 12,
            "chat": CHAT,
            "date": 1756750000,
            "document": {"file_id": "doc1", "mime_type": "application/pdf"},
        },
    }
    voice = {
        "update_id": 4,
        "message": {
            "message_id": 13,
            "chat": CHAT,
            "date": 1756750000,
            "voice": {"file_id": "v1"},
        },
    }
    assert parse_update(pdf).media.kind is MediaKind.PDF
    assert parse_update(voice).media.kind is MediaKind.VOICE


def test_callback_query_parses():
    update = {
        "update_id": 5,
        "callback_query": {
            "id": "cb99",
            "data": "ans:s1:i1:2",
            "message": {"message_id": 14, "chat": CHAT, "date": 1756750000},
        },
    }
    message = parse_update(update)
    assert message.callback_data == "ans:s1:i1:2"
    assert message.message_ref == "cb99"


def test_unsupported_updates_return_none():
    assert parse_update({"update_id": 6}) is None
    assert parse_update({"update_id": 7, "message": {"message_id": 1, "chat": CHAT}}) is None
    assert update_id_of({"update_id": "bad"}) is None


def test_duplicate_update_is_accepted_once(settings):
    store = build_state_store(settings)
    update = text_update(update_id=42)
    first = accept_update(update, store)
    second = accept_update(update, store)
    assert first is not None
    assert second is None


def test_distinct_updates_both_pass(settings):
    store = build_state_store(settings)
    assert accept_update(text_update(update_id=1), store) is not None
    assert accept_update(text_update(update_id=2), store) is not None
