from datetime import UTC, datetime

from repaso.schemas.common import Lang
from repaso.schemas.item import BloomLevel, Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source

NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
FRACTIONS = "math.g4.fractions.equivalence"
DECIMALS = "math.g4.decimals.tenths"


def make_item(item_id: str, **overrides) -> Item:
    payload = {
        "id": item_id,
        "competency_id": FRACTIONS,
        "kind": ItemKind.MCQ,
        "difficulty": 2,
        "bloom": BloomLevel.APPLY,
        "lang": Lang.ES,
        "grade": 4,
        "stem": f"¿Cuál fracción equivale a 1/2? ({item_id})",
        "options": ["2/4", "1/3", "3/5"],
        "answer_key": "2/4",
        "rationale": "multiplicas arriba y abajo por dos",
        "status": ItemStatus.ACTIVE,
        "provenance": Provenance(source=Source.GENERATED, created_at=NOW),
    }
    payload.update(overrides)
    return Item(**payload)
