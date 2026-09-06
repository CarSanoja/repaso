from datetime import UTC, date, datetime, timedelta

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import CloseRun
from repaso.core.orchestration.quality_graph import build_quality_graph
from repaso.core.orchestration.response_graph import daily_counts, scheduled_counts
from repaso.schemas.escalation import EscalationKind
from repaso.schemas.grading import EvidenceSpan, GradedBy, GradeResult
from repaso.schemas.mastery import MasteryLevel, MasteryState
from tests.orchestration.fixtures import FRACTIONS, make_services, seed_family

START = date(2026, 9, 1)
WEEKEND = [5, 6]
CARNAVAL = [date(2026, 9, 14), date(2026, 9, 15)]
OUTAGE = [date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10)]
BEFORE_THE_BREAK = [date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11)]
BEFORE_THE_DROP = [date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10)]
BEFORE_THE_OUTAGE = [date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 7)]
COHORT_DAYS = [START + timedelta(days=offset) for offset in range(-13, 21)]
PEERS = 3


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


def open_school(settings, answered, today, calendar=True, quiet=()):
    holidays = CARNAVAL if calendar else []
    services = make_services(settings.model_copy(update={"holiday_dates": holidays}))
    family, student = seed_family(services.store)
    family = family.model_copy(update={"rest_weekdays": WEEKEND if calendar else []})
    services.store.put_family(family)
    for day in answered:
        services.grade_log.append(grade_on(student.id, day))
    for index in range(PEERS):
        _, peer = seed_family(services.store, f"peer{index}", f"20{index}")
        for day in COHORT_DAYS:
            if day not in quiet:
                services.grade_log.append(grade_on(peer.id, day))
    services.clock.advance(days=(today - START).days)
    return services, family, student


def struggling_school(settings, today: date):
    services = make_services(settings.model_copy(update={"holiday_dates": CARNAVAL}))
    for index in range(3):
        family, student = seed_family(services.store, f"f{index}", str(300 + index))
        services.store.put_family(family.model_copy(update={"rest_weekdays": WEEKEND}))
        services.store.put_mastery(
            MasteryState(
                student_id=student.id,
                competency_id=FRACTIONS,
                ema_accuracy=0.2,
                attempts=9,
                correct=1,
                level=MasteryLevel.STRUGGLING,
            )
        )
        services.models[ModelRole.GENERATE].enqueue({"text": "Estimada maestra..."})
    services.clock.advance(days=(today - START).days)
    return services


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
    services, family, _ = open_school(settings, BEFORE_THE_BREAK, date(2026, 9, 16))

    run = await close(services)

    assert run.outbound == []
    assert engagement_alerts(services, family.id) == []


async def test_the_same_break_alarms_a_school_with_no_calendar_configured(settings):
    services, family, _ = open_school(settings, BEFORE_THE_BREAK, date(2026, 9, 16), calendar=False)

    run = await close(services)

    assert len(run.outbound) == 1
    assert len(engagement_alerts(services, family.id)) == 1


async def test_a_dropout_is_still_caught_after_three_scheduled_days(settings):
    services, family, _ = open_school(settings, BEFORE_THE_DROP, date(2026, 9, 17))

    run = await close(services)

    alerts = engagement_alerts(services, family.id)
    assert len(alerts) == 1
    assert len(run.outbound) == 1
    assert "3 días de clase sin practicar" in alerts[0].summary


async def test_two_scheduled_silent_days_are_still_below_the_floor(settings):
    services, family, _ = open_school(settings, BEFORE_THE_DROP, date(2026, 9, 16))

    await close(services)

    assert engagement_alerts(services, family.id) == []


async def test_a_cohort_wide_outage_is_not_disengagement(settings):
    services, family, _ = open_school(settings, BEFORE_THE_OUTAGE, date(2026, 9, 10), quiet=OUTAGE)

    run = await close(services)

    assert run.outbound == []
    assert engagement_alerts(services, family.id) == []


async def test_the_same_silence_alarms_when_the_rest_of_the_cohort_kept_answering(settings):
    services, family, _ = open_school(settings, BEFORE_THE_OUTAGE, date(2026, 9, 10))

    run = await close(services)

    assert len(run.outbound) == 1
    assert len(engagement_alerts(services, family.id)) == 1


async def test_a_dropout_whose_silence_starts_in_the_outage_is_still_caught(settings):
    services, family, _ = open_school(settings, BEFORE_THE_OUTAGE, date(2026, 9, 16), quiet=OUTAGE)

    await close(services)
    assert engagement_alerts(services, family.id) == []

    services.clock.advance(days=1)
    run = await close(services)

    alerts = engagement_alerts(services, family.id)
    assert len(alerts) == 1 and len(run.outbound) == 1
    assert "3 días de clase sin practicar" in alerts[0].summary


async def test_a_holiday_close_delivers_nothing_and_keeps_the_weekly_claim(settings):
    answered = [date(2026, 9, 7), date(2026, 9, 8)]
    services, family, _ = open_school(settings, answered, date(2026, 9, 14))

    holiday = await close(services)
    assert holiday.outbound == []
    assert engagement_alerts(services, family.id) == []

    services.clock.advance(days=2)
    run = await close(services)

    alerts = engagement_alerts(services, family.id)
    assert len(alerts) == 1 and len(run.outbound) == 1
    assert "4 días de clase sin practicar" in alerts[0].summary


async def test_a_holiday_close_defers_the_cohort_signal_without_burning_its_claim(settings):
    services = struggling_school(settings, date(2026, 9, 14))

    holiday = await close(services)
    assert holiday.cohort_fired == [] and holiday.outbound == []

    services.clock.advance(days=2)
    run = await close(services)

    assert len(run.cohort_fired) == 1
    assert len(run.outbound) == 1  # one shared note, not three copies


async def test_daily_counts_keep_calendar_days_and_scheduled_counts_drop_closed_ones(settings):
    services, family, student = open_school(settings, BEFORE_THE_BREAK, date(2026, 9, 15))

    counts = daily_counts(services, student.id)
    scheduled = scheduled_counts(services, student.id, family)

    assert len(counts) == 14 and counts[-4:] == [0, 0, 0, 0]
    assert len(scheduled) == 8 and scheduled[-1] > 0
    assert sum(scheduled) == sum(counts) == len(BEFORE_THE_BREAK)
