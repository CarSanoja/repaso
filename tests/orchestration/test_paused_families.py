from datetime import UTC, date, datetime, timedelta

from repaso.config.models import ModelRole
from repaso.core.harness.clock import SimClock
from repaso.core.orchestration.runner import (
    handle_answer,
    run_daily_close,
    start_daily_session,
)
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.schemas.escalation import EscalationKind
from repaso.schemas.family import FamilyStatus
from repaso.schemas.grading import EvidenceSpan, GradedBy, GradeResult
from repaso.schemas.session import SessionStatus
from tests.orchestration.fixtures import START, make_services, seed_family
from tests.runtime.fixtures import seed_item, seed_session

ANSWERED = [date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10)]
SILENT_DAY = date(2026, 9, 17)
COHORT_DAYS = [date(2026, 9, 1) + timedelta(days=offset) for offset in range(-13, 21)]
PEERS = 3
CAPSULE = {"text": "Las fracciones equivalentes..."}


def traced(settings, tmp_path):
    services = make_services(settings)
    services.telemetry = LocalTelemetrySink(tmp_path / "telemetry.jsonl", SimClock(START))
    return services


def pause(services, family):
    paused = family.model_copy(update={"status": FamilyStatus.PAUSED})
    services.store.put_family(paused)
    return paused


def resume(services, family):
    active = family.model_copy(update={"status": FamilyStatus.ACTIVE})
    services.store.put_family(active)
    return active


def skips(services, step: str) -> list:
    return [
        event
        for event in services.telemetry.events
        if event.name == "paused" and event.extra["step"] == step
    ]


def grade_on(student_id: str, day: date) -> GradeResult:
    return GradeResult(
        student_id=student_id,
        item_id="i1",
        correct=True,
        confidence=1.0,
        graded_by=GradedBy.DETERMINISTIC,
        evidence=EvidenceSpan(quote="2/4", source_ref=f"response:{day.isoformat()}"),
        feedback="",
        graded_at=datetime(day.year, day.month, day.day, 19, tzinfo=UTC),
    )


def silent_school(settings, tmp_path):
    services = traced(settings, tmp_path)
    family, student = seed_family(services.store)
    for day in ANSWERED:
        services.grade_log.append(grade_on(student.id, day))
    for index in range(PEERS):
        _, peer = seed_family(services.store, f"peer{index}", f"20{index}")
        for day in COHORT_DAYS:
            services.grade_log.append(grade_on(peer.id, day))
    services.clock.advance(days=(SILENT_DAY - services.clock.today()).days)
    return services, family, student


def engagement_alerts(services, family_id: str) -> list:
    return [
        escalation
        for escalation in services.store.list_escalations(family_id)
        if escalation.kind is EscalationKind.ENGAGEMENT
    ]


async def test_a_paused_family_is_offered_no_session(settings, tmp_path):
    services = traced(settings, tmp_path)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_item(services.store, "i2")

    run = await start_daily_session(services, pause(services, family), student)

    assert run.terminal == "paused"
    assert run.session is None
    assert services.store.get_session_by_date(student.id, services.clock.today()) is None
    assert services.sender.sent == []
    assert [event.student_id for event in skips(services, "daily_session")] == [student.id]


async def test_a_family_paused_on_day_one_hears_nothing_until_it_resumes(settings, tmp_path):
    services = traced(settings, tmp_path)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_item(services.store, "i2")
    family = pause(services, family)

    for _ in range(3):
        assert (await start_daily_session(services, family, student)).terminal == "paused"
        services.clock.advance(days=1)

    services.models[ModelRole.GENERATE].enqueue(CAPSULE)
    run = await start_daily_session(services, resume(services, family), student)

    assert run.terminal is None
    assert run.session.status is SessionStatus.DELIVERED
    assert len(services.sender.sent) == 1
    assert len(skips(services, "daily_session")) == 3


async def test_a_session_already_open_is_still_graded_while_paused(settings, tmp_path):
    services = traced(settings, tmp_path)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "ok"})

    run = await handle_answer(services, pause(services, family), student, "1/2", 12.0)

    assert run is not None
    assert run.grade.correct is True
    assert services.grade_log.by_student(student.id)


async def test_the_silence_that_alerts_a_family_still_practicing(settings, tmp_path):
    services, family, _ = silent_school(settings, tmp_path)

    run = await run_daily_close(services)

    assert len(engagement_alerts(services, family.id)) == 1
    assert len(run.outbound) == 1


async def test_the_same_silence_raises_no_alert_once_the_family_pauses(settings, tmp_path):
    services, family, _ = silent_school(settings, tmp_path)
    pause(services, family)

    run = await run_daily_close(services)

    assert engagement_alerts(services, family.id) == []
    assert run.outbound == []
    assert len(skips(services, "close_engagement")) == 1
