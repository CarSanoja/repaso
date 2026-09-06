from datetime import datetime

from pydantic import ValidationError

from repaso.core.orchestration.answer_outcome import record_answer_outcome
from repaso.core.orchestration.context import QuarantineRun, Services
from repaso.core.orchestration.runner import deliver_outbound
from repaso.i18n import msg
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.family import Family
from repaso.schemas.grading import GradedBy, GradeResult
from repaso.schemas.operation import OperationRecord
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


def release(
    services: Services,
    quarantine: QuarantineItem,
    accepted: bool = True,
    decided_at: datetime | None = None,
) -> str | None:
    held = held_answer(quarantine)
    if held is None:
        return None
    item = services.store.get_item(held.item_id)
    if item is None:
        return None
    student = services.store.get_student(held.student_id)
    if student is None or student.family_id != quarantine.family_id:
        raise ValueError("held answer does not belong to the family")
    outcome_id = f"human:{quarantine.id}"
    services.grade_log.append(
        GradeResult(
            id=outcome_id,
            supersedes=held.grade_id,
            student_id=held.student_id,
            item_id=item.id,
            correct=accepted,
            confidence=1.0,
            graded_by=GradedBy.HUMAN,
            responded_at=quarantine.created_at,
            evidence=quarantine.evidence,
            latency_seconds=held.latency_seconds,
            feedback="",
            graded_at=decided_at or services.clock.now(),
        )
    )
    record_answer_outcome(
        services, held.student_id, item, accepted, held.latency_seconds, outcome_id=outcome_id
    )
    return item.id


def acknowledge(services: Services, run: QuarantineRun) -> None:
    run.outbound.append(
        OutboundMessage(
            channel=run.family.channel,
            chat_ref=run.family.chat_ref,
            text=msg(ACK_KEYS[run.quarantine.status], run.family.lang),
        )
    )
    deliver_outbound(services, run.outbound, f"quarantine#{run.quarantine.id}", run.family.id)


def resolve_quarantine(
    services: Services, family: Family, quarantine: QuarantineItem, accepted: bool
) -> QuarantineRun:
    run = QuarantineRun(family=family, quarantine=quarantine)
    if quarantine.family_id != family.id:
        raise ValueError("quarantine does not belong to family")
    quarantine = services.store.get_quarantine(family.id, quarantine.id) or quarantine
    run.quarantine = quarantine
    if quarantine.status is not QuarantineStatus.PENDING:
        run.terminal = ALREADY_RESOLVED
        acknowledge(services, run)
        return run
    key = f"quarantine-decision#{quarantine.id}"
    choice = services.store.get_record(family.id, key)
    if choice is None:
        choice = OperationRecord(
            scope=family.id,
            key=key,
            payload={
                "accepted": accepted,
                "at": services.clock.now().isoformat(),
            },
        )
        services.store.put_record(choice)
    accepted = choice.payload["accepted"]
    at = datetime.fromisoformat(choice.payload["at"])
    decided = QuarantineStatus.APPROVED if accepted else QuarantineStatus.REJECTED
    run.released_item_id = release(services, quarantine, accepted, at)
    if run.released_item_id is None:
        run.terminal = NOTHING_TO_RELEASE
    run.quarantine = quarantine.model_copy(update={"status": decided, "resolved_at": at})
    services.store.put_quarantine(run.quarantine)
    acknowledge(services, run)
    return run
