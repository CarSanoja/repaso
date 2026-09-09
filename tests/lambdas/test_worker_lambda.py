import json
import logging

from repaso.lambdas import bootstrap, worker
from repaso.schemas.common import FamilyId
from repaso.schemas.events import DomainEvent, EventKind
from tests.lambdas.conftest import (
    NOW,
    envelope,
    make_batch,
    make_domain_event,
    make_record,
)

NO_FAILURES: dict[str, list[dict[str, str]]] = {"batchItemFailures": []}


def failures_of(response: dict) -> list[str]:
    return [entry["itemIdentifier"] for entry in response["batchItemFailures"]]


def test_worker_reports_no_failures_for_a_clean_batch(lambda_env, runtime):
    batch = make_batch(
        make_record(make_domain_event(idempotency_key="12345#10"), message_id="m1"),
        make_record(make_domain_event(idempotency_key="12345#11"), message_id="m2"),
    )
    assert worker.handler(batch, None) == NO_FAILURES
    assert runtime.keys == ["12345#10", "12345#11"]


def test_worker_reports_only_the_record_the_runtime_rejected(lambda_env, runtime):
    runtime.rejecting.add("12345#11")
    batch = make_batch(
        make_record(make_domain_event(idempotency_key="12345#10"), message_id="m1"),
        make_record(make_domain_event(idempotency_key="12345#11"), message_id="m2"),
        make_record(make_domain_event(idempotency_key="12345#12"), message_id="m3"),
    )
    assert failures_of(worker.handler(batch, None)) == ["m2"]
    assert runtime.keys == ["12345#10", "12345#11", "12345#12"]


def test_worker_does_not_redeliver_work_a_spent_ceiling_refused(lambda_env, runtime, caplog):
    runtime.spent.add("12345#11")
    batch = make_batch(
        make_record(make_domain_event(idempotency_key="12345#10"), message_id="m1"),
        make_record(make_domain_event(idempotency_key="12345#11"), message_id="m2"),
    )

    with caplog.at_level(logging.ERROR):
        assert worker.handler(batch, None) == NO_FAILURES

    assert "spend_ceiling_reached" in caplog.text


def test_worker_reports_a_body_that_is_not_json(lambda_env, runtime):
    batch = make_batch(
        make_record(body="{not json", message_id="m1"),
        make_record(make_domain_event(idempotency_key="12345#11"), message_id="m2"),
    )
    assert failures_of(worker.handler(batch, None)) == ["m1"]
    assert runtime.keys == ["12345#11"]


def test_worker_reports_a_detail_that_is_not_a_domain_event(lambda_env, runtime):
    body = json.dumps({"detail-type": "channel_message", "detail": {"kind": "nonsense"}})
    assert failures_of(worker.handler(make_batch(make_record(body=body)), None)) == ["m1"]
    assert runtime.calls == []


def test_worker_reports_a_record_that_is_not_an_object(lambda_env, runtime):
    assert worker.handler(make_batch("garbage"), None) == NO_FAILURES
    assert runtime.calls == []


def test_worker_accepts_a_bare_domain_event_body(lambda_env, runtime):
    event = make_domain_event(idempotency_key="12345#77")
    record = make_record(body=event.model_dump_json())
    assert worker.handler(make_batch(record), None) == NO_FAILURES
    assert runtime.keys == ["12345#77"]


def test_worker_reports_a_record_whose_dispatch_raised(lambda_env, runtime):
    runtime.raising.add("12345#11")
    batch = make_batch(
        make_record(make_domain_event(idempotency_key="12345#10"), message_id="m1"),
        make_record(make_domain_event(idempotency_key="12345#11"), message_id="m2"),
    )
    assert failures_of(worker.handler(batch, None)) == ["m2"]


def test_worker_reports_a_result_it_cannot_read(lambda_env, monkeypatch):
    monkeypatch.setattr(worker, "_dispatch", lambda event: "not a result")
    assert failures_of(worker.handler(make_batch(make_record()), None)) == ["m1"]


