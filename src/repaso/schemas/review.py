from datetime import datetime
from enum import StrEnum
from typing import Any

from repaso.schemas.common import FamilyId, StrictBaseModel
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
