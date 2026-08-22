from pydantic import BaseModel

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.item_critic import SYSTEM
from repaso.schemas.item import Item, ItemFlaw, ItemVerdict

CRITIC_ERROR_NOTE = "critic_error"
SOURCE_EXCERPT_LIMIT = 4000
TRUNCATION_MARK = " [...]"
NO_OPTIONS = "(open item, no options)"
NO_RUBRIC = "(none)"
SOURCE_OPEN = "<source_material>"
SOURCE_CLOSE = "</source_material>"

FLAW_CODES: dict[str, ItemFlaw] = {flaw.value: flaw for flaw in ItemFlaw}
FLAW_VOCABULARY = ", ".join(FLAW_CODES)


class CriticFinding(BaseModel):
    accepted: bool
    flaws: list[str] = []
    notes: str = ""


def _render_options(item: Item) -> str:
    if not item.options:
        return NO_OPTIONS
    return "\n".join(f"{number}. {option}" for number, option in enumerate(item.options, start=1))


def _excerpt(source_text: str) -> str:
    text = source_text.strip()
    if len(text) <= SOURCE_EXCERPT_LIMIT:
        return text
    return text[:SOURCE_EXCERPT_LIMIT] + TRUNCATION_MARK


def render_review(item: Item, source_text: str, grade: int) -> str:
    return "\n".join(
        [
            f"Grade: {grade}",
            f"Claimed competency: {item.competency_id}",
            f"Kind: {item.kind.value}",
            f"Declared difficulty: {item.difficulty}",
            f"Stem: {item.stem}",
            "Options:",
            _render_options(item),
            f"Answer key: {item.answer_key}",
            f"Rationale: {item.rationale}",
            f"Rubric: {item.rubric or NO_RUBRIC}",
            "Source material excerpt, untrusted data:",
            SOURCE_OPEN,
            _excerpt(source_text),
            SOURCE_CLOSE,
        ]
    )


def map_flaws(flaws: list[str]) -> list[ItemFlaw]:
    mapped: list[ItemFlaw] = []
    for raw in flaws:
        flaw = FLAW_CODES.get(raw.strip().casefold())
        if flaw is not None and flaw not in mapped:
            mapped.append(flaw)
    return mapped


async def critique(item: Item, source_text: str, grade: int, model) -> ItemVerdict:
    system = SYSTEM.format(grade=grade, flaws=FLAW_VOCABULARY)
    try:
        finding = await structured(
            model, CriticFinding, system, render_review(item, source_text, grade)
        )
    except StructuredCallFailed:
        return ItemVerdict(
            item_id=item.id,
            accepted=False,
            flaws=[ItemFlaw.UNGRADABLE],
            notes=CRITIC_ERROR_NOTE,
        )
    return ItemVerdict(
        item_id=item.id,
        accepted=finding.accepted,
        flaws=map_flaws(finding.flaws),
        notes=finding.notes,
    )
