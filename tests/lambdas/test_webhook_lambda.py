import json
from time import perf_counter

import pytest

from repaso.lambdas import bootstrap, webhook
from repaso.schemas.events import EventKind
from tests.lambdas.conftest import (
    SECRET_HEADER,
    TELEGRAM_SECRET,
    make_request,
    make_update,
    signed_request,
)

ACK = {"ok": True}
LATENCY_BUDGET_SECONDS = 0.2


@pytest.fixture(autouse=True)
def mangum_loop(event_loop_for_mangum):
    return event_loop_for_mangum


def body_of(response: dict) -> dict:
    return json.loads(response["body"])


def test_webhook_acks_a_signed_update_and_publishes_one_event(secured_env):
    response = webhook.handler(signed_request(), None)
    assert response["statusCode"] == 200
    assert body_of(response) == ACK
    assert len(secured_env.publisher.published) == 1
    published = secured_env.publisher.published[0]
    assert published.kind is EventKind.CHANNEL_MESSAGE
    assert published.idempotency_key == "12345#10"


def test_webhook_does_not_run_the_graphs_inline(secured_env):
    webhook.handler(signed_request(), None)
    assert secured_env.sender.sent == []


def test_webhook_acks_a_duplicate_update_without_publishing_twice(secured_env):
    request = signed_request(make_update(update_id=42))
    first = webhook.handler(request, None)
    second = webhook.handler(request, None)
    assert body_of(first) == ACK
    assert body_of(second) == {"ok": True, "duplicate": True}
    assert len(secured_env.publisher.published) == 1


def test_webhook_answers_a_warm_update_inside_the_ack_budget(secured_env):
    webhook.handler(signed_request(make_update(update_id=1)), None)
    started = perf_counter()
    webhook.handler(signed_request(make_update(update_id=2)), None)
    assert perf_counter() - started < LATENCY_BUDGET_SECONDS


def test_webhook_rejects_a_wrong_secret_with_a_client_error(secured_env):
    response = webhook.handler(
        make_request(json.dumps(make_update()), {SECRET_HEADER: "nope"}), None
    )
    assert response["statusCode"] == 401
    assert secured_env.publisher.published == []


def test_webhook_never_returns_5xx_when_the_secret_is_not_configured(lambda_env):
    response = webhook.handler(signed_request(), None)
    assert response["statusCode"] == 200
    assert body_of(response) == ACK
    assert bootstrap.container().publisher.published == []


def test_webhook_acks_a_body_that_is_not_json(secured_env):
    response = webhook.handler(make_request("{not json", {SECRET_HEADER: TELEGRAM_SECRET}), None)
    assert response["statusCode"] == 200
    assert body_of(response) == {"ok": True, "error": "logged"}
    assert secured_env.publisher.published == []


def test_webhook_acks_an_event_that_no_adapter_can_read(secured_env):
    response = webhook.handler({}, None)
    assert response["statusCode"] == 200
    assert body_of(response) == ACK


def test_webhook_acks_when_the_adapter_raises(secured_env, monkeypatch):
    def explode(event, context):
        raise RuntimeError("cold start failed")

    monkeypatch.setattr(webhook, "_ADAPTER", explode)
    response = webhook.handler(signed_request(), None)
    assert response["statusCode"] == 200
    assert body_of(response) == ACK


def test_webhook_downgrades_a_server_error_to_an_ack(secured_env, monkeypatch):
    monkeypatch.setattr(webhook, "_ADAPTER", lambda event, context: {"statusCode": 502})
    response = webhook.handler(signed_request(), None)
    assert response["statusCode"] == 200
    assert body_of(response) == ACK


def test_webhook_downgrades_a_response_that_is_not_a_lambda_payload(secured_env, monkeypatch):
    monkeypatch.setattr(webhook, "_ADAPTER", lambda event, context: "surprise")
    assert webhook.handler(signed_request(), None)["statusCode"] == 200


def test_webhook_downgrades_an_unreadable_status(secured_env, monkeypatch):
    monkeypatch.setattr(webhook, "_ADAPTER", lambda event, context: {"statusCode": "nope"})
    assert webhook.handler(signed_request(), None)["statusCode"] == 200


def test_webhook_builds_its_adapter_once_per_container(secured_env):
    webhook.reset_adapter()
    first = webhook.adapter()
    assert webhook.adapter() is first
