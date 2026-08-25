from strands.multiagent.graph import GraphBuilder

from repaso.agents.escalation_composer import compose_cohort, compose_engagement
from repaso.agents.goal_verifier import verify_daily
from repaso.agents.item_optimizer import retire, retirement_candidates
from repaso.config.models import ModelRole
from repaso.core.cohort.signal import CohortFailure, evaluate, signal_claim_key
from repaso.core.harness.budgets import BoundedAttempts
from repaso.core.harness.escalation_triggers import (
    DEFAULT_MIN_ACTIVE_DAYS,
    DEFAULT_SILENT_DAYS,
    engagement_trigger,
    trailing_silent_days,
)
from repaso.core.orchestration.context import CloseRun, Services
from repaso.core.orchestration.nodes import StepNode
from repaso.core.orchestration.response_graph import daily_counts
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.mastery import MasteryLevel

COHORT_WINDOW_DAYS = 7
REWORK_MAX = 2
RETIREMENT_MIN_ATTEMPTS = 8
SIGNAL_OWNER = "quality-graph"


def _all_grades(services: Services) -> list:
    grades = []
    for family in services.store.list_families():
        for student in services.store.list_students(family.id):
            grades.extend(services.grade_log.by_student(student.id))
    return grades


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
        grades = [g for g in _all_grades(services) if g.graded_at.date() == today]
        run.report = verify_daily(
            today, sessions, grades, [], quarantines, escalations, BoundedAttempts(REWORK_MAX)
        )

    async def cohort() -> None:
        today = services.clock.today()
        failures, families_by_section = [], {}
        for family in services.store.list_families():
            for student in services.store.list_students(family.id):
                families_by_section.setdefault(student.section_key, set()).add(family.id)
                for mastery in services.store.list_mastery(student.id):
                    established = mastery.attempts >= services.settings.escalation_min_samples
                    if mastery.level is MasteryLevel.STRUGGLING and established:
                        failures.append(
                            CohortFailure(
                                family_id=family.id,
                                section_key=student.section_key,
                                competency_id=mastery.competency_id,
                                failed_on=today,
                            )
                        )
        fired = evaluate(
            failures, services.settings.cohort_min_families, COHORT_WINDOW_DAYS, today
        )
        for key in fired:
            if not services.store.claim(signal_claim_key(key, today), SIGNAL_OWNER):
                continue
            run.cohort_fired.append(f"{key.section_key}#{key.competency_id}")
            competency = services.retriever.get_competency(key.competency_id)
            count = len(
                {f.family_id for f in failures
                 if f.section_key == key.section_key
                 and f.competency_id == key.competency_id}
            )
            for family_id in sorted(families_by_section.get(key.section_key, set())):
                family = services.store.get_family(family_id)
                escalation = await compose_cohort(
                    key.section_key, competency, count, family.lang,
                    services.model(ModelRole.GENERATE), services.clock.now(), family.id,
                )
                services.store.put_escalation(escalation)
                run.outbound.append(
                    OutboundMessage(
                        channel=family.channel, chat_ref=family.chat_ref,
                        text=escalation.summary
                        + ("\n\n" + escalation.drafted_note if escalation.drafted_note else ""),
                    )
                )

    async def engagement() -> None:
        today = services.clock.today()
        week = today.isocalendar()
        for family in services.store.list_families():
            for student in services.store.list_students(family.id):
                counts = daily_counts(services, student.id)
                if not engagement_trigger(
                    counts, DEFAULT_MIN_ACTIVE_DAYS, DEFAULT_SILENT_DAYS
                ):
                    continue
                claim_key = f"engage#{student.id}#{week.year}-W{week.week}"
                if not services.store.claim(claim_key, SIGNAL_OWNER):
                    continue
                escalation = compose_engagement(
                    family.id, student.id, student.alias,
                    trailing_silent_days(counts), family.lang, services.clock.now(),
                )
                services.store.put_escalation(escalation)
                run.outbound.append(
                    OutboundMessage(
                        channel=family.channel, chat_ref=family.chat_ref,
                        text=escalation.summary,
                    )
                )

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
