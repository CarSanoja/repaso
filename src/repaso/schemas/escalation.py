from datetime import datetime
from enum import StrEnum

from repaso.schemas.common import EscalationId, FamilyId, StrictBaseModel, StudentId
from repaso.schemas.grading import EvidenceSpan


class EscalationKind(StrEnum):
    STRUGGLE_TRIAGE = "struggle_triage"
    ENGAGEMENT = "engagement"
    COHORT_SIGNAL = "cohort_signal"
    REPHOTO_REQUEST = "rephoto_request"
    MATERIAL_REQUEST = "material_request"
    QUARANTINE_APPROVAL = "quarantine_approval"


class EscalationStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class EscalationOption(StrictBaseModel):
    key: str
    label: str
    tradeoff: str


class Escalation(StrictBaseModel):
    id: EscalationId
    kind: EscalationKind
    family_id: FamilyId
    student_id: StudentId | None = None
    summary: str
    evidence: list[EvidenceSpan] = []
    options: list[EscalationOption] = []
    drafted_note: str | None = None
    status: EscalationStatus = EscalationStatus.PENDING
    chosen_option: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
