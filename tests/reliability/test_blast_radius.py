from repaso.agents.item_generator import MAX_OVERPRODUCTION
from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.orchestration.ingest_graph import ITEMS_PER_MATERIAL
from repaso.schemas.channel import InboundMedia, MediaKind
from repaso.tools.call_quota import build_call_quota
from repaso.tools.instrumented_model import instrument_models
from repaso.tools.model_limits import ModelLimits
from tests.orchestration.fixtures import accepted_verdict, make_services, mcq_draft, seed_family
from tests.runtime.fixtures import (
    FAMILY_CHAT,
    FRACTION_TEXT,
    INVITE_CODE,
    inbound,
    send,
)

MEDIA_REF = "inbox/tg-file-1"
CEILING = 6
FLOOD = 60


def bounded_pilot(settings: Settings, ceiling: int = CEILING):
    services = make_services(
        Settings(
            local_mode=True,
            local_data_dir=settings.local_data_dir,
            pilot_invite_codes=INVITE_CODE,
            message_llm_budget_calls=ceiling,
        )
    )
    limits = ModelLimits(
        services.settings, services.store, services.clock, build_call_quota(services.settings)
    )
    inner = dict(services.models)
    services.models = instrument_models(inner, services.telemetry, limits)
    return services, inner


def script_flood(services, drafts: int = FLOOD) -> None:
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED].enqueue(
        {"competency_ids": ["math.g4.fractions.equivalence"]}
    )
    services.models[ModelRole.GENERATE].enqueue(
        {
            "items": [
                mcq_draft(f"¿Cuál equivale a {n}/8?", "1/2", ["2/8", "3/4"])
                for n in range(drafts)
            ]
        }
    )
    for _ in range(drafts * 2):
        services.models[ModelRole.JUDGE].enqueue(accepted_verdict())
        services.models[ModelRole.PROBE].enqueue({"answer": "no idea"})


def calls(inner) -> int:
    return sum(len(model.calls) for model in inner.values())


def photograph(services):
    services.media.put(MEDIA_REF, FRACTION_TEXT, "application/octet-stream")
    media = InboundMedia(kind=MediaKind.PDF, media_ref=MEDIA_REF)
    return send(services, inbound(media=media, chat_ref=FAMILY_CHAT))


def test_one_photograph_cannot_fan_out_past_its_ceiling(settings):
    services, inner = bounded_pilot(settings)
    seed_family(services.store)
    script_flood(services)

    photograph(services)

    assert calls(inner) == CEILING


def test_a_flood_of_drafts_is_cut_before_anything_judges_them(settings):
    services, inner = bounded_pilot(settings, ceiling=99)
    seed_family(services.store)
    script_flood(services)

    response = photograph(services)
    validated = ITEMS_PER_MATERIAL * MAX_OVERPRODUCTION

    assert response["ok"] is True
    assert len(response["result"]["ingest"]["kept_item_ids"]) == validated
    assert calls(inner) == 3 + 2 * validated


def test_an_ordinary_photograph_is_never_touched_by_the_ceiling(settings):
    services, inner = bounded_pilot(settings, ceiling=24)
    seed_family(services.store)
    script_flood(services, drafts=2)

    response = photograph(services)

    assert response["ok"] is True
    assert len(response["result"]["ingest"]["kept_item_ids"]) == 2
    assert calls(inner) == 7
