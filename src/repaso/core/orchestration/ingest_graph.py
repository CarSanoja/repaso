from hashlib import sha256

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
from repaso.i18n.competencies import competency_label
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.competency import CompetencyMatch
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.item import Item, ItemStatus, ItemVerdict
from repaso.schemas.material import Material, MaterialStatus
from repaso.schemas.operation import OperationRecord
from repaso.schemas.review import QuarantineItem, QuarantineKind
from repaso.tools.guardrails import ScreenVerdict

ITEMS_PER_MATERIAL = 6
STAGE_OWNER = "ingest-graph"


def _say(run: IngestRun, key: str, **kwargs) -> None:
    text = msg(key, run.family.lang, **kwargs)
    run.outbound.append(
        OutboundMessage(channel=run.family.channel, chat_ref=run.family.chat_ref, text=text)
    )


def build_ingest_graph(services: Services, run: IngestRun):
    settings = services.settings
    journal = services.store.get_record(run.family.id, f"ingest#{run.material.id}")
    if journal is None:
        journal = OperationRecord(scope=run.family.id, key=f"ingest#{run.material.id}", payload={})
    memo = journal.payload

    def save(key, value):
        memo[key] = value
        services.store.put_record(journal)

    async def parse() -> None:
        try:
            if "parsed" in memo:
                run.material = Material.model_validate(memo["parsed"])
            else:
                run.material = parse_material(
                    run.material,
                    run.data,
                    services.extractor,
                    settings.legibility_blur_floor,
                    DEFAULT_MIN_CONFIDENCE,
                )
                save("parsed", run.material.model_dump(mode="json"))
        except ValueError:
            run.terminal = "unsupported_material"
            run.material = run.material.model_copy(
                update={
                    "status": MaterialStatus.ILLEGIBLE,
                    "rejection_reason": run.terminal,
                }
            )
            services.store.put_material(run.material)
            _say(run, "supported_material")
            return
        services.store.put_material(run.material)
        if run.material.status is not MaterialStatus.PARSED:
            run.terminal = run.material.rejection_reason or "unparsed"
            key = "rephoto_request" if run.terminal == "blurry_photo" else "material_thin"
            _say(run, key)

    async def screen() -> None:
        if "screen" in memo:
            verdict = ScreenVerdict.model_validate(memo["screen"])
        else:
            verdict = await screen_text(
                run.material.parsed_text or "",
                services.screener,
                services.model(ModelRole.CLASSIFY),
            )
            save("screen", verdict.model_dump(mode="json"))
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
        if "matches" in memo:
            run.matches = [CompetencyMatch.model_validate(m) for m in memo["matches"]]
        else:
            run.matches = await map_material(
                run.material.parsed_text or "",
                run.student.grade,
                "math",
                services.retriever,
                services.model(ModelRole.STRUCTURED),
            )
            save("matches", [m.model_dump(mode="json") for m in run.matches])
        if not run.matches:
            run.terminal = "no_match"
            _say(run, "material_rejected", subject="matemática")
            return
        run.competency = services.retriever.get_competency(run.matches[0].competency_id)
        run.material = run.material.model_copy(update={"status": MaterialStatus.MAPPED})
        services.store.put_material(run.material)

    async def generate() -> None:
        if "generated" not in memo:
            drafts = await generate_items(
                run.material.parsed_text or "",
                run.competency,
                ITEMS_PER_MATERIAL,
                run.student.grade,
                services.model(ModelRole.GENERATE),
                services.clock.now(),
                lang=run.family.lang,
            )
            items = [
                item.model_copy(
                    update={
                        "id": sha256(
                            f"{run.family.id}:{run.material.id}:{item.id}".encode()
                        ).hexdigest()[:32],
                        "family_id": run.family.id,
                        "material_id": run.material.id,
                    }
                )
                for item in drafts
            ]
            save("generated", [i.model_dump(mode="json") for i in items])
        run.generated = [Item.model_validate(i) for i in memo["generated"]]
        for item in run.generated:
            if services.store.get_item(item.id) is None:
                services.store.put_item(item)
        if not run.generated:
            run.terminal = "thin_material"
            _say(run, "material_thin")

    async def validate() -> None:
        judge = services.model(ModelRole.JUDGE)
        probe = services.model(ModelRole.PROBE)
        source = run.material.parsed_text or ""
        for item in run.generated:
            verdict_key = f"verdict#{item.id}"
            if verdict_key in memo:
                final = ItemVerdict.model_validate(memo[verdict_key])
            else:
                verdict = await critique(item, source, run.student.grade, judge)
                final = combine(verdict, await probe_blind(item, probe))
                save(verdict_key, final.model_dump(mode="json"))
            run.verdicts.append(final)
            status = ItemStatus.ACTIVE if final.accepted else ItemStatus.REJECTED
            updated = item.model_copy(update={"status": status})
            services.store.put_item(updated)
            if final.accepted:
                run.kept.append(updated)
        if not run.kept:
            run.terminal = "all_rejected"
            run.material.status = MaterialStatus.REJECTED
            run.material.rejection_reason = "No generated item passed review."
            services.store.put_material(run.material)
            _say(run, "material_unusable")
            return
        _say(
            run,
            "material_ready",
            item_count=len(run.kept),
            competencies=competency_label(run.competency, run.family.lang),
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
