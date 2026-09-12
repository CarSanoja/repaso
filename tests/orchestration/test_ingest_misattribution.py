import pytest

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import IngestRun
from repaso.core.orchestration.ingest_graph import build_ingest_graph
from repaso.i18n import msg
from repaso.schemas.channel import MediaKind
from repaso.schemas.common import Lang
from tests.material_corpus import WORKSHEET_EN
from tests.orchestration.fixtures import make_material, make_services, seed_family

FRACTIONS = "math.g4.fractions.equivalence"


class BrokenModel:
    def __init__(self):
        self.calls: list[str] = []

    def structured_output(self, output_model, prompt, system_prompt=None):
        self.calls.append(output_model.__name__)

        async def failing():
            raise RuntimeError("bedrock throttled")
            yield {}

        return failing()


def make_run(services, text: str = WORKSHEET_EN) -> IngestRun:
    family, student = seed_family(services.store)
    material = make_material(family.id).model_copy(update={"kind": MediaKind.PDF})
    return IngestRun(
        family=family, student=student, material=material, data=text.encode("utf-8")
    )


async def test_a_failed_mapper_call_does_not_call_the_page_off_subject(settings):
    services = make_services(settings)
    run = make_run(services)
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED] = BrokenModel()

    await build_ingest_graph(services, run).invoke_async("ingest")

    assert run.terminal == "mapping_unavailable"
    assert run.matches == []
    assert run.outbound[-1].text == msg("material_interrupted", run.family.lang)
    assert services.models[ModelRole.GENERATE].calls == []


async def test_a_failed_mapper_call_is_not_remembered_as_a_refusal(settings):
    services = make_services(settings)
    run = make_run(services)
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED] = BrokenModel()
    await build_ingest_graph(services, run).invoke_async("ingest")

    retry = IngestRun(
        family=run.family,
        student=run.student,
        material=run.material,
        data=WORKSHEET_EN.encode("utf-8"),
    )
    services.models[ModelRole.STRUCTURED] = make_services(settings).models[ModelRole.STRUCTURED]
    services.models[ModelRole.STRUCTURED].enqueue({"competency_ids": [FRACTIONS]})
    services.models[ModelRole.GENERATE] = BrokenModel()

    await build_ingest_graph(services, retry).invoke_async("ingest")

    assert [str(key) for key in retry.matches] == [FRACTIONS]


@pytest.mark.parametrize("lang", [Lang.ES, Lang.EN])
def test_the_interrupted_message_blames_no_photograph(lang):
    text = msg("material_interrupted", lang).lower()
    assert "no parece" not in text
    assert "doesn't look like" not in text
    assert "foto" in text or "photo" in text
