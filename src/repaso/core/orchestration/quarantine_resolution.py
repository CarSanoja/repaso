from pydantic import ValidationError

from repaso.core.orchestration.answer_outcome import record_answer_outcome
from repaso.core.orchestration.context import QuarantineRun, Services
from repaso.core.orchestration.runner import deliver_outbound
from repaso.i18n import msg
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.family import Family
from repaso.schemas.review import HeldAnswer, QuarantineItem, QuarantineKind, QuarantineStatus

ALREADY_RESOLVED = "already_resolved"
NOTHING_TO_RELEASE = "nothing_to_release"
ACK_KEYS = {
    QuarantineStatus.APPROVED: "quarantine_ack_approved",
    QuarantineStatus.REJECTED: "quarantine_ack_rejected",
}


def held_answer(quarantine: QuarantineItem) -> HeldAnswer | None:
    if quarantine.kind is not QuarantineKind.LOW_CONFIDENCE_GRADE:
        return None
    try:
        return HeldAnswer.model_validate(quarantine.payload)
    except ValidationError:
        return None


def release(services: Services, quarantine: QuarantineItem) -> str | None:
    held = held_answer(quarantine)
    if held is None:
        return None
    item = services.store.get_item(held.item_id)
    if item is None:
        return None
    record_answer_outcome(services, held.student_id, item, True, held.latency_seconds)
    return item.id


def acknowledge(services: Services, run: QuarantineRun) -> None:
    run.outbound.append(
        OutboundMessage(
            channel=run.family.channel,
            chat_ref=run.family.chat_ref,
            text=msg(ACK_KEYS[run.quarantine.status], run.family.lang),
        )
    )
    deliver_outbound(services, run.outbound)


def resolve_quarantine(
    services: Services, family: Family, quarantine: QuarantineItem, accepted: bool
) -> QuarantineRun:
    run = QuarantineRun(family=family, quarantine=quarantine)
    if quarantine.status is not QuarantineStatus.PENDING:
        run.terminal = ALREADY_RESOLVED
        acknowledge(services, run)
        return run
    decided = QuarantineStatus.APPROVED if accepted else QuarantineStatus.REJECTED
    run.quarantine = quarantine.model_copy(
        update={"status": decided, "resolved_at": services.clock.now()}
    )
    services.store.put_quarantine(run.quarantine)
    if accepted:
        run.released_item_id = release(services, quarantine)
        if run.released_item_id is None:
            run.terminal = NOTHING_TO_RELEASE
    acknowledge(services, run)
    return run
