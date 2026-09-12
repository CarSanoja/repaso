from dataclasses import dataclass
from datetime import datetime

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.item_draft import (
    GeneratedBatch,
    ItemDraft,
    is_valid_draft,
    item_id_for,
    to_item,
)
from repaso.agents.prompts.item_generator import PROMPT_VERSION, SYSTEM
from repaso.schemas.common import Lang
from repaso.schemas.competency import Competency
from repaso.schemas.item import GeneratedItems, GenerationOutcome, Item

MAX_OVERPRODUCTION = 2
LANGUAGE_NAMES: dict[Lang, str] = {Lang.ES: "Spanish", Lang.EN: "English"}

__all__ = [
    "GeneratedBatch",
    "GeneratedItems",
    "Generation",
    "ItemDraft",
    "LANGUAGE_NAMES",
    "MAX_OVERPRODUCTION",
    "PROMPT_VERSION",
    "draft_report",
    "generate_items",
    "is_valid_draft",
    "item_id_for",
    "items_for_material",
]


@dataclass(frozen=True)
class Generation:
    items: list[Item]
    answered: bool


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
    return {
        "generated": len(drafts),
        "kept": len(kept),
        "dropped": len(drafts) - len(kept),
        "untagged": sum(1 for item in kept if item.bloom is None),
    }


async def _ask(
    parsed_text: str,
    competency: Competency,
    count: int,
    grade: int,
    model,
    lang: Lang,
    prompt_version: str = PROMPT_VERSION,
) -> GeneratedBatch:
    if count < 1:
        raise ValueError("count must be positive")
    return await structured(
        model,
        GeneratedBatch,
        SYSTEM.format(grade=grade),
        _request_text(parsed_text, competency, count, lang),
        prompt_version,
    )


def _kept(
    batch: GeneratedBatch,
    competency: Competency,
    count: int,
    now: datetime,
    grade: int,
    lang: Lang,
    model_id: str = "",
    prompt_version: str = PROMPT_VERSION,
) -> list[Item]:
    kept = [
        to_item(draft, competency, now, model_id, prompt_version, grade, lang)
        for draft in batch.items
        if is_valid_draft(draft)
    ]
    return kept[: count * MAX_OVERPRODUCTION]


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
) -> GeneratedItems:
    try:
        batch = await _ask(parsed_text, competency, count, grade, model, lang, prompt_version)
    except StructuredCallFailed:
        return GeneratedItems(outcome=GenerationOutcome.UNAVAILABLE)
    kept = _kept(batch, competency, count, now, grade, lang, model_id, prompt_version)
    outcome = GenerationOutcome.DRAFTED if kept else GenerationOutcome.EMPTY
    return GeneratedItems(outcome=outcome, items=kept)


async def items_for_material(
    parsed_text: str,
    competency: Competency,
    count: int,
    grade: int,
    model,
    now: datetime,
    retries: int = 0,
    lang: Lang = Lang.ES,
) -> Generation:
    if retries < 0:
        raise ValueError("retries cannot be negative")
    answered = False
    for _ in range(retries + 1):
        drafted = await generate_items(
            parsed_text, competency, count, grade, model, now, lang=lang
        )
        if drafted.outcome is GenerationOutcome.UNAVAILABLE:
            continue
        answered = True
        if drafted.items:
            return Generation(items=drafted.items, answered=True)
    return Generation(items=[], answered=answered)
