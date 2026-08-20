from datetime import UTC, datetime
from enum import StrEnum
from typing import NewType

from pydantic import BaseModel, ConfigDict

FamilyId = NewType("FamilyId", str)
StudentId = NewType("StudentId", str)
CompetencyId = NewType("CompetencyId", str)
ItemId = NewType("ItemId", str)
MaterialId = NewType("MaterialId", str)
SessionId = NewType("SessionId", str)
EscalationId = NewType("EscalationId", str)
JobId = NewType("JobId", str)


class Lang(StrEnum):
    EN = "en"
    ES = "es"


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FrozenStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def utc_now() -> datetime:
    return datetime.now(UTC)
