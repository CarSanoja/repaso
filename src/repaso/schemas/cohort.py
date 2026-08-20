from datetime import datetime

from pydantic import Field

from repaso.schemas.common import CompetencyId, FrozenStrictModel


class CohortKey(FrozenStrictModel):
    section_key: str
    competency_id: CompetencyId


class CohortSignal(FrozenStrictModel):
    key: CohortKey
    failing_families: int = Field(ge=0)
    total_families: int = Field(ge=0)
    window_days: int = Field(ge=1)
    note_draft: str
    fired_at: datetime
