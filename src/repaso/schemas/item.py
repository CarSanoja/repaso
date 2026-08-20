from enum import StrEnum

from pydantic import Field

from repaso.schemas.common import CompetencyId, ItemId, StrictBaseModel
from repaso.schemas.provenance import Provenance


class ItemKind(StrEnum):
    MCQ = "mcq"
    OPEN = "open"


class ItemStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    REJECTED = "rejected"
    RETIRED = "retired"


class ItemFlaw(StrEnum):
    AMBIGUOUS = "ambiguous"
    IMPLAUSIBLE_DISTRACTORS = "implausible_distractors"
    ANSWERABLE_WITHOUT_MATERIAL = "answerable_without_material"
    AGE_INAPPROPRIATE = "age_inappropriate"
    WRONG_COMPETENCY = "wrong_competency"
    UNGRADABLE = "ungradable"


class Item(StrictBaseModel):
    id: ItemId
    competency_id: CompetencyId
    kind: ItemKind
    difficulty: int = Field(ge=1, le=5)
    stem: str
    options: list[str] = []
    answer_key: str
    rationale: str
    rubric: str | None = None
    status: ItemStatus = ItemStatus.CANDIDATE
    provenance: Provenance


class ItemVerdict(StrictBaseModel):
    item_id: ItemId
    accepted: bool
    flaws: list[ItemFlaw] = []
    probe_answered_blind: bool | None = None
    notes: str = ""
