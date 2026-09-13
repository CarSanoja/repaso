from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from repaso.schemas.common import CompetencyId, ItemId, StrictBaseModel, StudentId
from repaso.schemas.item import BloomLevel


class StudySessionStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    ABANDONED = "abandoned"


class Actor(StrEnum):
    FAMILY = "family"
    SYSTEM = "system"


class CloseReason(StrEnum):
    QUESTIONS_SPENT = "questions_spent"
    MINUTES_SPENT = "minutes_spent"
    DAY_SPENT = "day_spent"
    ENOUGH_FOR_TODAY = "enough_for_today"
    BANK_EMPTY = "bank_empty"
    FAMILY_CLOSED = "family_closed"
    STOPPED_FOR_CARE = "stopped_for_care"
    EXPIRED = "expired"


class StudyGoal(StrictBaseModel):
    competency_id: CompetencyId | None = None
    bloom: BloomLevel | None = None
    label: str = ""


class StudyBudget(StrictBaseModel):
    questions: int = Field(ge=0, le=20)
    minutes: int = Field(ge=1, le=60)


class StudyProgress(StrictBaseModel):
    served: list[ItemId] = []
    answered_keys: list[str] = []
    correct: int = Field(default=0, ge=0)
    wrong: int = Field(default=0, ge=0)
    consecutive_wrong: int = Field(default=0, ge=0)


class StudySession(StrictBaseModel):
    id: str
    family_id: str
    student_id: StudentId
    opened_by: Actor
    opened_at: datetime
    opened_on: date
    last_event_at: datetime
    goal: StudyGoal = StudyGoal()
    budget: StudyBudget
    progress: StudyProgress = StudyProgress()
    status: StudySessionStatus = StudySessionStatus.PROPOSED
    closed_reason: CloseReason | None = None