def test_worker_retries_a_redelivered_record_past_its_own_claim(lambda_env, runtime):
    runtime.rejecting.add("12345#10")
    event = make_domain_event(idempotency_key="12345#10")
    first = worker.handler(make_batch(make_record(event, receive_count=1)), None)
    runtime.rejecting.clear()
    second = worker.handler(make_batch(make_record(event, receive_count=2)), None)
    assert failures_of(first) == ["m1"]
    assert second == NO_FAILURES
    assert runtime.keys == ["12345#10", "12345#10"]


def test_worker_delegates_repeat_delivery_to_durable_runtime(lambda_env, runtime):
    record = make_record(make_domain_event(idempotency_key="12345#10"))
    worker.handler(make_batch(record), None)
    assert worker.handler(make_batch(record), None) == NO_FAILURES
    assert runtime.keys == ["12345#10", "12345#10"]


def test_worker_delegates_batch_duplicates_to_durable_runtime(lambda_env, runtime):
    event = make_domain_event(idempotency_key="12345#10")
    batch = make_batch(make_record(event, message_id="m1"), make_record(event, message_id="m2"))
    assert worker.handler(batch, None) == NO_FAILURES
    assert runtime.keys == ["12345#10", "12345#10"]


def test_worker_does_not_burn_claims_before_the_runtime_commits(lambda_env, runtime):
    published_key = "job#daily_session#f1#2026-09-01"
    event = make_domain_event(kind=EventKind.DAILY_SESSION_DUE, idempotency_key=published_key)
    worker.handler(make_batch(make_record(event)), None)
    assert bootstrap.store().claim(published_key, "scheduler-tick") is True
    assert bootstrap.store().claim(worker.worker_key(event), "sqs-worker") is True


def test_worker_separates_the_same_key_across_event_kinds(lambda_env, runtime):
    channel = make_domain_event(idempotency_key="12345#10")
    response = make_domain_event(kind=EventKind.RESPONSE_RECEIVED, idempotency_key="12345#10")
    batch = make_batch(
        make_record(channel, message_id="m1"), make_record(response, message_id="m2")
    )
    assert worker.handler(batch, None) == NO_FAILURES
    assert [call["kind"] for call in runtime.calls] == ["channel_message", "response_received"]


def test_worker_hands_the_real_runtime_a_payload_it_can_parse(lambda_env, caplog):
    from repaso.runtime.context import reset_runtime_session

    event = DomainEvent(
        kind=EventKind.DAILY_SESSION_DUE,
        family_id=FamilyId("ghost"),
        idempotency_key="job#daily_session#ghost#2026-09-01",
        occurred_at=NOW,
        payload={"student_id": "ghost"},
    )
    reset_runtime_session()
    try:
        with caplog.at_level(logging.ERROR, logger="repaso.lambdas.worker"):
            response = worker.handler(make_batch(make_record(event)), None)
    finally:
        reset_runtime_session()
    assert failures_of(response) == ["m1"]
    assert "not_found" in caplog.text


def test_worker_hands_the_runtime_the_serialised_event(lambda_env, runtime):
    event = make_domain_event(idempotency_key="12345#10")
    worker.handler(make_batch(make_record(event)), None)
    assert runtime.calls == [json.loads(event.model_dump_json())]


def test_worker_accepts_an_empty_batch(lambda_env, runtime):
    assert worker.handler(make_batch(), None) == NO_FAILURES
    assert worker.handler({}, None) == NO_FAILURES
    assert worker.handler("not an event", None) == NO_FAILURES
    assert runtime.calls == []


def test_worker_cannot_report_a_record_without_a_message_id(lambda_env, runtime):
    record = {"body": "{not json"}
    assert worker.handler(make_batch(record), None) == NO_FAILURES
    assert runtime.calls == []


def test_worker_reads_the_eventbridge_envelope_it_is_wired_to(lambda_env, runtime):
    event = make_domain_event(idempotency_key="12345#10")
    assert json.loads(envelope(event))["detail"]["idempotency_key"] == "12345#10"
    worker.handler(make_batch(make_record(body=envelope(event))), None)
    assert runtime.keys == ["12345#10"]
