import pytest

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import IngestRun
from repaso.core.orchestration.ingest_graph import build_ingest_graph
from repaso.i18n import msg
from repaso.schemas.common import Lang
from repaso.schemas.material import MaterialStatus
from tests.agents.stress_models import STRESSES, stressed
from tests.orchestration.fixtures import (
    FRACTIONS,
    make_material,
    make_services,
    mcq_draft,
    seed_family,
)
from tests.orchestration.test_ingest_graph import FRACTION_TEXT

BLAMED = {
    "material_rejected": {"subject": "matemática"},
    "material_thin": {},
    "rephoto_request": {},
}


def make_run(services) -> IngestRun:
    family, student = seed_family(services.store)
    return IngestRun(
        family=family, student=student, material=make_material(family.id), data=FRACTION_TEXT
    )


@pytest.mark.parametrize("kind", STRESSES)
async def test_a_failed_screener_call_is_not_blamed_on_the_photograph(settings, kind):
    services = make_services(settings)
    services.models[ModelRole.CLASSIFY] = stressed(kind, {"safe": "quizás"})
    run = make_run(services)

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal == "screener_unavailable"
    assert run.outbound[-1].text == msg("material_screen_unavailable", run.family.lang)
    assert all(
        run.outbound[-1].text != msg(key, run.family.lang, **kwargs)
        for key, kwargs in BLAMED.items()
    )
    assert services.store.list_pending_quarantine(run.family.id) == []
    assert services.store.get_material(run.material.id).status is not MaterialStatus.QUARANTINED


@pytest.mark.parametrize("kind", STRESSES)
async def test_a_failed_generator_call_is_not_blamed_on_the_photograph(settings, kind):
    services = make_services(settings)
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED].enqueue({"competency_ids": [FRACTIONS]})
    services.models[ModelRole.GENERATE] = stressed(kind, {"items": "cuatro preguntas"})
    run = make_run(services)

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal == "generator_unavailable"
    assert run.outbound[-1].text == msg("material_generation_unavailable", run.family.lang)
    assert all(
        run.outbound[-1].text != msg(key, run.family.lang, **kwargs)
        for key, kwargs in BLAMED.items()
    )


async def test_a_page_the_model_answered_about_but_wrote_nothing_for_still_asks_for_more(settings):
    services = make_services(settings)
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED].enqueue({"competency_ids": [FRACTIONS]})
    for _ in range(settings.item_regen_max_rounds + 1):
        services.models[ModelRole.GENERATE].enqueue(
            {"items": [mcq_draft("Which fraction equals 2/4?", "1/2", ["1/2", "1/2"])]}
        )
    run = make_run(services)

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal == "thin_material"
    assert run.outbound[-1].text == msg("material_thin", run.family.lang)


def test_neither_outage_message_asks_for_another_photograph():
    asked = {Lang.ES: ("otra foto", "tomarla de nuevo"), Lang.EN: ("another photo", "retake")}
    for lang, phrases in asked.items():
        for key in ("material_screen_unavailable", "material_generation_unavailable"):
            text = msg(key, lang).lower()
            assert all(phrase not in text for phrase in phrases), (lang, key)
