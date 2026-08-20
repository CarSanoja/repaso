from typing import Any

from repaso.channel.telegram.parser import parse_update, update_id_of
from repaso.core.harness.idempotency import update_key
from repaso.schemas.channel import InboundMessage
from repaso.tools.state_store import StateStore

OWNER = "telegram-webhook"


def accept_update(update: dict[str, Any], store: StateStore) -> InboundMessage | None:
    message = parse_update(update)
    if message is None:
        return None
    update_id = update_id_of(update)
    if update_id is None:
        return message
    if not store.claim(update_key(message.chat_ref, update_id), OWNER):
        return None
    return message
