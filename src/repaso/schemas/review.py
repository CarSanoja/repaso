from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from repaso.schemas.common import FamilyId, ItemId, StrictBaseModel, StudentId
from repaso.schemas.grading import EvidenceSpan


class QuarantineKind(StrEnum):
    LOW_CONFIDENCE_GRADE = "low_confidence_grade"
    INJECTION_ATTEMPT = "injection_attempt"
    UNSAFE_CONTENT = "unsafe_content"


class QuarantineStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class QuarantineItem(StrictBaseModel):
    id: str
    kind: QuarantineKind
    family_id: FamilyId
    evidence: EvidenceSpan
    payload: dict[str, Any]
    status: QuarantineStatus = QuarantineStatus.PENDING
    created_at: datetime
    resolved_at: datetime | None = None


class HeldAnswer(StrictBaseModel):
    item_id: ItemId
    student_id: StudentId
    answer: str
    latency_seconds: float = Field(default=0.0, ge=0.0)
