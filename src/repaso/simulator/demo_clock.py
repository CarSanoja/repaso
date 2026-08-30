from dataclasses import dataclass
from datetime import UTC, date, datetime

from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.harness.calendar import is_scheduled
from repaso.core.harness.clock import SimClock
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.runner import (
    handle_answer,
    run_daily_close,
    start_daily_session,
)
from repaso.core.telemetry.sink import build_telemetry_sink
from repaso.schemas.item import ItemKind
from repaso.schemas.session import SessionStatus
from repaso.simulator.cohort import CohortLedger, build_cohort
from repaso.simulator.demo_result import DemoClockResult, collect_results, resolve_pending
from repaso.simulator.stub_model import AutoStubModel
from repaso.simulator.student_sim import INJECTION_REPLY, simulate_answer
from repaso.tools.event_bus import build_event_publisher
from repaso.tools.grade_log import build_grade_log
from repaso.tools.guardrails import build_screener
from repaso.tools.invite_codes import build_invite_codes
from repaso.tools.knowledge import build_knowledge_retriever
from repaso.tools.llm import instrument_models
from repaso.tools.media_store import build_media_store
from repaso.tools.ocr import build_text_extractor
from repaso.tools.state_store import build_state_store
from repaso.tools.telegram import build_channel_sender

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
HEDGED_PREFIX = "creo que"
OPEN_GRADE = "OpenGrade"


class StalePrimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class CalendarOverlay:
    rest_weekdays: tuple[int, ...] = ()
    holiday_dates: tuple[date, ...] = ()

    def is_school_day(self, day: date) -> bool:
        return is_scheduled(day, self.rest_weekdays, self.holiday_dates)


def build_offline_services(settings: Settings) -> Services:
    clock = SimClock(START)
    telemetry = build_telemetry_sink(settings, clock)
    models = instrument_models({role: AutoStubModel() for role in ModelRole}, telemetry)
    return Services(
        settings=settings,
        clock=clock,
        store=build_state_store(settings),
        grade_log=build_grade_log(settings),
        media=build_media_store(settings),
        extractor=build_text_extractor(settings),
        screener=build_screener(settings),
        retriever=build_knowledge_retriever(settings),
        publisher=build_event_publisher(settings),
        sender=build_channel_sender(settings),
        invites=build_invite_codes(settings),
        models=models,
        telemetry=telemetry,
    )


def _prime_open_grade(services: Services, correct: bool, hedged: bool) -> None:
    services.models[ModelRole.JUDGE].prime(
        OPEN_GRADE,
        {
            "correct": correct,
            "rubric_points": 2.0 if correct else 0.5,
            "confidence": 0.3 if hedged else 0.92,
            "feedback": "Revisemos juntos." if not correct else "Muy bien explicado.",
        },
    )


def _settle_open_prime(services: Services, result: DemoClockResult, hedged: bool) -> None:
    stale = services.models[ModelRole.JUDGE].drop_pending(OPEN_GRADE)
    if stale:
        result.dropped_open_primes += stale
    elif hedged:
        result.planted_hedged += 1


def _assert_primes_drained(services: Services) -> None:
    pending = services.models[ModelRole.JUDGE].pending(OPEN_GRADE)
    if pending:
        raise StalePrimeError(
            f"{pending} primed open grade(s) never reached the judge; "
            "every later open answer would be graded with someone else's payload"
        )


def _teach_calendar(services: Services, ledger: CohortLedger, rest_weekdays: tuple[int, ...]):
    if not rest_weekdays:
        return
    for member in ledger.members:
        member.family = member.family.model_copy(
            update={"rest_weekdays": list(rest_weekdays)}
        )
        services.store.put_family(member.family)


async def _play_day(
    services: Services,
    result: DemoClockResult,
    day: int,
    seed: int,
    overlay: CalendarOverlay,
) -> None:
    if not overlay.is_school_day(services.clock.today()):
        return
    result.scheduled_days += 1
    for member in result.ledger.members:
        run = await start_daily_session(services, member.family, member.student)
        if run.terminal is not None:
            continue
        result.sessions_delivered += 1
        while True:
            session = services.store.get_session_by_date(
                member.student.id, services.clock.today()
            )
            if session is None or session.status not in {
                SessionStatus.DELIVERED,
                SessionStatus.IN_PROGRESS,
            }:
                break
            item_ids = session.capsule.item_ids if session.capsule else []
            if session.current_item_index >= len(item_ids):
                break
            item = services.store.get_item(item_ids[session.current_item_index])
            answer = simulate_answer(seed, member.student.id, member.archetype, day, item)
            if not answer.responded:
                break
            if answer.text == INJECTION_REPLY:
                result.planted_injections += 1
            open_item = item.kind is ItemKind.OPEN
            hedged = open_item and answer.text.startswith(HEDGED_PREFIX)
            if open_item:
                _prime_open_grade(services, answer.correct_intent, hedged)
            outcome = await handle_answer(
                services, member.family, member.student, answer.text, answer.latency_seconds
            )
            if open_item:
                _settle_open_prime(services, result, hedged)
            if outcome is None:
                break
            result.responses += 1
            if outcome.session.status is SessionStatus.COMPLETED:
                break


async def run_demo_clock(
    settings: Settings,
    days: int = 14,
    seed: int = 20260901,
    rest_weekdays: list[int] | None = None,
    holiday_dates: list[date] | None = None,
    mask_scheduled: bool = True,
) -> DemoClockResult:
    overlay = CalendarOverlay(
        tuple(rest_weekdays or ()),
        tuple(settings.holiday_dates if holiday_dates is None else holiday_dates),
    )
    known = overlay if mask_scheduled else CalendarOverlay()
    services = build_offline_services(
        settings.model_copy(update={"holiday_dates": list(known.holiday_dates)})
    )
    ledger = build_cohort(services, services.clock.now())
    _teach_calendar(services, ledger, known.rest_weekdays)
    result = DemoClockResult(days=days, students=len(ledger.members), ledger=ledger)
    for day in range(days):
        services.clock.set_time(hour=19)
        resolve_pending(services)
        await _play_day(services, result, day, seed, overlay)
        _assert_primes_drained(services)
        close = await run_daily_close(services)
        result.cohort_signals.extend(close.cohort_fired)
        week = services.clock.today().isocalendar()
        result.cohort_weeks[f"{week.year}-W{week.week}"] += len(close.cohort_fired)
        result.retired_items.extend(close.retired_items)
        services.clock.advance(days=1)
    collect_results(services, result)
    return result
