import base64
from collections.abc import Awaitable, Callable
from typing import Any

from repaso.core.orchestration.context import Services
from repaso.core.orchestration.runner import (
    handle_answer,
    handle_material,
    run_daily_close,
    start_daily_session,
)
from repaso.runtime.errors import ErrorCode, InvocationError
from repaso.runtime.payload import (
    AnswerPayload,
    InvocationRequest,
    MaterialPayload,
    StudentScoped,
    validate,
)
from repaso.runtime.summaries import close_summary, ingest_summary, tutor_summary
from repaso.schemas.common import FamilyId, StudentId
from repaso.schemas.events import EventKind
from repaso.schemas.family import Family
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


async def on_material_uploaded(
    services: Services, request: InvocationRequest
) -> dict[str, Any]:
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


async def on_daily_session_due(
    services: Services, request: InvocationRequest
) -> dict[str, Any]:
    data = validate(StudentScoped, request.payload)
    family = resolve_family(services, request)
    student = resolve_student(services, family, data.student_id)
    return tutor_summary(await start_daily_session(services, family, student))


async def on_response_received(
    services: Services, request: InvocationRequest
) -> dict[str, Any]:
    data = validate(AnswerPayload, request.payload)
    family = resolve_family(services, request)
    student = resolve_student(services, family, data.student_id)
    run = await handle_answer(services, family, student, data.text, data.latency_seconds)
    return tutor_summary(run)


async def on_daily_close(services: Services, request: InvocationRequest) -> dict[str, Any]:
    return close_summary(await run_daily_close(services))


HANDLERS: dict[EventKind, Handler] = {
    EventKind.MATERIAL_UPLOADED: on_material_uploaded,
    EventKind.DAILY_SESSION_DUE: on_daily_session_due,
    EventKind.RESPONSE_RECEIVED: on_response_received,
    EventKind.DAILY_CLOSE: on_daily_close,
}
