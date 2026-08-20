from datetime import datetime

from pydantic import Field

from repaso.schemas.common import FamilyId, FrozenStrictModel


class TelemetryEvent(FrozenStrictModel):
    name: str
    family_id: FamilyId | None = None
    value: float = 1.0
    at: datetime


class CostRecord(FrozenStrictModel):
    model_id: str
    role: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    usd: float = Field(ge=0.0)
    at: datetime
