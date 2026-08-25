from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.harness.clock import SimClock
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.runner import (
    handle_answer,
    run_daily_close,
    start_daily_session,
)
from repaso.core.telemetry.sink import build_telemetry_sink
from repaso.schemas.escalation import EscalationKind
from repaso.schemas.item import ItemKind
from repaso.schemas.review import QuarantineKind
from repaso.schemas.session import SessionStatus
from repaso.simulator.cohort import SECTION_CLUSTER, CohortLedger, build_cohort
from repaso.simulator.stub_model import AutoStubModel
from repaso.simulator.student_sim import simulate_answer
from repaso.tools.event_bus import build_event_publisher
from repaso.tools.grade_log import build_grade_log
from repaso.tools.guardrails import build_screener
from repaso.tools.knowledge import build_knowledge_retriever
from repaso.tools.llm import instrument_models
from repaso.tools.media_store import build_media_store
from repaso.tools.ocr import build_text_extractor
from repaso.tools.state_store import build_state_store
from repaso.tools.telegram import build_channel_sender

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
HEDGED_PREFIX = "creo que"


@dataclass
class DemoClockResult:
    days: int
    students: int
    sessions_delivered: int = 0
    responses: int = 0
    escalations_by_kind: Counter = field(default_factory=Counter)
    escalated_students: dict[str, set[str]] = field(default_factory=dict)
    quarantines_by_kind: Counter = field(default_factory=Counter)
    cohort_signals: list[str] = field(default_factory=list)
    retired_items: list[str] = field(default_factory=list)
    ledger: CohortLedger | None = None


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
        models=models,
        telemetry=telemetry,
    )


def _prime_open_grade(services: Services, correct: bool, hedged: bool) -> None:
    services.models[ModelRole.JUDGE].prime(
        "OpenGrade",
        {
            "correct": correct,
            "rubric_points": 2.0 if correct else 0.5,
            "confidence": 0.3 if hedged else 0.92,
            "feedback": "Revisemos juntos." if not correct else "Muy bien explicado.",
        },
    )


async def _play_day(services: Services, result: DemoClockResult, day: int, seed: int) -> None:
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
            if item.kind is ItemKind.OPEN:
                hedged = answer.text.startswith(HEDGED_PREFIX)
                _prime_open_grade(services, answer.correct_intent, hedged)
            outcome = await handle_answer(
                services, member.family, member.student, answer.text, answer.latency_seconds
            )
            if outcome is None:
                break
            result.responses += 1
            if outcome.session.status is SessionStatus.COMPLETED:
                break


def _collect_escalations(services: Services, result: DemoClockResult) -> None:
    for member in result.ledger.members:
        for escalation in services.store.list_pending_escalations(member.family.id):
            result.escalations_by_kind[escalation.kind.value] += 1
            result.escalated_students.setdefault(escalation.kind.value, set()).add(
                escalation.student_id or member.student.id
            )
        for quarantine in services.store.list_pending_quarantine(member.family.id):
            result.quarantines_by_kind[quarantine.kind.value] += 1


async def run_demo_clock(
    settings: Settings, days: int = 14, seed: int = 20260901
) -> DemoClockResult:
    services = build_offline_services(settings)
    ledger = build_cohort(services, services.clock.now())
    result = DemoClockResult(days=days, students=len(ledger.members), ledger=ledger)
    for day in range(days):
        services.clock.set_time(hour=19)
        await _play_day(services, result, day, seed)
        close = await run_daily_close(services)
        result.cohort_signals.extend(close.cohort_fired)
        result.retired_items.extend(close.retired_items)
        services.clock.advance(days=1)
    _collect_escalations(services, result)
    return result


def verdict_rows(result: DemoClockResult) -> list[tuple[str, str, str, str]]:
    ledger = result.ledger
    struggle = result.escalated_students.get(EscalationKind.STRUGGLE_TRIAGE.value, set())
    engagement = result.escalated_students.get(EscalationKind.ENGAGEMENT.value, set())
    low_ability = {m.student.id for m in ledger.members if m.archetype.value in
                   {"struggling", "cohort_cluster"}}
    disengaged = {m.student.id for m in ledger.members if m.archetype.value == "disengaged"}
    injections = result.quarantines_by_kind.get(QuarantineKind.INJECTION_ATTEMPT.value, 0)
    low_grades = result.quarantines_by_kind.get(QuarantineKind.LOW_CONFIDENCE_GRADE.value, 0)
    rows = [
        ("struggle triage fires for every low-ability student",
         str(ledger.expected_struggle_students), str(len(struggle & low_ability)),
         "as expected" if struggle & low_ability == low_ability else "NOT as expected"),
        ("struggle triage never fires outside the low-ability group",
         "0", str(len(struggle - low_ability)),
         "as expected" if not (struggle - low_ability) else "NOT as expected"),
        ("engagement alert reaches every disengaged student",
         str(ledger.expected_engagement_students), str(len(engagement & disengaged)),
         "as expected" if engagement & disengaged == disengaged else "NOT as expected"),
        ("engagement alert never fires for active students",
         "0", str(len(engagement - disengaged)),
         "as expected" if not (engagement - disengaged) else "NOT as expected"),
        ("cohort signal fires only for the clustered section",
         SECTION_CLUSTER, ",".join(sorted({s.split("#")[0] for s in result.cohort_signals})) or "-",
         "as expected"
         if {s.split("#")[0] for s in result.cohort_signals} == {SECTION_CLUSTER}
         else "NOT as expected"),
        ("cohort signal fires at most once per iso week",
         "1-2", str(len(result.cohort_signals)),
         "as expected" if 1 <= len(result.cohort_signals) <= 2 else "NOT as expected"),
        ("injection attempts quarantined",
         f">={ledger.expected_injections}", str(injections),
         "as expected" if injections >= ledger.expected_injections else "NOT as expected"),
        ("hedged open answers quarantined, never auto-graded",
         ">=1", str(low_grades),
         "as expected" if low_grades >= 1 else "NOT as expected"),
    ]
    return rows
