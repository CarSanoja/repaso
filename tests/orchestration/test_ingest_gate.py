import pytest

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import IngestRun
from repaso.core.orchestration.ingest_graph import build_ingest_graph
from repaso.i18n import msg
from repaso.schemas.channel import MediaKind
from repaso.schemas.common import Lang
from tests.material_corpus_gate import BLANK_PAGE, GATE_CORPUS, NOT_SCHOOLWORK, WRONG_GRADE
from tests.orchestration.fixtures import make_material, make_services, seed_family

REACHES_THE_MODEL = sorted(set(GATE_CORPUS) - {"blank_page"})


def make_run(services, text: str) -> IngestRun:
    family, student = seed_family(services.store)
    material = make_material(family.id).model_copy(update={"kind": MediaKind.PDF})
    return IngestRun(
        family=family, student=student, material=material, data=text.encode("utf-8")
    )


@pytest.mark.parametrize("name", REACHES_THE_MODEL)
async def test_the_mapper_is_the_only_thing_that_can_refuse_these_pages(settings, name):
    services = make_services(settings)
    run = make_run(services, GATE_CORPUS[name])
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED].enqueue({"competency_ids": []})

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal == "no_match"
    assert run.matches == []
    assert len(services.models[ModelRole.STRUCTURED].calls) == 1
    assert services.models[ModelRole.GENERATE].calls == []
    assert run.outbound[-1].text == msg(
        "material_unmatched", run.family.lang, grade=run.student.grade
    )


async def test_a_blank_page_is_stopped_before_any_model_is_called(settings):
    services = make_services(settings)
    run = make_run(services, BLANK_PAGE)

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal == "empty_text"
    assert all(model.calls == [] for model in services.models.values())
    assert run.outbound[-1].text == msg("material_unreadable", run.family.lang)


@pytest.mark.parametrize("name", sorted(NOT_SCHOOLWORK) + sorted(WRONG_GRADE))
async def test_a_refusal_never_tells_a_parent_the_page_is_not_maths(settings, name):
    services = make_services(settings)
    run = make_run(services, GATE_CORPUS[name])
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED].enqueue({"competency_ids": []})

    await build_ingest_graph(services, run).invoke_async("ingest")

    refusal = run.outbound[-1].text.lower()
    assert "no parece de" not in refusal
    assert "ubicar esta página" in refusal


@pytest.mark.parametrize("lang", [Lang.ES, Lang.EN])
def test_the_unmatched_message_offers_three_reasons_and_asserts_none(lang):
    text = msg("material_unmatched", lang, grade=4).lower()

    assert "otra materia" in text or "another subject" in text
    assert "otro grado" in text or "another grade" in text
    assert "puede ser" in text or "may be" in text
