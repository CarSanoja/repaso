"""The frozen ablation item set: what was generated and what was planted into it."""

import json
from datetime import datetime
from pathlib import Path
from random import Random

from repaso.schemas.common import CompetencyId, FrozenStrictModel, ItemId
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source

NO_DEFECT = "none"
WRONG_KEY = "wrong_key"
IMPLAUSIBLE_DISTRACTORS = "implausible_distractors"
OPTION_CUE = "option_cue"
PLANTS = (WRONG_KEY, IMPLAUSIBLE_DISTRACTORS, OPTION_CUE)
CLUE_PLANTS = (IMPLAUSIBLE_DISTRACTORS, OPTION_CUE)

PLANT_STRIDE = 5
PLANTS_PER_STRIDE = 2
LABEL_SOURCE = "construction"

CUE_SUFFIX = (
    " — la fracción equivalente que se obtiene al multiplicar el numerador y el "
    "denominador por el mismo número, como muestra la regla del cuaderno"
)
ABSURD_OPTIONS = ("un elefante", "el color azul", "el día martes", "una bicicleta")


class FrozenItem(FrozenStrictModel):
    item_id: str
    source_page: str
    competency_id: str
    difficulty: int
    stem: str
    options: list[str]
    answer_key: str
    rationale: str
    defect: str
    construction_valid: bool
    construction_option_clue: bool
    generated_options: list[str]
    generated_answer_key: str


class FrozenSet(FrozenStrictModel):
    frozen_on: str
    model_id: str
    prompt_version: str
    source_page: str
    label_source: str
    items: list[FrozenItem]


def plant_for(index: int) -> str:
    if index % PLANT_STRIDE >= PLANTS_PER_STRIDE:
        return NO_DEFECT
    ordinal = index // PLANT_STRIDE * PLANTS_PER_STRIDE + index % PLANT_STRIDE
    return PLANTS[ordinal % len(PLANTS)]


def _wrong_key(options: list[str], key: str) -> tuple[list[str], str]:
    return options, next(option for option in options if option != key)


def _implausible(options: list[str], key: str) -> tuple[list[str], str]:
    filler = iter(ABSURD_OPTIONS)
    return [option if option == key else next(filler) for option in options], key


def _option_cue(options: list[str], key: str) -> tuple[list[str], str]:
    cued = key + CUE_SUFFIX
    return [cued if option == key else option for option in options], cued


PLANTERS = {
    WRONG_KEY: _wrong_key,
    IMPLAUSIBLE_DISTRACTORS: _implausible,
    OPTION_CUE: _option_cue,
}


def plant(item: Item, defect: str, source_page: str) -> FrozenItem:
    options, key = list(item.options), item.answer_key
    if defect != NO_DEFECT:
        options, key = PLANTERS[defect](options, key)
    return FrozenItem(
        item_id=str(item.id),
        source_page=source_page,
        competency_id=str(item.competency_id),
        difficulty=item.difficulty,
        stem=item.stem,
        options=options,
        answer_key=key,
        rationale=item.rationale,
        defect=defect,
        construction_valid=defect == NO_DEFECT,
        construction_option_clue=defect in CLUE_PLANTS,
        generated_options=list(item.options),
        generated_answer_key=item.answer_key,
    )


def freeze(items: list[Item], source_page: str) -> list[FrozenItem]:
    ordered = sorted(items, key=lambda item: str(item.id))
    return [plant(item, plant_for(index), source_page) for index, item in enumerate(ordered)]


def key_planted_wrong(item: FrozenItem) -> bool:
    return item.defect == WRONG_KEY


def presented_options(item: FrozenItem, seed: int) -> list[str]:
    order = list(item.options)
    Random(f"{item.item_id}:{seed}").shuffle(order)
    return order


def as_item(item: FrozenItem, options: list[str], now: datetime, model_id: str) -> Item:
    return Item(
        id=ItemId(item.item_id),
        competency_id=CompetencyId(item.competency_id),
        kind=ItemKind.MCQ,
        difficulty=item.difficulty,
        stem=item.stem,
        options=options,
        answer_key=item.answer_key,
        rationale=item.rationale,
        status=ItemStatus.CANDIDATE,
        provenance=Provenance(source=Source.GENERATED, created_at=now, model_id=model_id),
    )


def write_frozen(path: Path, frozen: FrozenSet) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(frozen.model_dump(), ensure_ascii=False, indent=2) + "\n")


def read_frozen(path: Path) -> FrozenSet:
    return FrozenSet.model_validate_json(path.read_text(encoding="utf-8"))
