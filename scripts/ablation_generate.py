"""Generate the multiple-choice items the ablation freezes, from the project's own page."""

from datetime import datetime

from ablation_items import LABEL_SOURCE, FrozenSet, freeze

from repaso.agents.item_generator import PROMPT_VERSION, generate_items
from repaso.schemas.competency import Competency
from repaso.schemas.item import Item, ItemKind
from repaso.simulator.demo_material import NOTEBOOK_REF, NOTEBOOK_TEXT
from repaso.tools.knowledge import LocalTaxonomyRetriever

GRADE = 4
MIN_OPTIONS = 3
COMPETENCY_IDS = ("math.g4.fractions.equivalence", "math.g4.fractions.comparison")
ITEMS_PER_CALL = 10
MAX_ROUNDS = 4


def competencies() -> list[Competency]:
    retriever = LocalTaxonomyRetriever()
    found = [retriever.get_competency(identifier) for identifier in COMPETENCY_IDS]
    missing = [name for name, item in zip(COMPETENCY_IDS, found, strict=True) if item is None]
    if missing:
        raise ValueError(f"taxonomy has no competency for {missing}")
    return [item for item in found if item is not None]


def usable(item: Item) -> bool:
    return (
        item.kind is ItemKind.MCQ
        and len(item.options) >= MIN_OPTIONS
        and item.answer_key in item.options
        and len(set(item.options)) == len(item.options)
    )


async def collect_items(model, model_id: str, wanted: int, now: datetime) -> list[Item]:
    kept: dict[str, Item] = {}
    rounds = 0
    while rounds < MAX_ROUNDS and len(kept) < wanted:
        rounds += 1
        for competency in competencies():
            if len(kept) >= wanted:
                break
            drafted = await generate_items(
                NOTEBOOK_TEXT, competency, ITEMS_PER_CALL, GRADE, model, now, model_id
            )
            kept.update({str(item.id): item for item in drafted if usable(item)})
    if len(kept) < wanted:
        raise RuntimeError(f"only {len(kept)} usable items after {rounds} rounds")
    ordered = sorted(kept.values(), key=lambda item: str(item.id))
    return ordered[:wanted]


def frozen_set(items: list[Item], model_id: str, now: datetime) -> FrozenSet:
    return FrozenSet(
        frozen_on=now.date().isoformat(),
        model_id=model_id,
        prompt_version=PROMPT_VERSION,
        source_page=NOTEBOOK_REF,
        label_source=LABEL_SOURCE,
        items=freeze(items, NOTEBOOK_REF),
    )
