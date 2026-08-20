from datetime import date, datetime
from enum import StrEnum

from repaso.schemas.common import ItemId, SessionId, StrictBaseModel, StudentId


class SessionStatus(StrEnum):
    PLANNED = "planned"
    DELIVERED = "delivered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"


class Capsule(StrictBaseModel):
    concept_snippet: str
    item_ids: list[ItemId]
    audio_ref: str | None = None


class PracticeSession(StrictBaseModel):
    id: SessionId
    student_id: StudentId
    session_date: date
    capsule: Capsule | None = None
    status: SessionStatus = SessionStatus.PLANNED
    current_item_index: int = 0
    delivered_at: datetime | None = None
    completed_at: datetime | None = None
