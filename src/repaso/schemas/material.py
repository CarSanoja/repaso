from enum import StrEnum

from pydantic import Field

from repaso.schemas.channel import MediaKind
from repaso.schemas.common import FamilyId, MaterialId, StrictBaseModel
from repaso.schemas.provenance import Provenance


class MaterialStatus(StrEnum):
    RECEIVED = "received"
    SCREENED = "screened"
    QUARANTINED = "quarantined"
    ILLEGIBLE = "illegible"
    PARSED = "parsed"
    MAPPED = "mapped"
    REJECTED = "rejected"


class Material(StrictBaseModel):
    id: MaterialId
    family_id: FamilyId
    kind: MediaKind
    media_ref: str
    status: MaterialStatus = MaterialStatus.RECEIVED
    parsed_text: str | None = None
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    legibility_score: float | None = Field(default=None, ge=0.0)
    effective_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rejection_reason: str | None = None
    provenance: Provenance
