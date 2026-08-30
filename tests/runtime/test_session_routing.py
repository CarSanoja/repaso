import json

from repaso.config.models import ModelRole
from repaso.runtime import invoke
from repaso.schemas.family import FamilyStatus
from repaso.schemas.session import SessionStatus
from tests.orchestration.fixtures import make_services, seed_family
from tests.runtime.fixtures import request, seed_item, seed_session


def test_daily_session_due_plans_and_delivers_a_capsule(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_item(services.store, "i2")
    services.models[ModelRole.GENERATE].enqueue({"text": "Las fracciones equivalentes..."})

    response = invoke(request("daily_session_due", family.id, student_id=student.id), services)

    assert response["ok"] is True
    result = response["result"]
    assert result["handled"] is True
    assert result["terminal"] is None
    assert result["session_status"] == SessionStatus.DELIVERED.value
    assert "Leo" in result["outbound"][0]["text"]


def test_a_second_session_the_same_day_reports_its_terminal(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])

    response = invoke(request("daily_session_due", family.id, student_id=student.id), services)

    assert response["ok"] is True
    assert response["result"]["terminal"] == "already_planned"
    assert response["result"]["outbound"] == []


def test_daily_session_due_delivers_nothing_to_a_paused_family(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    services.store.put_family(family.model_copy(update={"status": FamilyStatus.PAUSED}))

    response = invoke(request("daily_session_due", family.id, student_id=student.id), services)

    assert response["ok"] is True
    assert response["result"]["terminal"] == "paused"
    assert response["result"]["outbound"] == []
    assert services.store.get_session_by_date(student.id, services.clock.today()) is None


def test_response_received_grades_the_current_item(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "ok"})

    response = invoke(
        request(
            "response_received",
            family.id,
            student_id=student.id,
            text="1/2",
            latency_seconds=12.0,
        ),
        services,
    )

    assert response["ok"] is True
    result = response["result"]
    assert result["grade"]["correct"] is True
    assert result["grade"]["graded_by"] == "deterministic"
    assert result["session_status"] == SessionStatus.COMPLETED.value
    assert services.grade_log.by_student(student.id)


def test_response_received_without_an_open_session_is_a_handled_no_op(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)

    response = invoke(
        request("response_received", family.id, student_id=student.id, text="1/2"), services
    )

    assert response["ok"] is True
    assert response["result"] == {"handled": False, "outbound": []}


def test_daily_close_runs_the_quality_graph(settings):
    services = make_services(settings)

    response = invoke(request("daily_close"), services)

    assert response["ok"] is True
    result = response["result"]
    assert result["report"]["close_date"] == services.clock.today().isoformat()
    assert result["cohort_fired"] == []
    assert json.loads(json.dumps(response)) == response


def test_daily_close_ignores_a_scheduler_payload(settings):
    services = make_services(settings)

    response = invoke(request("daily_close", None, source="scheduler"), services)

    assert response["ok"] is True
