import os
from dataclasses import dataclass

from repaso.config.models import ModelRole
from repaso.config.settings import Settings, get_settings
from repaso.core.harness.clock import SystemClock
from repaso.core.orchestration.context import Services
from repaso.core.telemetry.sink import build_telemetry_sink
from repaso.tools.event_bus import build_event_publisher
from repaso.tools.grade_log import build_grade_log
from repaso.tools.guardrails import build_screener
from repaso.tools.instrumented_model import instrument_models
from repaso.tools.invite_codes import build_invite_codes
from repaso.tools.knowledge import build_knowledge_retriever
from repaso.tools.llm import build_model
from repaso.tools.media_store import build_media_store
from repaso.tools.ocr import build_text_extractor
from repaso.tools.state_store import build_state_store
from repaso.tools.telegram import build_channel_sender

GUARDRAIL_ID_ENV = "REPASO_GUARDRAIL_ID"
KNOWLEDGE_BASE_ID_ENV = "REPASO_KNOWLEDGE_BASE_ID"
TELEGRAM_TOKEN_ENV = "REPASO_TELEGRAM_TOKEN"


@dataclass
class RuntimeSession:
    settings: Settings
    services: Services


_session: RuntimeSession | None = None


def build_runtime_services(settings: Settings) -> Services:
    clock = SystemClock()
    telemetry = build_telemetry_sink(settings, clock)
    models = instrument_models(
        {role: build_model(role, settings) for role in ModelRole}, telemetry
    )
    return Services(
        settings=settings,
        clock=clock,
        store=build_state_store(settings),
        grade_log=build_grade_log(settings),
        media=build_media_store(settings),
        extractor=build_text_extractor(settings),
        screener=build_screener(settings, guardrail_id=os.environ.get(GUARDRAIL_ID_ENV)),
        retriever=build_knowledge_retriever(settings, os.environ.get(KNOWLEDGE_BASE_ID_ENV)),
        publisher=build_event_publisher(settings),
        sender=build_channel_sender(settings, os.environ.get(TELEGRAM_TOKEN_ENV)),
        invites=build_invite_codes(settings),
        models=models,
        telemetry=telemetry,
    )


def runtime_services(settings: Settings | None = None) -> Services:
    global _session
    resolved = settings if settings is not None else get_settings()
    if _session is None or _session.settings != resolved:
        _session = RuntimeSession(settings=resolved, services=build_runtime_services(resolved))
    return _session.services


def reset_runtime_session() -> None:
    global _session
    _session = None
