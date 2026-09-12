import pytest

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import IngestRun
from repaso.core.orchestration.ingest_graph import build_ingest_graph
from repaso.core.orchestration.ingest_holds import held_kind
from repaso.i18n import msg
from repaso.schemas.channel import MediaKind
from repaso.schemas.common import Lang
from repaso.schemas.review import QuarantineKind
from repaso.tools.guardrails import MARKER_REASON_PREFIX, ScreenVerdict
from tests.material_corpus import WORKSHEET_EN
from tests.orchestration.fixtures import make_material, make_services, seed_family

MARKER = ScreenVerdict(safe=False, reasons=[f"{MARKER_REASON_PREFIX}ignore your"])
GUARDRAIL = ScreenVerdict(safe=False, reasons=["contentPolicy"])
MODEL_CALLED_IT_UNSAFE = ScreenVerdict(safe=False, reasons=["graphic_violence"])
MODEL_NAMED_INJECTION = ScreenVerdict(
    safe=False, reasons=["prompt_injection", "grade_manipulation"]
)
MODEL_NAMED_IT_WITH_A_DASH = ScreenVerdict(safe=False, reasons=["prompt-injection"])


def make_run(services, text: str = WORKSHEET_EN) -> IngestRun:
    family, student = seed_family(services.store)
    material = make_material(family.id).model_copy(update={"kind": MediaKind.PDF})
    return IngestRun(
        family=family, student=student, material=material, data=text.encode("utf-8")
    )


def test_a_named_injection_is_recorded_as_one_whoever_named_it():
    assert held_kind(MARKER) is QuarantineKind.INJECTION_ATTEMPT
    assert held_kind(MODEL_NAMED_INJECTION) is QuarantineKind.INJECTION_ATTEMPT
    assert held_kind(MODEL_NAMED_IT_WITH_A_DASH) is QuarantineKind.INJECTION_ATTEMPT


def test_a_refusal_that_names_no_injection_is_recorded_as_unsafe_content():
    assert held_kind(GUARDRAIL) is QuarantineKind.UNSAFE_CONTENT
    assert held_kind(MODEL_CALLED_IT_UNSAFE) is QuarantineKind.UNSAFE_CONTENT


async def test_a_page_the_screener_model_refuses_is_not_filed_as_injection(settings):
    services = make_services(settings)
    run = make_run(services)
    services.models[ModelRole.CLASSIFY].enqueue(
        {"safe": False, "reasons": ["graphic_violence"]}
    )

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal == "quarantined"
    held = services.store.list_pending_quarantine(run.family.id)
    assert held and held[0].kind is QuarantineKind.UNSAFE_CONTENT
    assert held[0].payload["reasons"] == ["graphic_violence"]
    assert run.outbound[-1].text == msg("material_held", run.family.lang)


@pytest.mark.parametrize("lang", [Lang.ES, Lang.EN])
def test_the_held_message_never_claims_the_page_addressed_the_system(lang):
    text = msg("material_held", lang).lower()

    assert "instrucciones dirigidas" not in text
    assert "instructions aimed at" not in text
    assert "revisión de seguridad" in text or "safety check" in text


async def test_an_injection_the_marker_list_cannot_read_is_still_filed_as_one(settings):
    services = make_services(settings)
    run = make_run(services)
    services.models[ModelRole.CLASSIFY].enqueue(
        {"safe": False, "reasons": ["prompt_injection", "grade_manipulation"]}
    )

    await build_ingest_graph(services, run).invoke_async("ingest")

    held = services.store.list_pending_quarantine(run.family.id)
    assert held and held[0].kind is QuarantineKind.INJECTION_ATTEMPT
