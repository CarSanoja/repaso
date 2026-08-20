from datetime import datetime, time
from enum import StrEnum

from repaso.schemas.channel import ChannelKind
from repaso.schemas.common import FamilyId, Lang, StrictBaseModel
from repaso.schemas.consent import ConsentRecord


class FamilyStatus(StrEnum):
    ENROLLING = "enrolling"
    ACTIVE = "active"
    PAUSED = "paused"
    FORGOTTEN = "forgotten"


class Family(StrictBaseModel):
    id: FamilyId
    channel: ChannelKind
    chat_ref: str
    lang: Lang = Lang.ES
    timezone: str = "America/Caracas"
    practice_time: time = time(hour=19)
    status: FamilyStatus = FamilyStatus.ENROLLING
    invite_code: str
    consent: ConsentRecord | None = None
    created_at: datetime
