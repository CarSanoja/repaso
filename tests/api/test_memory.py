from datetime import UTC, datetime, timedelta
from threading import Lock
from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient

from repaso.api.memory_events import CloudEventFeed, owned_events
from repaso.api.memory_projection import opaque
from repaso.core.telemetry.context import invocation_context
from repaso.schemas.operation import OperationRecord
from repaso.schemas.telemetry import TraceEvent
from repaso.simulator.memory_rehearsal import FAMILY_ID, MemoryRehearsal
from tests.api.conftest import JUDGE_CODE, make_family, make_student

HEADERS = {"X-Judge-Code": JUDGE_CODE}
URL = "/judge/memory/snapshot/f1"


async def test_observer_cannot_read_without_a_valid_code_or_explicit_family_allowlist(
    client, container
):
    container.store.put_family(make_family())
    assert (await client.get(URL)).status_code == 403
    assert (await client.get(URL, headers={"X-Judge-Code": "wrong"})).status_code == 403
    assert (await client.get(URL.replace("f1", "unshared"), headers=HEADERS)).status_code == 404
    assert (await client.get(URL, headers=HEADERS)).status_code == 200


async def test_removed_family_is_not_shown_as_empty_live_memory(client):
    assert (await client.get(URL, headers=HEADERS)).status_code == 404


async def test_memory_projection_hides_transport_secrets_and_expired_child_words(client, container):
    container.store.put_family(make_family(chat_ref="555SECRET"))
    container.store.put_student(make_student())
    now = datetime.now(UTC)
    container.store.put_record(
        OperationRecord(
            scope="f1",
            key="turn#s#expired",
            payload={
                "expires_at": int((now - timedelta(seconds=1)).timestamp()),
                "note": {
                    "turn_id": "x",
                    "intent": "explanation",
                    "at": now.isoformat(),
                    "said": "EXPIRED WORDS",
                    "explained": "old",
                },
            },
        )
    )
    container.store.put_record(
        OperationRecord(
            scope="f1",
            key="outbox#test",
            payload={
                "messages": [{"chat_ref": "555SECRET", "text": "PRIVATE BODY"}],
                "receipts": ["PRIVATE RECEIPT"],
                "attempts": 1,
                "created_at": now.isoformat(),
            },
        )
    )
    result = await client.get(URL, headers=HEADERS)
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["notes"] == []
    assert result.json()["deliveries"][0]["status"] == "acknowledged"
    assert all(
        secret not in result.text
        for secret in ("555SECRET", "PRIVATE BODY", "PRIVATE RECEIPT", "EXPIRED WORDS", "INV-1")
    )


async def test_storage_failure_is_visible_and_does_not_leak_exception_details(client, container):
    def fail(_):
        raise RuntimeError("private database endpoint")

    container.store.get_family = fail
    result = await client.get(URL, headers=HEADERS)
    assert result.status_code == 503
    assert result.json() == {"detail": "memory_unavailable"}


