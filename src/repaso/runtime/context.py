import os
from dataclasses import dataclass

from repaso.config.models import ModelRole
from repaso.config.settings import Settings, get_settings
from repaso.core.harness.clock import SystemClock
from repaso.core.orchestration.context import Services
from repaso.core.telemetry.sink import build_telemetry_sink
from repaso.tools.call_ledger import build_call_ledger
from repaso.tools.call_quota import build_call_quota
from repaso.tools.event_bus import build_event_publisher
from repaso.tools.grade_log import build_grade_log
from repaso.tools.guardrails import build_screener
from repaso.tools.instrumented_model import instrument_models
from repaso.tools.invite_codes import build_invite_codes
from repaso.tools.knowledge import build_knowledge_retriever
from repaso.tools.llm import build_model
from repaso.tools.media_fetcher import build_media_fetcher
from repaso.tools.media_store import build_media_store
from repaso.tools.model_limits import ModelLimits
from repaso.tools.ocr import build_text_extractor
from repaso.tools.state_store import build_state_store
from repaso.tools.telegram import build_channel_sender

KNOWLEDGE_BASE_ID_ENV = "REPASO_KNOWLEDGE_BASE_ID"
TELEGRAM_TOKEN_ENV = "REPASO_TELEGRAM_TOKEN"


@dataclass
class RuntimeSession:
    settings: Settings
    services: Services


_session: RuntimeSession | None = None


def build_runtime_services(settings: Settings) -> Services:
    token = os.environ.get(TELEGRAM_TOKEN_ENV)
    if not settings.local_mode and not token:
        from repaso.lambdas.bootstrap import BOT_TOKEN_FIELD, _resolve

        token = _resolve(TELEGRAM_TOKEN_ENV, settings.telegram_secret_name, BOT_TOKEN_FIELD)
    clock = SystemClock()
    telemetry = build_telemetry_sink(settings, clock)
    store = build_state_store(settings)
    models = instrument_models(
        {role: build_model(role, settings) for role in ModelRole},
        telemetry,
        ModelLimits(settings, store, clock, build_call_quota(settings)),
        build_call_ledger(settings),
        clock,
    )
    return Services(
        settings=settings,
        clock=clock,
        store=store,
        grade_log=build_grade_log(settings, clock),
        media=build_media_store(settings),
        fetcher=build_media_fetcher(settings, token, telemetry),
        extractor=build_text_extractor(settings),
        screener=build_screener(settings),
        retriever=build_knowledge_retriever(settings, os.environ.get(KNOWLEDGE_BASE_ID_ENV)),
        publisher=build_event_publisher(settings),
        sender=build_channel_sender(settings, token),
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
