from datetime import datetime
from enum import StrEnum

from repaso.schemas.common import FrozenStrictModel


class Source(StrEnum):
    PARENT_UPLOAD = "parent_upload"
    GENERATED = "generated"
    SIMULATED = "simulated"
    SYSTEM = "system"


class Provenance(FrozenStrictModel):
    source: Source
    created_at: datetime
    model_id: str | None = None
    prompt_version: str | None = None
    trace_id: str | None = None
