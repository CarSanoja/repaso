from strands.multiagent.graph import GraphBuilder

from repaso.agents.answerability_probe import combine, probe_blind
from repaso.agents.competency_mapper import map_material
from repaso.agents.intake_screener import screen_text
from repaso.agents.item_critic import critique
from repaso.agents.item_generator import generate_items
from repaso.agents.material_parser import parse_material
from repaso.config.models import ModelRole
from repaso.core.harness.legibility import DEFAULT_MIN_CONFIDENCE
from repaso.core.orchestration.context import IngestRun, Services
from repaso.core.orchestration.nodes import StepNode
from repaso.i18n.catalog import msg
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.item import ItemStatus
from repaso.schemas.material import MaterialStatus
from repaso.schemas.review import QuarantineItem, QuarantineKind

ITEMS_PER_MATERIAL = 6
STAGE_OWNER = "ingest-graph"


def _say(run: IngestRun, key: str, **kwargs) -> None:
    text = msg(key, run.family.lang, **kwargs)
    run.outbound.append(
        OutboundMessage(channel=run.family.channel, chat_ref=run.family.chat_ref, text=text)
    )


def build_ingest_graph(services: Services, run: IngestRun):
    settings = services.settings

    async def parse() -> None:
        run.material = parse_material(
            run.material,
            run.data,
            services.extractor,
            settings.legibility_blur_floor,
            DEFAULT_MIN_CONFIDENCE,
        )
        services.store.put_material(run.material)
        if run.material.status is not MaterialStatus.PARSED:
            run.terminal = run.material.rejection_reason or "unparsed"
            key = "rephoto_request" if run.terminal == "blurry_photo" else "material_thin"
            _say(run, key)

    async def screen() -> None:
        verdict = await screen_text(
            run.material.parsed_text or "", services.screener, services.model(ModelRole.CLASSIFY)
        )
        run.screen = verdict
        if verdict.safe:
            run.material = run.material.model_copy(update={"status": MaterialStatus.SCREENED})
            services.store.put_material(run.material)
            return
        run.terminal = "quarantined"
        run.material = run.material.model_copy(
            update={"status": MaterialStatus.QUARANTINED, "rejection_reason": "screened_unsafe"}
        )
        services.store.put_material(run.material)
        quote = (run.material.parsed_text or "")[:200]
        services.store.put_quarantine(
            QuarantineItem(
                id=f"quar-{run.material.id}",
                kind=QuarantineKind.INJECTION_ATTEMPT,
                family_id=run.family.id,
                evidence=EvidenceSpan(quote=quote, source_ref=f"material:{run.material.id}"),
                payload={"reasons": verdict.reasons},
                created_at=services.clock.now(),
            )
        )
        _say(run, "material_rejected", subject="matemática")

    async def map_() -> None:
        run.matches = await map_material(
            run.material.parsed_text or "",
            run.student.grade,
            "math",
            services.retriever,
            services.model(ModelRole.STRUCTURED),
        )
        if not run.matches:
            run.terminal = "no_match"
            _say(run, "material_rejected", subject="matemática")
            return
        run.competency = services.retriever.get_competency(run.matches[0].competency_id)
        run.material = run.material.model_copy(update={"status": MaterialStatus.MAPPED})
        services.store.put_material(run.material)

    async def generate() -> None:
        stage = f"stage#{run.material.id}#generate"
        if services.store.claim(stage, STAGE_OWNER):
            run.generated = await generate_items(
                run.material.parsed_text or "",
                run.competency,
                ITEMS_PER_MATERIAL,
                run.student.grade,
                services.model(ModelRole.GENERATE),
                services.clock.now(),
                lang=run.family.lang,
            )
            for item in run.generated:
                services.store.put_item(item)
        else:
            run.generated = services.store.list_items_by_competency(
                run.competency.id, ItemStatus.CANDIDATE
            ) or services.store.list_items_by_competency(run.competency.id, ItemStatus.ACTIVE)
        if not run.generated:
            run.terminal = "thin_material"
            _say(run, "material_thin")

    async def validate() -> None:
        stage = f"stage#{run.material.id}#validate"
        if services.store.claim(stage, STAGE_OWNER):
            judge = services.model(ModelRole.JUDGE)
            probe = services.model(ModelRole.PROBE)
            source = run.material.parsed_text or ""
            for item in run.generated:
                verdict = await critique(item, source, run.student.grade, judge)
                final = combine(verdict, await probe_blind(item, probe))
                run.verdicts.append(final)
                status = ItemStatus.ACTIVE if final.accepted else ItemStatus.REJECTED
                updated = item.model_copy(update={"status": status})
                services.store.put_item(updated)
                if final.accepted:
                    run.kept.append(updated)
        else:
            run.kept = services.store.list_items_by_competency(
                run.competency.id, ItemStatus.ACTIVE
            )
        if not run.kept:
            run.terminal = "all_rejected"
            _say(run, "material_unusable")
            return
        _say(
            run,
            "material_ready",
            item_count=len(run.kept),
            competencies=run.competency.name,
        )

    def alive(_state) -> bool:
        return run.terminal is None

    builder = GraphBuilder()
    builder.add_node(StepNode("parse", parse, services.telemetry, "ingest"), "parse")
    builder.add_node(StepNode("screen", screen, services.telemetry, "ingest"), "screen")
    builder.add_node(StepNode("map", map_, services.telemetry, "ingest"), "map")
    builder.add_node(StepNode("generate", generate, services.telemetry, "ingest"), "generate")
    builder.add_node(StepNode("validate", validate, services.telemetry, "ingest"), "validate")
    builder.add_edge("parse", "screen", condition=alive)
    builder.add_edge("screen", "map", condition=alive)
    builder.add_edge("map", "generate", condition=alive)
    builder.add_edge("generate", "validate", condition=alive)
    builder.set_entry_point("parse")
    builder.set_max_node_executions(8)
    return builder.build()


def kept_item_ids(run: IngestRun) -> list[str]:
    return [item.id for item in run.kept]


