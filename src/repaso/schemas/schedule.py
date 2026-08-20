from datetime import date

from pydantic import Field

from repaso.schemas.common import CompetencyId, FrozenStrictModel, ItemId, StudentId


class SpacedItemState(FrozenStrictModel):
    student_id: StudentId
    item_id: ItemId
    interval_days: int = Field(default=0, ge=0)
    ease: float = Field(default=2.5, ge=1.3)
    repetitions: int = Field(default=0, ge=0)
    lapses: int = Field(default=0, ge=0)
    due_date: date


class ExamDate(FrozenStrictModel):
    student_id: StudentId
    competency_id: CompetencyId | None
    exam_date: date
