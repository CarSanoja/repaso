from datetime import UTC, datetime

import pytest

from repaso.agents.item_generator import ItemDraft
from repaso.schemas.common import CompetencyId
from repaso.schemas.competency import Competency
from repaso.schemas.item import ItemKind
from repaso.tools.knowledge import LocalTaxonomyRetriever

EQUIVALENCE = "math.g4.fractions.equivalence"
NOW = datetime(2026, 3, 2, 19, 0, tzinfo=UTC)
LATER = datetime(2026, 3, 9, 19, 0, tzinfo=UTC)
MATERIAL = (
    "Cuaderno de 4to grado: fracciones equivalentes. equivalent fractions such as 2/4 "
    "and 1/2, and comparing fractions with a common denominator."
)


@pytest.fixture
def competency() -> Competency:
    return LocalTaxonomyRetriever().get_competency(CompetencyId(EQUIVALENCE))


def mcq_draft(**overrides) -> ItemDraft:
    payload = {
        "kind": ItemKind.MCQ,
        "difficulty": 2,
        "stem": "¿Cuál fracción es equivalente a 1/2?",
        "options": ["2/4", "1/3", "3/5"],
        "answer_key": "2/4",
        "rationale": "Multiplicas arriba y abajo por 2 y llegas a 2/4.",
    }
    return ItemDraft(**{**payload, **overrides})


def open_draft(**overrides) -> ItemDraft:
    payload = {
        "kind": ItemKind.OPEN,
        "difficulty": 3,
        "stem": "Explica por qué 3/6 y 1/2 valen lo mismo.",
        "answer_key": "Porque 3/6 se simplifica dividiendo entre 3.",
        "rationale": "Dividir numerador y denominador entre 3 deja 1/2.",
        "rubric": "2 puntos si nombra la simplificación, 1 si solo dice que son iguales, 0 si no.",
    }
    return ItemDraft(**{**payload, **overrides})
