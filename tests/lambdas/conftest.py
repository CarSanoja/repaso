import asyncio
import json
import sys
import types
from datetime import UTC, datetime
from typing import Any

import pytest

from repaso.config.settings import clear_settings_cache
from repaso.lambdas import bootstrap, webhook
from repaso.schemas.events import DomainEvent, EventKind

TELEGRAM_SECRET = "lambdasecret"
WEBHOOK_PATH = "/telegram/webhook"
SECRET_HEADER = "x-telegram-bot-api-secret-token"
RUNTIME_MODULE = "repaso.runtime.entrypoint"
CHAT_REF = "12345"
MESSAGE_REF = "10"
NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


@pytest.fixture
def lambda_env(monkeypatch, tmp_path):
    monkeypatch.setenv("REPASO_LOCAL_MODE", "true")
    monkeypatch.setenv("REPASO_LOCAL_DATA_DIR", str(tmp_path / "lambda_data"))
    clear_settings_cache()
    bootstrap.reset()
    webhook.reset_adapter()
    yield
    bootstrap.reset()
    webhook.reset_adapter()
    clear_settings_cache()


@pytest.fixture
def secured_env(lambda_env, monkeypatch):
    monkeypatch.setenv("REPASO_TELEGRAM_SECRET", TELEGRAM_SECRET)
    clear_settings_cache()
    bootstrap.reset()
    webhook.reset_adapter()
    return bootstrap.container()


@pytest.fixture
def event_loop_for_mangum():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    asyncio.set_event_loop(None)
    loop.close()


class RuntimeSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.rejecting: set[str] = set()
        self.raising: set[str] = set()

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        key = payload.get("idempotency_key")
        kind = payload.get("kind")
        if key in self.raising:
            raise RuntimeError("runtime dispatch exploded")
        if key in self.rejecting:
            return {
                "ok": False,
                "kind": kind,
                "error": {"code": "handler_failed", "message": "graph failed"},
            }
        return {"ok": True, "kind": kind, "result": {}}

    @property
    def keys(self) -> list[str]:
        return [call["idempotency_key"] for call in self.calls]


@pytest.fixture
def runtime(monkeypatch) -> RuntimeSpy:
    spy = RuntimeSpy()
    module = types.ModuleType(RUNTIME_MODULE)
    module.invoke = spy.invoke
    monkeypatch.setitem(sys.modules, RUNTIME_MODULE, module)
    return spy


def make_update(text: str = "hola", update_id: int = 1, message_id: int = 10) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "chat": {"id": int(CHAT_REF), "type": "private"},
            "date": 1756750000,
            "text": text,
        },
    }


def make_request(body: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "version": "2.0",
        "routeKey": f"POST {WEBHOOK_PATH}",
        "rawPath": WEBHOOK_PATH,
        "rawQueryString": "",
        "headers": {
            "content-type": "application/json",
            "host": "webhook.example.com",
            **(headers or {}),
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api",
            "domainName": "webhook.example.com",
            "http": {
                "method": "POST",
                "path": WEBHOOK_PATH,
                "protocol": "HTTP/1.1",
                "sourceIp": "149.154.167.220",
                "userAgent": "telegram",
            },
            "requestId": "req-1",
            "stage": "$default",
            "time": "01/Sep/2026:19:00:00 +0000",
            "timeEpoch": 1756750000000,
        },
        "body": body,
        "isBase64Encoded": False,
    }


def signed_request(update: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(update if update is not None else make_update())
    return make_request(body, {SECRET_HEADER: TELEGRAM_SECRET})


def make_domain_event(
    kind: EventKind = EventKind.CHANNEL_MESSAGE,
    idempotency_key: str = f"{CHAT_REF}#{MESSAGE_REF}",
) -> DomainEvent:
    return DomainEvent(
        kind=kind,
        family_id=None,
        idempotency_key=idempotency_key,
        occurred_at=NOW,
        payload={"text": "hola"},
    )


def envelope(event: DomainEvent) -> str:
    return json.dumps(
        {
            "version": "0",
            "id": "eb-1",
            "detail-type": event.kind.value,
            "source": "repaso",
            "time": NOW.isoformat(),
            "detail": json.loads(event.model_dump_json()),
        }
    )


def make_record(
    event: DomainEvent | None = None,
    message_id: str = "m1",
    body: str | None = None,
    receive_count: int = 1,
) -> dict[str, Any]:
    if body is None:
        body = envelope(event if event is not None else make_domain_event())
    return {
        "messageId": message_id,
        "receiptHandle": f"rh-{message_id}",
        "body": body,
        "attributes": {"ApproximateReceiveCount": str(receive_count)},
    }


def make_batch(*records: dict[str, Any]) -> dict[str, Any]:
    return {"Records": list(records)}
