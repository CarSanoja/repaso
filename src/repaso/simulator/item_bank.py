from datetime import datetime

from repaso.schemas.competency import Competency
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source
from repaso.simulator.archetypes import MISCONCEPTIONS

MCQ_SLOTS = ("m0", "m2", "m3", "m5", "m6")
OPEN_SLOTS = ("m1", "m4")


def _provenance(now: datetime) -> Provenance:
    return Provenance(source=Source.SIMULATED, created_at=now)


def _mcq(competency: Competency, slot: str, index: int, now: datetime) -> Item:
    correct = f"respuesta correcta de {competency.name} #{index}"
    misconception = MISCONCEPTIONS.get(
        competency.id, f"error común de {competency.name} #{index}"
    )
    return Item(
        id=f"sim-{competency.id}-{slot}",
        competency_id=competency.id,
        kind=ItemKind.MCQ,
        difficulty=min(5, 1 + index),
        stem=f"Práctica {index + 1} de {competency.name}: elige la opción correcta.",
        options=[correct, misconception, f"otra opción {index}"],
        answer_key=correct,
        rationale=competency.description,
        status=ItemStatus.ACTIVE,
        provenance=_provenance(now),
    )


def _open(competency: Competency, slot: str, now: datetime) -> Item:
    return Item(
        id=f"sim-{competency.id}-{slot}",
        competency_id=competency.id,
        kind=ItemKind.OPEN,
        difficulty=3,
        stem=f"Explica con tus palabras: {competency.description}",
        options=[],
        answer_key=f"respuesta abierta esperada de {competency.name}",
        rationale=competency.description,
        rubric="2 puntos por explicar la idea central con un ejemplo correcto",
        status=ItemStatus.ACTIVE,
        provenance=_provenance(now),
    )


def build_item_bank(competencies: list[Competency], now: datetime) -> list[Item]:
    items: list[Item] = []
    for competency in competencies:
        items.extend(
            _mcq(competency, slot, index, now) for index, slot in enumerate(MCQ_SLOTS)
        )
        items.extend(_open(competency, slot, now) for slot in OPEN_SLOTS)
    return items
