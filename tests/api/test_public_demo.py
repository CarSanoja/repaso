import boto3
import pytest
from httpx import ASGITransport, AsyncClient

from repaso.lambdas.demo import COOKIE, DemoSessions
from repaso.simulator.memory_rehearsal import FAMILY_ID

HEADERS = {"X-Judge-Code": "REPASO-LIVE"}
SNAPSHOT = f"/judge/memory/snapshot/{FAMILY_ID}"


@pytest.fixture
def public_demo(monkeypatch):
    def no_aws(*args, **kwargs):
        raise AssertionError("The public rehearsal must not create an AWS client")

    monkeypatch.setattr(boto3.session.Session, "client", no_aws)
    return DemoSessions(code="REPASO-LIVE")


async def test_public_demo_isolates_visitors_and_reset_is_authorized(public_demo):
    transport = ASGITransport(app=public_demo)
    async with (
        AsyncClient(transport=transport, base_url="https://demo.test") as first,
        AsyncClient(transport=transport, base_url="https://demo.test") as second,
    ):
        page = await first.get("/judge/memory/")
        assert page.status_code == 200
        assert "HttpOnly" in page.headers["set-cookie"]
        assert "Secure" in page.headers["set-cookie"]
        assert "SameSite=Lax" in page.headers["set-cookie"]
        assert (await first.get(SNAPSHOT)).status_code == 403
        assert (await first.post("/judge/memory/rehearsal/reset")).status_code == 403
        assert (await first.post("/webhook", json={})).status_code == 404
        for step in ("help", "another", "answer", "reduce"):
            response = await first.post(f"/judge/memory/rehearsal/{step}", headers=HEADERS)
            assert response.status_code == 200, response.text
        completed = (await first.get(SNAPSHOT, headers=HEADERS)).json()
        assert completed["counts"]["assessed"] == 1
        assert completed["counts"]["explanations"] == 2
        assert completed["rehearsal_completed"] == ["help", "another", "answer", "reduce"]
        assert completed["sessions"][-1]["questions"] == 1
        untouched = (await second.get(SNAPSHOT, headers=HEADERS)).json()
        assert untouched["rehearsal_completed"] == []
        assert untouched["counts"]["assessed"] == 0
        assert second.cookies[COOKIE] != first.cookies[COOKIE]
        await second.post("/judge/memory/rehearsal/help", headers=HEADERS)
        assert (
            await first.post("/judge/memory/rehearsal/reset", headers=HEADERS)
        ).status_code == 200
        reset = (await first.get(SNAPSHOT, headers=HEADERS)).json()
        assert reset["rehearsal_reset_available"] is True
        assert reset["rehearsal_completed"] == []
        assert reset["counts"]["explanations"] == 0
        assert (await second.get(SNAPSHOT, headers=HEADERS)).json()["counts"]["explanations"] == 1
        assert (await first.get("/judge/")).status_code == 200


async def test_public_demo_cache_is_bounded_and_unknown_cookie_gets_fresh_state(public_demo):
    public_demo.max_sessions = 1
    transport = ASGITransport(app=public_demo)
    async with AsyncClient(transport=transport, base_url="https://demo.test") as client:
        await client.get("/judge/")
        old = client.cookies[COOKIE]
        response = await client.get("/judge/", headers={"Cookie": f"{COOKIE}=untrusted"})
        assert response.status_code == 200
        assert len(public_demo.sessions) == 1
        assert old not in public_demo.sessions
        assert "untrusted" not in public_demo.sessions