async def test_log_failure_does_not_claim_the_stream_is_connected(client, container, app):
    container.store.put_family(make_family())

    class BrokenFeed:
        def read(self):
            raise RuntimeError("private log ARN")

    app.state.memory_events = BrokenFeed()
    response = await client.get(URL, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["events_status"] == "unavailable"
    assert "private log" not in response.text


def test_cloud_events_require_a_verified_correlation_and_never_expose_arbitrary_extra():
    now = datetime.now(UTC)

    def event(family, correlation, name="test"):
        return TraceEvent(
            at=now,
            kind="node",
            name=name,
            family_id=family,
            extra={
                "correlation_id": correlation,
                "chat_ref": "SECRET",
                "body": "PRIVATE",
                "model_id": "model",
            },
        )

    rows = owned_events(
        [
            event(None, "allowed"),
            event(None, "other"),
            event("f2", "allowed"),
            event("f1", "local", "local"),
            event(None, "", "global"),
        ],
        "f1",
        {"allowed"},
    )
    assert {r["name"] for r in rows} == {"test", "local"}
    assert all(set(r["extra"]) == {"correlation_id", "model_id"} for r in rows)


async def test_cloud_correlation_is_derived_from_own_operations_not_other_families(
    client, container, app
):
    container.store.put_family(make_family())
    container.store.put_record(
        OperationRecord(scope="f1", key="pending#invocation#own", payload={})
    )
    container.store.put_record(
        OperationRecord(scope="f2", key="pending#invocation#foreign", payload={})
    )

    class Feed:
        def read(self):
            return [
                TraceEvent(
                    at=datetime.now(UTC),
                    kind="node",
                    name=n,
                    extra={"correlation_id": opaque("invocation#" + n)},
                )
                for n in ["own", "foreign"]
            ]

    app.state.memory_events = Feed()
    data = (await client.get(URL, headers=HEADERS)).json()
    assert [e["name"] for e in data["events"]] == ["own"]


async def test_rehearsal_mutations_do_not_exist_on_normal_observers(client):
    result = await client.post("/judge/memory/rehearsal/help", headers=HEADERS)
    assert result.status_code == 404


@pytest.fixture
async def rehearsal_client(api_settings, container, app):
    api_settings.judge_family_ids = FAMILY_ID
    rehearsal = MemoryRehearsal(api_settings)
    await rehearsal.prepare()
    container.clock = rehearsal.clock
    app.state.memory_rehearsal = rehearsal
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        yield client, rehearsal


async def test_all_pitch_moments_change_real_state_and_repeated_steps_do_not_double_grade(
    rehearsal_client,
):
    client, rehearsal = rehearsal_client
    url = "/judge/memory/snapshot/" + FAMILY_ID

    async def snapshot():
        result = await client.get(url, headers=HEADERS)
        assert result.status_code == 200, result.text
        return result.json()

    async def step(name):
        result = await client.post("/judge/memory/rehearsal/" + name, headers=HEADERS)
        assert result.status_code == 200, result.text
        return result.json()

    first = await snapshot()
    assert first["counts"]["assessed"] == 0
    assert first["sessions"][-1]["questions"] == 3
    await step("help")
    helped = await snapshot()
    assert helped["counts"]["assessed"] == 0
    assert helped["counts"]["explanations"] == 1
    assert helped["notes"][-1]["explained"] == "bar split into quarters"
    await step("another")
    again = await snapshot()
    assert again["learning_topics"][0]["explanations"] == 2
    assert again["learning_topics"][0]["assessed"] == 0
    assert again["counts"]["assessed"] == 0
    assert {n["explained"] for n in again["notes"]} == {"bar split into quarters", "pizza halves"}
    answer = await step("answer")
    assert await step("answer") == answer
    answered = await snapshot()
    assert answered["counts"]["assessed"] == 1
    assert answered["learning_topics"][0]["assessed"] == 1
    assert answered["learning_topics"][0]["distinct_contents"] == 1
    await step("reduce")
    final = await snapshot()
    assert final["rehearsal_completed"] == ["help", "another", "answer", "reduce"]
    assert final["sessions"][-1]["questions"] == 1
    assert final["sessions"][-1]["status"] == "delivered"
    assert final["adaptations"][0]["item_limit"] == 1
    assert final["decisions"][0]["choice"] == "reduce_load"
    assert final["decisions"][0]["status"] == "resolved"
    assert all(d["status"] == "acknowledged" for d in final["deliveries"])
    assert {e["name"] for e in final["events"]} >= {"turn.saved", "adaptation.saved"}
    recalled = [e for e in final["events"] if e["name"] == "explanation.context_loaded"]
    assert [e["extra"]["approaches_loaded"] for e in recalled] == ["0", "1"]
    delivery = [e for e in final["events"] if e["kind"] == "delivery"]
    assert all(e["extra"].get("parent_correlation_id") for e in delivery)
    assert invocation_context.get() is None
    # A new HTTP client reads the same persisted data, not browser state.
    reread = await snapshot()
    assert reread["notes"] == final["notes"]
    assert reread["adaptations"] == final["adaptations"]
    assert rehearsal.services.sender.__class__.__name__ == "LocalOutbox"


async def test_rehearsal_rejects_steps_out_of_order(rehearsal_client):
    client, _ = rehearsal_client
    result = await client.post("/judge/memory/rehearsal/reduce", headers=HEADERS)
    assert result.status_code == 409


async def test_observer_assets_and_no_unknown_file_access(client):
    assert (await client.get("/judge/memory/")).status_code == 200
    for asset in ["memory.js", "memory.css"]:
        assert (await client.get("/judge/memory/assets/" + asset)).status_code == 200
    assert (await client.get("/judge/memory/assets/.env")).status_code == 404


def test_cloud_feed_paginates_deduplicates_overlap_and_does_not_cache_failures():
    feed = CloudEventFeed.__new__(CloudEventFeed)
    feed.group = "test-log-group"
    feed.client = Mock()
    feed.start = datetime.now(UTC) - timedelta(minutes=15)
    feed.rows, feed.updated, feed.lock = {}, 0.0, Lock()
    event = TraceEvent(at=datetime.now(UTC), kind="node", name="test")
    row = {"eventId": "event-1", "timestamp": 1000, "message": event.model_dump_json()}
    feed.client.filter_log_events.side_effect = [
        {"events": [row], "nextToken": "page-2"},
        {"events": [row], "nextToken": "page-2"},
    ]
    assert len(feed.read()) == 1
    assert feed.client.filter_log_events.call_count == 2
    assert feed.client.filter_log_events.call_args.kwargs["nextToken"] == "page-2"
    assert len(feed.read()) == 1
    assert feed.client.filter_log_events.call_count == 2
    feed.updated = 0.0
    feed.client.filter_log_events.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError):
        feed.read()
    assert feed.updated == 0.0
    feed.client.filter_log_events.side_effect = [{"events": [row]}]
    assert len(feed.read()) == 1


