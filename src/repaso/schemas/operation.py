from datetime import datetime
from typing import Any

from repaso.schemas.common import StrictBaseModel


class OperationRecord(StrictBaseModel):
    scope: str
    key: str
    payload: dict[str, Any]


class AdaptationState(StrictBaseModel):
    student_id: str
    competency_id: str
    action: str
    difficulty: int | None = None
    force_open: bool = False
    item_limit: int | None = None
    expires_at: datetime
    source: str
