from repaso.schemas.channel import InboundMessage
from repaso.tools.state_store import StateStore


def is_known(message: InboundMessage, store: StateStore) -> bool:
    channel = message.channel.value
    if store.find_family_by_chat(channel, message.chat_ref) is not None:
        return True
    return store.get_enrollment(channel, message.chat_ref) is not None


def valid_invite(text: str, codes: frozenset[str]) -> bool:
    candidate = text.strip().casefold()
    if not candidate:
        return False
    return candidate in {code.strip().casefold() for code in codes}


def pilot_codes(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())
