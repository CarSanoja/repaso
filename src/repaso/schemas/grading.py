from datetime import datetime
from enum import StrEnum

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel, ItemId, StrictBaseModel, StudentId


class GradedBy(StrEnum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


class EvidenceSpan(FrozenStrictModel):
    quote: str
    source_ref: str


class StudentResponse(FrozenStrictModel):
    student_id: StudentId
    item_id: ItemId
    text: str
    latency_seconds: float = Field(ge=0.0)
    received_at: datetime


class GradeResult(StrictBaseModel):
    student_id: StudentId
    item_id: ItemId
    correct: bool | None
    rubric_points: float | None = Field(default=None, ge=0.0, le=2.0)
    confidence: float = Field(ge=0.0, le=1.0)
    graded_by: GradedBy
    evidence: EvidenceSpan
    feedback: str
    quarantined: bool = False
    graded_at: datetime
