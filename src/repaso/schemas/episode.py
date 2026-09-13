from datetime import datetime

from repaso.schemas.common import (
    CompetencyId,
    FrozenStrictModel,
    ItemId,
    SessionId,
    StudentId,
)
from repaso.schemas.grading import GradedBy


class AttemptEpisode(FrozenStrictModel):
    student_id: StudentId
    session_id: SessionId
    competency_id: CompetencyId
    item_id: ItemId
    correct: bool | None
    held: bool
    graded_by: GradedBy
    latency_seconds: float | None = None
    occurred_at: datetime
