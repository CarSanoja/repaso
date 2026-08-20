from datetime import datetime
from enum import StrEnum
from typing import Any

from repaso.schemas.common import FamilyId, FrozenStrictModel


class EventKind(StrEnum):
    MATERIAL_UPLOADED = "material_uploaded"
    CHANNEL_MESSAGE = "channel_message"
    DAILY_SESSION_DUE = "daily_session_due"
    RESPONSE_RECEIVED = "response_received"
    ESCALATION_RESOLVED = "escalation_resolved"
    DAILY_CLOSE = "daily_close"


class DomainEvent(FrozenStrictModel):
    kind: EventKind
    family_id: FamilyId | None
    idempotency_key: str
    occurred_at: datetime
    payload: dict[str, Any]
