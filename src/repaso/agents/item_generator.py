from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.item_generator import PROMPT_VERSION, SYSTEM
from repaso.schemas.common import CompetencyId, ItemId, Lang
from repaso.schemas.competency import Competency
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source

MIN_OPTIONS = 3
MAX_OPTIONS = 5
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
LANGUAGE_NAMES: dict[Lang, str] = {Lang.ES: "Spanish", Lang.EN: "English"}


class ItemDraft(BaseModel):
    kind: ItemKind
    difficulty: int
    stem: str
    options: list[str] = []
    answer_key: str
    rationale: str
    rubric: str | None = None


class GeneratedBatch(BaseModel):
    items: list[ItemDraft] = []


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


def _to_item(
    draft: ItemDraft,
    competency: Competency,
    now: datetime,
    model_id: str,
    prompt_version: str,
) -> Item:
    return Item(
        id=ItemId(uuid4().hex),
        competency_id=CompetencyId(str(competency.id)),
        kind=draft.kind,
        difficulty=draft.difficulty,
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


def _request_text(parsed_text: str, competency: Competency, count: int, lang: Lang) -> str:
    return (
        f"Competency: {competency.id} — {competency.name}\n"
        f"What it means: {competency.description}\n"
        f"Write exactly {count} items for this competency.\n"
        f"Write every word the family reads — stem, options, answer_key, rationale and "
        f"rubric — in {LANGUAGE_NAMES[lang]}.\n\n"
        f"Material:\n{parsed_text}"
    )


def draft_report(drafts: list[ItemDraft], kept: list[Item]) -> dict:
    return {"generated": len(drafts), "kept": len(kept), "dropped": len(drafts) - len(kept)}


async def generate_items(
    parsed_text: str,
    competency: Competency,
    count: int,
    grade: int,
    model,
    now: datetime,
    model_id: str = "",
    prompt_version: str = PROMPT_VERSION,
    lang: Lang = Lang.ES,
) -> list[Item]:
    if count < 1:
        raise ValueError("count must be positive")
    try:
        batch = await structured(
            model,
            GeneratedBatch,
            SYSTEM.format(grade=grade),
            _request_text(parsed_text, competency, count, lang),
        )
    except StructuredCallFailed:
        return []
    return [
        _to_item(draft, competency, now, model_id, prompt_version)
        for draft in batch.items
        if is_valid_draft(draft)
    ]
