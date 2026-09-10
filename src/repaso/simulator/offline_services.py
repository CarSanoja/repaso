from typing import Any

from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.harness.clock import Clock
from repaso.core.orchestration.context import Services
from repaso.core.telemetry.sink import build_telemetry_sink
from repaso.tools.call_ledger import build_call_ledger
from repaso.tools.event_bus import build_event_publisher
from repaso.tools.grade_log import build_grade_log
from repaso.tools.guardrails import build_screener
from repaso.tools.instrumented_model import instrument_models
from repaso.tools.invite_codes import build_invite_codes
from repaso.tools.knowledge import build_knowledge_retriever
from repaso.tools.media_fetcher import build_media_fetcher
from repaso.tools.media_store import build_media_store
from repaso.tools.ocr import build_text_extractor
from repaso.tools.state_store import build_state_store
from repaso.tools.telegram import build_channel_sender


def assemble_services(
    settings: Settings, clock: Clock, models: dict[ModelRole, Any]
) -> Services:
    telemetry = build_telemetry_sink(settings, clock)
    return Services(
        settings=settings,
        clock=clock,
        store=build_state_store(settings),
        grade_log=build_grade_log(settings),
        media=build_media_store(settings),
        fetcher=build_media_fetcher(settings),
        extractor=build_text_extractor(settings),
        screener=build_screener(settings),
        retriever=build_knowledge_retriever(settings),
        publisher=build_event_publisher(settings),
        sender=build_channel_sender(settings),
        invites=build_invite_codes(settings),
        models=instrument_models(
            models, telemetry, None, build_call_ledger(settings), clock
        ),
        telemetry=telemetry,
    )
