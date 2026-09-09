from botocore.exceptions import ClientError

from repaso.config.models import ModelRole
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.i18n import msg
from repaso.runtime.ceilings import NOTICES
from repaso.runtime.ceilings import SPENT as SPENT_REASONS
from repaso.runtime.errors import ErrorCode
from repaso.schemas.channel import InboundMedia, MediaKind
from repaso.schemas.common import Lang
from repaso.tools.llm import LocalPlaybackModel
from repaso.tools.model_limits import LimitReason
from tests.orchestration.fixtures import accepted_verdict, mcq_draft, seed_family
from tests.runtime.fixtures import (
    FAMILY_CHAT,
    FRACTION_TEXT,
    bounded_pilot,
    inbound,
    send,
)

MEDIA_REF = "inbox/tg-file-1"
CEILING_CODE = ErrorCode.SPEND_CEILING_REACHED.value


class Throttled(LocalPlaybackModel):
    async def structured_output(self, *args, **kwargs):
        raise ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "quota"}}, "Converse"
        )
        yield


def script(services, drafts: int = 2) -> None:
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED].enqueue(
        {"competency_ids": ["math.g4.fractions.equivalence"]}
    )
    services.models[ModelRole.GENERATE].enqueue(
        {"items": [mcq_draft(f"¿Cuánto es {n}/8?", "1/2", ["2/8", "3/4"]) for n in range(drafts)]}
    )
    for _ in range(drafts):
        services.models[ModelRole.JUDGE].enqueue(accepted_verdict())
        services.models[ModelRole.PROBE].enqueue({"answer": "no idea"})


def spent_pilot(settings, lang: Lang = Lang.ES, **limits):
    services, inner = bounded_pilot(settings, **limits)
    services.telemetry = LocalTelemetrySink(
        settings.local_data_dir / "traces.jsonl", services.clock
    )
    family, _ = seed_family(services.store)
    services.store.put_family(family.model_copy(update={"lang": lang}))
    script(services)
    return services, inner


def photograph(services, message_ref: str = "photo-1"):
    services.media.put(MEDIA_REF, FRACTION_TEXT, "application/octet-stream")
    media = InboundMedia(kind=MediaKind.PDF, media_ref=MEDIA_REF)
    return send(
        services, inbound(media=media, chat_ref=FAMILY_CHAT, message_ref=message_ref)
    )


def sent_texts(services) -> list[str]:
    return [record["text"] for record in services.sender.sent]


def traces(services) -> list[str]:
    return [f"{event.kind}.{event.name}.{event.status}" for event in services.telemetry.events]


def test_every_way_a_call_can_be_refused_has_something_to_say():
    assert set(NOTICES) == set(LimitReason)
    assert SPENT_REASONS < set(LimitReason)


def test_a_spent_day_tells_the_family_the_practice_is_paused(settings):
    services, _ = spent_pilot(settings, daily_llm_budget_calls=1)

    photograph(services)

    assert sent_texts(services) == [msg("practice_paused_today", Lang.ES)]


def test_the_pause_is_written_in_the_language_the_family_chose(settings):
    services, _ = spent_pilot(settings, Lang.EN, daily_llm_budget_calls=1)

    photograph(services)

    assert sent_texts(services) == [msg("practice_paused_today", Lang.EN)]


def test_a_spent_ceiling_raises_its_own_signal_for_a_person(settings):
    services, _ = spent_pilot(settings, daily_llm_budget_calls=1)

    photograph(services)

    assert "spend.daily_ceiling.tripped" in traces(services)


def test_a_message_that_spends_its_own_allowance_is_named_separately(settings):
    services, _ = spent_pilot(settings, message_llm_budget_calls=1)

    photograph(services)

    assert "spend.message_ceiling.tripped" in traces(services)


def test_a_spent_ceiling_is_not_reported_to_the_channel_as_a_crash(settings):
    services, _ = spent_pilot(settings, daily_llm_budget_calls=1)

    response = photograph(services)

    assert response["ok"] is False
    assert response["error"]["code"] == CEILING_CODE


def test_the_family_hears_about_the_pause_once_not_once_per_event(settings):
    services, _ = spent_pilot(settings, daily_llm_budget_calls=1)

    photograph(services, "photo-1")
    script(services)
    photograph(services, "photo-2")

    assert sent_texts(services) == [msg("practice_paused_today", Lang.ES)]


def test_a_provider_outage_still_promises_the_pending_work_is_kept(settings):
    services, inner = spent_pilot(settings, daily_llm_budget_calls=40)
    inner[ModelRole.CLASSIFY].structured_output = Throttled().structured_output

    response = photograph(services)

    assert response["error"]["code"] == ErrorCode.HANDLER_FAILED.value
    assert sent_texts(services) == [msg("model_waiting", Lang.ES)]
    assert "spend.daily_ceiling.tripped" not in traces(services)
