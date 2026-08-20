from datetime import date

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel


class DailyCloseReport(FrozenStrictModel):
    close_date: date
    sessions_planned: int = Field(ge=0)
    sessions_delivered: int = Field(ge=0)
    responses_graded: int = Field(ge=0)
    quarantines_open: int = Field(ge=0)
    escalations_fired: int = Field(ge=0)
    rework_attempts: int = Field(ge=0)
    pending_human: list[str] = []
    unresolved: list[str] = []
