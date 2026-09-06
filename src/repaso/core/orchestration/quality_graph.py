from collections import Counter
from datetime import date

from strands.multiagent.graph import GraphBuilder

from repaso.agents.escalation_composer import compose_cohort, compose_engagement
from repaso.agents.goal_verifier import verify_daily
from repaso.agents.item_optimizer import retire, retirement_candidates
from repaso.config.models import ModelRole
from repaso.core.cohort.signal import CohortFailure, evaluate, signal_claim_key
from repaso.core.harness.budgets import BoundedAttempts
from repaso.core.harness.calendar import is_scheduled, mask_to_scheduled, outage_days
from repaso.core.harness.clock import local_date
from repaso.core.harness.escalation_triggers import (
    DEFAULT_MIN_ACTIVE_DAYS,
    DEFAULT_SILENT_DAYS,
    engagement_trigger,
    trailing_silent_days,
)
from repaso.core.harness.pause import is_paused, trace_paused
from repaso.core.orchestration.context import CloseRun, Services
from repaso.core.orchestration.nodes import StepNode
from repaso.core.orchestration.outbox import deliver
from repaso.core.orchestration.response_graph import daily_counts, window_days
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.escalation import Escalation
from repaso.schemas.family import Family
from repaso.schemas.mastery import MasteryLevel
from repaso.schemas.operation import OperationRecord
from repaso.tools.grade_log import effective_grades

COHORT_WINDOW_DAYS = 7
REWORK_MAX = 2
RETIREMENT_MIN_ATTEMPTS = 8
SIGNAL_OWNER = "quality-graph"


def _all_grades(services: Services) -> list:
    grades = []
    for family in services.store.list_families():
        for student in services.store.list_students(family.id):
            grades.extend(effective_grades(services.grade_log.by_student(student.id)))
    return grades


def _cohort_totals(services: Services) -> dict[date, int]:
    return Counter(
        local_date(grade.responded_at or grade.graded_at) for grade in _all_grades(services)
    )


def _delivers_today(services: Services, family: Family, today: date, step: str) -> bool:
    if is_paused(family):
        trace_paused(services.telemetry, family, step)
        return False
    return is_scheduled(today, family.rest_weekdays, services.settings.holiday_dates)


def _closed_days(services: Services, family: Family, totals: dict[date, int]) -> list[date]:
    open_days = [
        day
        for day in window_days(services)
        if is_scheduled(day, family.rest_weekdays, services.settings.holiday_dates)
    ]
    return [*services.settings.holiday_dates, *outage_days(totals, open_days)]


