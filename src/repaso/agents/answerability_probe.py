from pydantic import BaseModel

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.answerability_probe import SYSTEM
from repaso.schemas.item import Item, ItemFlaw, ItemKind, ItemVerdict

NUMBER_NOISE = "().:-# "


class ProbeAnswer(BaseModel):
    answer: str


def _normalize(text: str) -> str:
    return text.strip().casefold()


def _resolve(item: Item, value: str) -> str:
    cleaned = value.strip().strip(NUMBER_NOISE)
    if cleaned.isdigit():
        number = int(cleaned)
        if 1 <= number <= len(item.options):
            return _normalize(item.options[number - 1])
    return _normalize(value)


def render_blind(item: Item) -> str:
    options = "\n".join(
        f"{number}. {option}" for number, option in enumerate(item.options, start=1)
    )
    return f"Question:\n{item.stem}\n\nOptions:\n{options}"


async def probe_blind(item: Item, model) -> bool | None:
    if item.kind is not ItemKind.MCQ:
        return None
    try:
        reply = await structured(model, ProbeAnswer, SYSTEM, render_blind(item))
    except StructuredCallFailed:
        return None
    if not reply.answer.strip():
        return False
    return _resolve(item, reply.answer) == _resolve(item, item.answer_key)


def combine(verdict: ItemVerdict, answered_blind: bool | None) -> ItemVerdict:
    flaws = list(verdict.flaws)
    if answered_blind is True and ItemFlaw.ANSWERABLE_WITHOUT_MATERIAL not in flaws:
        flaws.append(ItemFlaw.ANSWERABLE_WITHOUT_MATERIAL)
    return verdict.model_copy(
        update={
            "accepted": verdict.accepted and answered_blind is not True,
            "flaws": flaws,
            "probe_answered_blind": answered_blind,
        }
    )


def rejection_rate(verdicts: list[ItemVerdict]) -> float:
    if not verdicts:
        return 0.0
    rejected = sum(1 for verdict in verdicts if not verdict.accepted)
    return rejected / len(verdicts)
