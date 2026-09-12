from enum import StrEnum

from pydantic import Field

from repaso.schemas.common import CompetencyId, FrozenStrictModel


class MappingOutcome(StrEnum):
    MAPPED = "mapped"
    UNMATCHED = "unmatched"
    UNDETERMINED = "undetermined"


class Competency(FrozenStrictModel):
    id: CompetencyId
    subject: str
    grade: int = Field(ge=1, le=12)
    name: str
    description: str


class CompetencyMatch(FrozenStrictModel):
    competency_id: CompetencyId
    confidence: float = Field(ge=0.0, le=1.0)


class MaterialMapping(FrozenStrictModel):
    outcome: MappingOutcome
    competency_ids: list[CompetencyId] = []
