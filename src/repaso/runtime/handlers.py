import base64
from collections.abc import Awaitable, Callable
from typing import Any

from repaso.core.orchestration.channel_runner import handle_channel_message
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.quarantine_resolution import resolve_quarantine
from repaso.core.orchestration.runner import (
    handle_answer,
    handle_material,
    record_exam,
    resolve_escalation,
    run_daily_close,
    start_daily_session,
)
from repaso.runtime.errors import ErrorCode, InvocationError
from repaso.runtime.payload import (
    AnswerPayload,
    ChannelMessagePayload,
    EscalationPayload,
    ExamPayload,
    InvocationRequest,
    MaterialPayload,
    QuarantinePayload,
    StudentScoped,
    validate,
)
from repaso.runtime.summaries import (
    channel_summary,
    close_summary,
    escalation_summary,
    exam_summary,
    ingest_summary,
    quarantine_summary,
    tutor_summary,
)
from repaso.schemas.common import EscalationId, FamilyId, StudentId
from repaso.schemas.escalation import Escalation
from repaso.schemas.events import EventKind
from repaso.schemas.family import Family
from repaso.schemas.review import QuarantineItem
from repaso.schemas.student import Student

Handler = Callable[[Services, InvocationRequest], Awaitable[dict[str, Any]]]


def resolve_family(services: Services, request: InvocationRequest) -> Family:
    if not request.family_id:
        raise InvocationError(
            ErrorCode.INVALID_PAYLOAD, f"family_id is required for {request.kind.value}"
        )
    family = services.store.get_family(FamilyId(request.family_id))
    if family is None:
        raise InvocationError(ErrorCode.NOT_FOUND, f"family not found: {request.family_id}")
    return family


def resolve_student(services: Services, family: Family, student_id: str) -> Student:
    student = services.store.get_student(StudentId(student_id))
    if student is None:
        raise InvocationError(ErrorCode.NOT_FOUND, f"student not found: {student_id}")
    if student.family_id != family.id:
        raise InvocationError(
            ErrorCode.NOT_FOUND, f"student {student_id} does not belong to family {family.id}"
        )
    return student


def resolve_escalation_record(services: Services, family: Family, escalation_id: str) -> Escalation:
    escalation = services.store.get_escalation(EscalationId(escalation_id))
    if escalation is None:
        raise InvocationError(ErrorCode.NOT_FOUND, f"escalation not found: {escalation_id}")
    if escalation.family_id != family.id:
        raise InvocationError(
            ErrorCode.NOT_FOUND,
            f"escalation {escalation_id} does not belong to family {family.id}",
        )
    return escalation


def resolve_quarantine_record(
    services: Services, family: Family, quarantine_id: str
) -> QuarantineItem:
    quarantine = services.store.get_quarantine(family.id, quarantine_id)
    if quarantine is None:
        raise InvocationError(ErrorCode.NOT_FOUND, f"quarantine not found: {quarantine_id}")
    return quarantine


def resolve_material_data(services: Services, data: MaterialPayload) -> bytes:
    if data.content_b64:
        try:
            return base64.b64decode(data.content_b64, validate=True)
        except ValueError as error:
            raise InvocationError(
                ErrorCode.INVALID_PAYLOAD, f"content_b64 is not valid base64: {error}"
            ) from error
    try:
        blob = services.media.get(str(data.media_ref))
    except ValueError as error:
        raise InvocationError(ErrorCode.INVALID_PAYLOAD, str(error)) from error
    if blob is None:
        raise InvocationError(ErrorCode.NOT_FOUND, f"media not found: {data.media_ref}")
    return blob


async def on_material_uploaded(services: Services, request: InvocationRequest) -> dict[str, Any]:
    data = validate(MaterialPayload, request.payload)
    family = resolve_family(services, request)
    student = resolve_student(services, family, data.student_id)
    run = await handle_material(
        services,
        family,
        student,
        data.media_kind,
        resolve_material_data(services, data),
        data.material_id,
    )
    return ingest_summary(run)


async def on_daily_session_due(services: Services, request: InvocationRequest) -> dict[str, Any]:
    data = validate(StudentScoped, request.payload)
    family = resolve_family(services, request)
    student = resolve_student(services, family, data.student_id)
    return tutor_summary(await start_daily_session(services, family, student))


async def on_response_received(services: Services, request: InvocationRequest) -> dict[str, Any]:
    data = validate(AnswerPayload, request.payload)
    family = resolve_family(services, request)
    student = resolve_student(services, family, data.student_id)
    run = await handle_answer(
        services,
        family,
        student,
        data.text,
        data.latency_seconds,
        response_id=request.idempotency_key or None,
    )
    return tutor_summary(run)


async def on_daily_close(services: Services, request: InvocationRequest) -> dict[str, Any]:
    from repaso.runtime.recovery import recover_pending

    recovered = await recover_pending(services)
    return close_summary(await run_daily_close(services)) | {"recovery": recovered}


async def on_channel_message(services: Services, request: InvocationRequest) -> dict[str, Any]:
    message = validate(ChannelMessagePayload, request.payload)
    return channel_summary(await handle_channel_message(services, message))


async def on_escalation_resolved(services: Services, request: InvocationRequest) -> dict[str, Any]:
    data = validate(EscalationPayload, request.payload)
    family = resolve_family(services, request)
    escalation = resolve_escalation_record(services, family, data.escalation_id)
    return escalation_summary(resolve_escalation(services, family, escalation, data.option_key))


async def on_quarantine_resolved(services: Services, request: InvocationRequest) -> dict[str, Any]:
    data = validate(QuarantinePayload, request.payload)
    family = resolve_family(services, request)
    quarantine = resolve_quarantine_record(services, family, data.quarantine_id)
    return quarantine_summary(resolve_quarantine(services, family, quarantine, data.accepted))


async def on_exam_announced(services: Services, request: InvocationRequest) -> dict[str, Any]:
    data = validate(ExamPayload, request.payload)
    family = resolve_family(services, request)
    return exam_summary(record_exam(services, family, data.exam_date, data.topic))


HANDLERS: dict[EventKind, Handler] = {
    EventKind.MATERIAL_UPLOADED: on_material_uploaded,
    EventKind.CHANNEL_MESSAGE: on_channel_message,
    EventKind.DAILY_SESSION_DUE: on_daily_session_due,
    EventKind.RESPONSE_RECEIVED: on_response_received,
    EventKind.ESCALATION_RESOLVED: on_escalation_resolved,
    EventKind.QUARANTINE_RESOLVED: on_quarantine_resolved,
    EventKind.EXAM_ANNOUNCED: on_exam_announced,
    EventKind.DAILY_CLOSE: on_daily_close,
}
