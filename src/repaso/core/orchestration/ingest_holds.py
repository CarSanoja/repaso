from repaso.core.orchestration.context import IngestRun, Services
from repaso.i18n.catalog import msg
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.material import MaterialStatus
from repaso.schemas.review import QuarantineItem, QuarantineKind
from repaso.tools.guardrails import ScreenVerdict

QUOTE_LENGTH = 200
SCREEN_UNAVAILABLE = "screen_unavailable"
QUARANTINED = "quarantined"
SCREENED_UNSAFE = "screened_unsafe"
UNREADABLE_REPLY = "material_unreadable"
INJECTION_REASON = "injection"
PARSE_REPLIES = {"blurry_photo": "rephoto_request"}


def parse_reply(reason: str) -> str:
    return PARSE_REPLIES.get(reason, UNREADABLE_REPLY)


def held_kind(verdict: ScreenVerdict) -> QuarantineKind:
    named = any(INJECTION_REASON in reason.casefold() for reason in verdict.reasons)
    return QuarantineKind.INJECTION_ATTEMPT if named else QuarantineKind.UNSAFE_CONTENT


def say(run: IngestRun, key: str, **kwargs) -> None:
    run.outbound.append(
        OutboundMessage(
            channel=run.family.channel,
            chat_ref=run.family.chat_ref,
            text=msg(key, run.family.lang, **kwargs),
        )
    )


def _stop(run: IngestRun, services: Services, terminal: str, reason: str) -> None:
    run.terminal = terminal
    run.material = run.material.model_copy(
        update={"status": MaterialStatus.QUARANTINED, "rejection_reason": reason}
    )
    services.store.put_material(run.material)


def hold_unscreened(run: IngestRun, services: Services) -> None:
    _stop(run, services, SCREEN_UNAVAILABLE, SCREEN_UNAVAILABLE)
    say(run, "material_interrupted")


def hold_screened(run: IngestRun, services: Services, verdict: ScreenVerdict) -> None:
    _stop(run, services, QUARANTINED, SCREENED_UNSAFE)
    services.store.put_quarantine(
        QuarantineItem(
            id=f"quar-{run.material.id}",
            kind=held_kind(verdict),
            family_id=run.family.id,
            evidence=EvidenceSpan(
                quote=(run.material.parsed_text or "")[:QUOTE_LENGTH],
                source_ref=f"material:{run.material.id}",
            ),
            payload={"reasons": verdict.reasons},
            created_at=services.clock.now(),
        )
    )
    say(run, "material_held")
