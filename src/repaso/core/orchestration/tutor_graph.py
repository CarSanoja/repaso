from datetime import date, timedelta
from uuid import uuid4

from strands.multiagent.graph import GraphBuilder

from repaso.agents.capsule_composer import compose_capsule
from repaso.agents.session_planner import (
    DAILY_ITEM_LIMIT,
    UNKNOWN_EMA,
    build_session,
    plan_items,
)
from repaso.config.models import ModelRole
from repaso.core.bank.sources import bank_items
from repaso.core.orchestration.adaptations import open_variants, select_adapted
from repaso.core.orchestration.context import Services, TutorRun
from repaso.core.orchestration.nodes import StepNode
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.mastery import MasteryState
from repaso.schemas.schedule import ExamDate
from repaso.schemas.session import SessionStatus

EXAM_HORIZON_DAYS = 7
EXAM_ITEM_CAP = 4


def active_items(services: Services, run: TutorRun) -> list:
    return bank_items(services, run.family, run.student.grade)


def exam_is_near(exams: list[ExamDate], today: date) -> bool:
    horizon = today + timedelta(days=EXAM_HORIZON_DAYS)
    return any(today <= exam.exam_date <= horizon for exam in exams)


def weakest_first(items: list, mastery: list[MasteryState]) -> list:
    ema = {state.competency_id: state.ema_accuracy for state in mastery}
    return sorted(items, key=lambda item: (ema.get(item.competency_id, UNKNOWN_EMA), item.id))


def build_session_graph(services: Services, run: TutorRun):
    async def plan() -> None:
        today = services.clock.today()
        existing = services.store.get_session_by_date(run.student.id, today)
        if existing is not None:
            if existing.status is not SessionStatus.PLANNED:
                run.terminal = "already_planned"
                return
            run.session = existing
            if existing.delivery_message:
                run.outbound.append(OutboundMessage.model_validate(existing.delivery_message))
                run.terminal = "delivery_resumed"
                return
            run.items = [services.store.get_item(i) for i in existing.planned_item_ids]
            if run.items and all(run.items):
                run.competency = services.retriever.get_competency(run.items[0].competency_id)
                return
        available, adaptive_limit = select_adapted(services, run, active_items(services, run))
        allowed = {item.id for item in available}
        spaced = [s for s in services.store.list_spaced(run.student.id) if s.item_id in allowed]
        mastery = services.store.list_mastery(run.student.id)
        urgent = exam_is_near(services.store.list_exam_dates(run.student.id), today)
        limit = min(DAILY_ITEM_LIMIT + 1, EXAM_ITEM_CAP) if urgent else DAILY_ITEM_LIMIT
        limit = min(limit, adaptive_limit)
        item_ids = plan_items(spaced, mastery, available, today, limit)
        if not item_ids:
            run.terminal = "nothing_due"
            return
        planned = [services.store.get_item(item_id) for item_id in item_ids]
        run.items = weakest_first(planned, mastery) if urgent else planned
        run.items = open_variants(services, run, run.items)
        run.session = build_session(
            run.student.id, today, [item.id for item in run.items], uuid4().hex
        )
        run.competency = services.retriever.get_competency(run.items[0].competency_id)
        services.store.put_session(run.session)

    async def compose() -> None:
        capsule, message = await compose_capsule(
            run.session,
            run.items,
            run.competency,
            run.student.alias,
            run.family.lang,
            services.model(ModelRole.GENERATE),
        )
        run.session = run.session.model_copy(
            update={
                "capsule": capsule,
                "status": SessionStatus.PLANNED,
            }
        )
        stamped = message.model_copy(
            update={"channel": run.family.channel, "chat_ref": run.family.chat_ref}
        )
        run.session = run.session.model_copy(
            update={"delivery_message": stamped.model_dump(mode="json")}
        )
        services.store.put_session(run.session)
        run.outbound.append(stamped)

    def alive(_state) -> bool:
        return run.terminal is None

    builder = GraphBuilder()
    builder.add_node(StepNode("plan", plan, services.telemetry, "session"), "plan")
    builder.add_node(StepNode("compose", compose, services.telemetry, "session"), "compose")
    builder.add_edge("plan", "compose", condition=alive)
    builder.set_entry_point("plan")
    builder.set_max_node_executions(4)
    return builder.build()
