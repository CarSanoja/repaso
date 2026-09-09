import pytest
from httpx import ASGITransport, AsyncClient

from repaso.api.dependencies import build_container
from repaso.api.main import create_app
from repaso.schemas.events import EventKind
from tests.api.conftest import (
    JUDGE_CODE,
    TELEGRAM_SECRET,
    make_escalation,
    make_family,
    make_quarantine,
    make_student,
    make_update,
)

WEBHOOK = "/telegram/webhook"
SECRET_HEADER = {"X-Telegram-Bot-Api-Secret-Token": TELEGRAM_SECRET}
JUDGE_HEADER = {"X-Judge-Code": JUDGE_CODE}


@pytest.fixture
async def unconfigured_client(api_settings):
    app = create_app(build_container(api_settings))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def test_healthz_reports_ok(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_reports_local_mode(client):
    response = await client.get("/readyz")
    assert response.json() == {"status": "ready", "local_mode": True}


async def test_webhook_rejects_a_wrong_secret(client, container):
    response = await client.post(
        WEBHOOK, json=make_update(), headers={"X-Telegram-Bot-Api-Secret-Token": "nope"}
    )
    assert response.status_code == 401
    assert container.publisher.published == []


async def test_webhook_rejects_a_missing_secret_header(client):
    response = await client.post(WEBHOOK, json=make_update())
    assert response.status_code == 401


async def test_webhook_is_closed_when_no_secret_is_configured(unconfigured_client):
    response = await unconfigured_client.post(WEBHOOK, json=make_update(), headers=SECRET_HEADER)
    assert response.status_code == 503


async def test_webhook_publishes_one_channel_message_event(client, container):
    response = await client.post(WEBHOOK, json=make_update(), headers=SECRET_HEADER)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(container.publisher.published) == 1
    event = container.publisher.published[0]
    assert event.kind is EventKind.CHANNEL_MESSAGE
    assert event.family_id is None
    assert event.idempotency_key == "12345#10"
    assert event.payload["text"] == "hola"


async def test_duplicate_update_publishes_nothing_new(client, container):
    update = make_update(update_id=42)
    first = await client.post(WEBHOOK, json=update, headers=SECRET_HEADER)
    second = await client.post(WEBHOOK, json=update, headers=SECRET_HEADER)
    assert first.json() == {"ok": True}
    assert second.json() == {"ok": True, "duplicate": True}
    assert len(container.publisher.published) == 1


async def test_admission_does_not_depend_on_the_record_written_after_publishing(client, container):
    update = make_update(update_id=77)
    first = await client.post(WEBHOOK, json=update, headers=SECRET_HEADER)
    container.store.delete_records("chat:12345")
    second = await client.post(WEBHOOK, json=update, headers=SECRET_HEADER)

    assert first.json() == {"ok": True}
    assert second.json() == {"ok": True, "duplicate": True}
    assert len(container.publisher.published) == 1


async def test_an_update_whose_publish_failed_may_be_delivered_again(client, container):
    update = make_update(update_id=88)
    published = container.publisher.publish

    def refuse(event):
        raise RuntimeError("bus unavailable")

    container.publisher.publish = refuse
    failed = await client.post(WEBHOOK, json=update, headers=SECRET_HEADER)
    container.publisher.publish = published
    retried = await client.post(WEBHOOK, json=update, headers=SECRET_HEADER)

    assert failed.status_code == 503
    assert retried.json() == {"ok": True}
    assert len(container.publisher.published) == 1


async def test_malformed_body_is_logged_never_raised(client, container):
    response = await client.post(
        WEBHOOK,
        content=b"{not json",
        headers={**SECRET_HEADER, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "error": "logged"}
    assert container.publisher.published == []


async def test_judge_login_returns_the_code_as_token(client):
    response = await client.post("/judge/login", json={"code": JUDGE_CODE})
    assert response.status_code == 200
    assert response.json() == {"token": JUDGE_CODE}


async def test_judge_login_rejects_a_wrong_code(client):
    response = await client.post("/judge/login", json={"code": "wrong"})
    assert response.status_code == 403


async def test_judge_login_is_closed_when_no_code_is_configured(unconfigured_client):
    response = await unconfigured_client.post("/judge/login", json={"code": "anything"})
    assert response.status_code == 503


async def test_judge_reads_require_the_code_header(client):
    assert (await client.get("/judge/students")).status_code == 403
    assert (await client.get("/judge/students", headers={"X-Judge-Code": "bad"})).status_code == 403
    assert (await client.get("/judge/transcript/f1")).status_code == 403


async def test_judge_lists_seeded_students(client, container):
    container.store.put_family(make_family())
    container.store.put_student(make_student())
    response = await client.get("/judge/students", headers=JUDGE_HEADER)
    assert response.status_code == 200
    assert response.json() == [{"family_id": "f1", "alias": "Ana", "grade": 5, "section_key": "5A"}]


async def test_judge_transcript_returns_pending_work(client, container):
    container.store.put_family(make_family())
    container.store.put_escalation(make_escalation())
    container.store.put_quarantine(make_quarantine())
    response = await client.get("/judge/transcript/f1", headers=JUDGE_HEADER)
    body = response.json()
    assert [item["id"] for item in body["escalations"]] == ["e1"]
    assert [item["id"] for item in body["quarantine"]] == ["q1"]
    assert body["escalations"][0]["status"] == "pending"


async def test_judge_transcript_is_empty_for_an_unknown_family(client):
    response = await client.get("/judge/transcript/nope", headers=JUDGE_HEADER)
    assert response.status_code == 404
    assert response.json() == {"detail": "family_not_shared"}


async def test_judge_page_is_served(client):
    response = await client.get("/judge/")
    assert response.status_code == 200
    assert "Interactive simulation" in response.text
    asset = await client.get("/judge/assets/judge.js")
    assert asset.status_code == 200 and "X-Judge-Code" in asset.text


@pytest.mark.parametrize("decision,count", [("teacher_note", 3), ("reduce_load", 1)])
async def test_complete_judge_run_is_isolated_and_keeps_rejected_material_visible_as_rejected(
    client, container, decision, count
):
    private_family = make_family("not-shared", "56789")
    container.store.put_family(private_family)
    before = container.store.list_families()
    result = await client.post("/judge/demo/run", headers=JUDGE_HEADER, json={"decision": decision})
    assert result.status_code == 200
    data = result.json()
    assert data["passed"] and not data["live_inference"]
    assert "not-shared" not in result.text
    assert container.store.list_families() == before
    final = data["checkpoints"][-1]
    assert len(final["sessions"][-1]["capsule"]["item_ids"]) == count
    rejected = [m for m in final["materials"] if m["status"] == "rejected"]
    assert len(rejected) == 1 and "2/3 = 4/9" in rejected[0]["parsed_text"]
