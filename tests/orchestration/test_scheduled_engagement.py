from datetime import UTC, date, datetime, timedelta

from repaso.core.orchestration.context import CloseRun
from repaso.core.orchestration.quality_graph import build_quality_graph
from repaso.core.orchestration.response_graph import daily_counts, scheduled_counts
from repaso.schemas.escalation import EscalationKind
from repaso.schemas.grading import EvidenceSpan, GradedBy, GradeResult
from tests.orchestration.fixtures import make_services, seed_family

START = date(2026, 9, 1)
WEEKEND = [5, 6]
CARNAVAL = [date(2026, 9, 14), date(2026, 9, 15)]
BEFORE_THE_BREAK = [date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11)]
BEFORE_THE_DROP = [date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10)]


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


def open_school(settings, answered: list[date], today: date, calendar: bool = True):
    holidays = CARNAVAL if calendar else []
    services = make_services(settings.model_copy(update={"holiday_dates": holidays}))
    family, student = seed_family(services.store)
    family = family.model_copy(update={"rest_weekdays": WEEKEND if calendar else []})
    services.store.put_family(family)
    for day in answered:
        services.grade_log.append(grade_on(student.id, day))
    services.clock.advance(days=(today - START).days)
    return services, family, student


async def close(services) -> CloseRun:
    run = CloseRun()
    await build_quality_graph(services, run).invoke_async("close")
    return run


def engagement_alerts(services, family_id: str) -> list:
    return [
        escalation
        for escalation in services.store.list_escalations(family_id)
        if escalation.kind is EscalationKind.ENGAGEMENT
    ]


async def test_a_school_break_is_not_disengagement(settings):
    services, family, _ = open_school(settings, BEFORE_THE_BREAK, date(2026, 9, 15))

    run = await close(services)

    assert run.outbound == []
    assert engagement_alerts(services, family.id) == []


async def test_the_same_break_alarms_a_school_with_no_calendar_configured(settings):
    services, family, _ = open_school(
        settings, BEFORE_THE_BREAK, date(2026, 9, 15), calendar=False
    )

    run = await close(services)

    assert len(run.outbound) == 1
    assert len(engagement_alerts(services, family.id)) == 1


async def test_a_dropout_is_still_caught_after_three_scheduled_days(settings):
    services, family, _ = open_school(settings, BEFORE_THE_DROP, date(2026, 9, 17))

    run = await close(services)

    alerts = engagement_alerts(services, family.id)
    assert len(alerts) == 1
    assert len(run.outbound) == 1
    assert "3" in alerts[0].summary


async def test_two_scheduled_silent_days_are_still_below_the_floor(settings):
    services, family, _ = open_school(settings, BEFORE_THE_DROP, date(2026, 9, 16))

    await close(services)

    assert engagement_alerts(services, family.id) == []


async def test_daily_counts_keeps_counting_calendar_days(settings):
    services, _, student = open_school(settings, BEFORE_THE_BREAK, date(2026, 9, 15))

    counts = daily_counts(services, student.id)

    assert len(counts) == 14
    assert counts[-4:] == [0, 0, 0, 0]
    assert sum(counts) == len(BEFORE_THE_BREAK)


async def test_scheduled_counts_drop_the_days_school_was_closed(settings):
    services, family, student = open_school(settings, BEFORE_THE_BREAK, date(2026, 9, 15))
    window = [date(2026, 9, 15) - timedelta(days=offset) for offset in range(13, -1, -1)]

    counts = scheduled_counts(services, student.id, family)

    open_days = [day for day in window if day.weekday() < 5 and day not in CARNAVAL]
    assert len(counts) == len(open_days) == 8
    assert counts[-1] > 0
    assert sum(counts) == sum(daily_counts(services, student.id))
