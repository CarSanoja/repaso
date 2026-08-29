import json
import os
from typing import Any

from repaso.api.dependencies import AppContainer, build_container
from repaso.config.settings import Settings, get_settings
from repaso.tools.event_bus import EventPublisher, build_event_publisher
from repaso.tools.state_store import StateStore, build_state_store

TELEGRAM_SECRET_ENV = "REPASO_TELEGRAM_SECRET"
TELEGRAM_TOKEN_ENV = "REPASO_TELEGRAM_TOKEN"
JUDGE_CODE_ENV = "REPASO_JUDGE_CODE"

WEBHOOK_SECRET_FIELD = "webhook_secret"
BOT_TOKEN_FIELD = "bot_token"
JUDGE_CODE_FIELD = "code"

_CONTAINER: AppContainer | None = None
_STORE: StateStore | None = None
_PUBLISHER: EventPublisher | None = None


def _secret_string(name: str) -> str:
    from repaso.config.clients import secrets_client

    client = secrets_client()
    if client is None or not name:
        return ""
    return str(client.get_secret_value(SecretId=name).get("SecretString") or "")


def _secret_field(name: str, field: str) -> str:
    raw = _secret_string(name)
    if not raw:
        return ""
    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(parsed, dict):
        return str(parsed.get(field, ""))
    return raw


def _resolve(env_name: str, secret_name: str, field: str) -> str:
    from_env = os.environ.get(env_name, "").strip()
    if from_env:
        return from_env
    return _secret_field(secret_name, field)


def build_lambda_container(settings: Settings | None = None) -> AppContainer:
    resolved = settings or get_settings()
    return build_container(
        resolved,
        telegram_secret=_resolve(
            TELEGRAM_SECRET_ENV, resolved.telegram_secret_name, WEBHOOK_SECRET_FIELD
        ),
        judge_code=_resolve(JUDGE_CODE_ENV, resolved.judge_code_secret_name, JUDGE_CODE_FIELD),
        telegram_token=_resolve(
            TELEGRAM_TOKEN_ENV, resolved.telegram_secret_name, BOT_TOKEN_FIELD
        )
        or None,
    )


def container() -> AppContainer:
    global _CONTAINER
    if _CONTAINER is None:
        _CONTAINER = build_lambda_container()
    return _CONTAINER


def store() -> StateStore:
    global _STORE
    if _STORE is None:
        _STORE = build_state_store(get_settings())
    return _STORE


def publisher() -> EventPublisher:
    global _PUBLISHER
    if _PUBLISHER is None:
        _PUBLISHER = build_event_publisher(get_settings())
    return _PUBLISHER


def reset() -> None:
    global _CONTAINER, _STORE, _PUBLISHER
    _CONTAINER = None
    _STORE = None
    _PUBLISHER = None
