"""What a family is told when an ingest step ends the run, and what it leaves behind."""

from repaso.core.orchestration.context import IngestRun, Services
from repaso.i18n.catalog import msg
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.material import MaterialStatus
from repaso.schemas.review import QuarantineItem, QuarantineKind

QUOTE_LENGTH = 200


def say(run: IngestRun, key: str, **kwargs) -> None:
    text = msg(key, run.family.lang, **kwargs)
    run.outbound.append(
        OutboundMessage(channel=run.family.channel, chat_ref=run.family.chat_ref, text=text)
    )


def unavailable(run: IngestRun, terminal: str, key: str) -> None:
    run.terminal = terminal
    say(run, key)


def quarantine(services: Services, run: IngestRun, reasons: list[str]) -> None:
    run.terminal = "quarantined"
    run.material = run.material.model_copy(
        update={"status": MaterialStatus.QUARANTINED, "rejection_reason": "screened_unsafe"}
    )
    services.store.put_material(run.material)
    services.store.put_quarantine(
        QuarantineItem(
            id=f"quar-{run.material.id}",
            kind=QuarantineKind.INJECTION_ATTEMPT,
            family_id=run.family.id,
            evidence=EvidenceSpan(
                quote=(run.material.parsed_text or "")[:QUOTE_LENGTH],
                source_ref=f"material:{run.material.id}",
            ),
            payload={"reasons": reasons},
            created_at=services.clock.now(),
        )
    )
    say(run, "material_rejected", subject="matemática")
