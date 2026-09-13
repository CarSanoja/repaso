from datetime import datetime
from hashlib import sha256
from typing import Annotated

from pydantic import BaseModel, BeforeValidator

from repaso.core.harness.bloom import parse_bloom
from repaso.schemas.common import CompetencyId, ItemId, Lang
from repaso.schemas.competency import Competency
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.nullable import NULL_IS_EMPTY
from repaso.schemas.provenance import Provenance, Source

ITEM_ID_LENGTH = 32
MIN_OPTIONS = 3
MAX_OPTIONS = 5
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


AS_TEXT = BeforeValidator(_as_text)


class ItemDraft(BaseModel):
    kind: ItemKind
    difficulty: int
    bloom: Annotated[str, AS_TEXT] = ""
    stem: str
    options: Annotated[list[str], NULL_IS_EMPTY] = []
    answer_key: str
    rationale: str
    rubric: str | None = None


class GeneratedBatch(BaseModel):
    items: Annotated[list[ItemDraft], NULL_IS_EMPTY] = []


def _filled(text: str | None) -> bool:
    return bool(text and text.strip())


def _valid_mcq(draft: ItemDraft) -> bool:
    if not MIN_OPTIONS <= len(draft.options) <= MAX_OPTIONS:
        return False
    if len(set(draft.options)) != len(draft.options):
        return False
    return draft.answer_key in draft.options


def is_valid_draft(draft: ItemDraft) -> bool:
    if not MIN_DIFFICULTY <= draft.difficulty <= MAX_DIFFICULTY:
        return False
    if not (_filled(draft.stem) and _filled(draft.answer_key) and _filled(draft.rationale)):
        return False
    if draft.kind is ItemKind.MCQ:
        return _valid_mcq(draft)
    return not draft.options and _filled(draft.rubric)


def item_id_for(competency: Competency, draft: ItemDraft) -> ItemId:
    seed = "\n".join((str(competency.id), draft.kind.value, draft.stem.strip()))
    return ItemId(sha256(seed.encode("utf-8")).hexdigest()[:ITEM_ID_LENGTH])


def to_item(
    draft: ItemDraft,
    competency: Competency,
    now: datetime,
    model_id: str,
    prompt_version: str,
    grade: int,
    lang: Lang,
) -> Item:
    return Item(
        id=item_id_for(competency, draft),
        competency_id=CompetencyId(str(competency.id)),
        kind=draft.kind,
        difficulty=draft.difficulty,
        bloom=parse_bloom(draft.bloom),
        lang=lang,
        grade=grade,
        stem=draft.stem,
        options=list(draft.options),
        answer_key=draft.answer_key,
        rationale=draft.rationale,
        rubric=draft.rubric,
        status=ItemStatus.CANDIDATE,
        provenance=Provenance(
            source=Source.GENERATED,
            created_at=now,
            model_id=model_id,
            prompt_version=prompt_version,
        ),
    )