async def test_chat_delivery_is_shown_only_when_prepared_result_belongs_to_family(
    client, container, app
):
    family = make_family()
    container.store.put_family(family)
    scope = f"chat:{family.chat_ref}"
    for name, owner in [("own", "f1"), ("old-enrollment", "f2")]:
        container.store.put_record(
            OperationRecord(
                scope=scope, key=f"channel#{name}", payload={"summary": {"family_id": owner}}
            )
        )
        container.store.put_record(
            OperationRecord(
                scope=scope,
                key=f"outbox#channel#{name}",
                payload={
                    "created_at": datetime.now(UTC).isoformat(),
                    "messages": [{"text": "PRIVATE REPLY"}],
                    "receipts": ["PRIVATE RECEIPT"],
                },
            )
        )
        container.store.put_record(
            OperationRecord(
                scope=scope,
                key=f"invocation#{name}",
                payload={"result": {"result": {"family_id": owner}}},
            )
        )

    class Feed:
        def read(self):
            return [
                TraceEvent(
                    at=datetime.now(UTC),
                    kind="delivery",
                    name="acknowledged",
                    extra={"correlation_id": opaque(f"outbox#channel#{name}")},
                )
                for name in ["own", "old-enrollment"]
            ]

    app.state.memory_events = Feed()
    result = await client.get(URL, headers=HEADERS)
    data = result.json()
    assert len(data["deliveries"]) == len(data["events"]) == 1
    assert data["deliveries"][0]["id"] == opaque("outbox#channel#own")
    assert data["deliveries"][0]["status"] == "acknowledged"
    assert "PRIVATE" not in result.text


async def test_a_failed_explanation_request_is_not_counted_as_a_remembered_explanation(
    client, container
):
    container.store.put_family(make_family())
    container.store.put_record(
        OperationRecord(
            scope="f1",
            key="turn#s#blocked",
            payload={
                "note": {
                    "turn_id": "blocked",
                    "intent": "explanation",
                    "at": datetime.now(UTC).isoformat(),
                    "said": "no entiendo",
                    "explained": "",
                },
            },
        )
    )
    data = (await client.get(URL, headers=HEADERS)).json()
    assert data["counts"]["explanations"] == 0
    assert data["counts"]["assessed"] == 0
    assert data["notes"][0]["said"] == "no entiendo"
