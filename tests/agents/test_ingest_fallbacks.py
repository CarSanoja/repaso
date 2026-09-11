from datetime import UTC, datetime

import pytest

from repaso.agents.answerability_probe import probe_blind
from repaso.agents.competency_mapper import map_material
from repaso.agents.intake_screener import screen_text
from repaso.agents.item_critic import CRITIC_ERROR_NOTE, critique
from repaso.agents.item_generator import generate_items
from repaso.schemas.common import CompetencyId, ItemId
from repaso.schemas.competency import Competency
from repaso.schemas.item import Item, ItemFlaw, ItemKind
from repaso.schemas.provenance import Provenance, Source
from repaso.tools.guardrails import SCREENER_ERROR_REASON, LocalScreener
from repaso.tools.knowledge import LocalTaxonomyRetriever
from tests.agents.stress_models import MalformedModel, throttled_model, timed_out_model

NOW = datetime(2026, 9, 12, 19, 0, tzinfo=UTC)
MATERIAL = (
    "Cuaderno de 4to grado: fracciones equivalentes. equivalent fractions such as 2/4 "
    "and 1/2, and comparing fractions with a common denominator."
)
COMPETENCY = Competency(
    id=CompetencyId("math.g4.fractions.equivalence"),
    subject="math",
    grade=4,
    name="Fracciones equivalentes",
    description="Reconocer y producir fracciones equivalentes.",
)
ITEM = Item(
    id=ItemId("it-1"),
    competency_id=COMPETENCY.id,
    kind=ItemKind.MCQ,
    difficulty=2,
    stem="¿Cuál fracción equivale a 1/2?",
    options=["2/4", "1/3", "3/5"],
    answer_key="2/4",
    rationale="Multiplicar numerador y denominador por dos.",
    provenance=Provenance(source=Source.GENERATED, created_at=NOW),
)


def stressed(kind: str, payload: dict):
    if kind == "throttled":
        return throttled_model()
    if kind == "timed_out":
        return timed_out_model()
    return MalformedModel(payload)


STRESSES = ("throttled", "timed_out", "malformed")


@pytest.mark.parametrize("kind", STRESSES)
async def test_the_screener_refuses_material_it_could_not_screen(kind):
    model = stressed(kind, {"safe": "quizás"})
    verdict = await screen_text(MATERIAL, LocalScreener(), model)
    assert model.calls == 1
    assert verdict.safe is False
    assert verdict.reasons == [SCREENER_ERROR_REASON]


@pytest.mark.parametrize("kind", STRESSES)
async def test_the_mapper_falls_back_to_retrieval_ranking(kind):
    model = stressed(kind, {"competency_ids": "math.g4.fractions.equivalence"})
    matches = await map_material(MATERIAL, 4, "math", LocalTaxonomyRetriever(), model)
    assert model.calls == 1
    assert matches
    assert all(match.confidence > 0.0 for match in matches)


@pytest.mark.parametrize("kind", STRESSES)
async def test_the_generator_returns_no_items_rather_than_broken_ones(kind):
    model = stressed(kind, {"items": "cuatro preguntas"})
    items = await generate_items(MATERIAL, COMPETENCY, 4, 4, model, NOW)
    assert model.calls == 1
    assert items == []


@pytest.mark.parametrize("kind", STRESSES)
async def test_the_critic_rejects_an_item_it_could_not_review(kind):
    model = stressed(kind, {"accepted": "con reservas"})
    verdict = await critique(ITEM, MATERIAL, 4, model)
    assert model.calls == 1
    assert verdict.accepted is False
    assert verdict.flaws == [ItemFlaw.UNGRADABLE]
    assert verdict.notes == CRITIC_ERROR_NOTE


@pytest.mark.parametrize("kind", STRESSES)
async def test_the_probe_reports_no_finding_rather_than_a_guess(kind):
    model = stressed(kind, {})
    assert await probe_blind(ITEM, model) is None
    assert model.calls == 1
