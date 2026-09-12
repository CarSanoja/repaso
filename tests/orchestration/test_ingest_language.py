import pytest

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import IngestRun
from repaso.core.orchestration.ingest_graph import build_ingest_graph
from repaso.i18n import msg
from repaso.schemas.channel import MediaKind
from repaso.schemas.material import MaterialStatus
from tests.material_corpus import OFF_SUBJECT, PRINTED_PAGE_ES, WORKSHEET_PT
from tests.orchestration.fixtures import (
    accepted_verdict,
    make_material,
    make_services,
    mcq_draft,
    seed_family,
)

COMPARISON = "math.g4.fractions.comparison"
DECIMALS = "math.g4.decimals.tenths_hundredths"
ROMAN_NUMERALS = "math.g4.numeration.roman_numerals"


def make_run(services, text: str) -> IngestRun:
    family, student = seed_family(services.store)
    material = make_material(family.id).model_copy(update={"kind": MediaKind.PDF})
    return IngestRun(
        family=family, student=student, material=material, data=text.encode("utf-8")
    )


def enqueue_mapping(services, competency_ids: list[str]) -> None:
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED].enqueue({"competency_ids": competency_ids})


def enqueue_generation(services, count: int) -> None:
    services.models[ModelRole.GENERATE].enqueue(
        {
            "items": [
                mcq_draft(f"¿Cuál fracción equivale a {n}/8?", f"{n}/16", ["1/3", "2/5"])
                for n in range(1, count + 1)
            ]
        }
    )
    for _ in range(count):
        services.models[ModelRole.JUDGE].enqueue(accepted_verdict())
        services.models[ModelRole.PROBE].enqueue({"answer": "no idea"})


async def test_the_printed_spanish_page_maps_to_fractions_and_decimals(settings):
    services = make_services(settings)
    run = make_run(services, PRINTED_PAGE_ES)
    enqueue_mapping(services, [COMPARISON, DECIMALS])
    enqueue_generation(services, 2)

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal is None
    assert [str(key) for key in run.matches] == [COMPARISON, DECIMALS]
    assert services.store.get_material(run.material.id).status is not MaterialStatus.REJECTED
    assert run.kept


async def test_a_competency_the_hint_scores_at_zero_can_still_be_the_answer(settings):
    services = make_services(settings)
    run = make_run(services, PRINTED_PAGE_ES)
    hinted = services.retriever.retrieve(PRINTED_PAGE_ES, 4, "math", limit=24)
    assert ROMAN_NUMERALS not in {str(match.competency_id) for match in hinted}
    enqueue_mapping(services, [ROMAN_NUMERALS])
    enqueue_generation(services, 1)

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal is None
    assert [str(key) for key in run.matches] == [ROMAN_NUMERALS]


async def test_a_portuguese_worksheet_maps_against_an_english_taxonomy(settings):
    services = make_services(settings)
    run = make_run(services, WORKSHEET_PT)
    enqueue_mapping(services, [COMPARISON, DECIMALS])
    enqueue_generation(services, 2)

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal is None
    assert [str(key) for key in run.matches] == [COMPARISON, DECIMALS]


@pytest.mark.parametrize("name", sorted(OFF_SUBJECT))
async def test_off_subject_pages_in_two_languages_are_still_refused(settings, name):
    services = make_services(settings)
    run = make_run(services, OFF_SUBJECT[name])
    enqueue_mapping(services, [])

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal == "no_match"
    assert run.matches == []
    assert services.models[ModelRole.GENERATE].calls == []
    assert run.outbound[-1].text == msg(
        "material_unmatched", run.family.lang, grade=run.student.grade
    )


@pytest.mark.parametrize("name", sorted(OFF_SUBJECT))
async def test_a_refusal_never_claims_the_page_is_not_maths(settings, name):
    services = make_services(settings)
    run = make_run(services, OFF_SUBJECT[name])
    enqueue_mapping(services, [])

    await build_ingest_graph(services, run).invoke_async("ingest")

    refusal = run.outbound[-1].text.lower()
    assert "no parece de" not in refusal
    assert "ubicar esta página" in refusal
