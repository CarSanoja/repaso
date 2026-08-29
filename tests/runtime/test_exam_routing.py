from repaso.core.orchestration.tutor_graph import exam_is_near
from repaso.runtime import invoke
from repaso.schemas.student import Student
from tests.orchestration.fixtures import START, seed_family
from tests.runtime.fixtures import pilot, request


def test_an_exam_announcement_reaches_every_student_in_the_family(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    sibling = Student(
        id="s-f1-2", family_id=family.id, alias="Mia", grade=2, section_key="x", created_at=START
    )
    services.store.put_student(sibling)

    response = invoke(
        request("exam_announced", family.id, exam_date="2026-09-04", topic="Fracciones"), services
    )

    assert response["ok"] is True
    result = response["result"]
    assert sorted(result["student_ids"]) == sorted([student.id, sibling.id])
    assert result["days_away"] == 3
    assert result["topic"] == "Fracciones"
    for pupil in (student, sibling):
        dates = [exam.exam_date.isoformat() for exam in services.store.list_exam_dates(pupil.id)]
        assert dates == ["2026-09-04"]
    assert exam_is_near(services.store.list_exam_dates(student.id), services.clock.today())


def test_replaying_an_exam_announcement_does_not_duplicate_the_date(settings):
    services = pilot(settings)
    family, student = seed_family(services.store)
    body = request("exam_announced", family.id, exam_date="2026-09-04", topic="Fracciones")

    invoke(body, services)
    invoke(body, services)

    assert len(services.store.list_exam_dates(student.id)) == 1


def test_an_exam_announcement_needs_a_real_date(settings):
    services = pilot(settings)
    family, _ = seed_family(services.store)

    response = invoke(
        request("exam_announced", family.id, exam_date="pronto", topic="Fracciones"), services
    )

    assert response["error"]["code"] == "invalid_payload"
    assert "exam_date" in response["error"]["message"]


def test_an_exam_announcement_for_an_unknown_family_is_not_found(settings):
    services = pilot(settings)

    response = invoke(
        request("exam_announced", "ghost", exam_date="2026-09-04", topic="Fracciones"), services
    )

    assert response["error"] == {"code": "not_found", "message": "family not found: ghost"}
