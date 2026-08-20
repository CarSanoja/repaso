from datetime import datetime
from enum import StrEnum

from pydantic import Field

from repaso.schemas.common import CompetencyId, FrozenStrictModel, StudentId


class MasteryLevel(StrEnum):
    UNKNOWN = "unknown"
    STRUGGLING = "struggling"
    DEVELOPING = "developing"
    SOLID = "solid"
    MASTERED = "mastered"


class MasteryState(FrozenStrictModel):
    student_id: StudentId
    competency_id: CompetencyId
    ema_accuracy: float = Field(ge=0.0, le=1.0)
    attempts: int = Field(ge=0)
    correct: int = Field(ge=0)
    streak: int = 0
    level: MasteryLevel = MasteryLevel.UNKNOWN
    last_practiced_at: datetime | None = None