def build_quality_graph(services: Services, run: CloseRun):
    async def verify() -> None:
        today = services.clock.today()
        sessions, quarantines, escalations = [], [], []
        for family in services.store.list_families():
            quarantines.extend(services.store.list_pending_quarantine(family.id))
            escalations.extend(services.store.list_pending_escalations(family.id))
            for student in services.store.list_students(family.id):
                session = services.store.get_session_by_date(student.id, today)
                if session is not None:
                    sessions.append(session)
        grades = [
            g for g in _all_grades(services) if local_date(g.responded_at or g.graded_at) == today
        ]
        run.report = verify_daily(
            today, sessions, grades, [], quarantines, escalations, BoundedAttempts(REWORK_MAX)
        )

    async def cohort() -> None:
        today = services.clock.today()
        failures, families_by_section = [], {}
        for family in services.store.list_families():
            if not _delivers_today(services, family, today, "close_cohort"):
                continue
            for student in services.store.list_students(family.id):
                families_by_section.setdefault(student.cohort_id or student.section_key, set()).add(
                    family.id
                )
                for mastery in services.store.list_mastery(student.id):
                    established = mastery.attempts >= services.settings.escalation_min_samples
                    if mastery.level is MasteryLevel.STRUGGLING and established:
                        failures.append(
                            CohortFailure(
                                family_id=family.id,
                                section_key=student.cohort_id or student.section_key,
                                competency_id=mastery.competency_id,
                                failed_on=today,
                            )
                        )
        fired = evaluate(failures, services.settings.cohort_min_families, COHORT_WINDOW_DAYS, today)
        for key in fired:
            # One parent receives the aggregate note, avoiding multiple copies
            # reaching the teacher. The class code is namespaced by invitation.
            recipients = sorted(families_by_section.get(key.section_key, set()))
            if not recipients:
                continue
            family = services.store.get_family(recipients[0])
            notice_key = signal_claim_key(key, today)
            existing = services.store.get_record(family.id, f"notice#{notice_key}")
            if existing and existing.payload.get("delivered"):
                continue
            if existing:
                escalation = Escalation.model_validate(existing.payload["escalation"])
            else:
                competency = services.retriever.get_competency(key.competency_id)
                count = len(
                    {
                        f.family_id
                        for f in failures
                        if f.section_key == key.section_key and f.competency_id == key.competency_id
                    }
                )
                section_label = next(
                    (
                        s.section_key
                        for s in services.store.list_students(family.id)
                        if (s.cohort_id or s.section_key) == key.section_key
                    ),
                    "sección",
                )
                escalation = await compose_cohort(
                    section_label,
                    competency,
                    count,
                    family.lang,
                    services.model(ModelRole.GENERATE),
                    services.clock.now(),
                    family.id,
                )
            _deliver_notice(services, run, family, notice_key, escalation)
            run.cohort_fired.append(f"{key.section_key}#{key.competency_id}")

    async def engagement() -> None:
        today = services.clock.today()
        week = today.isocalendar()
        days = window_days(services)
        totals = _cohort_totals(services)
        for family in services.store.list_families():
            if not _delivers_today(services, family, today, "close_engagement"):
                continue
            closed = _closed_days(services, family, totals)
            for student in services.store.list_students(family.id):
                counts = mask_to_scheduled(
                    days, daily_counts(services, student.id), family.rest_weekdays, closed
                )
                if not engagement_trigger(counts, DEFAULT_MIN_ACTIVE_DAYS, DEFAULT_SILENT_DAYS):
                    continue
                claim_key = f"engage#{student.id}#{week.year}-W{week.week}"
                existing = services.store.get_record(family.id, f"notice#{claim_key}")
                if existing and existing.payload.get("delivered"):
                    continue
                escalation = compose_engagement(
                    family.id,
                    student.id,
                    student.alias,
                    trailing_silent_days(counts),
                    family.lang,
                    services.clock.now(),
                )
                if existing:
                    escalation = Escalation.model_validate(existing.payload["escalation"])
                _deliver_notice(services, run, family, claim_key, escalation)

    async def optimize() -> None:
        grades = _all_grades(services)
        item_ids = {grade.item_id for grade in grades}
        items = [services.store.get_item(item_id) for item_id in sorted(item_ids)]
        items = [item for item in items if item is not None]
        for item_id in retirement_candidates(items, grades, RETIREMENT_MIN_ATTEMPTS):
            item = services.store.get_item(item_id)
            services.store.put_item(retire(item))
            run.retired_items.append(item_id)

    builder = GraphBuilder()
    builder.add_node(StepNode("verify", verify, services.telemetry, "close"), "verify")
    builder.add_node(StepNode("engagement", engagement, services.telemetry, "close"), "engagement")
    builder.add_node(StepNode("cohort", cohort, services.telemetry, "close"), "cohort")
    builder.add_node(StepNode("optimize", optimize, services.telemetry, "close"), "optimize")
    builder.add_edge("verify", "engagement")
    builder.add_edge("engagement", "cohort")
    builder.add_edge("cohort", "optimize")
    builder.set_entry_point("verify")
    builder.set_max_node_executions(6)
    return builder.build()


def _deliver_notice(services, run, family, key, escalation):
    record = services.store.get_record(family.id, f"notice#{key}")
    if record is None:
        record = OperationRecord(
            scope=family.id,
            key=f"notice#{key}",
            payload={
                "escalation": escalation.model_dump(mode="json"),
                "delivered": False,
            },
        )
        services.store.put_record(record)
    services.store.put_escalation(escalation)
    message = OutboundMessage(
        channel=family.channel,
        chat_ref=family.chat_ref,
        text=escalation.summary
        + ("\n\n" + escalation.drafted_note if escalation.drafted_note else ""),
    )
    deliver(services, [message], f"notice#{key}", family.id)
    record.payload["delivered"] = True
    services.store.put_record(record)
    run.outbound.append(message)
