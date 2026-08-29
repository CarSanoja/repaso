import pytest

from repaso.runtime import invoke, invoke_async
from repaso.runtime.entrypoint import supported_kinds
from repaso.schemas.events import EventKind
from tests.orchestration.fixtures import make_services, seed_family
from tests.runtime.fixtures import request, seed_item

UNSUPPORTED = sorted(set(EventKind) - {EventKind(kind) for kind in supported_kinds()})


def test_every_event_kind_is_either_routed_or_explicitly_unsupported():
    assert supported_kinds() == [
        "daily_close",
        "daily_session_due",
        "material_uploaded",
        "response_received",
    ]
    assert [kind.value for kind in UNSUPPORTED] == [
        "channel_message",
        "escalation_resolved",
        "exam_announced",
    ]


def test_an_unknown_kind_is_a_structured_error(settings):
    services = make_services(settings)

    response = invoke({"kind": "material_deleted", "payload": {}}, services)

    assert response["ok"] is False
    assert response["kind"] == "material_deleted"
    assert response["error"]["code"] == "unknown_kind"


@pytest.mark.parametrize("kind", UNSUPPORTED, ids=lambda kind: kind.value)
def test_known_kinds_without_a_handler_report_what_is_supported(settings, kind):
    services = make_services(settings)

    response = invoke(request(kind.value, "f1"), services)

    assert response["ok"] is False
    assert response["kind"] == kind.value
    assert response["error"]["code"] == "unsupported_kind"
    assert "daily_close" in response["error"]["message"]


def test_a_missing_family_id_never_reaches_the_store(settings):
    services = make_services(settings)

    response = invoke({"kind": "daily_session_due", "payload": {"student_id": "s1"}}, services)

    assert response["error"]["code"] == "invalid_payload"
    assert "family_id" in response["error"]["message"]


def test_unknown_family_and_student_are_reported_as_not_found(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)

    missing_family = invoke(request("daily_session_due", "nope", student_id="s1"), services)
    missing_student = invoke(request("daily_session_due", family.id, student_id="ghost"), services)

    assert missing_family["error"] == {"code": "not_found", "message": "family not found: nope"}
    assert missing_student["error"]["code"] == "not_found"


def test_a_student_from_another_family_is_refused(settings):
    services = make_services(settings)
    seed_family(services.store, "f1", "100")
    _, other_student = seed_family(services.store, "f2", "200")

    response = invoke(request("daily_session_due", "f1", student_id=other_student.id), services)

    assert response["error"]["code"] == "not_found"
    assert "does not belong" in response["error"]["message"]


def test_a_failing_graph_returns_a_structured_error_not_a_traceback(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")

    response = invoke(request("daily_session_due", family.id, student_id=student.id), services)

    assert response["ok"] is False
    assert response["kind"] == "daily_session_due"
    assert response["error"]["code"] == "handler_failed"
    assert "PlaybackExhausted" in response["error"]["message"]


async def test_invoke_async_is_the_awaitable_form(settings):
    services = make_services(settings)

    response = await invoke_async(request("daily_close"), services)

    assert response["ok"] is True


async def test_the_sync_form_refuses_to_run_inside_a_live_event_loop(settings):
    services = make_services(settings)

    response = invoke(request("daily_close"), services)

    assert response == {
        "ok": False,
        "kind": "daily_close",
        "error": {
            "code": "event_loop_running",
            "message": (
                "invoke() cannot run inside a running event loop; await invoke_async() instead"
            ),
        },
    }
