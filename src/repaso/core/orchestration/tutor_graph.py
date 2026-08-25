from uuid import uuid4

from strands.multiagent.graph import GraphBuilder

from repaso.agents.capsule_composer import compose_capsule
from repaso.agents.session_planner import build_session, plan_items
from repaso.config.models import ModelRole
from repaso.core.orchestration.context import Services, TutorRun
from repaso.core.orchestration.nodes import StepNode
from repaso.schemas.item import ItemStatus
from repaso.schemas.session import SessionStatus


def active_items(services: Services, run: TutorRun) -> list:
    items = []
    for competency in services.retriever.list_competencies(run.student.grade, "math"):
        items.extend(services.store.list_items_by_competency(competency.id, ItemStatus.ACTIVE))
    return items


def build_session_graph(services: Services, run: TutorRun):
    async def plan() -> None:
        today = services.clock.today()
        if services.store.get_session_by_date(run.student.id, today) is not None:
            run.terminal = "already_planned"
            return
        spaced = services.store.list_spaced(run.student.id)
        mastery = services.store.list_mastery(run.student.id)
        item_ids = plan_items(spaced, mastery, active_items(services, run), today)
        if not item_ids:
            run.terminal = "nothing_due"
            return
        run.session = build_session(run.student.id, today, item_ids, uuid4().hex)
        run.items = [services.store.get_item(item_id) for item_id in item_ids]
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
                "status": SessionStatus.DELIVERED,
                "delivered_at": services.clock.now(),
            }
        )
        services.store.put_session(run.session)
        stamped = message.model_copy(
            update={"channel": run.family.channel, "chat_ref": run.family.chat_ref}
        )
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
